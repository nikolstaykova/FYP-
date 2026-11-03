"""The lesson loop for lessons from a 3D model and from an Arduino link.

What it is   make(recipe, case): load the source, plan each section with Claude, check it with code, send problems
             back to Claude (up to REPAIRS rounds), finish with code's own fixes and a final check, save with time
             and cost. A Recipe says what differs between domains (lego_3d/lesson.py: LegoLessons,
             arduino/circuit_lesson.py: CircuitLessons).
Used for     making a step-by-step lesson for a LEGO set from its 3D model, or for an Arduino tutorial from its
             link. (A booklet lesson has its own pipeline: lego_booklet/pdf_lesson.py.)
Where        the command line, then lesson_store.py registers the lesson: python -m graph.lessons lego 42124-1;
             python -m graph.lessons electronics https://docs.arduino.cc/built-in-examples/basics/Blink/

  1. source    the recipe loads what the lesson is made from (LEGO: the set's 3D model, its pieces and joins;
               Arduino: the tutorial's circuit graph, arduino/circuit_graph.py, and its page)
  2. sections  the parts planned one at a time (LEGO: the booklet's bags or parts of a big model; Arduino: one)
  3. plan      Claude, on the recipe's prompt (LEGO: the order and the words; Arduino: code has already ordered
               the steps and worked out what each one connects, Claude writes the words)
  4. check     the recipe's rules; every problem goes back to the same conversation, up to REPAIRS rounds; the
               plan with the fewest issues of all rounds is kept (a repair can make it worse)
  5. finish    the recipe's code fixes (LEGO: LEGO's own order, then rewording), a last check, saved with its stats
Every Claude turn and check is a timed, costed phase; progress is logged as it happens.
"""
import collections
import sys
import time

REPAIRS = 3


def log(*msg):
    """Progress, as it happens (a batch log shows where a long case is)."""
    print(time.strftime("%H:%M:%S"), *msg, file=sys.stderr, flush=True)


class Recipe:
    """What differs between domains. A recipe fills these in; make() runs them in the same order for every domain."""
    name = ""
    system = ""          # Claude's instructions for planning (and repairing) a section
    schema = None        # the structured answer Claude returns (pydantic model)
    hint = "lego-v8"     # extract.HINTS key; the recipe's own `system` replaces the graph instructions
    timeout = 1800       # per Claude turn, seconds
    default_model = "sonnet"  # the model when none is named (the LEGO recipe: opus, chosen in R28)

    def source(self, case):              # -> src: everything the lesson is made from (src["id"] names the case)
        raise NotImplementedError

    def sections(self, src):             # -> [(label, ids)], planned in order; with the phases they cost
        return [(None, None)], []

    def prompt(self, src, section, built):   # -> the text Claude plans this section from
        raise NotImplementedError

    def merge(self, src, section, answer):   # -> this section's lesson, from Claude's answer (and the recipe's draft)
        return answer

    def check(self, src, part, section, built):  # -> [(rule, message)]
        raise NotImplementedError

    def join(self, src, done):           # [(section, part lesson)] -> the whole lesson
        raise NotImplementedError

    def finish(self, src, lesson, phases):   # code fixes after the plan; may add phases
        return lesson

    def final_check(self, src, lesson):
        return self.check(src, lesson, None, set())

    def save(self, src, lesson, stats):  # -> where it was written
        raise NotImplementedError


