"""Print one built graph in readable form, for a manual sanity check.

  .venv-research/bin/python -m graphgen.inspect experiments/graphgen/<run>/<manual>
"""
import collections
import json
import pathlib
import sys

from . import catalogue as cat
from . import logical


def main():
    d = pathlib.Path(sys.argv[1])
    flat = json.loads((d / "graph.json").read_text())
    result = json.loads((d / "result.json").read_text())
    resp = json.loads((d / "response.json").read_text())["graph"]
    print(f"== {result['case']}  ({result['stats']['seconds']} s, ${result['stats']['cost_usd']})")
    types = collections.Counter(n["type"] for n in flat["nodes"])
    print("parts:", ", ".join(f"{t}×{c}" for t, c in types.most_common(25)))
    if resp["repeats"]:
        for r in resp["repeats"]:
            print(f"repeat {r['group']} ×{r['times']}: parts {[p['type'] for p in r['parts']]}, "
                  f"overrides {[(o['copy_number'], o['kind'], o['target'], o['value']) for o in r['overrides']]}")
    if resp["new_part_types"]:
        for t in resp["new_part_types"]:
            print(f"new type {t['type']}: ports {[p['name'] for p in t['ports']]} polarized={t['polarized']} "
                  f"symmetric={t['symmetric']} connector={t['connector']} conducts={t['conducts']} through={t['through']}")
    if result["domain"] == "arduino":
        catalogue = cat.Catalogue(json.loads((d.parent / "catalogue_after.json").read_text()))
        print("nets (connectors folded):")
        for net in sorted(logical.nets(flat, catalogue), key=lambda n: sorted(n)):
            print("   ", " — ".join(sorted(net)))
        loose = [e for e in flat["edges"] if e["type"] == "joined" and not any(
            x["type"] == "electrical" and {x["u"], x["v"]} == {e["u"], e["v"]} for x in flat["edges"])]
        if loose:
            print(f"joined without electrical: {[(e['u'], e['u_port'], e['v'], e['v_port']) for e in loose[:8]]}")
    else:
        kinds = collections.Counter((e["type"], e.get("method"), e.get("freedom")) for e in flat["edges"])
        print("edges:", kinds.most_common(8))
        print("sample:", [(e["u"], e["v"], e.get("method")) for e in flat["edges"][:10]])
    print("score:", {k: v for k, v in result["score"].items() if not isinstance(v, (list, dict))})
    print("problems:", result["problems"][:6])
    print("notes:", [n[:160] for n in result["notes"][:4]])


if __name__ == "__main__":
    main()
