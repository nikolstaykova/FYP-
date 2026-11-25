import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:parts_quest/session/photo_guide.dart';

void main() {
  testWidgets('the gather guide moves from the first photo to the resistor close up, and Skip closes it', (tester) async {
    var done = 0;
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: PhotoGuide(kind: GuideKind.gather, onDone: () => done++))));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.textContaining('Photo 1'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 5500)); // past the move (9 s a round)
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.textContaining('resistor close up'), findsOneWidget);
    await tester.tap(find.text('Skip'));
    expect(done, 1);
    await tester.pumpWidget(const SizedBox());
  });

  test('no resistor in the lesson: only the photo from above; the LED guide ends low at the side', () {
    expect(guidePages(GuideKind.gather, resistor: false).length, 1);
    expect(guidePages(GuideKind.ledSide).last.tilt, greaterThan(30));
  });

  test('the timeline: still, then a smooth move, then back for the next round', () {
    expect(GuideTimeline.move(0.2), 0);
    expect(GuideTimeline.move(0.53), inExclusiveRange(0.2, 0.8));
    expect(GuideTimeline.move(0.8), 1);
    expect(GuideTimeline.move(0.999), lessThan(0.05));
    expect(GuideTimeline.flash(GuideTimeline.snap1), 1);
    expect(GuideTimeline.flash(GuideTimeline.snap2, two: false), 0);
    // no jumps: small steps in time make small steps in the move
    for (var u = 0.0; u < 1; u += 0.005) {
      expect((GuideTimeline.move(u + 0.005) - GuideTimeline.move(u)).abs(), lessThan(0.1)); // 45 ms steps
    }
  });
}
