"""A web page as a person's browser shows it.

What it is   headless Chrome (Playwright, the system's Google Chrome) loads the page and runs its scripts
             (docs.arduino.cc gives no text to a plain fetch); returns the visible text, a markdown version,
             screenshots of the larger images and the page's code blocks with their line breaks; a browser that
             fails to start is started again.
Used for     reading a tutorial page: its sketch, its text and images for the lesson; and the open_page tool Claude
             uses to read a link itself.
Where        arduino/circuit_lesson.py (render), parts/mcp_server.py (open_page).

Many tutorial sites build their pages with JavaScript (docs.arduino.cc returns no readable text to a plain fetch),
so the page is loaded in headless Chrome (Playwright driving the system's Google Chrome), its scripts run, and what
a reader sees is returned: the visible text of the page, and its larger images (circuit diagrams, schematics).

  page = render("https://docs.arduino.cc/built-in-examples/basics/Blink/")
  page["text"]    visible text
  page["images"]  [(png bytes, alt text)] screenshots of the page's larger images
  page["code"]    the page's code blocks, line breaks kept
"""
import re
import time

MAX_IMAGES = 6
CODE_JS = """() => {
  const out = [];
  for (const ed of document.querySelectorAll('.cm-content'))
    out.push([...ed.querySelectorAll('.cm-line')].map((l) => l.innerText.replace(/\\n$/, '')).join('\\n'));
  for (const pre of document.querySelectorAll('pre'))
    if (!pre.closest('.cm-editor') && pre.innerText.trim()) out.push(pre.innerText);
  return out;
}"""
MIN_SIDE = 150  # smaller images are icons and logos


EXAMPLE = re.compile(r"create\.arduino\.cc/example/builtin/([^/]+)%5C([^/]+)/")
EXAMPLES = "https://raw.githubusercontent.com/arduino/arduino-examples/main/examples/{folder}/{name}/{name}.ino"


def official_examples(frame_urls):
    """docs.arduino.cc shows Arduino's built-in examples in an embedded editor that draws only the lines on screen;
    the embed names the example, so its sketch is copied whole from Arduino's own examples repository."""
    import urllib.request
    out = []
    for u in frame_urls:
        m = EXAMPLE.search(u or "")
        if not m:
            continue
        try:
            with urllib.request.urlopen(EXAMPLES.format(folder=m.group(1), name=m.group(2)), timeout=30) as r:
                out.append(r.read().decode("utf-8", "replace"))
        except Exception:  # not there: the page's own code blocks are used instead
            continue
    return out


def example_by_name(url):
    """A docs.arduino.cc built-in example page that only points to the IDE's example ("the ArduinoISP sketch"): its
    sketch is the example of the page's name in Arduino's examples repository (one lookup of the repository's files)."""
    import json
    import urllib.request
    m = re.search(r"docs\.arduino\.cc/built-in-examples/.+/([^/]+)/?$", url or "")
    if not m:
        return []
    try:
        tree = json.loads(urllib.request.urlopen(
            "https://api.github.com/repos/arduino/arduino-examples/git/trees/main?recursive=1", timeout=30).read())
        path = next((t["path"] for t in tree["tree"] if t["path"].lower().endswith(f"/{m.group(1).lower()}.ino")), None)
        if not path:
            return []
        with urllib.request.urlopen(
                f"https://raw.githubusercontent.com/arduino/arduino-examples/main/{path}", timeout=30) as r:
            return [r.read().decode("utf-8", "replace")]
    except Exception:
        return []


def create_sketches(text):
    """Sketches embedded from Arduino's online editor (an iframe 'create.arduino.cc/editor/<user>/<id>/preview'):
    read from the editor's public files API, the main .ino first."""
    import base64
    import json
    import urllib.parse
    import urllib.request
    out = []
    for sid in dict.fromkeys(re.findall(r"create\.arduino\.cc/editor/[^/'\"]+/([0-9a-f-]{36})", text or "")):
        try:
            api = "https://api2.arduino.cc/create/v2"
            meta = json.loads(urllib.request.urlopen(f"{api}/sketches/byID/{sid}", timeout=30).read())
            path = f"{meta['path']}/{meta['name']}.ino"
            got = json.loads(urllib.request.urlopen(f"{api}/files/f/{urllib.parse.quote(path)}", timeout=30).read())
            out.append(base64.b64decode(got["data"]).decode("utf-8", "replace"))
        except Exception:  # private, moved or gone
            continue
    return out


