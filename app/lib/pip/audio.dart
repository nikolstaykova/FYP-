// Pip's voice from Gemini Live: 16-bit PCM at 24 kHz, played as it arrives; dropped at once when the learner talks
// over it.
import 'dart:typed_data';

import 'package:mp_audio_stream/mp_audio_stream.dart';

class PcmPlayer {
  static const rate = 24000;
  AudioStream? _out;
  DateTime _endsAt = DateTime.fromMillisecondsSinceEpoch(0);

  /// Call from a tap (the web needs a user action to start sound).
  void start() {
    _out ??= getAudioStream()..init(sampleRate: rate, channels: 1, bufferMilliSec: 30000, waitingBufferMilliSec: 60);
    _out!.resume();
  }

  /// Still talking: what was pushed has not all played yet.
  bool get playing => DateTime.now().isBefore(_endsAt);

  void push(Uint8List pcm16) {
    final out = _out;
    if (out == null || pcm16.length < 2) return;
    final bd = ByteData.sublistView(pcm16);
    final n = pcm16.length ~/ 2;
    final f = Float32List(n);
    for (var i = 0; i < n; i++) {
      f[i] = bd.getInt16(i * 2, Endian.little) / 32768.0;
    }
    out.push(f);
    final now = DateTime.now();
    final from = _endsAt.isAfter(now) ? _endsAt : now.add(const Duration(milliseconds: 60));
    _endsAt = from.add(Duration(microseconds: n * 1000000 ~/ rate));
  }

  /// The learner interrupted: drop what is still buffered.
  void flush() {
    _endsAt = DateTime.fromMillisecondsSinceEpoch(0);
    final out = _out;
    if (out == null) return;
    out.uninit();
    out.init(sampleRate: rate, channels: 1, bufferMilliSec: 30000, waitingBufferMilliSec: 60);
    out.resume();
  }

  void dispose() {
    _out?.uninit();
    _out = null;
  }
}
