// A whole lesson with Pip: hello → (electronics: parts → camera → check) → build steps → done. LEGO lessons go
// straight to the cards: gather cards (find the pieces, check them with the camera) between the build steps.
//
// Pip leads by voice and acts through the tools below (the same as the web game, code/tutor/live.py TOOL_DEFS);
// every tool is also a button, and what the learner taps is told to Pip.
import 'dart:async';
import 'dart:convert';

import 'package:camera/camera.dart';
import 'package:confetti/confetti.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:material_ui/material_ui.dart';

import '../api.dart';
import '../models.dart';
import '../pip/pip.dart';
import '../pip/pip_bar.dart';
import '../pip/summary.dart';
import '../screens/capture.dart';
import '../screens/check.dart';
import '../screens/gather.dart';
import '../theme.dart';
import '../widgets/bouncy.dart';
import '../widgets/full_frame.dart';
import 'board_guide.dart';
import 'heard.dart';
import 'theirs.dart';
import 'viewer.dart';

enum Stage { hello, parts, camera, result, build, done }

const _stageName = {
  Stage.hello: 'Hello',
  Stage.parts: 'Gather',
  Stage.camera: 'Show me',
  Stage.result: 'Check',
  Stage.build: 'Build',
  Stage.done: 'Done',
};

const _levelName = {'beginner': 'beginner', 'some': 'some experience', 'advanced': 'advanced'};

class SessionScreen extends StatefulWidget {
  const SessionScreen({super.key, required this.summary, this.startPip = true});

  final LessonSummary summary;
  final bool startPip;

  @override
  State<SessionScreen> createState() => _SessionScreenState();
}

class _SessionScreenState extends State<SessionScreen> implements PipHost {
  final _api = Api.instance;
  late final Pip pip = Pip(this)..onHeard = _heard;
  final _viewer = ViewerController();
  final _confetti = ConfettiController(duration: const Duration(seconds: 2));

  LessonDetail? _b;
  String? _loadError;
  Stage _stage = Stage.hello;

  // the check
  final List<Shot> _photos = [];
  final _visible = ValueNotifier<List<double>?>(null); // the part of the frame on screen (installed app)
  String? _lookQuestion; // the browser: Pip's look waits for the learner's photo
  Stage _lookBack = Stage.build;
  String? _upload;
  Map<String, dynamic>? _last; // the server's raw answer
  String? _working; // a check is running: what to show
  Ask? _pending; // the close-up being taken (key "*": one for all)
  final Map<String, Map<String, dynamic>> _closeupDone = {}; // a close-up the learner gave by tapping: its result for Pip
  Map<String, dynamic>? _closeupAllDone;
  int _gcard = 0; // the LEGO gather card being checked

  // the build
  int _i = 0;
  final Set<int> _done = {};
  final Map<int, Set<int>> _got = {}; // ticked pieces per card
  final Set<int> _partsGot = {};
  final Map<String, String> _cols = {}; // breadboard columns: the lesson's → the learner's (use_column)
  final Map<String, String> _swaps = {}; // their versions: "orange wire" → "blue wire" (use_instead, or the check)

  // the step check (code/validator): after a build step, a photo of the board
  final Map<String, dynamic> _where = {}; // the learner's places so far: lesson place -> theirs ("15t" -> "16t")
  bool _stepPending = false; // the browser: a step check waits for the learner's photo
  bool _checkingStep = false;
  // the live camera lines the board up by itself: a frame about once a second to the server's free check; when the
  // board is ready twice running, that frame is the photo
  bool _stepArduino = false; // the step wires to the Arduino: one photo with the board and the Arduino
  String? _hint;
  bool _ready = false;
  // the frames taken while lining up where the board was found (with how sharp each was): when the photo takes itself
  // the sharpest others go with it, so the check can read the best one and needs no retake for a blurry frame
  final List<(Shot, num)> _burst = [];
  Map<String, List<double>>? _outline; // where the outlines are drawn (fractions of the screen = of the frame sent)
  List<Shot> _burstExtras = [];
  int _okRun = 0;
  int _softRun = 0; // frames where all is fine but no (blue) Arduino was seen: after a few, take it anyway
  bool _framing = false;
  Timer? _frameTimer;
  final Set<int> _passed = {}; // build steps whose check passed: the next step waits for it
  Map<String, dynamic>? _stepResult; // the last step check, shown on its step
  int? _stepResultFor;
  DateTime _lastPhotoAt = DateTime.fromMillisecondsSinceEpoch(0); // the last photo of the parts the learner took
  Map<String, dynamic>? _lastLook;
  DateTime _lastLookAt = DateTime.fromMillisecondsSinceEpoch(0);

  // the camera, inside the session so Pip can take the photo
  CameraController? _cam;
  String? _camError;
  bool _flash = false;

  LessonSummary get s => widget.summary;
  bool get _lego => s.isLego;
  bool get _is3d => _lego && !s.isBooklet;

  @override
  String get lessonId => s.id;

  @override
  bool get busy => _working != null;

  @override
  bool get finished => _stage == Stage.done;

  late final _life = AppLifecycleListener(onResume: () => pip.wake());

  @override
  void initState() {
    super.initState();
    _life; // wake Pip when the page or app comes back to the front
    pip.addListener(_onPip);
    _load();
  }

  void _onPip() {
    if (mounted) setState(() {});
  }

  // "I'm done" opens the camera for the step check straight away (Pip did not always call check_step itself)
  int? _heardDoneFor; // the step "done" already opened the camera for

  void _heard(String line) {
    final b = _b;
    if (b == null || !mounted || _stage != Stage.build || _stepPending || _checkingStep) return;
    final n = _i + 1;
    final st = b.steps[_i];
    if (!_checkable(st) || _passed.contains(n) || _heardDoneFor == n) return;
    if (!saysDone(line)) return;
    _heardDoneFor = n;
    setState(() => _stepPending = true);
    _openCamera();  // Pip heard them too and answers by itself: no extra message (it made Pip say it all twice)
  }

  /// Another step is on the screen: Pip stops talking about the old one and is told the new one, with its words.
  void _toldStep(String how, int n) {
    final st = _b?.steps[n - 1];
    final what = st == null ? '' : ' It says: "${st.title}${st.text.isNotEmpty ? ': ${st.text}' : ''}".';
    pip.moveOn('($how: the screen now shows ${_lego ? 'card' : 'step'} $n.$what Talk only about this one now; '
        'forget what you were saying about the other step.)');
  }

