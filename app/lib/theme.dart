import 'package:cupertino_ui/cupertino_ui.dart' show CupertinoPageTransitionsBuilder;
import 'package:material_ui/material_ui.dart';

import 'models.dart';

/// Colours: the warm paper of the web game, with one bright colour per kind of lesson.
class Pq {
  static const paper = Color(0xFFF6F3EC);
  static const paperDark = Color(0xFF141413);
  static const ink = Color(0xFF1C1B19);
  static const muted = Color(0xFF6D6A62);

  static const electronics = Color(0xFF2A78D6);
  static const lego = Color(0xFFEB6834);
  static const booklet = Color(0xFFE0A21B);

  static const have = Color(0xFF1BAF7A);
  static const swap = Color(0xFF7D5BD6);
  static const check = Color(0xFFE0A21B);
  static const missing = Color(0xFFD9453B);
  static const skipped = Color(0xFF9A978F);

  static Color forLesson(LessonSummary l) => !l.isLego ? electronics : l.isBooklet ? booklet : lego;

  static IconData iconFor(LessonSummary l) =>
      !l.isLego ? Icons.memory_rounded : l.isBooklet ? Icons.menu_book_rounded : Icons.view_in_ar_rounded;

  static String kindLabel(LessonSummary l) => !l.isLego ? 'Electronics' : l.isBooklet ? 'LEGO · booklet' : 'LEGO · 3D';

  static Color forVerdict(Verdict v) => switch (v) {
        Verdict.have => have,
        Verdict.swap => swap,
        Verdict.check => check,
        Verdict.missing => missing,
        Verdict.skipped => skipped,
      };

  static IconData verdictIcon(Verdict v) => switch (v) {
        Verdict.have => Icons.check_rounded,
        Verdict.swap => Icons.swap_horiz_rounded,
        Verdict.check => Icons.question_mark_rounded,
        Verdict.missing => Icons.close_rounded,
        Verdict.skipped => Icons.remove_rounded,
      };

  static String verdictLabel(Verdict v) => switch (v) {
        Verdict.have => 'Found',
        Verdict.swap => 'Use another',
        Verdict.check => 'Not sure',
        Verdict.missing => 'Missing',
        Verdict.skipped => "Don't have",
      };

  /// A LEGO colour name ("Light Bluish Gray", "Trans-Clear") as a swatch.
  static Color brick(String? name) {
    final n = (name ?? '').toLowerCase().replaceAll('-', ' ');
    const table = <String, int>{
      'black': 0xFF1B2A34, 'white': 0xFFF4F4F4, 'red': 0xFFC91A09, 'dark red': 0xFF720E0F, 'blue': 0xFF0055BF,
      'dark blue': 0xFF0A3463, 'medium blue': 0xFF5A93DB, 'yellow': 0xFFF2CD37, 'green': 0xFF237841,
      'dark green': 0xFF184632, 'bright green': 0xFF4B9F4A, 'lime': 0xFFBBE90B, 'orange': 0xFFFE8A18,
      'tan': 0xFFE4CD9E, 'dark tan': 0xFF958A73, 'brown': 0xFF583927, 'reddish brown': 0xFF582A12,
      'light bluish gray': 0xFFA0A5A9, 'dark bluish gray': 0xFF6C6E68, 'light gray': 0xFF9BA19D,
      'dark gray': 0xFF6D6E5C, 'pink': 0xFFFC97AC, 'dark pink': 0xFFC870A0, 'purple': 0xFF81007B,
      'magenta': 0xFF923978, 'pearl gold': 0xFFAA7F2E, 'flat silver': 0xFF898788, 'trans clear': 0xFFE8F4F8,
      'trans red': 0xFFE8504B, 'trans yellow': 0xFFF5CD2F, 'trans light blue': 0xFFAEEFEC, 'trans green': 0xFF84B68D,
      'trans dark blue': 0xFF4F7BC9, 'trans orange': 0xFFF08F1C, 'sand green': 0xFFA0BCAC, 'dark orange': 0xFFA95500,
      'medium azure': 0xFF36AEBF, 'dark azure': 0xFF078BC9, 'bright light orange': 0xFFF8BB3D,
    };
    for (final k in table.keys.toList()..sort((a, b) => b.length.compareTo(a.length))) {
      if (n.contains(k)) return Color(table[k]!);
    }
    return const Color(0xFFBDB9AE);
  }
}

ThemeData buildTheme(Brightness b) {
  final dark = b == Brightness.dark;
  final scheme = ColorScheme.fromSeed(
    seedColor: Pq.electronics,
    brightness: b,
    surface: dark ? const Color(0xFF1E1E1C) : Colors.white,
  );
  final base = ThemeData(useMaterial3: true, colorScheme: scheme, brightness: b);
  final text = base.textTheme.apply(
    bodyColor: dark ? const Color(0xFFEDEBE5) : Pq.ink,
    displayColor: dark ? const Color(0xFFEDEBE5) : Pq.ink,
  );
  return base.copyWith(
    scaffoldBackgroundColor: dark ? Pq.paperDark : Pq.paper,
    textTheme: text.copyWith(
      displaySmall: text.displaySmall?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -1),
      headlineMedium: text.headlineMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.6),
      titleLarge: text.titleLarge?.copyWith(fontWeight: FontWeight.w700, letterSpacing: -0.3),
      titleMedium: text.titleMedium?.copyWith(fontWeight: FontWeight.w700),
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
      foregroundColor: dark ? Colors.white : Pq.ink,
      elevation: 0,
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: dark ? const Color(0xFF1E1E1C) : Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      margin: EdgeInsets.zero,
    ),
    chipTheme: base.chipTheme.copyWith(shape: const StadiumBorder(), side: BorderSide.none),
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: CupertinoPageTransitionsBuilder(),
      TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
    }),
  );
}