def make(recipe, case, model="sonnet", effort="high"):
    """The one lesson loop. Returns the stats written with the lesson."""
    from graph.extract import SubscriptionSession
    t0 = time.monotonic()
    log(case, f"start ({recipe.name}): loading the source")
    src = recipe.source(case)
    prep_s = time.monotonic() - t0
    secs, phases = recipe.sections(src)
    log(case, f"{len(secs)} section(s)")
    done, built, first_issues = [], set(), 0
    for k, section in enumerate(secs, 1):
        s = SubscriptionSession(recipe.prompt(src, section, built), "", recipe.hint, model=model, effort=effort,
                                timeout=recipe.timeout, schema=recipe.schema, system=recipe.system)
        try:
            log(case, f"part {k}/{len(secs)}: planning")
            answer, st = s.first()
            part = recipe.merge(src, section, answer)
            log(case, f"part {k}: plan back ({st.get('seconds')} s, ${st.get('cost_usd')}); checking")
            t1 = time.monotonic()
            issues = recipe.check(src, part, section, built)
            rules = dict(collections.Counter(r for r, _ in issues))
            log(case, f"part {k}: {len(issues)} issues {rules}")
            phases.append({"phase": f"plan part {k}", **st, "check_seconds": round(time.monotonic() - t1, 1),
                           "issues": len(issues), "rules": rules})
            first_issues += len(issues)
            best = (len(issues), 0, part)  # the plan with the fewest issues so far (a later one on a tie): a repair
            # can make a plan worse (31028-1: 11, 12, 1, then 7 issues), and the 1-issue one must not be lost
            for n in range(REPAIRS):
                if not issues:
                    break
                msg = "The plan has problems:\n" + "\n".join(f"- {r}: {m}" for r, m in issues[:40]) + \
                      "\n\nReturn the COMPLETE corrected plan (every step), not only the changes."
                log(case, f"part {k}: repair {n + 1} sent")
                answer, st = s.repair(msg)
                part = recipe.merge(src, section, answer)
                log(case, f"part {k}: repair {n + 1} back ({st.get('seconds')} s, ${st.get('cost_usd')}); checking")
                t1 = time.monotonic()
                issues = recipe.check(src, part, section, built)
                rules = dict(collections.Counter(r for r, _ in issues))
                log(case, f"part {k}: {len(issues)} issues {rules}")
                phases.append({"phase": f"repair{n + 1} part {k}", **st, "check_seconds": round(time.monotonic() - t1, 1),
                               "issues": len(issues), "rules": rules})
                if len(issues) <= best[0]:
                    best = (len(issues), n + 1, part)
            if best[2] is not part:
                log(case, f"part {k}: keeping the plan of {'the first answer' if not best[1] else f'repair {best[1]}'} "
                          f"({best[0]} issues, the last had {len(issues)})")
                phases.append({"phase": f"kept best part {k}", "seconds": 0, "cost_usd": 0, "from": best[1],
                               "issues": best[0]})
                part = best[2]
        finally:
            s.close()
        done.append((section, part))
        built |= set(section[1] or [])
    lesson = recipe.join(src, done)
    log(case, "finishing (code fixes)")
    lesson = recipe.finish(src, lesson, phases)
    log(case, "final check")
    issues = recipe.final_check(src, lesson)
    log(case, f"done: {len(lesson['steps'])} steps, {len(issues)} issues left")
    stats = {"case": src["id"], "domain": recipe.name, "model": model, "steps": len(lesson["steps"]),
             "seconds": round(sum(p.get("seconds", 0) + p.get("check_seconds", 0) for p in phases) + prep_s, 1),
             "cost_usd": round(sum(p.get("cost_usd", 0) for p in phases), 4),
             "repairs": sum(1 for p in phases if p["phase"].startswith("repair")),
             "issues_first": first_issues, "issues_final": [list(i) for i in issues], "phases": phases}
    path = recipe.save(src, lesson, stats)
    log(case, f"saved {path}")
    return stats


def recipe_for(domain, model=None):
    if domain == "lego":
        from graph.lego_3d.lesson import LegoLessons
        return LegoLessons(model=model)  # its own calls (the bags, rewording) use the same model as the planning
    if domain in ("electronics", "arduino"):
        from graph.arduino.circuit_lesson import CircuitLessons
        return CircuitLessons()
    raise ValueError(f"no lesson recipe for {domain}")


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("domain", choices=["lego", "electronics", "arduino"])
    ap.add_argument("cases", nargs="+", help="LEGO set ids; electronics tutorial links (or ids of an extracted run)")
    ap.add_argument("--model", default=None, help="default: the recipe's (LEGO opus, Arduino sonnet)")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--hint", default="", help="electronics: a correction where the tutorial is wrong (kept for later runs)")
    ap.add_argument("--sketch", default="", help="electronics: the sketch (file or link) when the page has none or a wrong one")
    ap.add_argument("--why", default="", help="what was wrong with the tutorial (kept with the correction)")
    cfg = ap.parse_args(argv)
    recipe = recipe_for(cfg.domain, cfg.model)
    cfg.model = cfg.model or recipe.default_model
    if cfg.hint or cfg.sketch:
        from graph.arduino.circuit_lesson import correct, slug
        for c in cfg.cases:  # a link is kept under the lesson's id
            correct(slug(c) if c.startswith("http") else c, cfg.hint, cfg.sketch, cfg.why)
    import re
    failed = 0
    for c in cfg.cases:
        for attempt in range(20):
            try:
                st = make(recipe, c, cfg.model, cfg.effort)
                break
            except Exception as e:  # one case failing never stops the rest; it is reported
                # not the case's fault (the usage limit, a lapsed login, the network): wait and try it again
                if re.search(r"session limit|usage limit|weekly limit|rate limit|hit your|authenticate|reach the API|ENOTFOUND|ECONNRESET|"
                             r"overloaded|went to sleep|timed out", str(e)) and attempt < 19:
                    log(c, f"{str(e)[:120]}: waiting 15 min, then trying again")
                    time.sleep(900)
                    continue
                import traceback
                traceback.print_exc(limit=3)
                print(f"{c}: FAILED {type(e).__name__}: {str(e)[:200]}", flush=True)
                st = None
                break
        if st is None:
            failed += 1
            continue
        print(f"{c}: {st['steps']} steps, {len(st['issues_final'])} issues left, {st['seconds']} s, ${st['cost_usd']}",
              flush=True)
    return 1 if failed else 0  # the exit code: a script that builds the store next stops on a case not made


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
