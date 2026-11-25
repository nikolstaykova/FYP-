// A short animated guide to the photos a check needs, shown over the camera while Pip explains; skippable.
// One continuous scene, played round until skipped: the phone takes the first photo (a flash), then glides to where
// the second one is taken while the picture moves with it (zooms into the resistor; tilts to the LED's side view),
// and the second photo appears. The pictures are the learner's own photos (assets/guide); a small drawing beside
// them shows where the phone is (flat above, close, or low at the side).

import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../theme.dart';

/// How the first picture turns into the second one.
enum GuideMove { none, zoom, tilt }

/// One photo of the guide: an example photo, what to do, and where the phone is (degrees from flat above).
class GuidePage {
  const GuidePage(this.image, this.caption, this.tilt, {this.close = false, this.focus = Alignment.center});
  final String image;
  final String caption;
  final double tilt; // 0: straight above; 35-45: low from the side
  final bool close; // the phone close to the part (a close-up)
  final Alignment focus; // where in this photo the next one is taken (the move zooms or tilts towards it)
}

enum GuideKind { gather, ledSide }

List<GuidePage> guidePages(GuideKind k, {bool resistor = true}) => switch (k) {
      GuideKind.gather => [
          const GuidePage('assets/guide/parts_above.jpg', 'Photo 1: all the parts, straight from above, a little apart', 0,
              focus: Alignment(-0.25, 0.7)), // the resistor in that photo
          if (resistor)
            const GuidePage('assets/guide/resistor_close.jpg',
                'Photo 2: the resistor close up, on white paper, filling the photo, so its colour bands show', 0,
                close: true),
        ],
      GuideKind.ledSide => const [
          GuidePage('assets/guide/led_above.jpg', 'From above, the LED hides one of its legs', 0,
              focus: Alignment(0.04, 0.02)), // the LED in that photo
          GuidePage('assets/guide/led_side.jpg', 'So one more: low from the side, aimed at the LED: both legs show', 40),
        ],
    };

GuideMove guideMove(GuideKind k) => switch (k) {
      GuideKind.gather => GuideMove.zoom,
      GuideKind.ledSide => GuideMove.tilt,
    };

String guideTitle(GuideKind k) => switch (k) {
      GuideKind.gather => 'How to take the photos',
      GuideKind.ledSide => 'One more photo, from the side',
    };

/// The scene's timeline, as fractions of one round (two photos; one photo: only the first part).
class GuideTimeline {
  static const snap1 = 0.10; // the first photo is taken (a flash)
  static const moveFrom = 0.40, moveTo = 0.66; // the phone glides to the second place, the picture with it
  static const fadeFrom = 0.56, fadeTo = 0.68; // the second photo comes in over the moving first
  static const snap2 = 0.70;
  static const backFrom = 0.9; // round again: back to the first photo

  static double _ease(double a, double b, double u) => Curves.easeInOut.transform(((u - a) / (b - a)).clamp(0.0, 1.0));

  /// How far the phone and the picture have moved towards the second photo (0..1).
  static double move(double u) => u >= backFrom ? 1 - _ease(backFrom, 1, u) : _ease(moveFrom, moveTo, u);

  /// How much of the second photo shows (0..1).
  static double fade(double u) => u >= backFrom ? 1 - _ease(backFrom, 1, u) : _ease(fadeFrom, fadeTo, u);

  /// The camera's flash at each photo (0..1).
  static double flash(double u, {bool two = true}) {
    double pulse(double at) {
      final d = (u - at).abs();
      return d > 0.03 ? 0 : 1 - d / 0.03;
    }
    return math.max(pulse(snap1), two ? pulse(snap2) : 0);
  }

  /// Which photo the words are about.
  static int page(double u) => u >= 0.53 && u < backFrom + 0.03 ? 1 : 0;
}

/// The guide: a card over a dimmed screen with the scene, the words for the photo it is on, Skip and Got it.
class PhotoGuide extends StatefulWidget {
  const PhotoGuide({super.key, required this.kind, required this.onDone, this.resistor = true});
  final GuideKind kind;
  final VoidCallback onDone;
  final bool resistor;

  @override
  State<PhotoGuide> createState() => _PhotoGuideState();
}

class _PhotoGuideState extends State<PhotoGuide> with SingleTickerProviderStateMixin {
  late final List<GuidePage> _pages = guidePages(widget.kind, resistor: widget.resistor);
  late final AnimationController _t =
      AnimationController(vsync: this, duration: Duration(milliseconds: _pages.length > 1 ? 9000 : 4500))..repeat();