  @override
  void dispose() {
    _frameTimer?.cancel();
    _life.dispose();
    pip.removeListener(_onPip);
    pip.dispose();
    _cam?.dispose();
    _confetti.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final b = await _api.lesson(s.id);
      if (!mounted) return;
      setState(() => _b = b);
      // everything for the lesson now, so no step waits: the booklet pictures (and the 3D model, when it is shown)
      for (final p in b.pictures) {
        precacheImage(NetworkImage(_api.link(p)), context).catchError((_) {});
      }
      if (widget.startPip) _startPip();
    } catch (e) {
      if (mounted) setState(() => _loadError = e is ApiError ? e.message : '$e');
    }
  }

  void _startPip() => pip.start();

  // ---------------------------------------------------------------- what Pip is told
  @override
  String situation() {
    final who = Pip.name.isEmpty ? 'with a new learner' : 'with ${Pip.name}';
    final where = _stage == Stage.build && _b != null ? ', ${_lego ? 'card' : 'step'} ${_i + 1}' : '';
    return '(Session $who. The screen shows: ${_stageName[_stage]}$where. They give photos with the phone camera.)';
  }

  void _tell(String text) => pip.tell(text);

  // ---------------------------------------------------------------- the tools (Pip, or a tap)
  @override
  Future<Map<String, dynamic>> runTool(String name, Map<String, dynamic> args) async {
    switch (name) {
      case 'remember_name':
        Pip.name = '${args['name'] ?? ''}'.trim().split(RegExp(r'\s+')).take(3).join(' ');
        await Pip.saveMe();
        setState(() {});
        return {'remembered': Pip.name};
      case 'remember_level':
        Pip.level = const ['beginner', 'some', 'advanced'].contains(args['level']) ? '${args['level']}' : 'beginner';
        await Pip.saveMe();
        setState(() {});
        return {'remembered': Pip.level};
      case 'show_parts_list':
        _go(Stage.parts);
        return {'shown': true, 'parts': [for (final p in s.parts) '${p.count}x ${p.what}']};
      case 'open_camera':
        await _openCamera();
        if (kIsWeb) return {'camera': 'ready', 'tell_them': 'tap Take photo: their phone camera opens full screen; one clear photo from above is enough'};
        return _cam != null ? {'mode': 'camera', 'camera': 'open'} : {'camera': 'not available', 'tell_them': 'they can pick photos from the gallery'};
      case 'take_photo':
        if (_stage != Stage.camera) await _openCamera();
        if (kIsWeb && _photos.isNotEmpty && DateTime.now().difference(_lastPhotoAt).inSeconds < 90) {
          return {'photos': _photos.length, 'note': 'they have already taken ${_photos.length} photo(s): do not ask for more; check when they say they are done or tap Check'};
        }
        if (kIsWeb) return {'photos': _photos.length, 'waiting': 'In the browser they take the photo themselves: ask them to tap Take photo (their phone camera opens). The result comes to you as soon as they have.'};
        final p = await _snap();
        if (p == null) return {'error': 'the camera is not ready yet; try again in a second'};
        setState(() => _photos.add(p));
        return {'photos': _photos.length};
      case 'check_parts':
        return _checkParts();
      case 'take_closeup':
        final key = '${args['key'] ?? ''}';
        final done = _closeupDone.remove(key);
        if (done != null) return done;
        final asks = _asks;
        final q = asks.where((a) => a.key == key).firstOrNull ?? asks.firstOrNull;
        if (q == null) return {'error': 'no open question with that key', 'open_questions': [for (final a in asks) a.key]};
        _pending = q;
        if (_stage != Stage.camera) await _openCamera();
        if (kIsWeb) return {'waiting': 'In the browser they take the photo themselves: ask them to tap Take photo (their phone camera opens). The result comes to you as soon as they have.'};
        await Future<void>.delayed(const Duration(milliseconds: 300));
        final p = await _snap();
        if (p == null) return {'error': 'the camera is not ready; try again'};
        return _closeupWith(q.key, p);
      case 'take_closeup_all':
        if (_closeupAllDone != null) {
          final r = _closeupAllDone!;
          _closeupAllDone = null;
          return r;
        }
        if (_asks.isEmpty) return {'error': 'no open questions'};
        _pending = Ask(key: '*', kind: 'closeup', message: 'All ${_asks.length} together: hold them up close in one photo');
        if (_stage != Stage.camera) await _openCamera();
        if (kIsWeb) return {'waiting': 'In the browser they take the photo themselves: ask them to tap Take photo (their phone camera opens). The result comes to you as soon as they have.'};
        await Future<void>.delayed(const Duration(milliseconds: 300));
        final p = await _snap();
        if (p == null) return {'error': 'the camera is not ready; try again'};
        return _closeupWith('*', p);
      case 'skip_question':
        try {
          final st = await _api.flow('dismiss', {'upload': _upload, 'key': args['key']});
          _show(st);
          _go(Stage.result);
          return _told(st);
        } catch (e) {
          return {'error': '$e'};
        }
      case 'use_column':
        final a = int.tryParse('${args['lesson']}'), b = int.tryParse('${args['theirs']}');
        if (a == null || b == null) return {'error': 'give two column numbers'};
        setState(() => a == b ? _cols.remove('$a') : _cols['$a'] = '$b');
        return {'columns': _cols, 'note': 'the step cards now show their columns'};
      case 'use_instead':
        final a = '${args['lesson'] ?? ''}'.trim(), b = '${args['theirs'] ?? ''}'.trim();
        if (a.isEmpty || b.isEmpty) return {'error': 'say what the lesson uses and what they use'};
        setState(() => a.toLowerCase() == b.toLowerCase() ? _swaps.remove(a.toLowerCase()) : _swaps[a.toLowerCase()] = b);
        return {'their_versions': _swaps, 'note': 'the step cards now show theirs; call it their way from now on'};
      case 'look':
        final back = _stage;
        if (kIsWeb && _lastLook != null && DateTime.now().difference(_lastLookAt).inSeconds < 60) {
          final r = _lastLook!;
          _lastLook = null;
          return r;
        }
        if (kIsWeb) {
          _lookBack = back;
          setState(() => _lookQuestion = '${args['question'] ?? 'What is this?'}');
          if (_stage != Stage.camera) await _openCamera();
          return {'waiting': 'In the browser they take the photo themselves: ask them to tap Take photo (their phone camera opens). The result comes to you as soon as they have.'};
        }
        if (_stage != Stage.camera) await _openCamera();
        await Future<void>.delayed(const Duration(milliseconds: 600));
        final p = await _snap();
        if (p == null) return {'error': 'the camera is not ready; try again'};
        setState(() => _working = 'Having a look…');
        try {
          return await _api.look(s.id, p, '${args['question'] ?? 'What is this?'}');
        } catch (e) {
          return {'error': e is ApiError ? e.message : '$e'};
        } finally {
          if (mounted) {
            setState(() => _working = null);
            if (back != Stage.camera) _go(back == Stage.result && _last == null ? Stage.build : back);
          }
        }
      case 'check_step':
        if (_stepPending && _stage == Stage.camera) {  // already open (they said "done", or tapped): just wait
          return {'waiting': 'The camera is already open for this step: say at most one short sentence (hold the phone '
              'over the board; the photo takes itself), then wait for the result. Do not read the step again.'};
        }
        final cur = _b?.steps[_i];
        if (cur == null || _stage != Stage.build || !_checkable(cur)) {
          return {'note': 'show the build step first (show_step); a step that puts nothing on the board has nothing to check'};
        }
        if (_checkingStep) {
          return {'status': 'checking the photo they just took: the result comes to you in a few seconds; do not ask for another photo'};
        }
        setState(() => _stepPending = true);
        await _openCamera();
        return {
          'waiting': 'NO PHOTO YET, so there is no result: say nothing about how the step looks. The camera is open '
              'with an outline on it (the board, and the Arduino when this step wires to it): ask them to hold the phone '
              'straight above so the board fills the outline; the photo is taken by itself when the board is clear '
              '(or they tap the white button). Then wait: the result comes to you as soon as it is taken.'
        };
      case 'tell_places':
        final places = <String, dynamic>{
          for (final x in (args['places'] as List? ?? const []).cast<Map>())
            '${x['key']}': {for (final f in const ['column', 'half', 'pin', 'rail']) if (x[f] != null) f: x[f]}
        };
        if (places.isEmpty) return {'error': 'give the leg keys and where they are'};
        return _tellPlaces(places);
      case 'start_building':
        return {'step': _showStep(1), 'steps': _b?.steps.length ?? 0};
      case 'show_step':
        final want = int.tryParse('${args['n']}') ?? 1;
        if (_stage == Stage.camera && _stepPending && want == _i + 1) {  // its check is under way: stay on the camera
          return {'screen_shows_step': want, 'note': 'the camera is open for this step\'s check: wait for the result; do not read the step again'};
        }
        final stop = _uncheckedBefore(want);
        if (stop != null) {
          _showStep(stop);
          return {'screen_shows_step': stop, 'note': 'step $stop has not been checked yet: it must be checked (check_step) before going on'};
        }
        return {'screen_shows_step': _showStep(want)};
      case 'lesson_info' || 'step_info' || 'part_info':
        try {
          final r = await _api.lookup(s.id, name, args);
          return r is Map<String, dynamic> ? r : {'result': r};
        } catch (e) {
          return {'error': '$e'};
        }
      case 'finish_lesson':
        _finish();
        return {'finished': true};
    }
    return {'error': 'unknown tool $name'};
  }

  /// A check result for Pip: the facts, and the learner's versions the check found (their wire colours).
  Map<String, dynamic> _told(Map<String, dynamic> st) {
    final wires = [for (final p in s.parts) if ((p.type ?? '').contains('wire')) ...p.values];
    final found = wireSwaps(wires, st);
    final added = {for (final e in found.entries) if (!_swaps.containsKey(e.key)) e.key: e.value};
    if (added.isNotEmpty) setState(() => _swaps.addAll(added));
    return {
      ...summary(st),
      if (_swaps.isNotEmpty) 'their_versions': _swaps,
      if (added.isNotEmpty)
        'note': 'Their wires are other colours: the step cards now say ${added.values.join(' and ')}. '
            'Tell them any colour works, and call each wire their way from now on.',
    };
  }

  List<Ask> get _asks => [for (final a in (_last?['asks'] as List? ?? const [])) Ask.fromJson(a as Map<String, dynamic>)];

  void _go(Stage st) {
    if (_stage == st) return;
    if (_stage == Stage.camera && st != Stage.camera) _stopCamera();
    setState(() => _stage = st);
  }

  void _show(Map<String, dynamic> st) {
    final r = CheckResult.fromJson(st);
    setState(() {
      _last = st;
      _working = null;
      // what the check found gets its tick on the list (what it did not find stays for the learner)
      if (_lego && _gcard > 0 && _b != null) {
        _got.putIfAbsent(_gcard, () => {}).addAll(foundPieces(r, _b!.steps[_gcard - 1].parts, lego: true));
      } else if (!_lego) {
        _partsGot.addAll(foundPieces(r, s.parts, lego: false));
      }
    });
    if (r.allFound && r.asks.isEmpty) {
      HapticFeedback.heavyImpact();
      _confetti.play();
    }
  }

  Future<Map<String, dynamic>> _checkParts() async {
    final card = _lego ? _gcard : null;
    if (_lego && (card == 0 || _b == null || !_b!.steps[card! - 1].isGather)) return {'error': 'show a gather card first (show_step)'};
    if (_photos.isEmpty) return {'error': 'no photos yet: take one first'};
    setState(() {
      _working = _lego ? 'Looking at your pieces…' : 'Looking at your parts…';
      _last = null;
    });
    _go(Stage.result);
    try {
      _upload = await _api.upload(s.id, _photos);
      final st = await _api.flow('first', {'upload': _upload, 'lesson': s.id, 'card': ?card});
      _show(st);
      return _told(st);
    } catch (e) {
      setState(() => _working = null);
      return {'error': e is ApiError ? e.message : '$e'};
    }
  }

  Future<Map<String, dynamic>> _closeupWith(String key, Shot photo) async {
    setState(() {
      _pending = null;
      _working = 'Looking at your close-up…';
    });
    _go(Stage.result);
    try {
      final st = await _api.flow(key == '*' ? 'closeup_all' : 'closeup',
          {'upload': _upload, 'photo': Api.dataUrl(photo.bytes), 'crop': ?photo.cropOrNull, if (key != '*') 'key': key});
      _show(st);
      return _told(st);
    } catch (e) {
      setState(() => _working = null);
      return {'error': e is ApiError ? e.message : '$e'};
    }
  }

  int _showStep(int n) {
    final b = _b;
    if (b == null || b.steps.isEmpty) return 0;
    n = n.clamp(1, b.steps.length);
    final st = b.steps[n - 1];
    final find = _lego && st.isGather;
    if (find && _gcard != n) {
      _gcard = n;
      _photos.clear();
      _upload = null;
      _last = null;
      _pending = null;
    }
    _go(Stage.build);
    setState(() => _i = n - 1);
    if (_is3d) {
      // a build step: its own step in the viewer, played; a gather card: the model so far, still
      final next = b.steps.skip(n - 1).where((x) => !x.isGather).firstOrNull;
      final k = next?.ownNumber ?? 1;
      final first = find && !b.steps.take(n - 1).any((x) => !x.isGather);
      _viewer.send(first
          ? {'step': 9999, 'play': false, 'whole': true}
          : find
              ? {'step': k > 1 ? k - 1 : 1, 'play': false}
              : {'step': st.ownNumber ?? 1, 'play': true});
    }
    return n;
  }

  void _finish() {
    final b = _b;
    if (b != null) {
      for (var k = 1; k <= b.steps.length; k++) {
        _done.add(k);
      }
    }
    _go(Stage.done);
    HapticFeedback.heavyImpact();
    _confetti.play();
  }

  // ---------------------------------------------------------------- the camera
  Future<void> _openCamera() async {
    _go(Stage.camera);
    if (_stepPending) _startFraming();
    // the browser: the phone's own camera app, opened by a tap; but the live camera for a step check, to show the
    // outline the board should fill
    if (_cam != null || (kIsWeb && !_stepPending)) return;
    setState(() => _camError = null);
    try {
      final cams = await availableCameras();
      if (cams.isEmpty) throw CameraException('none', 'No camera on this device');
      final back = pickBackCamera(cams);
      final c = CameraController(back, ResolutionPreset.max, enableAudio: false, imageFormatGroup: ImageFormatGroup.jpeg);
      await c.initialize();
      try {
        await c.setFocusMode(FocusMode.auto);
      } catch (_) {}
      if (!mounted || _stage != Stage.camera) {
        await c.dispose();
        return;
      }
      setState(() {
        _cam = c;
        _camError = null;
      });
    } catch (e) {
      if (mounted) setState(() => _camError = e is CameraException ? (e.description ?? e.code) : '$e');
    }
  }

  void _startFraming() {
    _frameTimer?.cancel();
    _okRun = 0;
    _softRun = 0;
    _ready = false;
    _hint = 'Line the board up with the outline';
    _burst.clear();
    _burstExtras = [];
    _api.validateShots(s.id, _i + 1).then((x) {
      if (mounted) setState(() => _stepArduino = x.contains('arduino'));
    }).catchError((_) {});
    _frameTimer = Timer.periodic(const Duration(milliseconds: 800), (_) => _frameTick());
  }

  Future<void> _frameTick() async {
    final c = _cam;
    if (_framing || c == null || !c.value.isInitialized || !_stepPending || _checkingStep || _stage != Stage.camera) return;
    _framing = true;
    try {
      final shot = Shot(await (await c.takePicture()).readAsBytes(), _visible.value);
      final r = await _api.validateFrame(shot, arduino: _stepArduino, outline: _outline);
      if (!mounted || !_stepPending || _checkingStep) return;
      _softRun = r['soft'] == true ? _softRun + 1 : 0;
      final ok = r['ok'] == true || _softRun >= 3;
      _okRun = ok ? _okRun + 1 : 0;
      if ((r['measure'] as Map?)?['fill'] != null) {  // the board's holes were found in this frame
        _burst.add((shot, ((r['measure'] as Map?)?['sharp'] as num?) ?? 0));
        if (_burst.length > 4) _burst.removeAt(0);
      }
      setState(() {
        _ready = ok;
        _hint = _okRun >= 1 ? 'Got it!' : '${r['hint'] ?? ''}';
      });
      if (_okRun >= 1) {  // one clear frame is enough: the frames before it go along as spares
        _frameTimer?.cancel();
        _burstExtras = ([..._burst.where((b) => !identical(b.$1, shot))]..sort((a, b) => b.$2.compareTo(a.$2)))
            .take(2)
            .map((b) => b.$1)
            .toList();
        HapticFeedback.mediumImpact();
        setState(() => _flash = true);
        Future.delayed(const Duration(milliseconds: 140), () {
          if (mounted) setState(() => _flash = false);
        });
        await _gotPhoto(shot);
      }
    } catch (_) {
      // a frame that could not be taken or checked: the next one tries again
    } finally {
      _framing = false;
    }
  }

  void _stopCamera() {
    _frameTimer?.cancel();
    _frameTimer = null;
    _hint = null;
    _ready = false;
    _burst.clear();
    final c = _cam;
    _cam = null;
    c?.dispose();
    if (kIsWeb && c != null) pip.wake(); // the browser's camera can take the sound and the mic with it
  }

  Future<Shot?> _snap() async {
    final c = _cam;
    if (c == null || !c.value.isInitialized) return null;
    HapticFeedback.mediumImpact();
    setState(() => _flash = true);
    try {
      return Shot(await (await c.takePicture()).readAsBytes(), _visible.value);
    } catch (_) {
      return null;
    } finally {
      if (mounted) setState(() => _flash = false);
    }
  }

  /// The shutter, tapped: a close-up goes straight to the check; a photo of the parts joins the others.
  /// (_snap is the installed app's live camera; the browser takes photos with the phone's camera app.)
  Future<void> _shutter() async {
    final p = await _snap();
    if (p == null) return;
    await _gotPhoto(p);
  }

  /// A build step on an electronics lesson that puts something on the board: it can be checked from a photo.
  bool _checkable(LessonStep st) => !_lego && !st.isGather && st.kind != 'upload' && st.parts.isNotEmpty;

  /// The step check: the photo to the server, the verdict on the step card, their columns from now on.
  Future<Map<String, dynamic>> _validateStep(Shot photo) async =>
      _runStepCheck(() {
        final extras = _burstExtras; // frames from lining up, when the photo took itself
        _burstExtras = [];
        _burst.clear();
        return _api.validateStep(s.id, _i + 1, [photo, ...extras], {'where': _where});
      });

  /// What the learner says about the legs the photo could not show, judged like a photo.
  Future<Map<String, dynamic>> _tellPlaces(Map<String, dynamic> places) async {
    final last = _stepResultFor == _i + 1 ? _stepResult : null;
    final readings = ((last?['readings'] as Map?) ?? const {}).cast<String, dynamic>();
    final before = ((last?['before'] as Map?) ?? {'where': Map<String, dynamic>.of(_where)}).cast<String, dynamic>();
    return _runStepCheck(() => _api.validateTold(s.id, _i + 1, before, readings, places));
  }

  Future<Map<String, dynamic>> _runStepCheck(Future<Map<String, dynamic>> Function() call) async {
    final n = _i + 1;
    if (_checkingStep) return {'status': 'already checking this step'};
    final before = {'where': Map<String, dynamic>.of(_where)}; // the places before this step (for a told answer)
    setState(() {
      _stepPending = false;
      _checkingStep = true;
      _stepResult = null;
      _stepResultFor = n;
    });
    _go(Stage.build);
    try {
      final r = {...await call(), 'before': before};
      final where = ((r['state'] as Map?)?['where'] as Map?)?.cast<String, dynamic>() ?? {};
      final cols = (r['columns'] as Map?)?.cast<String, dynamic>() ?? {};
      final ok = const ['pass', 'harmless', 'moved'].contains(r['verdict']);
      setState(() {
        if (ok) {  // only a step that passed changes the learner's places
          _where
            ..clear()
            ..addAll(where);
          for (final e in cols.entries) {
            _cols[e.key] = '${e.value}';
          }
          _passed.add(n);
          _done.add(n);
        }
        _stepResult = r;
      });
      ok ? HapticFeedback.mediumImpact() : HapticFeedback.heavyImpact();
      return {
        'verdict': r['verdict'],
        'say': r['say'],
        'legs': [
          for (final l in (r['legs'] as List? ?? const []).cast<Map>())
            {'key': l['key'], 'what': l['who'], 'status': l['status'], 'where': l['place'],
              if ('${l['words']}'.isNotEmpty) 'note': l['words']}
        ],
        if (cols.isNotEmpty && ok) 'their_columns': cols,
        if ((r['asks'] as List? ?? const []).isNotEmpty) 'tell_them': [for (final a in (r['asks'] as List).cast<Map>()) a['message']],
        if (r['verdict'] == 'unsure') 'next': 'ask them where those legs are, then call tell_places with the keys',
      };
    } catch (e) {
      setState(() => _stepResult = {'verdict': 'error', 'say': e is ApiError ? e.message : '$e'});
      return {'error': e is ApiError ? e.message : '$e'};
    } finally {
      if (mounted) setState(() => _checkingStep = false);
    }
  }

  /// The first build step that must still be checked before going past it (null: none before `n`).
  int? _uncheckedBefore(int n) {
    final b = _b;
    if (b == null) return null;
    for (var k = 1; k < n && k <= b.steps.length; k++) {
      if (_checkable(b.steps[k - 1]) && !_passed.contains(k)) return k;
    }
    return null;
  }

  Future<void> _gotPhoto(Shot p) async {
    pip.wake(); // back from the phone's camera app: the browser paused Pip's sound, mic and connection
    if (_stepPending) {
      final r = await _validateStep(p);
      pip.tell('(The step check of the photo they have just taken: ${jsonEncode(r)}. Tell them what it means.)', now: true);
      return;
    }
    final look = _lookQuestion;
    if (look != null) {
      setState(() {
        _lookQuestion = null;
        _working = 'Having a look…';
      });
      Map<String, dynamic> r;
      try {
        r = await _api.look(s.id, p, look);
      } catch (e) {
        r = {'error': e is ApiError ? e.message : '$e'};
      }
      if (!mounted) return;
      setState(() => _working = null);
      _lastLook = r;
      _lastLookAt = DateTime.now();
      _go(_lookBack == Stage.camera || (_lookBack == Stage.result && _last == null) ? Stage.build : _lookBack);
      _tell('(You asked to look: "$look". The photo shows: ${jsonEncode(r)}. Tell them, in your own words.)');
      return;
    }
    final q = _pending;
    if (q != null) {
      final r = await _closeupWith(q.key, p);
      if (q.key == '*') {
        _closeupAllDone = r;
      } else {
        _closeupDone[q.key] = r;
      }
      _tell('(The learner took the close-up${q.key == '*' ? ' of all of them' : ' for key ${q.key}'} themselves: '
          'here is the new result: ${_told(_last ?? {})}. Tell them what it means.)');
      return;
    }
    setState(() => _photos.add(p));
    _lastPhotoAt = DateTime.now();
    _tell('(The learner added a photo of the parts: ${_photos.length} so far. They may take more: do not check yet, '
        'and do not ask for another photo. Wait until they tap Check or say they are done.)');
  }

  /// The phone's own camera app: full screen, its autofocus, full quality.
  Future<void> _phoneCamera() async {
    final shot = await phoneCameraShot();
    if (shot != null) await _gotPhoto(shot);
  }

  Future<void> _gallery() async {
    final one = _pending != null || _lookQuestion != null;
    final shots = await galleryShots(one ? 1 : 3 - _photos.length);
    if (shots.isEmpty) return;
    if (one) return _gotPhoto(shots.first);
    setState(() => _photos.addAll(shots));
    _tell('(The learner picked ${shots.length} photo(s) from the gallery: ${_photos.length} so far.)');
  }

  Future<void> _checkTapped() async {
    if (pip.on) {
      _tell('(The learner tapped Check: call check_parts now.)');
    } else {
      await _checkParts();
    }
  }

  // ---------------------------------------------------------------- the screen
  @override
  Widget build(BuildContext context) {
    final c = Pq.forLesson(s);
    // the live camera fills the whole screen, like the phone's camera app (no title bar, no Pip bar: Pip still talks)
    final full = _stage == Stage.camera && !(kIsWeb && (!_stepPending || _camError != null));
    return PopScope(
      onPopInvokedWithResult: (_, _) => pip.stop(),
      child: Scaffold(
        backgroundColor: full ? Colors.black : null,
        appBar: full ? null : AppBar(
          title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(s.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.titleMedium),
            Text(Pip.name.isEmpty ? Pq.kindLabel(s) : 'Hi, ${Pip.name}${Pip.level.isEmpty ? '' : ' · ${_levelName[Pip.level]}'}',
                style: TextStyle(fontSize: 12, color: c, fontWeight: FontWeight.w700)),
          ]),
          actions: [_Menu(pip: pip, onLevel: _setLevel)],
        ),
        body: Stack(children: [
          Column(children: [
            if (_stage != Stage.camera) _Track(stage: _stage, lego: _lego, color: c),
            Expanded(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 320),
                switchInCurve: Curves.easeOutCubic,
                transitionBuilder: (w, a) => FadeTransition(
                  opacity: a,
                  child: SlideTransition(position: Tween(begin: const Offset(0.04, 0), end: Offset.zero).animate(a), child: w),
                ),
                child: KeyedSubtree(key: ValueKey(_stage), child: _body(c)),
              ),
            ),
            if (!full) PipBar(pip: pip, onStart: _startPip),
          ]),
          Align(
            alignment: Alignment.topCenter,
            child: ConfettiWidget(
              confettiController: _confetti,
              blastDirectionality: BlastDirectionality.explosive,
              numberOfParticles: 30,
              gravity: 0.25,
              colors: const [Pq.electronics, Pq.lego, Pq.booklet, Pq.have, Pq.swap],
            ),
          ),
        ]),
      ),
    );
  }

  void _setLevel(String v) async {
    Pip.level = v;
    await Pip.saveMe();
    setState(() {});
    _tell(v.isEmpty ? '(The learner wants you to ask their level again.)'
        : '(The learner set their level to ${_levelName[v]}: change your pace to suit it from now on.)');
  }

  Widget _body(Color c) {
    if (_loadError != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(32), child: Text("Couldn't load the lesson.\n$_loadError", textAlign: TextAlign.center)));
    }
    if (_b == null) return const Center(child: CircularProgressIndicator());
    return switch (_stage) {
      Stage.hello => _hello(c),
      Stage.parts => _parts(c),
      Stage.camera => _camera(c),
      Stage.result => _result(c),
      Stage.build => _build(c),
      Stage.done => _doneView(c),
    };
  }

  Widget _hello(Color c) {
    final t = Theme.of(context).textTheme;
    final b = _b!;
    final pieces = _lego
        ? b.gatherCards.fold<int>(0, (a, g) => a + g.pieceCount)
        : s.parts.fold<int>(0, (a, p) => a + p.count);
    return ListView(padding: const EdgeInsets.all(20), children: [
      Center(child: Orb(state: pip.state, size: 110)).animate().scale(curve: Curves.elasticOut, duration: 900.ms),
      const SizedBox(height: 22),
      Text(Pip.name.isEmpty ? 'Meet Pip, your tutor' : 'Welcome back, ${Pip.name}!',
          textAlign: TextAlign.center, style: t.headlineMedium),
      const SizedBox(height: 8),
      Text(
        _lego
            ? 'Grab your set. Pip will tell you which pieces to find for each step, and how they go together.'
            : 'Pip will help you gather $pieces parts, check them with the camera, then build it with you step by step.',
        textAlign: TextAlign.center,
        style: t.bodyLarge?.copyWith(color: Pq.muted, height: 1.4),
      ),
      const SizedBox(height: 18),
      Wrap(alignment: WrapAlignment.center, spacing: 8, runSpacing: 8, children: [
        _Pill(icon: Icons.layers_rounded, text: '${b.steps.length} ${_lego ? 'cards' : 'steps'}', color: c),
        _Pill(icon: Icons.extension_rounded, text: '$pieces ${_lego ? 'pieces' : 'parts'}', color: c),
        if (b.pictures.isNotEmpty) _Pill(icon: Icons.image_rounded, text: '${b.pictures.length} booklet pictures', color: c),
        if (_is3d) _Pill(icon: Icons.view_in_ar_rounded, text: '3D model', color: c),
      ]),
      const SizedBox(height: 28),
      if (!pip.on)
        BigButton(label: 'Start with Pip', icon: Icons.graphic_eq_rounded, color: c, onTap: _startPip),
      const SizedBox(height: 10),
      Center(
        child: TextButton(
          onPressed: () => _lego ? runTool('start_building', {}) : runTool('show_parts_list', {}),
          child: const Text('Go on without talking'),
        ),
      ),
    ]);
  }

  Widget _parts(Color c) {
    final t = Theme.of(context).textTheme;
    return Stack(children: [
      ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 100), children: [
        Text('Put these on the table', style: t.headlineMedium),
        const SizedBox(height: 4),
        Text('${_partsGot.length} / ${s.parts.length} ticked', style: const TextStyle(color: Pq.muted)),
        const SizedBox(height: 12),
        for (var i = 0; i < s.parts.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: PieceRow(
              piece: s.parts[i],
              got: _partsGot.contains(i),
              expanded: false,
              accent: c,
              onTick: () {
                HapticFeedback.lightImpact();
                setState(() => _partsGot.contains(i) ? _partsGot.remove(i) : _partsGot.add(i));
                if (_partsGot.length == s.parts.length) _tell('(The learner ticked every part: everything is on the table.)');
              },
            ),
          ).animate().fadeIn(delay: (40 * i).ms).slideY(begin: 0.15),
      ]),
      _bottom(BigButton(
        label: "Everything's on the table",
        icon: Icons.photo_camera_rounded,
        color: c,
        onTap: () {
          if (pip.on) {
            _tell('(The learner tapped: everything is on the table.)');
          } else {
            _openCamera();
          }
        },
      )),
    ]);
  }

  Widget _camera(Color c) {
    final q = _pending;
    final what = _stepPending
        ? (_stepArduino
            ? 'The breadboard and the Arduino in the outlines: it takes the photo by itself'
            : 'Straight above, the breadboard in the outline: it takes the photo by itself')
        : _lookQuestion != null
        ? 'Hold it up so Pip can see it'
        : q != null
            ? 'Close-up: ${q.message}'
            : _lego
                ? 'Lay the pieces flat, a little apart'
                : 'Lay the parts out so I can see them all';
    final thumbs = _photos.isNotEmpty && q == null && _lookQuestion == null && !_stepPending;
    final checkBtn = q == null && _lookQuestion == null && !_stepPending;
    return kIsWeb && (!_stepPending || _camError != null)
        ? _cameraBrowser(c, what, thumbs, checkBtn)
        : _cameraLive(c, what, thumbs, checkBtn);
  }

  /// A phone's browser: the phone's own camera app takes the photo (full screen, its focus, full quality).
  Widget _cameraBrowser(Color c, String what, bool thumbs, bool checkBtn) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
        child: Column(children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: (_pending != null || _lookQuestion != null ? Pq.check : c).withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Text(what, textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          ),
          Expanded(
            child: thumbs
                ? GridView.count(
                    padding: const EdgeInsets.only(top: 14),
                    crossAxisCount: 2,
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    children: [
                      for (var i = 0; i < _photos.length; i++)
                        Stack(fit: StackFit.expand, children: [
                          ClipRRect(borderRadius: BorderRadius.circular(16), child: Image.memory(_photos[i].bytes, fit: BoxFit.cover)),
                          Positioned(
                            right: 6,
                            top: 6,
                            child: GestureDetector(
                              onTap: () => setState(() => _photos.removeAt(i)),
                              child: const CircleAvatar(radius: 14, backgroundColor: Colors.white, child: Icon(Icons.close_rounded, size: 16, color: Pq.ink)),
                            ),
                          ),
                        ]).animate().scale(curve: Curves.easeOutBack, duration: 300.ms),
                    ],
                  )
                : _stepPending
                    ? const SingleChildScrollView(padding: EdgeInsets.only(top: 14), child: BoardGuide())
                    : Center(
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.photo_camera_rounded, size: 72, color: c)
                          .animate(onPlay: (a) => a.repeat(reverse: true))
                          .scale(begin: const Offset(0.94, 0.94), end: const Offset(1.05, 1.05), duration: 1100.ms),
                      const SizedBox(height: 12),
                      const Text("Your phone's camera opens full screen.\nOne clear photo is enough.",
                          textAlign: TextAlign.center, style: TextStyle(color: Pq.muted, height: 1.4)),
                    ]),
                  ),
          ),
          const SizedBox(height: 12),
          // one clear photo is enough: once there is one, checking is the big button
          if (thumbs && checkBtn)
            BigButton(label: 'Check (${_photos.length})', icon: Icons.check_rounded, color: Pq.have, onTap: _checkTapped)
          else
            BigButton(label: 'Take photo', icon: Icons.photo_camera_rounded, color: c, onTap: _phoneCamera),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: SoftButton(label: 'From gallery', icon: Icons.photo_library_rounded, onTap: _gallery)),
            const SizedBox(width: 10),
            Expanded(
              child: thumbs && checkBtn
                  ? SoftButton(label: 'Add another', icon: Icons.add_a_photo_rounded, onTap: _photos.length >= 3 ? null : _phoneCamera)
                  : !checkBtn
                      ? SoftButton(
                          label: 'Cancel',
                          icon: Icons.close_rounded,
                          color: Pq.muted,
                          onTap: () {
                            setState(() {
                              _pending = null;
                              _lookQuestion = null;
                              _stepPending = false;
                            });
                            if (_b != null && _stage == Stage.camera) _go(Stage.build);
                          },
                        )
                      : const SizedBox.shrink(),
            ),
          ]),
        ]),
      );

  /// The installed app: the camera live and filling the screen; the photo is cropped to what was on it.
  Widget _cameraLive(Color c, String what, bool thumbs, bool checkBtn) {
    final cam = _cam;
    return Container(
      color: Colors.black,
      child: SafeArea(child: Stack(fit: StackFit.expand, children: [
        if (cam != null && cam.value.isInitialized)
          CameraFill(controller: cam, visible: _visible, overlay: _stepPending ? BoardOutline(arduino: _stepArduino, hint: _hint, ready: _ready, onOutline: (o) => _outline = o) : null)
        else
          Center(
            child: _camError == null
                ? const CircularProgressIndicator(color: Colors.white)
                : Padding(
                    padding: const EdgeInsets.all(28),
                    child: Text("The camera isn't available here: $_camError\nPick photos from the gallery instead.",
                        textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70)),
                  ),
          ),
        IgnorePointer(child: AnimatedOpacity(opacity: _flash ? 0.8 : 0, duration: 90.ms, child: const ColoredBox(color: Colors.white))),
        const Positioned(top: 0, left: 0, right: 0, height: 120, child: IgnorePointer(child: Shade(top: true))),
        const Positioned(bottom: 0, left: 0, right: 0, height: 220, child: IgnorePointer(child: Shade(top: false))),
        Positioned(
          top: 12,
          left: 16,
          right: 16,
          child: Text(what,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 15, shadows: [Shadow(blurRadius: 8, color: Colors.black54)])),
        ),
        if (kIsWeb && _stepPending)
          Positioned(
            top: 34,
            right: 4,
            child: TextButton.icon(
              onPressed: _phoneCamera,
              style: TextButton.styleFrom(foregroundColor: Colors.white70),
              icon: const Icon(Icons.photo_camera_outlined, size: 18),
              label: const Text('Phone camera'),
            ),
          ),
        Positioned(
          left: 0,
          right: 0,
          bottom: 12,
          child: Column(children: [
            if (thumbs)
              SizedBox(
                height: 56,
                child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 16), children: [
                  for (var i = 0; i < _photos.length; i++)
                    Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: GestureDetector(
                        onTap: () => setState(() => _photos.removeAt(i)),
                        child: ClipRRect(borderRadius: BorderRadius.circular(10), child: Image.memory(_photos[i].bytes, width: 56, height: 56, fit: BoxFit.cover)),
                      ),
                    ),
                ]),
              ),
            const SizedBox(height: 10),
            Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
              _RoundBtn(icon: Icons.photo_library_rounded, label: 'Photos', onTap: _gallery),
              Bouncy(
                onTap: cam == null ? null : _shutter,
                scale: 0.88,
                child: Container(
                  width: 76,
                  height: 76,
                  padding: const EdgeInsets.all(5),
                  decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 5)),
                  child: const DecoratedBox(decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white)),
                ),
              ),
              checkBtn
                  ? _RoundBtn(
                      icon: Icons.check_rounded,
                      label: _photos.isEmpty ? 'Check' : 'Check (${_photos.length})',
                      color: _photos.isEmpty ? null : Pq.have,
                      onTap: _photos.isEmpty ? null : _checkTapped,
                    )
                  : _RoundBtn(
                      icon: Icons.close_rounded,
                      label: 'Cancel',
                      onTap: () {
                        final step = _stepPending;
                        setState(() {
                          _pending = null;
                          _stepPending = false;
                        });
                        if (step && _b != null) _go(Stage.build); // back to the step (and the camera off)
                      }),
            ]),
          ]),
        ),
      ])),
    );
  }

  Widget _result(Color c) {
    if (_working != null || _last == null) {
      return _photos.isEmpty
          ? Center(child: Text(_working ?? 'No check yet.', style: Theme.of(context).textTheme.titleLarge))
          : ScanningView(photo: _photos.first.bytes, lego: _lego);
    }
    final r = CheckResult.fromJson(_last!);
    return Stack(children: [
      ResultsView(
        result: r,
        accent: c,
        busyAsk: null,
        bottom: 100,
        onCloseup: (a) {
          _pending = a;
          _openCamera();
          _tell('(The learner opened the camera for the close-up, key ${a.key}: call take_closeup when they say they are holding it up.)');
        },
        onCloseupAll: () {
          _pending = Ask(key: '*', kind: 'closeup', message: 'All ${r.asks.length} together: hold them up close in one photo');
          _openCamera();
          _tell('(The learner opened the camera for one close-up of all the parts asked about: call take_closeup_all when they say they are ready.)');
        },
        onDismiss: (a) {
          if (pip.on) {
            _tell('(The learner tapped "I don\'t have it" for key ${a.key}: call skip_question.)');
          } else {
            runTool('skip_question', {'key': a.key});
          }
        },
      ),
      _bottom(Row(children: [
        Expanded(
          child: BigButton(
            label: _lego ? 'Back to building' : 'Start building',
            icon: Icons.construction_rounded,
            color: r.allFound ? Pq.have : c,
            onTap: () {
              if (_lego) {
                final n = _showStep(_gcard + 1);
                _tell('(The learner tapped Back to building: the screen shows card $n. Teach it.)');
              } else if (pip.on) {
                _tell('(The learner tapped Start building: call start_building.)');
              } else {
                runTool('start_building', {});
              }
            },
          ),
        ),
        const SizedBox(width: 10),
        _RoundBtn(
          icon: Icons.refresh_rounded,
          label: '',
          dark: false,
          onTap: () {
            setState(() {
              _photos.clear();
              _pending = null;
            });
            _tell('(The learner wants to give new photos.)');
            _openCamera();
          },
        ),
      ])),
    ]);
  }

  Widget _build(Color c) {
    final b = _b!;
    final st = b.steps[_i];
    final n = _i + 1;
    final find = _lego && st.isGather;
    final got = _got.putIfAbsent(n, () => {});
    final t = Theme.of(context).textTheme;
    final first = find && !b.steps.take(_i).any((x) => !x.isGather);
    return Stack(children: [
      ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 110), children: [
        _Dots(steps: b.steps, at: _i, done: _done, lego: _lego, color: c, onTap: (k) {
          final stop = _uncheckedBefore(k);
          if (stop != null) {
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Step $stop needs its check first.')));
            k = stop;
          }
          _showStep(k);
          _toldStep('The learner opened it on the screen', k);
        }),
        const SizedBox(height: 10),
        if (_is3d)
          _ThreeD(lessonId: s.id, controller: _viewer, tag: find ? (first ? "What you'll build" : 'Built so far') : null),
        if (st.picture != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: GestureDetector(
              onTap: () => _zoom(_api.link(st.picture!)),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(18),
                child: ColoredBox(
                  color: Colors.white,
                  child: Image.network(_api.link(st.picture!), fit: BoxFit.contain, height: 260, width: double.infinity),
                ),
              ),
            ),
          ),
        Text('${_lego ? 'Card' : 'Step'} $n of ${b.steps.length}', style: TextStyle(color: c, fontWeight: FontWeight.w800)),
        const SizedBox(height: 4),
        Text(st.title, style: t.headlineMedium),
        const SizedBox(height: 8),
        _ColText(text: st.text, cols: _cols, swaps: _swaps, style: t.bodyLarge?.copyWith(height: 1.4)),
        if ((st.goal ?? '').isNotEmpty) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: c.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(14)),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(Icons.flag_rounded, color: c, size: 20),
              const SizedBox(width: 8),
              Expanded(child: _ColText(text: st.goal!, cols: _cols, swaps: _swaps, style: const TextStyle(fontWeight: FontWeight.w600))),
            ]),
          ),
        ],
        if (_swaps.isNotEmpty) ...[
          const SizedBox(height: 10),
          Row(children: [
            const Icon(Icons.swap_horiz_rounded, color: Pq.swap, size: 20),
            const SizedBox(width: 6),
            Expanded(
              child: Text('Yours: ${_swaps.entries.map((e) => '${e.key} → ${e.value}').join(', ')}',
                  style: const TextStyle(color: Pq.swap, fontWeight: FontWeight.w700)),
            ),
            TextButton(
              onPressed: () {
                setState(_swaps.clear);
                _tell("(The learner switched the screen back to the lesson's own colours and parts.)");
              },
              child: const Text("Use the lesson's"),
            ),
          ]),
        ],
        if (_cols.isNotEmpty) ...[
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
              child: Text('Your columns: ${_cols.entries.map((e) => '${e.key} → ${e.value}').join(', ')}',
                  style: const TextStyle(color: Pq.swap, fontWeight: FontWeight.w700)),
            ),
            TextButton(
              onPressed: () {
                setState(_cols.clear);
                _tell("(The learner switched the screen back to the lesson's own columns.)");
              },
              child: const Text("Use the lesson's"),
            ),
          ]),
        ],
        if (st.parts.isNotEmpty) ...[
          const SizedBox(height: 14),
          Text(find ? 'Find these' : 'You need', style: t.titleMedium),
          const SizedBox(height: 8),
          if (find)
            for (var i = 0; i < st.parts.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: PieceRow(
                  piece: st.parts[i],
                  got: got.contains(i),
                  expanded: false,
                  accent: c,
                  onTick: () {
                    HapticFeedback.lightImpact();
                    setState(() => got.contains(i) ? got.remove(i) : got.add(i));
                    if (got.length == st.parts.length) _tell('(The learner ticked every piece on card $n: they have them all.)');
                  },
                ),
              )
          else
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final p in st.parts)
                Chip(
                  avatar: p.colour == null ? null : CircleAvatar(backgroundColor: Pq.brick(p.colour)),
                  label: Text('${p.count > 1 ? '${p.count}× ' : ''}${p.what}'),
                ),
            ]),
        ],
        if (find)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: SoftButton(
              label: 'Check my pieces',
              icon: Icons.photo_camera_rounded,
              color: c,
              onTap: () {
                _tell('(The learner tapped Check my pieces on card $_gcard: ask them to lay the pieces out flat, open the camera, and check them.)');
                _openCamera();
              },
            ),
          ),
        if (_checkable(st)) ...[
          const SizedBox(height: 14),
          _StepCheck(
            result: _stepResultFor == n ? _stepResult : null,
            busy: _checkingStep && _stepResultFor == n,
            color: c,
            onTell: (places) async {
              final r = await _tellPlaces(places);
              _tell('(The learner typed where the legs are for step $n: ${jsonEncode(r)}. Tell them what it means.)');
            },
            onCheck: () {
              setState(() => _stepPending = true);
              _openCamera();
              _tell('(The learner tapped Check my step on step $n: they take a photo of the board; the result comes to you.)');
            },
          ),
        ],
        if (st.hints.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Card(
              child: ExpansionTile(
                shape: const Border(),
                leading: const Icon(Icons.tips_and_updates_rounded, color: Pq.booklet),
                title: const Text('Stuck? Hints', style: TextStyle(fontWeight: FontWeight.w700)),
                children: [
                  for (final h in st.hints)
                    ListTile(dense: true, leading: const Text('•'), title: _ColText(text: h, cols: _cols, swaps: _swaps)),
                ],
              ),
            ),
          ),
        if (st.code != null) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: const Color(0xFF1C1B19), borderRadius: BorderRadius.circular(16)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Text('The sketch', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
                const Spacer(),
                TextButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: st.code!));
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied: paste it into the Arduino IDE.')));
                    _tell('(The learner copied the sketch.)');
                  },
                  icon: const Icon(Icons.copy_rounded, size: 18),
                  label: const Text('Copy'),
                ),
              ]),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Text(st.code!, style: const TextStyle(color: Color(0xFFE8E6DF), fontFamily: 'monospace', fontSize: 12.5)),
              ),
            ]),
          ),
        ],
      ]),
      _bottom(Row(children: [
        if (n > 1) ...[
          _RoundBtn(
            icon: Icons.arrow_back_rounded,
            label: '',
            dark: false,
            onTap: () {
              _showStep(n - 1);
              _toldStep('The learner tapped Back', n - 1);
            },
          ),
          const SizedBox(width: 10),
        ],
        Expanded(
          child: BigButton(
            label: _checkable(st) && !_passed.contains(n) ? 'Done: check it' : n == b.steps.length ? 'Finish' : find ? 'Got them: build' : 'Done: next',
            icon: n == b.steps.length ? Icons.emoji_events_rounded : Icons.arrow_forward_rounded,
            color: c,
            onTap: () {
              if (_checkable(st) && !_passed.contains(n)) {  // the check comes first: it cannot be skipped
                setState(() => _stepPending = true);
                _openCamera();
                _tell('(The learner tapped Next on step $n, which has not been checked yet: they are taking the photo '
                    'of the board now; the result comes to you.)');
                return;
              }
              _done.add(n);
              if (n >= b.steps.length) {
                runTool('finish_lesson', {});
                _tell('(The learner tapped Finish: the lesson is complete.)');
                return;
              }
              _showStep(n + 1);
              _toldStep('The learner tapped Next: ${_lego ? 'card' : 'step'} $n is done', n + 1);
            },
          ),
        ),
      ])),
    ]);
  }

  Widget _doneView(Color c) => Center(
        child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('🏆', style: TextStyle(fontSize: 84)).animate().scale(curve: Curves.elasticOut, duration: 1200.ms),
            const SizedBox(height: 12),
            Text(Pip.name.isEmpty ? 'Lesson complete!' : 'Well done, ${Pip.name}!', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 6),
            Text('You finished ${s.name}.', style: const TextStyle(color: Pq.muted)),
            const SizedBox(height: 24),
            BigButton(label: 'Choose another lesson', icon: Icons.apps_rounded, color: c, onTap: () => Navigator.of(context).pop()),
          ]),
        ),
      );

  Widget _bottom(Widget child) => Positioned(left: 16, right: 16, bottom: 12, child: child);

  void _zoom(String url) => showDialog<void>(
        context: context,
        builder: (_) => Dialog.fullscreen(
          backgroundColor: Colors.white,
          child: Stack(children: [
            InteractiveViewer(maxScale: 5, child: Center(child: Image.network(url))),
            Positioned(top: 8, right: 8, child: IconButton(icon: const Icon(Icons.close_rounded), onPressed: () => Navigator.pop(context))),
          ]),
        ),
      );
}

