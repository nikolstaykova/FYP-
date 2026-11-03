"""The tests run from any folder: the product's package (code/graph; the checks are in code/checker), the tests' tools (consensus and the
like) and the research versions (code/tests/research), which are not part of the product, are put on the path."""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE / "tools"), str(HERE / "research")]
