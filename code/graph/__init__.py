"""Pinpoint's lesson engine: step-by-step building lessons made from instructions, checked by code.

What it is   the product's Python package. Common code sits here; each way of making a lesson has its own folder.
Used for     making a lesson from a LEGO booklet PDF (lego_booklet/), from a LEGO set's 3D model (lego_3d/) or from
             an Arduino tutorial link (arduino/); storing it as graphs (lesson_store.py); the parts it uses
             (parts/); serving it to a tutor (tutor_mcp.py).
Where        run from the code/ folder: python -m graph.<module>. Data it reads and writes is in data/
             (data/sources, data/reference, data/lessons).

  lessons.py        the lesson loop for the 3D-model and Arduino routes (Claude plans, code checks, repairs)
  extract.py        every Claude call (structured answers, time and cost)
  lesson_store.py   the lesson store: registering, reading and checking every lesson, the catalogue, and the
                    validator of every lesson and part (lesson_store validate)
  lego_model.py     LEGO parts and models from LDraw: real shapes, studs and pins, joins, model files (every LEGO route)
  tutor_mcp.py      the lesson data as tools for a tutoring agent
  filelock.py       one writer at a time for the shared files
  lego_booklet/     lessons from a LEGO booklet PDF
  lego_3d/          lessons from a LEGO set's 3D model (graphs.py: the lesson as stored graphs)
  arduino/          lessons from an Arduino tutorial link (graphs.py: the lesson as stored graphs)
  parts/            the parts catalogue and part cards (parts/lego, parts/arduino)
"""