// ---------------------------------------------------------------- small pieces

/// The step text with the learner's versions in place of the lesson's (columns, wire colours, stand-ins), marked.
class _ColText extends StatelessWidget {
  const _ColText({required this.text, required this.cols, required this.swaps, this.style});

  final String text;
  final Map<String, String> cols;
  final Map<String, String> swaps;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    final edits = theirEdits(text, cols, swaps);
    if (edits.isEmpty) return Text(text, style: style);
    final spans = <InlineSpan>[];
    var at = 0;
    for (final e in edits) {
      spans.add(TextSpan(text: text.substring(at, e.start)));
      spans.add(TextSpan(
          text: e.text,
          style: const TextStyle(backgroundColor: Color(0x337D5BD6), color: Pq.swap, fontWeight: FontWeight.w800)));
      at = e.end;
    }
    spans.add(TextSpan(text: text.substring(at)));
    return Text.rich(TextSpan(style: style, children: spans));
  }
}

class _ThreeD extends StatefulWidget {
  const _ThreeD({required this.lessonId, required this.controller, this.tag});

  final String lessonId;
  final ViewerController controller;
  final String? tag;

  @override
  State<_ThreeD> createState() => _ThreeDState();
}

class _ThreeDState extends State<_ThreeD> {
  bool _big = false;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) => AnimatedContainer(
          duration: const Duration(milliseconds: 280),
          curve: Curves.easeOutCubic,
          height: _big ? 440 : 260,
          margin: const EdgeInsets.only(bottom: 12),
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
          child: Stack(children: [
            Positioned.fill(child: Viewer3D(lessonId: widget.lessonId, controller: widget.controller)),
            if (!widget.controller.ready)
              Positioned.fill(
                child: ColoredBox(
                  color: Colors.white,
                  child: Center(
                    child: Text(widget.controller.error ?? 'Building the 3D model…',
                        textAlign: TextAlign.center, style: const TextStyle(color: Pq.muted)),
                  ),
                ),
              ),
            if (widget.tag != null)
              Positioned(
                left: 10,
                top: 10,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(color: Pq.lego, borderRadius: BorderRadius.circular(20)),
                  child: Text(widget.tag!, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12)),
                ),
              ),
            Positioned(
              right: 6,
              top: 6,
              child: IconButton.filledTonal(
                tooltip: _big ? 'Smaller' : 'Bigger',
                icon: Icon(_big ? Icons.close_fullscreen_rounded : Icons.open_in_full_rounded, size: 18),
                onPressed: () => setState(() => _big = !_big),
              ),
            ),
          ]),
        ),
      );
}

