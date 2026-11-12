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

  static String _dataUrl(Uint8List b) => 'data:image/jpeg;base64,${base64Encode(b)}';

  /// Sends the photos; returns the upload id the check works on.
  Future<String> upload(String lesson, List<Uint8List> photos) async {
    final j = await _post('/api/upload', {
      'lesson': lesson,
      'photos': [for (var i = 0; i < photos.length; i++) {'name': 'photo-${i + 1}.jpg', 'data': _dataUrl(photos[i])}],
    });
    return j['upload'] as String;
  }

  /// The first look. card: the LEGO gather card's number; null for an electronics lesson.
  Future<CheckResult> firstLook(String upload, String lesson, int? card) async => CheckResult.fromJson(
      await _post('/api/flow/first', {'upload': upload, 'lesson': lesson, 'card': ?card}));

  Future<CheckResult> closeup(String upload, String askKey, Uint8List photo) async =>
      CheckResult.fromJson(await _post('/api/flow/closeup', {'upload': upload, 'key': askKey, 'photo': _dataUrl(photo)}));

  Future<CheckResult> dismiss(String upload, String askKey) async =>
      CheckResult.fromJson(await _post('/api/flow/dismiss', {'upload': upload, 'key': askKey}));
}
