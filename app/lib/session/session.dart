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
  late final Pip pip = Pip(this);
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

  @override
  void initState() {
    super.initState();
    pip.addListener(_onPip);
    _load();
  }

  void _onPip() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
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
      case 'start_building':
        return {'step': _showStep(1), 'steps': _b?.steps.length ?? 0};
      case 'show_step':
        return {'screen_shows_step': _showStep(int.tryParse('${args['n']}') ?? 1)};
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
    if (kIsWeb || _cam != null) return; // the browser: the phone's own camera app, opened by a tap
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

  void _stopCamera() {
    final c = _cam;
    _cam = null;
    c?.dispose();
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

  Future<void> _gotPhoto(Shot p) async {
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
    _tell('(The learner took a photo themselves: ${_photos.length} so far.)');
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
    return PopScope(
      onPopInvokedWithResult: (_, _) => pip.stop(),
      child: Scaffold(
        appBar: AppBar(
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
            PipBar(pip: pip, onStart: _startPip),
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
    final what = _lookQuestion != null
        ? 'Hold it up so Pip can see it'
        : q != null
            ? 'Close-up: ${q.message}'
            : _lego
                ? 'Lay the pieces flat, a little apart'
                : 'Lay the parts out so I can see them all';
    final thumbs = _photos.isNotEmpty && q == null && _lookQuestion == null;
    final checkBtn = q == null && _lookQuestion == null;
    return kIsWeb ? _cameraBrowser(c, what, thumbs, checkBtn) : _cameraLive(c, what, thumbs, checkBtn);
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
                          onTap: () => setState(() {
                            _pending = null;
                            _lookQuestion = null;
                          }),
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
      child: Stack(fit: StackFit.expand, children: [
        if (cam != null && cam.value.isInitialized)
          CameraFill(controller: cam, visible: _visible)
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
                  : _RoundBtn(icon: Icons.close_rounded, label: 'Cancel', onTap: () => setState(() => _pending = null)),
            ]),
          ]),
        ),
      ]),
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
          _showStep(k);
          _tell('(The learner opened ${_lego ? 'card' : 'step'} $k on the screen.)');
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
              _tell('(The learner tapped Back: the screen shows ${_lego ? 'card' : 'step'} ${n - 1}.)');
            },
          ),
          const SizedBox(width: 10),
        ],
        Expanded(
          child: BigButton(
            label: n == b.steps.length ? 'Finish' : find ? 'Got them: build' : 'Done: next',
            icon: n == b.steps.length ? Icons.emoji_events_rounded : Icons.arrow_forward_rounded,
            color: c,
            onTap: () {
              _done.add(n);
              if (n >= b.steps.length) {
                runTool('finish_lesson', {});
                _tell('(The learner tapped Finish: the lesson is complete.)');
                return;
              }
              _showStep(n + 1);
              _tell('(The learner tapped Next: ${_lego ? 'card' : 'step'} $n is done and the screen shows ${n + 1}. Teach it.)');
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
