"""The first look sends photos at 768 px, JPEG 35 (CHECKER.md §3.7)."""
import io

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from gather import gather_vlm as vlm  # noqa: E402


def _photo(tmp_path, size, fmt="JPEG", name="p.jpg"):
    p = tmp_path / name
    Image.new("RGB", size, (200, 30, 30)).save(p, fmt)
    return p


def test_big_photo_is_shrunk(tmp_path):
    b, mt = vlm.shrink(_photo(tmp_path, (4032, 3024)))
    assert mt == "image/jpeg"
    assert Image.open(io.BytesIO(b)).size == (768, 576)


def test_small_photo_is_not_enlarged(tmp_path):
    b, _ = vlm.shrink(_photo(tmp_path, (500, 300)))
    assert Image.open(io.BytesIO(b)).size == (500, 300)


def test_png_becomes_jpeg(tmp_path):
    b, mt = vlm.shrink(_photo(tmp_path, (1000, 1000), "PNG", "p.png"))
    assert mt == "image/jpeg" and b[:2] == b"\xff\xd8"


def test_unreadable_file_is_sent_as_it_is(tmp_path):
    p = tmp_path / "x.jpg"
    p.write_bytes(b"not a photo")
    assert vlm.shrink(p) == (b"not a photo", "image/jpeg")
