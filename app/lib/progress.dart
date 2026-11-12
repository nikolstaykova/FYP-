// What the learner has done, kept on the phone: finished gather cards and ticked pieces.
import 'package:shared_preferences/shared_preferences.dart';

class Progress {
  static SharedPreferences? _p;
  static Future<SharedPreferences> get _prefs async => _p ??= await SharedPreferences.getInstance();

  static Future<Set<int>> doneCards(String lesson) async =>
      ((await _prefs).getStringList('done:$lesson') ?? const []).map(int.parse).toSet();

  static Future<void> markDone(String lesson, int card) async {
    final s = await doneCards(lesson)..add(card);
    await (await _prefs).setStringList('done:$lesson', [for (final c in s) '$c']);
  }

  static Future<Set<int>> ticked(String lesson, int card) async =>
      ((await _prefs).getStringList('got:$lesson:$card') ?? const []).map(int.parse).toSet();

  static Future<void> setTicked(String lesson, int card, Set<int> got) async =>
      (await _prefs).setStringList('got:$lesson:$card', [for (final g in got) '$g']);
}
