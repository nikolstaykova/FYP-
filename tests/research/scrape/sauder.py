"""Download Sauder instruction booklets and extract parts, hardware and step text.

Sauder's own site blocks automated requests (HTTP 403), so the PDFs come from
retailers that host Sauder's own booklets (see RESEARCH.md, Source policy).
PDFs and the extracted step text are saved to research/raw/sauder/
(git-ignored, as they are Sauder's own text); analyze_sauder.py turns them
into counts in research/data/sauder_connections.json, which is committed.

Run: .venv-research/bin/python research/scrape/sauder.py
"""
import json
import pathlib
import re

import pymupdf
import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW = ROOT / "research" / "raw" / "sauder"
OUT = ROOT / "research" / "raw" / "sauder" / "sauder.json"
UA = {"User-Agent": "Mozilla/5.0 (research; Pinpoint FYP)"}

URLS = [
    "https://cdn.menardc.com/main/items/media/SAUDE001/Assembly_Instructions/2114705_instruct.PDF",
    "https://pdf.lowes.com/productdocuments/27b128d0-99d5-466b-b6eb-cdc2b3e1b72e/68649647.pdf",
    "https://pdf.lowes.com/productdocuments/62ec7318-2ad5-4ef5-9a42-7a948dff0f5d/68649639.pdf",
    "https://pdf.lowes.com/productdocuments/758cbf66-80f2-4d56-afcc-892bc4ea96a8/68649651.pdf",
    "https://pdf.lowes.com/productdocuments/2c59bc4b-66ff-4a44-bd8d-f19da29a3cdb/68649645.pdf",
    "https://pdf.lowes.com/productdocuments/5af78b18-7e66-4b86-83b8-8ad3267e87c7/68649641.pdf",
    "https://s7d9.scene7.com/is/content/NationalBusinessFurniture/SAU-34963-AIpdf",
    "https://s7d9.scene7.com/is/content/OfficeFurniturecom/408558pdf",
    "https://img1.wsimg.com/blobby/go/dd39cebc-08dd-45e3-a763-946f40d1d843/downloads/sauder_executive_desk_instructions.pdf",
    "https://assets.wfcdn.com/dm/document/78d3c022-c07c-4e9c-9c13-114efb05863f/%20colton%204%20-%20shelf%20storage%20cabinet.pdf",
    "https://assets.wfcdn.com/dm/document/e7ba9fbb-d7be-4d23-818b-4dfc191fe768/43ff2ba2-c8b4-4432-abff-12fcbe9af6a3.pdf",
    "https://bobs-ui.s3.us-east-1.amazonaws.com/DTC/Sauder/DETLOFBOOKCASEOAK_2175006001.pdf",
    "https://cdn.shopify.com/s/files/1/2660/5202/files/427466.PDF",
]

# Steps are bullet lines; the booklets use a private-use glyph (rendered "å") as the bullet.
BULLET = re.compile(r"^\s*(?:å|•||•)\s*")
MODEL = re.compile(r"Model\s+(\d{5,6})|(\d{6})\s*/\s*[\d-]+\s*$", re.M)
# Hardware/parts are written in capitals followed by a reference in brackets: "WOOD DOWELS (1)", "END (B)".
REF = re.compile(r"\b([A-Z][A-Z0-9\-/\"' .]{2,60}?)\s*\(([A-Z0-9]{1,4})\)")


def download(url):
    RAW.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9]+", "_", url.split("//", 1)[1])[-80:]
    path = RAW / (name if name.lower().endswith("pdf") else name + ".pdf")
    if not path.exists():
        r = requests.get(url, headers=UA, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


def english_text(doc):
    """English pages only: stop at the French/Spanish sections."""
    pages = []
    for page in doc:
        t = page.get_text()
        # The French and Spanish sections start with their own parts list.
        # (Language names alone also appear in the English table of contents.)
        if re.search(r"LISTE DE PI[EÈ]CES|LISTA DE PARTES|Étape\s+\d|Paso\s+\d", t):
            break
        pages.append(t)
    return "\n".join(pages)


def extract(path, url):
    doc = pymupdf.open(path)
    text = english_text(doc)
    m = MODEL.search(text)
    model = (m.group(1) or m.group(2)) if m else None
    title = next((l.strip() for l in text.splitlines()
                  if re.search(r"(Desk|Bookcase|Cabinet|Organizer|Dresser|Stand|Credenza|Chest|Table|Bar|Shelf|Hutch|File)", l)
                  and len(l.strip()) < 60), None)
    # A bullet glyph sits on its own line; the sentence follows over one or
    # more lines and ends at the next bullet, the next "Step n", or a figure
    # label (a short line such as "B", "4" or "(4 used in this step)").
    steps, current, open_sentence = [], None, False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        step = re.match(r"^Step\s+(\d+)$", line)
        if step:
            current = {"step": int(step.group(1)), "lines": []}
            steps.append(current)
            open_sentence = False
            continue
        if BULLET.match(raw_line):
            if current is None:
                current = {"step": 0, "lines": []}
                steps.append(current)
            rest = BULLET.sub("", raw_line).strip()
            current["lines"].append(rest)
            open_sentence = True
            continue
        if open_sentence and current:
            if len(line) <= 3 or line.startswith("(") or line.startswith("Page "):
                open_sentence = False
                continue
            current["lines"][-1] = (current["lines"][-1] + " " + line).strip()
            if re.search(r"[.!]\s*$", line):
                open_sentence = False
    refs = {}
    for name, ref in REF.findall(text):
        name = re.sub(r"\s+", " ", name).strip(" .")
        refs.setdefault(ref, set()).add(name)
    return {
        "url": url,
        "model": model,
        "title": title,
        "pages": doc.page_count,
        "steps": [s for s in steps if s["lines"]],
        "refs": {k: sorted(v) for k, v in sorted(refs.items())},
    }


def main():
    out = []
    for url in URLS:
        try:
            path = download(url)
            out.append(extract(path, url))
            print("ok  ", out[-1]["model"], out[-1]["title"], len(out[-1]["steps"]), "steps")
        except Exception as e:  # keep going; report what failed
            print("FAIL", url, e)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("wrote", OUT, len(out), "manuals")


if __name__ == "__main__":
    main()
