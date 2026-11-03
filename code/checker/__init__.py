"""The build checker: does what the learner has built match the lesson's step?

What it is   compares the learner's build (what is placed and how it is joined) with the expected state of a lesson
             step, and says what is right, what is a harmless difference, and what to fix. One verdict vocabulary
             for LEGO and Arduino, from CircuitQuest's checker: pass / harmless (a symmetric swap, a substitutable
             colour) / substituted (another part of the same kind) / wrong; plus missing and extra.
Used for     the learner's feedback after each step; later, the same check on what a VLM reads from a photo (AR).
Where        reads a lesson from the store (lesson_store: data/lessons/store/<id>/assembled.json); nothing here
             writes to the store.

The expected state after step N is every part and join of steps 1..N (assembled.json steps[*].parts and
.connections: instances with type, colour and place; joins port to port, e.g. b1 stud.1.1 -> b7 anti.1.2,
wire1 a -> uno 13). LEGO compares parts, places and joins; Arduino compares nets (position-free), as CircuitQuest.
Tolerance per part (exact / any colour / any part of a kind, e.g. a minifigure head) decides harmless against wrong.
"""
