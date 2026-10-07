"""Open a web page the way a person's browser does (v6: Claude reads tutorial links itself).

Many tutorial sites build their pages with JavaScript (docs.arduino.cc returns no readable text to a plain fetch),
so the page is loaded in headless Chrome (Playwright driving the system's Google Chrome), its scripts run, and what
a reader sees is returned: the visible text of the page, and its larger images (circuit diagrams, schematics).

  page = render("https://docs.arduino.cc/built-in-examples/basics/Blink/")
  page["text"]    visible text
  page["images"]  [(png bytes, alt text)] screenshots of the page's larger images
"""
import time

MAX_IMAGES = 6
MIN_SIDE = 150  # smaller images are icons and logos


def render(url, timeout_s=45, max_text=40000):
    from playwright.sync_api import sync_playwright

    t0 = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 1600})
            page.goto(url, wait_until="networkidle", timeout=timeout_s * 1000)
            text = page.inner_text("body")
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
    return {"url": url, "text": " ".join(text.split())[:max_text], "images": images,
            "seconds": round(time.monotonic() - t0, 1)}
