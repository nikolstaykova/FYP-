"""LEGO gathering in groups (checker.lego_gather) and the gather cards in the tutor's steps."""
from checker import lego_gather
from tutor import live


def _step(number, pieces, bag=None, times=1):
    return {"number": str(number), "bag": bag, "times": times,
            "parts": [{"what": f"piece {k}", "count": 1} for k in range(pieces)]}


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
    steps = [_step(1, 4), _step(2, 4), _step("3.1", 2, times=2), _step("3.2", 2, times=2), _step(3, 1), _step(4, 6)]
    g = lego_gather.groups(steps)
    assert not any(x["first"] in (3, 4) for x in g)  # never between 3.1 and 3
    assert sum(x["pieces"] for x in g) == 4 + 4 + 4 + 4 + 1 + 6


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


def test_cards_fit_one_photo():
    from graph import lesson_store
    for r in lesson_store.catalogue()["lessons"]:
        if r.get("lesson_type") != "lego":
            continue
        for c in [s for s in live.steps(r["lesson_id"])["steps"] if s["kind"] == "gather"]:
            assert len(c["parts"]) <= lego_gather.KINDS, (r["lesson_id"], c["id"])
            assert sum(p["count"] for p in c["parts"]) <= 16 or len(c["parts"]) == 1, (r["lesson_id"], c["id"])


def test_card_check_result():
    from checker import lego_check
    card = {"parts": [{"what": "Red Brick 2 x 4", "count": 1}, {"what": "Black Plate 1 x 1 Round", "count": 6},
                      {"what": "Blue Plate 2 x 3", "count": 2}, {"what": "White Tile 1 x 2", "count": 1},
                      {"what": "Yellow Minifig Head", "count": 1}]}
    its = lego_check.items(card)
    v = {"p1": {"status": "there", "seen": 1}, "p2": {"status": "there", "seen": 3},
         "p3": {"status": "there", "seen": 1}, "p4": {"status": "unsure", "seen": 0, "ask": "Hold it up?"},
         "p5": {"status": "other_colour", "colour_seen": "tan"}}
    res = lego_check.result(its, v)
    st = {r["type"]: r["status"] for r in res["parts"]}
    assert st == {"p1": "have", "p2": "have", "p3": "check", "p4": "check", "p5": "use another colour"}
    assert [q["key"] for q in res["asks"]] == ["p3", "p4"] and res["asks"][1]["message"] == "Hold it up?"
    res = lego_check.result(its, {}, dismissed=["p1"])
    assert res["parts"][0]["status"] == "skipped" and "p1" not in [q["key"] for q in res["asks"]]


def test_cards_are_stored_in_the_lesson_graph():
    """add_cards puts each card in the step order with COVERS links; running it again changes nothing."""
    import copy
    from checker import lego_gather
    phys = {"nodes": [{"id": f"b{i}", "type": "lego-3001", "label": "Brick 2 x 4", "props": {"colour": "Red"}}
                      for i in range(1, 25)]}
    steps = [{"id": f"step-{n}", "kind": "step", "n": n, "text": f"step {n}", "bag": None} for n in range(1, 7)]
    edges = [{"type": "NEXT_STEP", "u": f"step-{n}", "v": f"step-{n + 1}"} for n in range(1, 6)]
    edges += [{"type": "PLACES", "u": f"step-{(i - 1) // 4 + 1}", "v": f"b{i}"} for i in range(1, 25)]  # 4 a step
    g = {"instruction": {"nodes": steps, "edges": edges}, "physical": phys, "lesson": {}}
    n = lego_gather.add_cards(g)
    assert n >= 2  # 24 pieces: more than one card of about 10
    once = copy.deepcopy(g["instruction"])
    lego_gather.add_cards(g)
    assert g["instruction"] == once  # the same cards again, not more
    from graph import lesson_store
    order = lesson_store._order(g["instruction"])
    assert order[0].startswith("gather-")  # a card first, then its steps
    covers = [e for e in g["instruction"]["edges"] if e["type"] == "COVERS"]
    assert sorted({e["v"] for e in covers}) == [f"step-{k}" for k in range(1, 7)]  # every step gathered for
    for e in covers:  # each card comes before every step it covers
        assert order.index(e["u"]) < order.index(e["v"])
