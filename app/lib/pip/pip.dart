// Pip, the voice tutor: leads the whole session by voice and acts on the screen through tools.
//
// Two voices, as in the web game (research/recognition/lab/game.html, code/tutor/live.py):
//   live  Gemini Live, speech to speech: the phone streams the mic (16 kHz PCM) and plays Pip (24 kHz); talking over
//         Pip cuts it off. The server mints a single-use token, so the Gemini key never reaches the phone.
//         About 0.6¢ to say hello; stops at the lesson's €4 cap.
//   free  the phone listens (speech to text), Haiku writes Pip's words on the server, the phone speaks them.
// Every tool Pip can call is also a button on the screen; what the learner taps is told to Pip.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:record/record.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../api.dart';
import 'audio.dart';

/// What Pip can do on the screen: the session screen.
abstract class PipHost {
  String get lessonId;

  /// What the screen shows now, for Pip: "(Session with Mark. The screen shows: the parts list.)"
  String situation();

  /// A check is running (no nudges then).
  bool get busy;

  /// The lesson is finished (no nudges then).
  bool get finished;

  Future<Map<String, dynamic>> runTool(String name, Map<String, dynamic> args);
}

enum PipMode { live, free }

enum PipState { off, connecting, listening, thinking, speaking }

class PipLine {
  PipLine(this.who, this.text);
  final String who; // tutor, learner, sys
  String text;
}

const _nonBlocking = {'check_parts', 'take_closeup', 'take_closeup_all'};

/// Tools whose result goes back to Pip in free mode (the others just change the screen).
const _answerBack = {
  'remember_name', 'remember_level', 'take_photo', 'check_parts', 'take_closeup', 'take_closeup_all',
  'skip_question', 'start_building', 'lesson_info', 'step_info', 'part_info',
};

/// Long silences go to Pip, so it can check in, tease a little, or offer a break.
const _nudges = [
  (90, '(It has been about 90 seconds since the learner said anything. Check in briefly, with a light joke if it fits.)'),
  (180, '(It has been 3 minutes since they said anything. Gently tease them about taking their time, then offer a hint or help.)'),
  (300, '(It has been 5 minutes. Ask, briefly, if they want a break or some help.)'),
];

class Pip extends ChangeNotifier {
  Pip(this.host);

  final PipHost host;
  final _api = Api.instance;

  PipMode mode = PipMode.live;
  PipState state = PipState.off;
  final List<PipLine> lines = [];
  bool muted = false;
  bool speakers = true; // a phone on the table, not headphones: Pip's own voice must not cut it off
  double cost = 0;
  double cap = 4.0;
  double warn = 3.0;
  Map<String, dynamic>? _prices;

  static String name = '';
  static String level = ''; // beginner, some, advanced

  bool get on => state != PipState.off;

  void refresh() => notifyListeners();

  // ---- remembered between lessons
  static Future<void> loadMe() async {
    final p = await SharedPreferences.getInstance();
    name = p.getString('quest.name') ?? '';
    level = p.getString('quest.level') ?? '';
  }

