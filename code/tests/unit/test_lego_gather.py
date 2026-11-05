"""LEGO gathering in groups (checker.lego_gather) and the gather cards in the tutor's steps."""
from checker import lego_gather
from tutor import live


def _step(number, pieces, bag=None, times=1):
    return {"number": str(number), "bag": bag, "times": times,
            "parts": [{"what": f"piece {number}-{k}", "count": 1} for k in range(pieces)]}


def test_small_lesson_one_card():
    g = lego_gather.groups([_step(1, 3), _step(2, 4), _step(3, 2)])
    assert len(g) == 1 and (g[0]["first"], g[0]["last"], g[0]["pieces"]) == (0, 2, 9)


def test_bags_start_new_cards():
    steps = [_step(n, 3, bag=1) for n in range(1, 5)] + [_step(n, 3, bag=2) for n in range(5, 9)]
    g = lego_gather.groups(steps)
    assert [(x["bag"], x["open_bag"]) for x in g] == [(1, True), (2, True)] and g[1]["first"] == 4


def test_long_lesson_split_and_balanced():
    g = lego_gather.groups([_step(n, 3) for n in range(1, 21)])  # 60 pieces
    assert len(g) == 5 and all(x["pieces"] == 12 for x in g)
    assert [x["first"] for x in g] == [0, 4, 8, 12, 16]


def test_sub_build_kept_together_and_times_counted():
    steps = [_step(1, 4), _step(2, 4), _step("3.1", 2, times=3), _step("3.2", 2, times=3), _step(3, 1), _step(4, 6)]
    g = lego_gather.groups(steps)
    assert not any(x["first"] in (3, 4) for x in g)  # never between 3.1 and 3
    assert sum(x["pieces"] for x in g) == 4 + 4 + 6 + 6 + 1 + 6


def test_no_empty_card():
    g = lego_gather.groups([_step(n, 4) for n in range(1, 10)] + [_step(10, 0)])
    assert all(x["pieces"] > 0 for x in g)


def test_every_lego_lesson_gets_cards():
    from graph import lesson_store
    ids = [r["lesson_id"] for r in lesson_store.catalogue()["lessons"] if r.get("lesson_type") == "lego"]
    assert ids
    for lid in ids:
        st = live.steps(lid)["steps"]
        assert st[0]["kind"] == "gather", lid
        assert [s["n"] for s in st] == list(range(1, len(st) + 1))
        built = [s for s in st if s["kind"] != "gather"]
        assert [s["title"] for s in built] == [f"Step {k}" for k in range(1, len(built) + 1)]
        assert "Card 1, " in live.brief(lid)
