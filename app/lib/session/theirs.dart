// The learner's own versions of the lesson: their breadboard columns (use_column), their wire colours and stand-in
// parts (use_instead, or found by the check). The step text shows theirs, marked, and Pip calls things their way.

const wireColours = [
  'black', 'brown', 'red', 'orange', 'yellow', 'green', 'blue', 'purple', 'violet', 'grey', 'gray', 'white', 'pink',
];

/// From a check result: the lesson's wire colours the learner does not have → colours they do have.
/// lessonColours: the lesson's jumper-wire colours, e.g. [black, orange]. A colour they have stays; one they lack
/// takes the next colour they have that the lesson does not use ("orange wire" → "green wire"); when those run out,
/// it reuses one ("black wire" → "other green wire").
Map<String, String> wireSwaps(List<String> lessonColours, Map<String, dynamic> result) {
  final want = [for (final c in lessonColours) c.toLowerCase().trim()].where(wireColours.contains).toList();
  if (want.isEmpty) return {};
  final rows = (result['parts'] as List? ?? const []).cast<Map<String, dynamic>>();
  final row = rows.where((r) => '${r['type']}'.contains('jumper') || '${r['type']}'.contains('wire')).firstOrNull;
  if (row == null) return {};
  final seen = <String>[];
  for (final h in [...(row['have'] as List? ?? const []), ...(row['use_instead'] as List? ?? const [])].cast<Map>()) {
    for (final w in '${h['value'] ?? ''} ${h['object'] ?? ''}'.toLowerCase().split(RegExp('[^a-z]+'))) {
      final c = w == 'gray' ? 'grey' : w;
      if (wireColours.contains(c) && !seen.contains(c)) seen.add(c);
    }
  }
  // "various colours" with no colour named, or nothing seen: nothing to change
  if (seen.isEmpty) return {};
  final free = seen.where((c) => !want.contains(c)).toList();
  final out = <String, String>{};
  String? last;
  for (final c in want) {
    if (seen.contains(c)) continue;
    if (free.isNotEmpty) {
      last = free.removeAt(0);
      out['$c wire'] = '$last wire';
    } else if (last != null) {
      out['$c wire'] = 'other $last wire';
    } else {
      last = seen.first;
      out['$c wire'] = '$last wire';
    }
  }
  return out;
}

/// One change to the step text: replace [start, end) with [text].
class Edit {
  Edit(this.start, this.end, this.text);
  final int start;
  final int end;
  final String text;
}

/// The changes that turn the lesson's words into the learner's: columns, then "[colour] (jumper) wire(s)" and any
/// other phrase they use instead. Sorted, never overlapping.
List<Edit> theirEdits(String text, Map<String, String> cols, Map<String, String> swaps) {
  final edits = <Edit>[];
  if (cols.isNotEmpty) {
    final re = RegExp(r'\b(columns?)(\s+)(\d+(?:\s*(?:,|and|or|to)\s*\d+)*)', caseSensitive: false);
    for (final m in re.allMatches(text)) {
      final from = m.start + m[1]!.length + m[2]!.length;
      for (final d in RegExp(r'\d+').allMatches(m[3]!)) {
        final mine = cols[d[0]];
        if (mine != null) edits.add(Edit(from + d.start, from + d.end, mine));
      }
    }
  }
  for (final e in swaps.entries) {
    final lesson = e.key.toLowerCase().trim();
    final colour = RegExp(r'^(\w+) wire$').firstMatch(lesson);
    final theirsColour = RegExp(r'^(.+?) wire$').firstMatch(e.value.trim());
    if (colour != null && theirsColour != null) {
      // "orange wire", "orange jumper wire", "orange wires": only the colour changes
      final re = RegExp('\\b(${RegExp.escape(colour[1]!)})(?=\\s+(?:jumper\\s+)?wires?\\b)', caseSensitive: false);
      for (final m in re.allMatches(text)) {
        edits.add(Edit(m.start, m.end, theirsColour[1]!));
      }
    } else if (lesson.isNotEmpty) {
      for (final m in RegExp('\\b${RegExp.escape(lesson)}\\b', caseSensitive: false).allMatches(text)) {
        edits.add(Edit(m.start, m.end, e.value));
      }
    }
  }
  edits.sort((a, b) => a.start.compareTo(b.start));
  final kept = <Edit>[];
  for (final e in edits) {
    if (kept.isEmpty || e.start >= kept.last.end) kept.add(e);
  }
  return kept;
}

/// The text with the edits made (for Pip, or plain text).
String applyEdits(String text, List<Edit> edits) {
  final b = StringBuffer();
  var at = 0;
  for (final e in edits) {
    b
      ..write(text.substring(at, e.start))
      ..write(e.text);
    at = e.end;
  }
  b.write(text.substring(at));
  return b.toString();
}