  static Future<void> saveMe() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('quest.name', name);
    await p.setString('quest.level', level);
  }

  // ---- shared
  bool _stopping = false;
  PipLine? _open; // the caption line being written
  DateTime _lastActive = DateTime.now();
  int _nudged = 0;
  Timer? _tick;

  void _set(PipState s) {
    if (state != s) {
      state = s;
      notifyListeners();
    }
  }

  void caption(String who, String text, {bool append = false}) {
    if (append && _open != null && _open!.who == who) {
      _open!.text += text;
    } else {
      _open = PipLine(who, text);
      lines.add(_open!);
      if (lines.length > 60) lines.removeAt(0);
    }
    notifyListeners();
  }

  void _addCost(double usd) {
    cost += usd;
    if (cost >= cap) {
      caption('sys', 'This lesson reached its €4 limit: Pip stops here. Carry on with the buttons.');
      stop();
    }
    notifyListeners();
  }

  void _active() {
    _lastActive = DateTime.now();
    _nudged = 0;
  }

  Future<void> start({String? first}) async {
    if (on) return;
    _stopping = false;
    _set(PipState.connecting);
    _active();
    _tick = Timer.periodic(const Duration(seconds: 1), (_) => _onTick());
    try {
      mode == PipMode.live ? await _liveStart(first) : await _freeStart(first);
    } catch (e) {
      caption('sys', 'Pip could not start: ${e is ApiError ? e.message : e}${mode == PipMode.live ? ' (try the free voice)' : ''}');
      await stop();
    }
  }

  Future<void> stop() async {
    _tick?.cancel();
    _tick = null;
    if (!on) return;
    _stopping = true;
    _set(PipState.off);
    await _ws?.sink.close();
    _ws = null;
    _player.flush();
    await _micSub?.cancel();
    _micSub = null;
    try {
      await _mic.stop();
    } catch (_) {}
    try {
      await _stt.cancel();
      await _tts.stop();
    } catch (_) {}
    _speaking = false;
  }

  void setMuted(bool v) {
    muted = v;
    if (mode == PipMode.free && on) v ? _stt.stop() : _listen();
    notifyListeners();
  }

  /// What the learner did on the screen, or typed.
  void tell(String text) {
    _active();
    if (!on) return;
    _send(text);
  }

  void _send(String text) {
    if (mode == PipMode.live) {
      _ws?.sink.add(jsonEncode({
        'realtimeInput': {'text': text}
      }));
    } else {
      _freeAsk(text);
    }
  }

  void _onTick() {
    if (!on) return;
    if (mode == PipMode.live && state == PipState.speaking && !_player.playing) _set(PipState.listening);
    if (host.finished || host.busy || _player.playing || _speaking || _freeBusy) return;
    final idle = DateTime.now().difference(_lastActive).inSeconds;
    if (_nudged < _nudges.length && idle >= _nudges[_nudged].$1) {
      _send(_nudges[_nudged].$2);
      _nudged++;
    }
  }

  String _opening(String? first) => '${first == null ? '' : '$first '}${host.situation()} (Start the session.)';

  // ---- Gemini Live
  final _player = PcmPlayer();
  final _mic = AudioRecorder();
  StreamSubscription<Uint8List>? _micSub;
  WebSocketChannel? _ws;
  String? _handle;

  Future<void> _liveStart(String? first) async {
    _player.start();
    await _openLive(first, resumed: false);
    if (!await _mic.hasPermission()) throw ApiError('Pip needs the microphone: allow it in Settings.');
    final stream = await _mic.startStream(const RecordConfig(
      encoder: AudioEncoder.pcm16bits,
      sampleRate: 16000,
      numChannels: 1,
      echoCancel: true,
      noiseSuppress: true,
      autoGain: true,
    ));
    _micSub = stream.listen((chunk) {
      if (muted || _ws == null) return;
      _ws!.sink.add(jsonEncode({
        'realtimeInput': {
          'audio': {'data': base64Encode(chunk), 'mimeType': 'audio/pcm;rate=16000'}
        }
      }));
    });
  }

  Future<void> _openLive(String? first, {required bool resumed}) async {
    final s = await _api.tutorSession(host.lessonId,
        resume: _handle, speakers: speakers, name: name.isEmpty ? null : name, level: level.isEmpty ? null : level);
    cap = (s['cap_usd'] as num?)?.toDouble() ?? cap;
    warn = (s['warn_usd'] as num?)?.toDouble() ?? warn;
    _prices = (s['prices'] as Map?)?.cast<String, dynamic>();
    final ws = WebSocketChannel.connect(Uri.parse(s['ws'] as String));
    await ws.ready;
    _ws = ws;
    ws.sink.add(jsonEncode(s['setup']));
    ws.stream.listen(
      (data) {
        final text = data is String ? data : utf8.decode(data as List<int>);
        _onLive(jsonDecode(text) as Map<String, dynamic>, first, resumed);
      },
      onDone: () {
        if (on && !_stopping && identical(ws, _ws)) {
          caption('sys', 'Reconnecting…');
          Future.delayed(const Duration(milliseconds: 400), () {
            if (on) {
              _openLive(null, resumed: true).catchError((Object e) {
                caption('sys', 'Could not reconnect: $e');
                stop();
              });
            }
          });
        }
      },
      onError: (Object e) => debugPrint('pip socket: $e'),
    );
  }

  void _onLive(Map<String, dynamic> m, String? first, bool resumed) {
    if (m.containsKey('setupComplete')) {
      _set(PipState.listening);
      if (!resumed) {
        _ws?.sink.add(jsonEncode({
          'realtimeInput': {'text': _opening(first)}
        }));
      }
    }
    final upd = m['sessionResumptionUpdate'] as Map?;
    if (upd?['newHandle'] != null) _handle = upd!['newHandle'] as String;
    if (m.containsKey('goAway')) {
      final old = _ws;
      _ws = null;
      _openLive(null, resumed: true).then((_) => old?.sink.close());
    }
    final sc = m['serverContent'] as Map<String, dynamic>?;
    if (sc != null) {
      if (sc['interrupted'] == true) {
        _player.flush();
        _set(PipState.listening);
      }
      for (final p in ((sc['modelTurn'] as Map?)?['parts'] as List? ?? const [])) {
        final d = (p as Map)['inlineData'] as Map?;
        if (d?['data'] != null) {
          _player.push(base64Decode(d!['data'] as String));
          _set(PipState.speaking);
        }
      }
      final heard = (sc['inputTranscription'] as Map?)?['text'] as String?;
      if (heard != null && heard.isNotEmpty) {
        _active();
        caption('learner', heard, append: true);
      }
      final said = (sc['outputTranscription'] as Map?)?['text'] as String?;
      if (said != null && said.isNotEmpty) caption('tutor', said, append: true);
      if (sc['turnComplete'] == true) {
        _open = null;
        _lastActive = DateTime.now();
      }
    }
    final calls = ((m['toolCall'] as Map?)?['functionCalls'] as List?) ?? const [];
    for (final fc in calls.cast<Map<String, dynamic>>()) {
      final name = fc['name'] as String;
      host.runTool(name, (fc['args'] as Map?)?.cast<String, dynamic>() ?? {}).then((result) {
        final r = {
          'id': fc['id'],
          'name': name,
          'response': {'result': result},
          if (_nonBlocking.contains(name)) 'scheduling': 'INTERRUPT',
        };
        _ws?.sink.add(jsonEncode({
          'toolResponse': {
            'functionResponses': [r]
          }
        }));
      });
    }
    final u = m['usageMetadata'] as Map<String, dynamic>?;
    if (u != null) _addCost(_liveCost(u));
  }

  double _liveCost(Map<String, dynamic> u) {
    final p = _prices ?? const {'text_in': 0.75, 'audio_in': 3.0, 'text_out': 4.5, 'audio_out': 12.0};
    Map<String, num> by(Object? list) => {
          for (final d in (list as List? ?? const []).cast<Map>()) '${d['modality']}': (d['tokenCount'] as num?) ?? 0
        };
    final i = by(u['promptTokensDetails']), o = by(u['responseTokensDetails']);
    num pr(String k) => (p[k] as num?) ?? 0;
    return ((i['TEXT'] ?? 0) * pr('text_in') +
            (i['AUDIO'] ?? 0) * pr('audio_in') +
            (o['AUDIO'] ?? 0) * pr('audio_out') +
            (o['TEXT'] ?? 0) * pr('text_out') +
            ((u['thoughtsTokenCount'] as num?) ?? 0) * pr('text_out')) /
        1e6;
  }

  // ---- the free voice: the phone hears and speaks, Haiku answers (with the same tools)
  final _stt = SpeechToText();
  final _tts = FlutterTts();
  bool _sttReady = false;
  bool _speaking = false;
  bool _freeBusy = false;
  final List<String> _queue = [];
  final List<Map<String, String>> _history = [];

  Future<void> _freeStart(String? first) async {
    await _tts.setLanguage('en-GB');
    await _tts.setSpeechRate(kIsWeb ? 1.0 : 0.5);
    await _tts.awaitSpeakCompletion(true);
    _sttReady = await _stt.initialize(onStatus: (s) {
      // phones stop listening after a pause: listen again, unless Pip is talking
      if ((s == 'done' || s == 'notListening') && on && !muted && !_speaking) {
        Future.delayed(const Duration(milliseconds: 300), _listen);
      }
    }, onError: (_) {});
    if (!_sttReady) caption('sys', "This phone can't listen here: type to Pip below.");
    _set(PipState.listening);
    _listen();
    _freeAsk(_opening(first));
  }

  void _listen() {
    if (!_sttReady || !on || muted || _speaking || _stt.isListening) return;
    _stt.listen(
      listenOptions: SpeechListenOptions(
        localeId: 'en_GB',
        partialResults: false,
        cancelOnError: false,
        listenMode: ListenMode.dictation,
        pauseFor: const Duration(seconds: 3),
        listenFor: const Duration(seconds: 60),
      ),
      onResult: (r) {
        final t = r.recognizedWords.trim();
        if (r.finalResult && t.isNotEmpty) {
          _active();
          caption('learner', t);
          _freeAsk(t);
        }
      },
    );
  }

  Future<void> _say(String text) async {
    _speaking = true;
    await _stt.stop(); // the phone's own voice must not be heard as the learner
    _set(PipState.speaking);
    await _tts.speak(text);
    _speaking = false;
    if (on) {
      _set(PipState.listening);
      _listen();
    }
  }

  Future<void> _freeAsk(String text) async {
    if (_freeBusy) {
      _queue.add(text);
      return;
    }
    _freeBusy = true;
    _set(PipState.thinking);
    try {
      String? next = text;
      for (var hops = 0; hops < 4 && next != null && on; hops++) {
        final r = await _api.tutorReply(host.lessonId, _history, next,
            name: name.isEmpty ? null : name, level: level.isEmpty ? null : level);
        final say = '${r['say'] ?? ''}';
        final tool = (r['tool'] as Map?)?.cast<String, dynamic>();
        _history
          ..add({'who': 'learner', 'text': next})
          ..add({'who': 'tutor', 'text': say + (tool != null ? ' [${tool['name']}]' : '')});
        _addCost((r['cost_usd'] as num?)?.toDouble() ?? 0);
        caption('tutor', say);
        final said = on ? _say(say) : Future.value();
        next = null;
        if (tool != null) {
          final result = await host.runTool('${tool['name']}', (tool['args'] as Map?)?.cast<String, dynamic>() ?? {});
          if (_answerBack.contains(tool['name'])) {
            await said;
            next = '(result of ${tool['name']}: ${jsonEncode(result)})';
          }
        }
        await said;
      }
    } catch (e) {
      caption('sys', 'Pip could not answer: ${e is ApiError ? e.message : e}');
    }
    _freeBusy = false;
    if (on && !_speaking) _set(PipState.listening);
    if (_queue.isNotEmpty) _freeAsk(_queue.removeAt(0));
  }

  @override
  void dispose() {
    stop();
    _player.dispose();
    _mic.dispose();
    super.dispose();
  }
}