class _Dots extends StatelessWidget {
  const _Dots({required this.steps, required this.at, required this.done, required this.lego, required this.color, required this.onTap});

  final List<LessonStep> steps;
  final int at;
  final Set<int> done;
  final bool lego;
  final Color color;
  final void Function(int) onTap;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 38,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: steps.length,
          separatorBuilder: (_, _) => const SizedBox(width: 6),
          itemBuilder: (_, i) {
            final on = i == at, ok = done.contains(i + 1);
            final gather = lego && steps[i].isGather;
            return Bouncy(
              onTap: () => onTap(i + 1),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                width: on ? 46 : 34,
                decoration: BoxDecoration(
                  color: on ? color : ok ? Pq.have.withValues(alpha: 0.18) : color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                alignment: Alignment.center,
                child: gather
                    ? Icon(Icons.shopping_basket_rounded, size: 17, color: on ? Colors.white : color)
                    : Text('${i + 1}', style: TextStyle(fontWeight: FontWeight.w800, color: on ? Colors.white : ok ? Pq.have : color)),
              ),
            );
          },
        ),
      );
}

class _Track extends StatelessWidget {
  const _Track({required this.stage, required this.lego, required this.color});

  final Stage stage;
  final bool lego;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final order = lego ? [Stage.hello, Stage.build] : [Stage.hello, Stage.parts, Stage.camera, Stage.result, Stage.build];
    final j = stage == Stage.done ? order.length : order.indexOf(stage);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Row(children: [
        for (var i = 0; i < order.length; i++) ...[
          Expanded(
            child: Column(children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                height: 5,
                decoration: BoxDecoration(
                  color: i < j ? Pq.have : i == j ? color : color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              const SizedBox(height: 4),
              Text(_stageName[order[i]]!,
                  style: TextStyle(fontSize: 11, fontWeight: i == j ? FontWeight.w800 : FontWeight.w500, color: i == j ? color : Pq.muted)),
            ]),
          ),
          if (i < order.length - 1) const SizedBox(width: 6),
        ],
      ]),
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({required this.icon, required this.text, required this.color});

