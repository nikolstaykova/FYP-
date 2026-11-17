// How to take the photo of the board for a step check: shown before the phone's camera opens. The step check reads
// which column each leg is in, so the board must be big, straight and sharp in the photo (the server also checks the
// photo before any model looks: validator/board.py quality()).
import 'dart:math' as math;

import 'package:flutter_animate/flutter_animate.dart';
import 'package:material_ui/material_ui.dart';

import '../theme.dart';

class BoardGuide extends StatelessWidget {
  const BoardGuide({super.key});

  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, children: [
        AspectRatio(
          aspectRatio: 1.9,
          child: CustomPaint(painter: _GuidePainter()),
        ).animate().fadeIn(duration: 400.ms).scale(begin: const Offset(0.96, 0.96), curve: Curves.easeOutBack),
        const SizedBox(height: 14),
        for (final (i, (icon, text)) in const [
          (Icons.screen_rotation_rounded, 'Hold the phone sideways'),
          (Icons.fit_screen_rounded, 'Fill the screen with the breadboard, printed numbers showing'),
          (Icons.vertical_align_bottom_rounded, 'Straight above it, not at an angle'),
          (Icons.center_focus_strong_rounded, 'Tap the board to focus before you take it'),
        ].indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(children: [
              Icon(icon, size: 20, color: Pq.electronics),
              const SizedBox(width: 10),
              Expanded(child: Text(text, style: const TextStyle(fontWeight: FontWeight.w600))),
            ]),
          ).animate().fadeIn(delay: (120 + 80 * i).ms).slideX(begin: 0.08),
      ]);
}

/// A phone held sideways with the breadboard filling its screen.
class _GuidePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size s) {
    final phone = RRect.fromRectAndRadius(Rect.fromLTWH(4, 4, s.width - 8, s.height - 8), const Radius.circular(22));
    canvas.drawRRect(phone, Paint()..color = const Color(0xFF1C1B19));
    final screen = Rect.fromLTWH(22, 14, s.width - 44, s.height - 28);
    canvas.drawRRect(RRect.fromRectAndRadius(screen, const Radius.circular(10)), Paint()..color = const Color(0xFFE9E4D8));
    // the board, filling the screen
    final b = screen.deflate(math.min(screen.width, screen.height) * 0.06);
    canvas.drawRRect(RRect.fromRectAndRadius(b, const Radius.circular(6)), Paint()..color = Colors.white);
    final rail = b.height * 0.13;
    final red = Paint()
      ..color = const Color(0xFFE5484D)
      ..strokeWidth = 1.6;
    final blue = Paint()
      ..color = const Color(0xFF2A78D6)
      ..strokeWidth = 1.6;
    canvas.drawLine(Offset(b.left + 6, b.top + 3), Offset(b.right - 6, b.top + 3), red);
    canvas.drawLine(Offset(b.left + 6, b.top + rail), Offset(b.right - 6, b.top + rail), blue);
    canvas.drawLine(Offset(b.left + 6, b.bottom - rail), Offset(b.right - 6, b.bottom - rail), red);
    canvas.drawLine(Offset(b.left + 6, b.bottom - 3), Offset(b.right - 6, b.bottom - 3), blue);
    // the holes: 30 columns, 5 rows a half, a channel down the middle
    const cols = 30;
    final dx = (b.width - 24) / (cols - 1);
    final top = b.top + rail + b.height * 0.13, half = (b.height - 2 * rail) * 0.3;
    final dy = half / 4;
    final hole = Paint()..color = const Color(0xFF8A857A);
    for (var k = 0; k < cols; k++) {
      final x = b.left + 12 + k * dx;
      for (var r = 0; r < 5; r++) {
        canvas.drawRect(Rect.fromCenter(center: Offset(x, top + r * dy), width: 2.6, height: 2.6), hole);
        canvas.drawRect(Rect.fromCenter(center: Offset(x, top + half + dy * 1.6 + r * dy), width: 2.6, height: 2.6), hole);
      }
      if ((k + 1) % 5 == 0 || k == 0) {  // the printed numbers along the top edge
        final tp = TextPainter(
          text: TextSpan(text: '${k + 1}', style: const TextStyle(fontSize: 8, color: Color(0xFF1C1B19), fontWeight: FontWeight.w700)),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(x - tp.width / 2, top - dy - tp.height + 1));
      }
    }
    // a resistor and an LED, as in a step
    final legs = Paint()
      ..color = const Color(0xFF9A978F)
      ..strokeWidth = 1.4;
    final x1 = b.left + 12 + 9 * dx, x2 = b.left + 12 + 13 * dx;
    canvas.drawLine(Offset(x1, top + dy), Offset(x1, top - dy * 0.4), legs);
    canvas.drawLine(Offset(x2, top + dy), Offset(x2, top - dy * 0.4), legs);
    canvas.drawLine(Offset(x1, top - dy * 0.4), Offset(x2, top - dy * 0.4), legs);
    canvas.drawRRect(
        RRect.fromRectAndRadius(Rect.fromCenter(center: Offset((x1 + x2) / 2, top - dy * 0.4), width: dx * 2.2, height: dy * 0.9),
            const Radius.circular(3)),
        Paint()..color = const Color(0xFFD9B98C));
    final x3 = b.left + 12 + 14 * dx;
    canvas.drawLine(Offset(x2, top + 2 * dy), Offset(x2 + dx * 0.4, top - dy * 0.2), legs);
    canvas.drawLine(Offset(x3 + dx, top + 2 * dy), Offset(x3 + dx * 0.6, top - dy * 0.2), legs);
    canvas.drawCircle(Offset(x3 + dx * 0.5, top - dy * 0.9), dy * 0.7, Paint()..color = const Color(0xFFEB6834));
    // corner marks: "fill this"
    final mark = Paint()
      ..color = Pq.have
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    final f = screen.deflate(4);
    const l = 16.0;
    for (final (x, y, sx, sy) in [(f.left, f.top, 1.0, 1.0), (f.right, f.top, -1.0, 1.0), (f.left, f.bottom, 1.0, -1.0), (f.right, f.bottom, -1.0, -1.0)]) {
      canvas.drawPath(Path()
        ..moveTo(x, y + sy * l)
        ..lineTo(x, y)
        ..lineTo(x + sx * l, y), mark);
    }
  }

  @override
  bool shouldRepaint(_) => false;
}
