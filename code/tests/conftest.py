"""The tests run from any folder: the product's package (code/graph; the checks are in code/checker), the tests' tools (consensus and the
like) and the research versions (code/tests/research), which are not part of the product, are put on the path."""
import os
import pathlib
import sys

os.environ["PINPOINT_DB_SYNC"] = "0"  # tests never write to the real database
os.environ["PINPOINT_DATA"] = "files"  # and read the files, so they run offline and the same every time

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE / "tools"), str(HERE / "research")]
