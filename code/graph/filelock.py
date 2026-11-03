"""One writer at a time for the shared files.

What it is   with locked(path): an exclusive lock on <path>.lock, across processes; taken again in the same thread,
             it does not wait.
Used for     keeping the card stores, parts.json and the lesson catalogue whole when several lessons are made at
             once (a batch run).
Where        lesson_store.py, parts/part_catalogue.py, parts/part_metadata.py, parts/arduino/pinouts.py.
"""
import contextlib
import fcntl
import pathlib
import threading

_held = threading.local()


@contextlib.contextmanager
def locked(path):
    key = str(pathlib.Path(path).with_suffix(".lock"))
    held = getattr(_held, "keys", None)
    if held is None:
        held = _held.keys = set()
    if key in held:
        yield
        return
    with open(key, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        held.add(key)
        try:
            yield
        finally:
            held.discard(key)
            fcntl.flock(f, fcntl.LOCK_UN)
