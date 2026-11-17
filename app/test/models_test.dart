import 'package:flutter_test/flutter_test.dart';
import 'package:parts_quest/models.dart';

void main() {
  test('a LEGO lesson: gather cards keep their number in the lesson', () {
    final d = LessonDetail.fromJson({
      'lesson_id': '2134-1',
      'name': 'Bison',
      'lesson_type': 'lego',
      'steps': [
        {
          'kind': 'gather',
          'title': 'Find the pieces',
          'text': 'Find these pieces',
          'parts': [
            {'what': 'Black Brick 1 x 2', 'count': 2, 'type': 'lego-3004', 'colour': 'Black'},
          ],
        },
        {'kind': 'build', 'title': 'Step 1', 'text': '', 'parts': []},
        {'kind': 'gather', 'title': 'Bag 2: find the pieces', 'text': '', 'parts': []},
      ],
    });
    expect(d.gatherCards.map((s) => s.number), [1, 3]);
    expect(d.gatherCards.first.pieceCount, 2);
    expect(d.gatherCards.first.parts.first.colour, 'Black');
  });

  test('an electronics lesson lists its parts with their values', () {
    final l = LessonSummary.fromJson({
      'id': 'blink',
      'name': 'Blink',
      'type': 'arduino',
      'parts': [
        {'type': 'jumper-wire', 'name': 'Jumper wire', 'count': 2, 'values': ['black', 'orange']},
        {'type': 'resistor', 'name': 'Resistor 220', 'count': 1, 'values': ['220']},
      ],
    });
    expect(l.parts.map((p) => p.what), ['Jumper wire (black, orange)', 'Resistor 220']);
  });

  test('check results: every server status becomes a verdict', () {
    final r = CheckResult.fromJson({
      'parts': [
        {'type': 'a', 'part': 'A', 'need': 1, 'status': 'have', 'have': [], 'use_instead': []},
        {'type': 'b', 'part': 'B', 'need': 1, 'status': 'use another colour', 'have': [],
          'use_instead': [{'object': 'Red B'}]},
        {'type': 'c', 'part': 'C', 'need': 3, 'status': 'missing 2', 'have': [], 'use_instead': []},
        {'type': 'd', 'part': 'D', 'need': 1, 'status': 'check', 'have': [{'why': 'blurry'}], 'use_instead': []},
        {'type': 'e', 'part': 'E', 'need': 1, 'status': 'skipped', 'have': [], 'use_instead': []},
      ],
      'asks': [{'key': 'd', 'kind': 'closeup', 'message': 'Close-up please'}],
      'not_needed': [{'object': 'a fan'}],
    });
    expect(r.parts.map((p) => p.verdict),
        [Verdict.have, Verdict.swap, Verdict.missing, Verdict.check, Verdict.skipped]);
    expect(r.parts[1].note, 'Use Red B instead');
    expect(r.parts[2].note, '2 still to find');
    expect(r.found, 2);
    expect(r.allFound, isFalse);
    expect(r.asks.single.kind, 'closeup');
    expect(r.extra, ['a fan']);
  });

  test('what a check found gets its tick', () {
    final r = CheckResult.fromJson({
      'parts': [
        {'type': 'p1', 'part': 'Black Brick 1 x 2', 'need': 2, 'status': 'have', 'have': [], 'use_instead': []},
        {'type': 'p2', 'part': 'Red Plate', 'need': 1, 'status': 'use another colour', 'have': [], 'use_instead': []},
        {'type': 'p3', 'part': 'Wheel', 'need': 1, 'status': 'missing', 'have': [], 'use_instead': []},
      ],
    });
    final pieces = [Piece(what: 'a', count: 2), Piece(what: 'b', count: 1), Piece(what: 'c', count: 1)];
    expect(foundPieces(r, pieces, lego: true), {0, 1});
    final e = CheckResult.fromJson({
      'parts': [
        {'type': 'resistor', 'part': 'Resistor 220', 'need': 1, 'status': 'have', 'have': [], 'use_instead': []},
        {'type': 'led', 'part': 'LED', 'need': 1, 'status': 'check', 'have': [], 'use_instead': []},
      ],
    });
    final parts = [Piece(what: 'LED', count: 1, type: 'led'), Piece(what: 'Resistor 220', count: 1, type: 'resistor')];
    expect(foundPieces(e, parts, lego: false), {1});
  });
}
