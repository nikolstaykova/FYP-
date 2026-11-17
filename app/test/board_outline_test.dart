import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:parts_quest/session/board_guide.dart';

void main() {
  Widget at(BoardOutline o) => MaterialApp(home: Scaffold(body: SizedBox(width: 400, height: 800, child: o)));

  testWidgets('the live outline: the board and the Arduino where they were found, then gliding to new corners',
      (tester) async {
    const board = [Offset(0.5, 0.1), Offset(0.9, 0.1), Offset(0.9, 0.9), Offset(0.5, 0.9)];
    const uno = [Offset(0.1, 0.2), Offset(0.4, 0.2), Offset(0.4, 0.45), Offset(0.1, 0.45)];
    await tester.pumpWidget(at(const BoardOutline(arduino: true, hint: 'Hold still', board: board, uno: uno)));
    expect(find.text('Hold still'), findsOneWidget);
    const moved = [Offset(0.45, 0.12), Offset(0.88, 0.1), Offset(0.92, 0.88), Offset(0.47, 0.9)];
    await tester.pumpWidget(at(const BoardOutline(arduino: true, ready: true, board: moved, uno: uno)));
    await tester.pump(const Duration(milliseconds: 150));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(at(const BoardOutline(arduino: true)));  // lost: back to the guide
    expect(tester.takeException(), isNull);
  });
}
