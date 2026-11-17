// The page's audio (Pip's voice, the mic) after the browser suspended it: see web/index.html.
import 'dart:js_interop';

@JS('pipWakeSound')
external JSFunction? get _wake;

@JS('pipSoundBlocked')
external JSFunction? get _blocked;

/// Start the page's audio again (works without a tap on most browsers; iPhones may need one).
void wakeSound() {
  try {
    _wake?.callAsFunction();
  } catch (_) {}
}

/// Some of the page's audio is still stopped: the learner needs to tap.
bool soundBlocked() {
  try {
    final r = _blocked?.callAsFunction();
    return r != null && (r as JSBoolean).toDart;
  } catch (_) {
    return false;
  }
}