  final IconData icon;
  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(20)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 6),
          Text(text, style: TextStyle(color: color, fontWeight: FontWeight.w700)),
        ]),
      );
}

class _RoundBtn extends StatelessWidget {
  const _RoundBtn({required this.icon, required this.label, this.onTap, this.color, this.dark = true});

  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final Color? color;
  final bool dark;

  @override
  Widget build(BuildContext context) => Bouncy(
        onTap: onTap,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color ?? (dark ? Colors.white24 : Theme.of(context).cardTheme.color),
              boxShadow: dark ? null : [BoxShadow(color: Colors.black.withValues(alpha: 0.08), blurRadius: 10)],
            ),
            child: Icon(icon, color: dark || color != null ? Colors.white : null),
          ),
          if (label.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(label, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
          ],
        ]),
      );
}

/// Voice and level settings.
class _Menu extends StatelessWidget {
  const _Menu({required this.pip, required this.onLevel});

  final Pip pip;
  final void Function(String) onLevel;

  @override
  Widget build(BuildContext context) => PopupMenuButton<String>(
        icon: const Icon(Icons.tune_rounded),
        onSelected: (v) async {
          if (v.startsWith('level:')) return onLevel(v.substring(6));
          if (v == 'live' || v == 'free') {
            await pip.stop();
            pip.mode = v == 'live' ? PipMode.live : PipMode.free;
          }
          if (v == 'speakers') {
            await pip.stop();
            pip.speakers = !pip.speakers;
          }
          pip.refresh();
        },
        itemBuilder: (_) => [
          const PopupMenuItem(enabled: false, child: Text('Voice', style: TextStyle(fontWeight: FontWeight.w800))),
          CheckedPopupMenuItem(value: 'live', checked: pip.mode == PipMode.live, child: const Text('Pip, live (best, ≤ €4 a lesson)')),
          CheckedPopupMenuItem(value: 'free', checked: pip.mode == PipMode.free, child: const Text('Free voice (slower)')),
          CheckedPopupMenuItem(value: 'speakers', checked: !pip.speakers, child: const Text("I'm wearing headphones")),
          const PopupMenuDivider(),
          const PopupMenuItem(enabled: false, child: Text('My level', style: TextStyle(fontWeight: FontWeight.w800))),
          for (final l in const ['beginner', 'some', 'advanced'])
            CheckedPopupMenuItem(value: 'level:$l', checked: Pip.level == l, child: Text(_levelName[l]!)),
          CheckedPopupMenuItem(value: 'level:', checked: Pip.level.isEmpty, child: const Text('Let Pip ask')),
        ],
      );
}


