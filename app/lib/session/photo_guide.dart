// A short animated guide to the photos a check needs, shown over the camera while Pip explains; skippable.
// The pictures are the learner's own photos (assets/guide): what a good photo looks like, and a small drawing of
// where the phone is (flat above, close, or low at the side).

import 'dart:async';
import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../theme.dart';

/// One picture of the guide: an example photo, what to do, and where the phone is (degrees from flat above).
class GuidePage {
  const GuidePage(this.image, this.caption, this.tilt, {this.close = false});
  final String image;
  final String caption;
  final double tilt; // 0: straight above; 35-45: low from the side
  final bool close; // the phone close to the part (a close-up)
}

enum GuideKind { gather, ledSide }

List<GuidePage> guidePages(GuideKind k, {bool resistor = true}) => switch (k) {
      GuideKind.gather => [
          const GuidePage('assets/guide/parts_above.jpg', 'Photo 1: all the parts, straight from above, a little apart', 0),
          if (resistor)
            const GuidePage('assets/guide/resistor_close.jpg',
                'Photo 2: the resistor close up, on white paper, filling the photo, so its colour bands show', 0,
                close: true),
        ],
      GuideKind.ledSide => const [
          GuidePage('assets/guide/led_above.jpg', 'From above, the LED hides one of its legs', 0),
          GuidePage('assets/guide/led_side.jpg', 'So one more: low from the side, aimed at the LED: both legs show', 40),
        ],
    };

String guideTitle(GuideKind k) => switch (k) {
      GuideKind.gather => 'The photos',
      GuideKind.ledSide => 'One more photo, from the side',
    };

/// The guide: a card over a dimmed screen, its pictures in turn (about 3.5 s each, round again until skipped).
class PhotoGuide extends StatefulWidget {
  const PhotoGuide({super.key, required this.kind, required this.onDone, this.resistor = true});
  final GuideKind kind;
  final VoidCallback onDone;
  final bool resistor;

  @override
  State<PhotoGuide> createState() => _PhotoGuideState();
}

class _PhotoGuideState extends State<PhotoGuide> {
  int _i = 0;
  Timer? _t;
  late final List<GuidePage> _pages = guidePages(widget.kind, resistor: widget.resistor);

  @override
  void initState() {
    super.initState();
    if (_pages.length > 1) {
      _t = Timer.periodic(const Duration(milliseconds: 3600), (_) {
        if (mounted) setState(() => _i = (_i + 1) % _pages.length);
      });
    }
  }

  @override
  void dispose() {
    _t?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = _pages[_i];
    final prev = _pages[(_i - 1 + _pages.length) % _pages.length];
    return GestureDetector(
      onTap: widget.onDone,
      child: ColoredBox(
        color: Colors.black.withValues(alpha: 0.55),
        child: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: GestureDetector(
                onTap: () {}, // taps on the card do not close it
                child: Container(
                  margin: const EdgeInsets.all(16),
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
                  decoration: BoxDecoration(color: Pq.paper, borderRadius: BorderRadius.circular(22)),
                  child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Text(guideTitle(widget.kind),
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: Pq.ink)),
                    const SizedBox(height: 10),
                    AspectRatio(
                      aspectRatio: 4 / 3,
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: AnimatedSwitcher(
                          duration: 450.ms,
                          child: Stack(key: ValueKey(_i), fit: StackFit.expand, children: [
                            // the example photo, drifting in slowly (a close-up zooms in)
                            Image.asset(p.image, fit: BoxFit.cover)
                                .animate()
                                .scale(begin: Offset(p.close ? 0.8 : 1.0, p.close ? 0.8 : 1.0),
                                    end: Offset(p.close ? 1.08 : 1.06, p.close ? 1.08 : 1.06), duration: 3400.ms),
                            Positioned(
                              right: 8,
                              bottom: 8,
                              width: 112,
                              height: 84,
                              child: DecoratedBox(
                                decoration: BoxDecoration(
                                    color: Colors.white.withValues(alpha: 0.88), borderRadius: BorderRadius.circular(10)),
                                child: TweenAnimationBuilder<double>(
                                  tween: Tween(begin: prev.tilt, end: p.tilt),
                                  duration: 900.ms,
                                  curve: Curves.easeInOut,
                                  builder: (_, tilt, _) => CustomPaint(painter: _PhonePainter(tilt, p.close)),
                                ),
                              ),
                            ),
                          ]),
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    AnimatedSwitcher(
                      duration: 300.ms,
                      child: Text(p.caption,
                          key: ValueKey('c$_i'),
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Pq.ink, height: 1.3)),
                    ),
                    const SizedBox(height: 6),
                    Row(children: [
                      for (var k = 0; k < _pages.length; k++)
                        Container(
                          width: 8,
                          height: 8,
                          margin: const EdgeInsets.only(right: 6),
                          decoration: BoxDecoration(
                              shape: BoxShape.circle, color: k == _i ? Pq.ink : Pq.muted.withValues(alpha: 0.35)),
                        ),
                      const Spacer(),
                      TextButton(onPressed: widget.onDone, child: const Text('Skip')),
                      FilledButton(onPressed: widget.onDone, child: const Text('Got it')),
                    ]),
                  ]),
                ),
              ),
            ),
          ).animate().fadeIn(duration: 250.ms).scale(begin: const Offset(0.96, 0.96), curve: Curves.easeOut),
        ),
      ),
    );
  }
}

/// Seen from the side: the board on the table and the phone, flat above it (tilt 0) or low at its edge (tilt 40),
/// with the line it looks along.
class _PhonePainter extends CustomPainter {
  _PhonePainter(this.tilt, this.close);
  final double tilt;
  final bool close;

  @override
  void paint(Canvas canvas, Size s) {
    final board = Paint()..color = const Color(0xFFE9E2D2);
    final edge = Paint()
      ..color = const Color(0xFF9A9384)
      ..style = PaintingStyle.stroke;
    final r = Rect.fromLTWH(s.width * 0.18, s.height * 0.74, s.width * 0.64, s.height * 0.1);
    canvas.drawRect(r, board);
    canvas.drawRect(r, edge);
    final target = Offset(s.width * 0.5, r.top);
    // the phone on an arc round the target: straight above at tilt 0, lower and to the side as it tilts
    final dist = close ? s.height * 0.34 : s.height * 0.58;
    final a = tilt * math.pi / 180;
    final phone = target + Offset(-math.sin(a) * dist * 1.2, -math.cos(a) * dist);
    final look = Paint()
      ..color = const Color(0xFF2A78D6)
      ..strokeWidth = 1.6;
    canvas.drawLine(phone, target, look);
    canvas.save();
    canvas.translate(phone.dx, phone.dy);
    canvas.rotate(-math.atan2(target.dx - phone.dx, target.dy - phone.dy));
    canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: Offset.zero, width: 30, height: 6), const Radius.circular(2)),
        Paint()..color = const Color(0xFF333333));
    canvas.restore();
    canvas.drawCircle(target, 3, Paint()..color = const Color(0xFF2A78D6));
  }

  @override
  bool shouldRepaint(_PhonePainter old) => old.tilt != tilt || old.close != close;
}
