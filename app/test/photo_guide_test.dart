import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:parts_quest/session/photo_guide.dart';

void main() {
  testWidgets('the gather guide shows its photos in turn and Skip closes it', (tester) async {
    var done = 0;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PhotoGuide(kind: GuideKind.gather, onDone: () => done++))));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.textContaining('Photo 1'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 3700));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.textContaining('resistor close up'), findsOneWidget);
    await tester.tap(find.text('Skip'));
    expect(done, 1);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('no resistor in the lesson: only the photo from above', (tester) async {
    expect(guidePages(GuideKind.gather, resistor: false).length, 1);
    expect(guidePages(GuideKind.ledSide).last.tilt, greaterThan(30));
  });
}