/// The step check on a build step: the button, then what the photo of the board showed.
class _StepCheck extends StatelessWidget {
  const _StepCheck({required this.result, required this.busy, required this.color, required this.onCheck, required this.onTell});

  final Map<String, dynamic>? result;
  final bool busy;
  final Color color;
  final VoidCallback onCheck;
  final Future<void> Function(Map<String, dynamic> places) onTell; // where the learner says the unseen legs are

  @override
  Widget build(BuildContext context) {
    if (busy) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(18)),
        child: const Row(children: [
          SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.4)),
          SizedBox(width: 12),
          Text('Checking your board…', style: TextStyle(fontWeight: FontWeight.w700)),
        ]),
      ).animate(onPlay: (a) => a.repeat(reverse: true)).fade(begin: 0.7, end: 1, duration: 700.ms);
    }
    final r = result;
    if (r == null) {
      return SoftButton(label: 'Check my step', icon: Icons.photo_camera_rounded, color: color, onTap: onCheck);
    }
    final v = '${r['verdict']}';
    final (tone, icon, title) = switch (v) {
      'pass' => (Pq.have, Icons.check_circle_rounded, 'Spot on!'),
      'harmless' => (Pq.have, Icons.check_circle_rounded, 'All good'),
      'moved' => (Pq.swap, Icons.swap_horiz_rounded, 'All connected, in your own columns'),
      'unsure' => (Pq.check, Icons.help_rounded, "I couldn't see everything"),
      'retake' => (Pq.check, Icons.photo_camera_back_rounded, 'Take it again'),
      'wrong' => (Pq.missing, Icons.build_circle_rounded, 'Something to fix'),
      _ => (Pq.muted, Icons.error_outline_rounded, "The check didn't work"),
    };
    final legs = (r['legs'] as List? ?? const []).cast<Map>().where((l) => '${l['words'] ?? ''}'.isNotEmpty).toList();
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: tone.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: tone.withValues(alpha: 0.5), width: 1.5),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: tone),
          const SizedBox(width: 8),
          Expanded(child: Text(title, style: TextStyle(fontWeight: FontWeight.w800, color: tone, fontSize: 16))),
        ]),
        if (v == 'error' || v == 'retake') Padding(padding: const EdgeInsets.only(top: 6), child: Text('${r['say']}')),
        for (final l in legs)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('${'${l['who']}'.replaceFirst('the ', 'The ')}: ${l['words']}', style: const TextStyle(height: 1.3)),
          ),
        if (v == 'pass' || v == 'harmless' || v == 'moved' || v == 'wrong')
          // the photo reading can be a column off: the learner, who sees the board, can put it right
          _TellWhere(
              legs: (r['legs'] as List? ?? const []).cast<Map>().toList(),
              onTell: onTell,
              title: 'Is that where they are? Put right any I misread',
              startOpen: false),
        if (v != 'pass' && v != 'harmless' && v != 'moved') ...[
          const SizedBox(height: 10),
          if (v == 'unsure')
            _TellWhere(legs: (r['legs'] as List? ?? const []).cast<Map>().where((l) => l['status'] == 'unsure').toList(), onTell: onTell),
          SoftButton(
              label: v == 'unsure' ? 'Or take another photo' : v == 'retake' ? 'Take it again' : 'Fixed it: check again',
              icon: Icons.refresh_rounded,
              color: tone,
              onTap: onCheck),
        ],
      ]).animate().fadeIn().slideY(begin: 0.1),
    );
  }
}


