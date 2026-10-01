# Manual survey: scripts and data

Scripts that collect real manuals and count the connections they use. Results feed [`GRAPH_SPEC.md`](../GRAPH_SPEC.md) and [`RESEARCH.md`](../RESEARCH.md) (R20).

| Script | Source | Output |
|---|---|---|
| `scrape/sauder.py` → `scrape/analyze_sauder.py` | 13 Sauder instruction booklets (retailer-hosted copies of Sauder's own PDFs) | `data/sauder_connections.json` |
| `scrape/lego_ldraw.py` | 30 official LEGO sets from the LDraw Official Model Repository + the LDraw parts library | `data/lego_connections.json` |
| `scrape/lego_repeats.py` | Same LDraw sets | `data/lego_repeats.json` |
| `scrape/arduino_circuitquest.py` | 53 CircuitQuest lessons (48 from docs.arduino.cc) + part library in `~/Desktop/CirquitQuest` | `data/arduino_connections.json` |

**Run** (from the repo root):
```
python3 -m venv .venv-research && .venv-research/bin/pip install pymupdf requests
.venv-research/bin/python research/scrape/sauder.py
.venv-research/bin/python research/scrape/analyze_sauder.py
.venv-research/bin/python research/scrape/lego_ldraw.py      # downloads the 146 MB LDraw library once
.venv-research/bin/python research/scrape/lego_repeats.py
.venv-research/bin/python research/scrape/arduino_circuitquest.py
```

Downloaded PDFs, LDraw files and extracted manual text go to `research/raw/` and are **not committed**: they are the manufacturers' and LDraw authors' material. Only counts and short examples are committed.