  @override
  void dispose() {
    _t.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
                  child: AnimatedBuilder(
                    animation: _t,
                    builder: (context, _) => _card(_t.value),
                  ),
                ),
              ),
            ),
          ).animate().fadeIn(duration: 250.ms).scale(begin: const Offset(0.96, 0.96), curve: Curves.easeOut),
        ),
      ),
    );
  }

  Widget _card(double u) {
    final two = _pages.length > 1;
    final i = two ? GuideTimeline.page(u) : 0;
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text(guideTitle(widget.kind), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: Pq.ink)),
      const SizedBox(height: 10),
      AspectRatio(
        aspectRatio: 4 / 3,
        child: ClipRRect(borderRadius: BorderRadius.circular(14), child: _scene(u, two)),
      ),
      const SizedBox(height: 10),
      SizedBox(
        height: 64,
        child: AnimatedSwitcher(
          duration: 350.ms,
          child: Align(
            key: ValueKey('c$i'),
            alignment: Alignment.topLeft,
            child: Text(_pages[i].caption,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Pq.ink, height: 1.3)),
          ),
        ),
      ),
      Row(children: [
        for (var k = 0; k < _pages.length; k++)
          AnimatedContainer(
            duration: 250.ms,
            width: k == i ? 20 : 8,
            height: 8,
            margin: const EdgeInsets.only(right: 6),
            decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(4), color: k == i ? Pq.ink : Pq.muted.withValues(alpha: 0.35)),
          ),
        const Spacer(),
        TextButton(onPressed: widget.onDone, child: const Text('Skip')),
        FilledButton(onPressed: widget.onDone, child: const Text('Got it')),
      ]),
    ]);
  }

  /// The pictures and the phone, at moment [u] of the round.
  Widget _scene(double u, bool two) {
    final a = _pages.first;
    final b = two ? _pages[1] : null;
    final m = two ? GuideTimeline.move(u) : 0.0;
    final f = two ? GuideTimeline.fade(u) : 0.0;
    // the first photo: settles in after its flash, then moves with the phone (zooms into the part, or tilts away)
    final settle = Curves.easeOut.transform((u / GuideTimeline.snap1).clamp(0.0, 1.0));
    Matrix4 first;
    switch (two ? guideMove(widget.kind) : GuideMove.none) {
      case GuideMove.zoom:
        first = Matrix4.identity()..scaleByDouble(1 + 2.2 * m, 1 + 2.2 * m, 1, 1);
      case GuideMove.tilt:
        first = Matrix4.identity()
          ..setEntry(3, 2, 0.0015)
          ..rotateX(-0.75 * m)
          ..scaleByDouble(1 + 0.25 * m, 1 + 0.25 * m, 1, 1);
      case GuideMove.none:
        first = Matrix4.identity()..scaleByDouble(1.08 - 0.08 * settle, 1.08 - 0.08 * settle, 1, 1);
    }
    final tilt = b == null ? a.tilt : a.tilt + (b.tilt - a.tilt) * m;
    final close = b == null ? (a.close ? 1.0 : 0.0) : ((a.close ? 1.0 : 0.0) + ((b.close ? 1.0 : 0.0) - (a.close ? 1.0 : 0.0)) * m);
    return Stack(fit: StackFit.expand, children: [
      const ColoredBox(color: Color(0xFFEDEAE3)),
      Transform(
        alignment: a.focus,
        transform: first,
        child: Image.asset(a.image, fit: BoxFit.cover, alignment: a.focus),
      ),
      if (b != null && f > 0)
        Opacity(
          opacity: f,
          child: Transform.scale(scale: 1.06 - 0.06 * f, child: Image.asset(b.image, fit: BoxFit.cover)),
        ),
      // the camera's flash at each photo
      IgnorePointer(
        child: Opacity(
          opacity: 0.75 * GuideTimeline.flash(u, two: two),
          child: const ColoredBox(color: Colors.white),
        ),
      ),
      Positioned(
        right: 8,
        bottom: 8,
        width: 120,
        height: 90,
        child: DecoratedBox(
          decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.9), borderRadius: BorderRadius.circular(10)),
          child: CustomPaint(painter: PhonePainter(tilt, close, flash: GuideTimeline.flash(u, two: two))),
        ),
      ),
    ]);
  }
}

/// Seen from the side: the table with the parts and the phone, flat above them (tilt 0) or low at their edge (tilt
/// 40), far (close 0) or near (close 1), with the line it looks along; it lights up as it takes a photo.
class PhonePainter extends CustomPainter {
  PhonePainter(this.tilt, this.close, {this.flash = 0});
  final double tilt;
  final double close;
  final double flash;

  @override
  void paint(Canvas canvas, Size s) {
    final board = Paint()..color = const Color(0xFFE9E2D2);
    final edge = Paint()
      ..color = const Color(0xFF9A9384)
      ..style = PaintingStyle.stroke;
    final r = Rect.fromLTWH(s.width * 0.18, s.height * 0.76, s.width * 0.64, s.height * 0.09);
    canvas.drawRect(r, board);
    canvas.drawRect(r, edge);
    final target = Offset(s.width * 0.5, r.top);
    canvas.drawCircle(target - const Offset(0, 4), 4, Paint()..color = const Color(0xFF3B7BD9)); // the part
    // the phone on an arc round the part: straight above at tilt 0, lower and to the side as it tilts; nearer as it
    // comes close
    final dist = s.height * (0.6 - 0.26 * close);
    final a = tilt * math.pi / 180;
    final phone = target + Offset(-math.sin(a) * dist * 1.25, -math.cos(a) * dist);
    final look = Paint()
      ..color = const Color(0xFF2A78D6).withValues(alpha: 0.5 + 0.5 * flash)
      ..strokeWidth = 1.6 + 1.6 * flash;
    canvas.drawLine(phone, target, look);
    canvas.save();
    canvas.translate(phone.dx, phone.dy);
    canvas.rotate(-math.atan2(target.dx - phone.dx, target.dy - phone.dy));
    canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromCenter(center: Offset.zero, width: 34, height: 7), const Radius.circular(2)),
        Paint()..color = Color.lerp(const Color(0xFF333333), const Color(0xFFFFD54F), flash)!);
    canvas.restore();
  }

  @override
  bool shouldRepaint(PhonePainter old) => old.tilt != tilt || old.close != close || old.flash != flash;
}
