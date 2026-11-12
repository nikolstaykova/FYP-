"""The gather check: before a stretch of steps, does the learner have the parts?

What it is   from a few photos of the parts laid out: electronics (an Arduino lesson's whole parts list: what is on
             the table, matched to the catalogue, with values and substitutes) and LEGO (one gather card of about 10
             pieces: is each one there, the right kind and size, in the right colour). One result shape for both.
Files        gather.py       the check, both kinds of lesson (electronics: check; LEGO: card_*)
             gather_flow.py  the electronics check as the learner gets it: Haiku first, close-ups, Opus once
             gather_vlm.py   the one Claude call (photos + text -> JSON), with prices and photo shrinking
Used for     the gather steps of every lesson (the app, the web game, the tutor's check_parts); CHECKER.md (cost).
             The gather cards themselves are made with the lesson (graph/lego_gather.py). After a step, whether the
             build is right is the validator's job (code/validator).
"""
