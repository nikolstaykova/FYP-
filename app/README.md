# Parts Quest app (Flutter: iPhone, Android, web)

The learner's app. Two ways through a lesson:

- **Learn with Pip** (`lib/session/`): the whole lesson led by Pip, the voice tutor: hello (name, level) → find the
  parts → show them to the camera → the check (close-ups, "I don't have it") → the build steps (booklet picture, or
  the 3D model playing each step) → done. Every tool Pip uses is also a button, and what you tap is told to Pip.
- **Quests** (`lib/screens/`): find the parts on your own, card by card, with the camera check.

The app holds no keys and no lessons. Everything comes from the parts server
(`research/recognition/lab/server.py`), which reads the lessons (database or files) and calls the models.

```
phone app ──https──▶ parts server (your Mac) ──▶ lessons (Neo4j / files)
                                             └─▶ Claude Haiku (first look, 768 px) / Opus (hard close-ups)
```

## Run it

1. Start the server on the Mac: `research/recognition/lab/run.sh --lan --https`. It prints
   `On your phone (same Wi-Fi): https://192.168.x.x:8765/?key=…`. The key stays the same between starts
   (`research/recognition/runs/lab/lan_key.txt`; delete it for a new one).
2. Open the app and paste that link on the first screen. The phone must be on the same Wi-Fi.

The server's certificate is self-signed; the app trusts it only on private addresses (192.168.x, 10.x, this Mac).

### In a browser (no install)

```
cd app && flutter build web --base-href /app/
```

Then open `https://192.168.x.x:8765/app/?key=…` on the phone (accept the certificate warning once).

### On an iPhone

Needs **Xcode** (Mac App Store) and an Apple ID (free is enough for your own phone, re-sign every 7 days).

```
cd app && flutter run -d <your iPhone>        # plug it in, trust the Mac, turn on Developer Mode
```

### On an Android phone

Needs the **Android SDK** (Android Studio, or `brew install --cask android-commandlinetools`).
Turn on Developer options → USB debugging, plug in, then `flutter run`.

## Pip, the voice tutor (`lib/pip/`)

The same tutor as the web game (`code/tutor/live.py`, `research/recognition/lab/game.html`), with what we settled:

| | |
|---|---|
| Live voice (default) | Gemini Live, speech to speech: the phone streams the mic (16 kHz PCM, `record`) and plays Pip (24 kHz, `mp_audio_stream`); talk over Pip to cut it off. The server mints a single-use token (`/api/tutor/session`), so the Gemini key never reaches the phone. Session resumption + reconnect. |
| Free voice | the phone listens (`speech_to_text`), Haiku writes Pip's words (`/api/tutor/reply`, about 0.02¢ a turn), the phone speaks (`flutter_tts`). |
| Cost | counted from Gemini's usage; stops at €4 a lesson (warning colour from €3). Hello costs about 0.6¢. |
| Remembers | your name and level (beginner / some / advanced) between lessons; level also in the ⚙ menu. |
| Tools | remember_name, remember_level, show_parts_list, open_camera, take_photo, check_parts, take_closeup, take_closeup_all, skip_question, use_column (your breadboard columns shown on every step), start_building, show_step, finish_lesson, lesson_info / step_info / part_info (look-ups). Check results go to Pip as plain facts (`pip/summary.dart`). |
| Nudges | after 90 s, 3 min and 5 min of silence Pip checks in, teases a little, offers a break. |
| Speakers / headphones | on speakers Pip needs a clearer start of speech before it counts as an interruption, so its own voice doesn't cut it off. |

The 3D model (`lib/session/viewer*.dart`): an iframe on the web; on phones a web view that is handed the viewer page
and the model by the app (a web view can't accept the server's self-signed certificate).

Not tried on a real phone yet (needs Xcode / the Android SDK): echo on speakers, and the free voice's listening.

## Screens

| Screen | File | What it does |
|---|---|---|
| Connect | `lib/screens/connect.dart` | paste the server's link (address + key), saved on the phone |
| Lessons | `lib/screens/home.dart` | all lessons, search, Electronics / LEGO filter |
| Lesson | `lib/screens/lesson.dart` | the gather quests and progress |
| Quest | `lib/screens/gather.dart` | the pieces to find, tap to tick, "Scan my pieces" |
| Camera | `lib/screens/capture.dart` | live camera, up to 3 photos (or pick from the gallery) |
| Check | `lib/screens/check.dart` | scanning animation, result, close-up / "I don't have it", confetti |
| Learn with Pip | `lib/session/session.dart` | the whole lesson with Pip: stages, camera, check, steps, 3D, done |

Server calls (`lib/api.dart`): `GET /api/lessons?all=1`, `GET /api/lesson?id=`, `POST /api/upload`,
`POST /api/flow/first|closeup|dismiss`. Progress (finished quests, ticked pieces) is kept on the phone
(`lib/progress.dart`).
