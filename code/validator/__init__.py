"""The validator: after each step, is what the learner built right?

What it is   compares the learner's build (what is placed, where, and how it is joined) with the expected state of a
             lesson step, and says what is right, what is a harmless difference, and what to fix. One verdict
             vocabulary for LEGO and Arduino, from CircuitQuest's checker: pass / harmless (a symmetric swap, a
             substitutable colour) / substituted (another part of the same kind) / wrong; plus missing and extra.
Used for     the learner's feedback after each step (a photo of the build); later, the same check in AR.
Where        reads a lesson through the lesson store (graph.lesson_store.assemble: the database when it is set up,
             else the files); nothing here writes to the store. The gather check (code/gather) runs before a step:
             have the pieces. This runs after it: are they put together right.

The expected state after step N is every part and join of steps 1..N (assemble(...)["steps"][*]["parts"] and
["connections"]: instances with type, colour and place; joins port to port, e.g. b1 stud.1.1 -> b7 anti.1.2,
wire1 a -> uno 13). LEGO compares parts, places and joins; Arduino compares nets (position-free), as CircuitQuest.
Tolerance per part (exact / any colour / any part of a kind, e.g. a minifigure head) decides harmless against wrong.
"""
