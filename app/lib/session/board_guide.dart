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

/// On the live camera, for a step check: the outline the breadboard should fill (big, so the photo is close), and
/// when the step wires to the Arduino, the Arduino's place beside it (one photo with both: the server cuts out each).
/// [hint] is what the live check says ("Closer", "Hold still"); [ready] turns the outline green.
class BoardOutline extends StatefulWidget {
  const BoardOutline({super.key, this.arduino = false, this.hint, this.ready = false});

  final bool arduino;
  final String? hint;
  final bool ready;

  static bool full = true; // a full-size board (about 3 : 1) or a half one (about 1.5 : 1)

  @override
  State<BoardOutline> createState() => _BoardOutlineState();
}

class _BoardOutlineState extends State<BoardOutline> {
  @override
  Widget build(BuildContext context) => Stack(fit: StackFit.expand, children: [
        IgnorePointer(child: CustomPaint(painter: _OutlinePainter(BoardOutline.full ? 3.0 : 1.5, widget.arduino, widget.ready))),
        if (widget.hint != null)
          Align(
            alignment: const Alignment(0, -0.05),
            child: IgnorePointer(
              child: AnimatedContainer(
                duration: 250.ms,
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  color: (widget.ready ? Pq.have : Colors.black).withValues(alpha: widget.ready ? 0.9 : 0.55),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(widget.hint!, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16)),
              ),
            ),
          ),
        Positioned(
          top: 40,
          left: 10,
          child: Container(
            padding: const EdgeInsets.all(2),
            decoration: BoxDecoration(color: Colors.black45, borderRadius: BorderRadius.circular(16)),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              for (final (full, label) in const [(true, 'Full'), (false, 'Half')])
                GestureDetector(
                  onTap: () => setState(() => BoardOutline.full = full),
                  child: AnimatedContainer(
                    duration: 200.ms,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                    decoration: BoxDecoration(
                      color: BoardOutline.full == full ? Colors.white : Colors.transparent,
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Text(label,
                        style: TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 12, color: BoardOutline.full == full ? Pq.ink : Colors.white)),
                  ),
                ),
            ]),
          ),
        ),
      ]);
}

/// The board's outline (and the Arduino's place): dims what is outside, corner marks, the rails and the middle gap
/// drawn faintly inside so the real board can be lined up with it.
class _OutlinePainter extends CustomPainter {
  _OutlinePainter(this.ratio, this.arduino, this.ready);

  final double ratio; // the board's long side / short side
  final bool arduino;
  final bool ready;

  @override
  void paint(Canvas canvas, Size s) {
    final wide = s.width >= s.height;
    // as big as the screen allows: the words at the top, the shutter row at the bottom
    final area = Rect.fromLTRB(s.width * 0.02, 72, s.width * 0.98, s.height - (wide ? 100 : 130));
    // with the Arduino: the board takes about 60% of the short side, the Arduino the rest beside its first end
    final share = arduino ? 0.6 : 1.0;
    var long = wide ? area.width : area.height, short = long / ratio;
    final room = (wide ? area.height : area.width) * share;
    if (short > room) {
      short = room;
      long = short * ratio;
    }
    final Rect r;
    Rect? uno;
    if (!arduino) {
      r = Rect.fromCenter(center: area.center, width: wide ? long : short, height: wide ? short : long);
    } else if (wide) {
      // board along the bottom, the Arduino above its left end
      r = Rect.fromLTWH(area.center.dx - long / 2, area.bottom - short, long, short);
      final h = math.min(area.height - short - 8, short * 1.4), w = h * 1.35;
      uno = Rect.fromLTWH(r.left, r.top - 8 - h, w, h);
    } else {
      // phone upright: board down the right, the Arduino beside its top end (as it usually sits)
      r = Rect.fromLTWH(area.right - short, area.center.dy - long / 2, short, long);
      final w = math.min(area.width - short - 8, short * 1.4), h = w * 1.35;
      uno = Rect.fromLTWH(r.left - 8 - w, r.top, w, h);
    }
    final hole = Path()..addRRect(RRect.fromRectAndRadius(r, const Radius.circular(10)));
    if (uno != null) hole.addRRect(RRect.fromRectAndRadius(uno, const Radius.circular(10)));
    canvas.drawPath(Path.combine(PathOperation.difference, Path()..addRect(Offset.zero & s), hole),
        Paint()..color = Colors.black.withValues(alpha: 0.35));
    final edge = Paint()
      ..color = (ready ? Pq.have : Colors.white).withValues(alpha: ready ? 0.95 : 0.6)
      ..strokeWidth = ready ? 3 : 1.5
      ..style = PaintingStyle.stroke;
    canvas.drawRRect(RRect.fromRectAndRadius(r, const Radius.circular(10)), edge);
    void across(double f, Color c, {double w = 2}) {
      final p = Paint()
        ..color = c.withValues(alpha: 0.6)
        ..strokeWidth = w;
      if (wide) {
        final y = r.top + r.height * f;
        canvas.drawLine(Offset(r.left + 10, y), Offset(r.right - 10, y), p);
      } else {
        final x = r.left + r.width * f;
        canvas.drawLine(Offset(x, r.top + 10), Offset(x, r.bottom - 10), p);
      }
    }

    across(0.05, const Color(0xFFE5484D));
    across(0.15, const Color(0xFF2A78D6));
    across(0.85, const Color(0xFFE5484D));
    across(0.95, const Color(0xFF2A78D6));
    across(0.5, Colors.white, w: 6);
    if (uno != null) {
      canvas.drawRRect(RRect.fromRectAndRadius(uno, const Radius.circular(10)), edge);
      final tp = TextPainter(
        text: const TextSpan(text: 'Arduino', style: TextStyle(color: Colors.white70, fontSize: 14, fontWeight: FontWeight.w800)),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, uno.center - Offset(tp.width / 2, tp.height / 2));
    }
    final mark = Paint()
      ..color = Pq.have
      ..strokeWidth = 5
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    for (final b in [r, ?uno]) {
      final l = math.min(34.0, b.shortestSide * 0.25);
      for (final (x, y, sx, sy) in [(b.left, b.top, 1.0, 1.0), (b.right, b.top, -1.0, 1.0), (b.left, b.bottom, 1.0, -1.0), (b.right, b.bottom, -1.0, -1.0)]) {
        canvas.drawPath(Path()
          ..moveTo(x, y + sy * l)
          ..lineTo(x, y)
          ..lineTo(x + sx * l, y), mark);
      }
    }
  }

  @override
  bool shouldRepaint(_OutlinePainter old) => old.ratio != ratio || old.arduino != arduino || old.ready != ready;
}
