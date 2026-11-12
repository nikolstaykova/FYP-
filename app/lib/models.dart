import 'dart:typed_data';

// What the parts server sends (research/recognition/lab/server.py), as Dart objects.

int _int(Object? v, [int d = 0]) => v is int ? v : v is num ? v.toInt() : int.tryParse('$v') ?? d;

/// One lesson in the list (/api/lessons).
class LessonSummary {
  LessonSummary({required this.id, required this.name, required this.type, this.kind, this.parts = const []});

  final String id;
  final String name;
  final String type; // "arduino" or "lego"
  final String? kind; // LEGO: "3D model" or "booklet"
  final List<Piece> parts; // Arduino: everything the lesson needs

  bool get isLego => type == 'lego';
  bool get isBooklet => kind == 'booklet';

  factory LessonSummary.fromJson(Map<String, dynamic> j) => LessonSummary(
        id: j['id'] as String,
        name: (j['name'] ?? j['id']) as String,
        type: (j['type'] ?? 'arduino') as String,
        kind: j['kind'] as String?,
        parts: [
          for (final p in (j['parts'] as List? ?? const []))
            Piece(
              what: _arduinoName(p as Map<String, dynamic>),
              count: _int(p['count'], 1),
              type: p['type'] as String?,
              values: [for (final v in (p['values'] as List? ?? const [])) '$v'],
            ),
        ],
      );

  static String _arduinoName(Map<String, dynamic> p) {
    final vals = [for (final v in (p['values'] as List? ?? const [])) '$v'];
    final name = (p['name'] ?? p['type'] ?? '?') as String;
    return vals.isEmpty || name.contains(vals.join()) ? name : '$name (${vals.join(', ')})';
  }
}

/// A piece or part to find.
class Piece {
  Piece({required this.what, required this.count, this.type, this.colour, this.about, this.values = const []});

  final String what;
  final List<String> values; // electronics: the lesson's values (wire colours, 220...)
  final int count;
  final String? type;
  final String? colour;
  final String? about;

  factory Piece.fromJson(Map<String, dynamic> j) => Piece(
        what: (j['what'] ?? '?') as String,
        count: _int(j['count'], 1),
        type: j['type'] as String?,
        colour: j['colour'] as String?,
        about: j['about'] as String?,
      );
}

/// One card of a lesson (/api/lesson): a gather card or a build step.
class LessonStep {
  LessonStep({
    required this.number,
    required this.kind,
    required this.title,
    required this.text,
    required this.parts,
    this.bag,
    this.id = '',
    this.goal,
    this.hints = const [],
    this.picture,
    this.code,
  });

  final int number; // 1-based, the "card" the server checks
  final String kind; // gather, build, upload...
  final String title;
  final String text;
  final List<Piece> parts;
  final Object? bag;
  final String id; // "step-3": a 3D lesson's own step number is the last part
  final String? goal;
  final List<String> hints;
  final String? picture; // a booklet step's picture, a server path
  final String? code; // an Arduino sketch

  /// The lesson's own build step number (3D viewer), from the id.
  int? get ownNumber => int.tryParse(id.split('-').last);

  bool get isGather => kind == 'gather';
  int get pieceCount => parts.fold(0, (a, p) => a + p.count);
}

class LessonDetail {
  LessonDetail({required this.id, required this.name, required this.type, required this.steps, this.viewer});

  final String id;
  final String name;
  final String type;
  final List<LessonStep> steps;
  final String? viewer;

  List<LessonStep> get gatherCards => steps.where((s) => s.isGather).toList();
  List<String> get pictures => [for (final s in steps) if (s.picture != null) s.picture!];

