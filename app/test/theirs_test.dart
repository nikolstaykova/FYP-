import 'package:flutter_test/flutter_test.dart';
import 'package:parts_quest/session/theirs.dart';

Map<String, dynamic> _wires(List<Map<String, dynamic>> have) => {
      'parts': [
        {'type': 'jumper-wire', 'part': 'Jumper wire', 'have': have, 'use_instead': []},
      ],
    };

void main() {
  test('green wires instead of orange and black', () {
    final r = _wires([
      {'object': 'Jumper wire (green)', 'value': 'green', 'count': 2},
    ]);
    expect(wireSwaps(['black', 'orange'], r), {'black wire': 'green wire', 'orange wire': 'other green wire'});
  });

  test('a colour they have stays; one they lack takes a free colour', () {
    final r = _wires([
      {'object': 'Jumper wires', 'value': 'black, blue', 'count': 2},
    ]);
    expect(wireSwaps(['black', 'orange'], r), {'orange wire': 'blue wire'});
  });

  test('nothing named, nothing changes', () {
    expect(wireSwaps(['orange'], _wires([{'object': 'Jumper wires (mixed)', 'value': '', 'count': 3}])), isEmpty);
  });

  test('the step text says their colour, and their columns', () {
    const t = 'Plug the orange jumper wire into column 14, then the black wire into column 15.';
    final e = theirEdits(t, {'14': '20'}, {'orange wire': 'blue wire', 'black wire': 'green wire'});
    expect(applyEdits(t, e), 'Plug the blue jumper wire into column 20, then the green wire into column 15.');
  });

  test('a stand-in part by its words', () {
    const t = 'Put the 220 ohm resistor in.';
    expect(applyEdits(t, theirEdits(t, {}, {'220 ohm resistor': '330 ohm resistor'})), 'Put the 330 ohm resistor in.');
  });
}