/// The legs the photo could not show: the learner types where they are (column and half, or the Arduino pin).
class _TellWhere extends StatefulWidget {
  const _TellWhere({required this.legs, required this.onTell, this.title = "I couldn't see these. Where are they?", this.startOpen = true});

  final List<Map> legs;
  final String title;
  final bool startOpen;
  final Future<void> Function(Map<String, dynamic> places) onTell;

  @override
  State<_TellWhere> createState() => _TellWhereState();
}

class _TellWhereState extends State<_TellWhere> {
  final Map<String, TextEditingController> _text = {};
  final Map<String, String> _half = {};
  bool _busy = false;
  late bool _open = widget.startOpen;

  @override
  void dispose() {
    for (final c in _text.values) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => !_open
      ? Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: () => setState(() => _open = true),
            icon: const Icon(Icons.edit_location_alt_rounded, size: 18),
            label: const Text('Not right? Tell me where they are'),
          ),
        )
      : Padding(
        padding: const EdgeInsets.only(bottom: 10, top: 6),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Text(widget.title, style: const TextStyle(fontWeight: FontWeight.w700)),
          ),
          for (final l in widget.legs) _row(l),
          const SizedBox(height: 4),
          SoftButton(
            label: _busy ? 'Checking…' : 'That\'s where they are',
            icon: Icons.check_rounded,
            color: Pq.have,
            onTap: _busy
                ? null
                : () async {
                    final places = <String, dynamic>{};
                    for (final l in widget.legs) {
                      final k = '${l['key']}', t = _text[k]?.text.trim() ?? '';
                      if (t.isEmpty) continue;
                      places[k] = l['kind'] == 'pin'
                          ? {'pin': t}
                          : l['kind'] == 'rail'
                              ? {'rail': t}
                              : {'column': int.tryParse(t), 'half': _half[k] ?? 'top'};
                    }
                    if (places.isEmpty) return;
                    setState(() => _busy = true);
                    await widget.onTell(places);
                    if (mounted) setState(() => _busy = false);
                  },
          ),
        ]),
      );

  Widget _row(Map l) {
    final k = '${l['key']}';
    final read = RegExp(r'column (\d+) \((top|bottom)').firstMatch('${l['place'] ?? ''}');
    final c = _text.putIfAbsent(k, () => TextEditingController(text: l['status'] == 'unsure' ? '' : read?.group(1) ?? ''));
    if (read != null) _half.putIfAbsent(k, () => read.group(2)!);
    final kind = '${l['kind']}';
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        Expanded(child: Text('${l['who']}'.replaceFirst('the ', 'The '), style: const TextStyle(height: 1.2))),
        const SizedBox(width: 8),
        SizedBox(
          width: kind == 'strip' ? 64 : 90,
          child: TextField(
            controller: c,
            keyboardType: kind == 'strip' ? TextInputType.number : TextInputType.text,
            decoration: InputDecoration(
              isDense: true,
              hintText: kind == 'pin' ? 'pin' : kind == 'rail' ? 'top -' : 'col',
              filled: true,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
            ),
          ),
        ),
        if (kind == 'strip') ...[
          const SizedBox(width: 6),
          ToggleButtons(
            isSelected: [(_half[k] ?? 'top') == 'top', _half[k] == 'bottom'],
            onPressed: (i) => setState(() => _half[k] = i == 0 ? 'top' : 'bottom'),
            borderRadius: BorderRadius.circular(10),
            constraints: const BoxConstraints(minHeight: 34, minWidth: 52),
            children: const [Text('top'), Text('bottom')],
          ),
        ],
      ]),
    );
  }
}
