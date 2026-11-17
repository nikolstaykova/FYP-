import 'package:flutter_test/flutter_test.dart';
import 'package:parts_quest/session/heard.dart';

void main() {
  test('"done" opens the step check; questions and "not yet" do not', () {
    for (final y in ["I'm done", 'done', 'Okay it\'s in', 'finished!', 'check it please', 'Ready.']) {
      expect(saysDone(y), isTrue, reason: y);
    }
    for (final n in ['not done yet', "I haven't finished", 'almost done', 'how do I put it in?', 'which column?', 'hello']) {
      expect(saysDone(n), isFalse, reason: n);
    }
  });
}
