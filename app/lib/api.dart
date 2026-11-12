// Talks to the parts server (research/recognition/lab/server.py). The server holds the lessons, the database
// connection and the model keys; the app only ever sends the access key from the server's link.
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'client_stub.dart' if (dart.library.io) 'client_io.dart';
import 'models.dart';

class ApiError implements Exception {
  ApiError(this.message);
  final String message;
  @override
  String toString() => message;
}

class Api {
  Api._();
  static final instance = Api._();

  Uri? base;
  String key = '';
  final http.Client _client = makeClient();
  List<LessonSummary>? _lessons;

  bool get ready => base != null && key.isNotEmpty;

  Future<void> load() async {
    // On the web the server itself serves the app: same address, key in the page's link.
    if (kIsWeb && setLink(Uri.base.toString())) return;
    final prefs = await SharedPreferences.getInstance();
    final link = prefs.getString('server_link');
    if (link != null) setLink(link);
  }

  /// "https://192.168.1.59:8765/?key=abc" (the link the server prints) → address + key.
  bool setLink(String link) {
    final u = Uri.tryParse(link.trim());
    final k = u?.queryParameters['key'];
    if (u == null || k == null || k.isEmpty || u.host.isEmpty) return false;
    base = Uri(scheme: u.scheme.isEmpty ? 'https' : u.scheme, host: u.host, port: u.hasPort ? u.port : null);
    key = k;
    _lessons = null;
    return true;
  }

  Future<void> save(String link) async {
    if (!setLink(link)) throw ApiError('That link has no key in it. Copy the whole link the server prints.');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_link', link.trim());
  }

  Uri url(String path, [Map<String, String> q = const {}]) => base!.replace(path: path, queryParameters: {...q, 'key': key});

  Future<dynamic> _get(String path, [Map<String, String> q = const {}]) async {
    final r = await _client.get(url(path, q)).timeout(const Duration(seconds: 60));
    return _decode(r);
  }

  /// A file from the server as text (the 3D viewer's page and model).
  Future<String> text(String path) async {
    final r = await _client.get(url(path)).timeout(const Duration(minutes: 2));
    if (r.statusCode != 200) throw ApiError('Server error ${r.statusCode}');
    return utf8.decode(r.bodyBytes);
  }

  Future<dynamic> _post(String path, Map<String, dynamic> body) async {
    final r = await _client
        .post(url(path), headers: {'Content-Type': 'application/json'}, body: jsonEncode(body))
        .timeout(const Duration(minutes: 3));
    return _decode(r);
  }

  dynamic _decode(http.Response r) {
    dynamic j;
    try {
      j = jsonDecode(utf8.decode(r.bodyBytes));
    } catch (_) {
      throw ApiError('The server sent something unexpected (${r.statusCode}).');
    }
    if (r.statusCode == 403) throw ApiError('The server did not accept the key. Scan or paste its link again.');
    if (r.statusCode != 200) throw ApiError(j is Map && j['error'] != null ? '${j['error']}' : 'Server error ${r.statusCode}');
    return j;
  }

  Future<List<LessonSummary>> lessons({bool fresh = false}) async {
    if (_lessons != null && !fresh) return _lessons!;
    final j = await _get('/api/lessons', {'all': '1'}) as List;
    return _lessons = [for (final x in j) LessonSummary.fromJson(x as Map<String, dynamic>)];
  }

  Future<LessonDetail> lesson(String id) async => LessonDetail.fromJson(await _get('/api/lesson', {'id': id}) as Map<String, dynamic>);

  static String dataUrl(Uint8List b) => _dataUrl(b);
  static String _dataUrl(Uint8List b) => 'data:image/jpeg;base64,${base64Encode(b)}';

  /// Sends the photos; returns the upload id the check works on.
  Future<String> upload(String lesson, List<Shot> photos) async {
    final j = await _post('/api/upload', {
      'lesson': lesson,
      'photos': [
        for (var i = 0; i < photos.length; i++)
          {'name': 'photo-${i + 1}.jpg', 'data': _dataUrl(photos[i].bytes), 'crop': ?photos[i].cropOrNull},
      ],
    });
    return j['upload'] as String;
  }

  /// The first look. card: the LEGO gather card's number; null for an electronics lesson.
  Future<CheckResult> firstLook(String upload, String lesson, int? card) async => CheckResult.fromJson(
      await _post('/api/flow/first', {'upload': upload, 'lesson': lesson, 'card': ?card}));

  /// The raw answer of a check, for Pip (it is told the facts in its own words: see pip/summary.dart).
  Future<Map<String, dynamic>> flow(String action, Map<String, dynamic> body) async =>
      (await _post('/api/flow/$action', body)) as Map<String, dynamic>;

  /// A Gemini Live session for Pip: a single-use token and the setup (the key stays on the server).
  Future<Map<String, dynamic>> tutorSession(String lesson,
          {String? resume, bool speakers = false, String? name, String? level}) async =>
      (await _post('/api/tutor/session', {
        'lesson': lesson,
        'resume': resume,
        'speakers': speakers,
        'name': name,
        'level': level,
      })) as Map<String, dynamic>;

  /// The free voice: Haiku writes Pip's next words (and one tool), the phone speaks them.
  Future<Map<String, dynamic>> tutorReply(String lesson, List<Map<String, String>> history, String text,
          {String? name, String? level}) async =>
      (await _post('/api/tutor/reply', {
        'lesson': lesson,
        'history': history,
        'text': text,
        'name': name,
        'level': level,
      })) as Map<String, dynamic>;

  /// Pip's look tool: one photo, one question, answered by Haiku on the server.
  Future<Map<String, dynamic>> look(String lesson, Shot photo, String question) async =>
      (await _post('/api/tutor/look',
              {'lesson': lesson, 'photo': _dataUrl(photo.bytes), 'crop': ?photo.cropOrNull, 'question': question}))
          as Map<String, dynamic>;

  /// Pip looks something up in the lesson (lesson_info, step_info, part_info).
  Future<dynamic> lookup(String lesson, String tool, Map<String, dynamic> args) async =>
      _post('/api/tutor/lookup', {'lesson': lesson, 'tool': tool, 'args': args});

  /// A server path ("/files/...", "/viewer/...") as a full link with the key.
  String link(String path) {
    final u = Uri.parse(path);
    return base!.replace(path: u.path, queryParameters: {...u.queryParameters, 'key': key}).toString();
  }

  Future<CheckResult> closeup(String upload, String askKey, Shot photo) async => CheckResult.fromJson(await _post(
      '/api/flow/closeup', {'upload': upload, 'key': askKey, 'photo': _dataUrl(photo.bytes), 'crop': ?photo.cropOrNull}));

  Future<CheckResult> dismiss(String upload, String askKey) async =>
      CheckResult.fromJson(await _post('/api/flow/dismiss', {'upload': upload, 'key': askKey}));
}