def github_markdown_code(url):
    """A tutorial kept as a markdown file on GitHub (arduino/docs-content): GitHub shows it in its own file viewer, so
    the code blocks are read from the raw file (``` fences), whole."""
    import urllib.request
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/blob/(.+\.md)$", url or "")
    if not m:
        return []
    try:
        with urllib.request.urlopen(f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}",
                                    timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    blocks = create_sketches(text) + [b for b in re.findall(r"^[ \t]*```[^\n`]*\n(.*?)^[ \t]*```", text, re.S | re.M) if b.strip()]
    for src in re.findall(r'<CodeBlock\s+url="(https://github\.com/[^"]+\.ino)"', text):  # a sketch shown from its
        raw = re.sub(r"https://github\.com/([^/]+)/([^/]+)/blob/", r"https://raw.githubusercontent.com/\1/\2/", src)
        try:                                                                         # own file in another repo
            with urllib.request.urlopen(raw, timeout=30) as r:
                blocks.append(r.read().decode("utf-8", "replace"))
        except Exception:
            pass
    return blocks


# the page's headings and list items as markdown (# Hardware, - 1x servo): the parts list is read from its section,
# which flat text loses (tutorial.hardware_list)
MARKDOWN_JS = """() => { const out = [], root = document.querySelector('main') || document.body;
  root.querySelectorAll('h1,h2,h3,h4,li,p').forEach((e) => {
    if (e.closest('nav,header,footer,aside')) return;
    const t = e.innerText.trim(); if (!t) return;
    if (e.tagName[0] === 'H') out.push('#'.repeat(+e.tagName[1]) + ' ' + t.split('\\n')[0]);
    else if (e.tagName === 'LI') { if (!e.querySelector('li')) out.push('- ' + t.split('\\n')[0]); }
    else if (!e.closest('li')) out.push(t);
  });
  return out.join('\\n'); }"""


def render(url, timeout_s=45, max_text=40000, tries=3):
    """The page as the browser shows it. A browser that fails to start (its driver closes: several starting at once
    in a batch) is started again, up to `tries` times, a little later each time."""
    for k in range(tries):
        try:
            return _render(url, timeout_s, max_text)
        except Exception as e:
            if "Connection closed" not in str(e) and "Target closed" not in str(e) or k == tries - 1:
                raise
            time.sleep(10 * (k + 1))


def _render(url, timeout_s=45, max_text=40000):
    from playwright.sync_api import sync_playwright

    t0 = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 1600})
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_s * 1000)
            except Exception:  # a page that never goes quiet (GitHub, trackers): read it once its content is in
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 2000)
                page.wait_for_timeout(5000)
            text = page.inner_text("body")
            try:
                markdown = page.evaluate(MARKDOWN_JS)
            except Exception:  # a page the walk cannot read: the flat text only
                markdown = ""
            # code blocks as written (line breaks kept): the tutorial's sketch is copied, never rewritten. Sites put
            # it in <pre> blocks, or in an embedded code viewer (docs.arduino.cc: a CodeMirror frame, one .cm-line
            # per line, line numbers kept apart)
            # a built-in example page: its sketch is the example itself, from Arduino's repository (the page's own
            # viewer can read out with its line numbers in it)
            frames = page.evaluate("() => [...document.querySelectorAll('iframe')].map((i) => i.src)")
            code = example_by_name(url) or official_examples(frames) or create_sketches(" ".join(frames))
            for frame in ([] if code else page.frames):
                try:
                    code += frame.evaluate(CODE_JS)
                except Exception:  # a frame that is gone or blocked has no code for us
                    continue
            images = []
            for img in page.query_selector_all("img"):
                if len(images) >= MAX_IMAGES:
                    break
                box = img.bounding_box()
                if not box or box["width"] < MIN_SIDE or box["height"] < MIN_SIDE:
                    continue
                try:
                    img.scroll_into_view_if_needed(timeout=3000)
                    images.append((img.screenshot(timeout=5000), img.get_attribute("alt") or ""))
                except Exception:  # an image that cannot be captured is skipped, not fatal
                    continue
        finally:
            browser.close()
    if not any("setup" in c and "loop" in c for c in code):
        code += github_markdown_code(url) or example_by_name(url)
    return {"url": url, "text": " ".join(text.split())[:max_text], "markdown": markdown[:max_text], "images": images,
            "code": code,
            "seconds": round(time.monotonic() - t0, 1)}
