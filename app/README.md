# Parts Quest app (Flutter: iPhone, Android, web)

The learner's app. For now it does the **gather step**: choose a lesson, see the pieces to find (one quest for an
electronics lesson, one every few steps or per bag for LEGO), tick them off, show them to the camera, and get the
check back. Questions the checker can't settle come back as cards: show a close-up, or say "I don't have it".

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

## Screens

| Screen | File | What it does |
|---|---|---|
| Connect | `lib/screens/connect.dart` | paste the server's link (address + key), saved on the phone |
| Lessons | `lib/screens/home.dart` | all lessons, search, Electronics / LEGO filter |
| Lesson | `lib/screens/lesson.dart` | the gather quests and progress |
| Quest | `lib/screens/gather.dart` | the pieces to find, tap to tick, "Scan my pieces" |
| Camera | `lib/screens/capture.dart` | live camera, up to 3 photos (or pick from the gallery) |
| Check | `lib/screens/check.dart` | scanning animation, result, close-up / "I don't have it", confetti |

Server calls (`lib/api.dart`): `GET /api/lessons?all=1`, `GET /api/lesson?id=`, `POST /api/upload`,
`POST /api/flow/first|closeup|dismiss`. Progress (finished quests, ticked pieces) is kept on the phone
(`lib/progress.dart`).
