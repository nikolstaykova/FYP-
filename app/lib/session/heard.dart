// What the learner says that the screen acts on itself (Pip did not always call the tool).

final _doneWords = RegExp(r"\b(done|finished|i did it|it'?s in|they'?re in|placed it|put it in|that'?s it|check (it|me)|ready)\b",
    caseSensitive: false);
final _notDone = RegExp(r"\b(not|almost|nearly|yet|how|what|where|which)\b|n't", caseSensitive: false);

/// "I'm done", "it's in", "check it": the step is finished (not "not done yet", "how do I...", "I haven't").
bool saysDone(String line) => _doneWords.hasMatch(line) && !_notDone.hasMatch(line);
