"""Build graphs from manuals with Claude, following GRAPH_SPEC.md.

model.py      what Claude must return (structured output schema)
catalogue.py  the part catalogue: seeded (Arduino from CircuitQuest, LEGO from LDraw) or empty
extract.py    prompt + Claude call, with timing and token usage
expand.py     repeated sub-assemblies (with overrides) -> one flat graph
validate.py   spec rules V2-V4 on the flat graph
logical.py    electrical nets from the flat graph (connectors folded away)
truth.py      ground truth: CircuitQuest lessons (Arduino), LDraw geometry (LEGO)
score.py      compare a graph with the ground truth
"""