  factory LessonDetail.fromJson(Map<String, dynamic> j) {
    final raw = (j['steps'] as List? ?? const []).cast<Map<String, dynamic>>();
    return LessonDetail(
      id: j['lesson_id'] as String,
      name: (j['name'] ?? j['lesson_id']) as String,
      type: (j['lesson_type'] ?? 'arduino') as String,
      viewer: j['viewer'] as String?,
      steps: [
        for (var i = 0; i < raw.length; i++)
          LessonStep(
            number: i + 1,
            kind: (raw[i]['kind'] ?? 'build') as String,
            title: (raw[i]['title'] ?? 'Step ${i + 1}') as String,
            text: (raw[i]['text'] ?? '') as String,
            bag: raw[i]['bag'],
            id: '${raw[i]['id'] ?? ''}',
            goal: raw[i]['goal'] as String?,
            hints: [for (final h in (raw[i]['hints'] as List? ?? const [])) '$h'],
            picture: raw[i]['picture'] as String?,
            code: raw[i]['code'] as String?,
            parts: [for (final p in (raw[i]['parts'] as List? ?? const [])) Piece.fromJson(p as Map<String, dynamic>)],
          ),
      ],
    );
  }
}

/// The verdict on one part after a check.
enum Verdict { have, swap, check, missing, skipped }

class PartResult {
  PartResult({required this.key, required this.name, required this.need, required this.status, required this.note});

  final String key;
  final String name;
  final int need;
  final String status; // the server's words: have, check, missing 2, use instead...
  final String note;

  Verdict get verdict {
    if (status == 'have') return Verdict.have;
    if (status.startsWith('use')) return Verdict.swap;
    if (status == 'check') return Verdict.check;
    if (status == 'skipped') return Verdict.skipped;
    return Verdict.missing;
  }

  factory PartResult.fromJson(Map<String, dynamic> j) {
    final have = (j['have'] as List? ?? const []).cast<Map<String, dynamic>>();
    final instead = (j['use_instead'] as List? ?? const []).cast<Map<String, dynamic>>();
    final status = (j['status'] ?? 'missing') as String;
    var note = '';
    if (status.startsWith('use') && instead.isNotEmpty) {
      note = 'Use ${instead.first['object']} instead';
    } else if (have.isNotEmpty && (have.first['why'] ?? '').toString().isNotEmpty) {
      note = '${have.first['why']}';
    } else if (status.startsWith('missing ')) {
      note = '${status.substring(8)} still to find';
    }
    return PartResult(
      key: (j['type'] ?? j['part']) as String,
      name: (j['part'] ?? j['type'] ?? '?') as String,
      need: _int(j['need'], 1),
      status: status,
      note: note,
    );
  }
}

/// A question the checker asks the learner: a close-up, or "can you find it?".
class Ask {
  Ask({required this.key, required this.kind, required this.message});

  final String key;
  final String kind; // closeup or find
  final String message;

  factory Ask.fromJson(Map<String, dynamic> j) =>
      Ask(key: j['key'] as String, kind: (j['kind'] ?? 'closeup') as String, message: (j['message'] ?? '') as String);
}

class CheckResult {
  CheckResult({required this.parts, required this.asks, required this.extra});

  final List<PartResult> parts;
  final List<Ask> asks;
  final List<String> extra; // things on the table the lesson does not need

  int get found => parts.where((p) => p.verdict == Verdict.have || p.verdict == Verdict.swap).length;
  bool get allFound => parts.isNotEmpty && found == parts.length;

  factory CheckResult.fromJson(Map<String, dynamic> j) => CheckResult(
        parts: [for (final p in (j['parts'] as List? ?? const [])) PartResult.fromJson(p as Map<String, dynamic>)],
        asks: [for (final a in (j['asks'] as List? ?? const [])) Ask.fromJson(a as Map<String, dynamic>)],
        extra: [
          for (final e in (j['not_needed'] as List? ?? const []))
            if (e is Map && e['object'] != null) '${e['object']}'
        ],
      );
}

/// A photo, and the part of it the learner saw on screen ([x0, y0, x1, y1] fractions; null: all of it). The server
/// crops it to that part.
class Shot {
  Shot(this.bytes, [this.crop]);
  final Uint8List bytes;
  final List<double>? crop;

  /// Nearly the whole frame: no need to crop.
  List<double>? get cropOrNull => crop == null || (crop![2] - crop![0]) * (crop![3] - crop![1]) > 0.97 ? null : crop;
}
