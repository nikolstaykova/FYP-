// The photo guide's scene in 3D: the table with the parts (or the breadboard with the LED), drawn as shaded boxes and
// cylinders from a slowly turning view, and the phone flying to where each photo is taken, its view drawn as a cone,
// flashing as it takes the photo. A small renderer of its own (no 3D package): flat-shaded faces, back faces culled,
// drawn far to near, layer by layer (table, board, parts on it, phone).

import 'dart:math' as math;
import 'dart:ui' show PointMode;

import 'package:material_ui/material_ui.dart';

class V3 {
  const V3(this.x, this.y, this.z);
  final double x, y, z;
  V3 operator +(V3 o) => V3(x + o.x, y + o.y, z + o.z);
  V3 operator -(V3 o) => V3(x - o.x, y - o.y, z - o.z);
  V3 operator *(double k) => V3(x * k, y * k, z * k);
  double dot(V3 o) => x * o.x + y * o.y + z * o.z;
  V3 cross(V3 o) => V3(y * o.z - z * o.y, z * o.x - x * o.z, x * o.y - y * o.x);
  double get len => math.sqrt(dot(this));
  V3 get unit => this * (1 / len);
  static V3 lerp(V3 a, V3 b, double t) => a + (b - a) * t;
}

class Face3 {
  Face3(this.pts, this.colour, this.normal);
  final List<V3> pts;
  final Color colour;
  final V3 normal;
  V3 get mid => pts.fold(const V3(0, 0, 0), (a, p) => a + p) * (1 / pts.length);
}

class Line3 {
  Line3(this.pts, this.colour, this.width);
  final List<V3> pts;
  final Color colour;
  final double width; // in cm (drawn thinner far away)
}

/// One thing in the scene: its faces, then what is drawn on it (holes, lines), in one layer.
class Obj3 {
  Obj3(this.layer, this.faces, {this.lines = const [], this.dots = const [], this.dotColour = Colors.black});
  final int layer;
  final List<Face3> faces;
  final List<Line3> lines;
  final List<V3> dots;
  final Color dotColour;
  V3 get mid => faces.isEmpty
      ? (lines.isEmpty ? const V3(0, 0, 0) : lines.first.pts.first)
      : faces.fold(const V3(0, 0, 0), (a, f) => a + f.mid) * (1 / faces.length);
}

List<Face3> _box(V3 c, double sx, double sy, double sz, Color colour, {Color? top}) {
  V3 v(int i) => V3(c.x + (i & 1 == 1 ? sx : -sx) / 2, c.y + (i & 2 == 2 ? sy : -sy) / 2, c.z + (i & 4 == 4 ? sz : -sz) / 2);
  Face3 f(List<int> ix, V3 n, [Color? col]) => Face3([for (final i in ix) v(i)], col ?? colour, n);
  return [
    f([0, 2, 3, 1], const V3(0, 0, -1)),
    f([4, 5, 7, 6], const V3(0, 0, 1), top),
    f([0, 1, 5, 4], const V3(0, -1, 0)),
    f([2, 6, 7, 3], const V3(0, 1, 0)),
    f([0, 4, 6, 2], const V3(-1, 0, 0)),
    f([1, 3, 7, 5], const V3(1, 0, 0)),
  ];
}

/// A box along any three axes (the phone): centre, half sizes along r, u, f.
List<Face3> _orientedBox(V3 c, V3 r, V3 u, V3 f, double w, double h, double t, Color colour, {Color? front, Color? back}) {
  V3 v(int i) => c + r * ((i & 1 == 1 ? w : -w) / 2) + u * ((i & 2 == 2 ? h : -h) / 2) + f * ((i & 4 == 4 ? t : -t) / 2);
  Face3 face(List<int> ix, V3 n, Color col) => Face3([for (final i in ix) v(i)], col, n);
  return [
    face([0, 1, 3, 2], f * -1, front ?? colour), // the screen, away from where it looks
    face([4, 6, 7, 5], f, back ?? colour), // the back, with the lens
    face([0, 4, 5, 1], u * -1, colour),
    face([2, 3, 7, 6], u, colour),
    face([0, 2, 6, 4], r * -1, colour),
    face([1, 5, 7, 3], r, colour),
  ];
}

/// A cylinder (n-sided) from [a] along [axis] for [length], radius [rad].
List<Face3> _cyl(V3 a, V3 axis, double length, double rad, Color colour, {int n = 10, double capR = -1}) {
  final ax = axis.unit;
  final e1 = ax.cross(ax.z.abs() < 0.9 ? const V3(0, 0, 1) : const V3(1, 0, 0)).unit;
  final e2 = ax.cross(e1);
  final b = a + ax * length;
  final r2 = capR < 0 ? rad : capR;
  V3 ring(V3 c, double r, int i) {
    final t = 2 * math.pi * i / n;
    return c + e1 * (r * math.cos(t)) + e2 * (r * math.sin(t));
  }
  final out = <Face3>[];
  for (var i = 0; i < n; i++) {
    final t = 2 * math.pi * (i + 0.5) / n;
    out.add(Face3([ring(a, rad, i), ring(a, rad, i + 1), ring(b, r2, i + 1), ring(b, r2, i)], colour,
        e1 * math.cos(t) + e2 * math.sin(t)));
  }
  out.add(Face3([for (var i = n; i > 0; i--) ring(a, rad, i)], colour, ax * -1));
  if (r2 > 0.001) out.add(Face3([for (var i = 0; i < n; i++) ring(b, r2, i)], colour, ax));
  return out;
}

/// Where the phone is: what it looks at, how high (degrees from the table: 90 straight down), how far.
class PhonePose {
  const PhonePose(this.target, this.elevation, this.distance);
  final V3 target;
  final double elevation;
  final double distance;
  static PhonePose lerp(PhonePose a, PhonePose b, double t) => PhonePose(V3.lerp(a.target, b.target, t),
      a.elevation + (b.elevation - a.elevation) * t, a.distance + (b.distance - a.distance) * t);
}

/// A scene for the guide: the things on the table, where the view turns round, and the phone's two places.
class GuideScene {
  GuideScene._(this.objects, this.centre, this.viewDistance, this.azimuth, this.first, this.second, {this.phoneSize = 1});
  final List<Obj3> objects;
  final V3 centre;
  final double viewDistance;
  final double azimuth; // degrees, where the view is from (-90: the near long edge)
  final PhonePose first, second;
  final double phoneSize; // the phone drawn smaller when the scene is close up

  static const cream = Color(0xFFF1ECDD);
  static const hole = Color(0xFF55524C);

  /// A breadboard centred at [c] (16.5 × 5.5 cm), its holes and rails.
  static Obj3 _board(V3 c, {int cols = 40}) {
    final top = c.z + 0.45;
    final dots = <V3>[];
    for (var k = 0; k < cols; k++) {
      final x = c.x - 7.6 + k * 15.2 / (cols - 1);
      for (var r = 0; r < 5; r++) {
        dots.add(V3(x, c.y + 0.35 + r * 0.32, top));
        dots.add(V3(x, c.y - 0.35 - r * 0.32, top));
      }
      if (k % 6 != 5) {
        for (final y in [2.25, 2.5, -2.25, -2.5]) {
          dots.add(V3(x, c.y + y, top));
        }
      }
    }
    return Obj3(1, _box(V3(c.x, c.y, c.z), 16.5, 5.5, 0.9, const Color(0xFFE4DECD), top: cream),
        dots: dots,
        dotColour: hole,
        lines: [
          Line3([V3(c.x - 7.8, c.y + 2.05, top), V3(c.x + 7.8, c.y + 2.05, top)], const Color(0xFF2A78D6), 0.05),
          Line3([V3(c.x - 7.8, c.y + 2.7, top), V3(c.x + 7.8, c.y + 2.7, top)], const Color(0xFFE5484D), 0.05),
          Line3([V3(c.x - 7.8, c.y - 2.05, top), V3(c.x + 7.8, c.y - 2.05, top)], const Color(0xFFE5484D), 0.05),
          Line3([V3(c.x - 7.8, c.y - 2.7, top), V3(c.x + 7.8, c.y - 2.7, top)], const Color(0xFF2A78D6), 0.05),
        ]);
  }

  /// An LED standing at [c] (where its legs go in), [colour] body, legs [legs] long.
  static Obj3 _led(V3 c, Color colour, {double legs = 0.6}) {
    final base = c + V3(0, 0, legs);
    return Obj3(2, [
      ..._cyl(base, const V3(0, 0, 1), 0.12, 0.33, colour.withValues(alpha: 1)), // the rim
      ..._cyl(base + const V3(0, 0, 0.12), const V3(0, 0, 1), 0.55, 0.27, colour),
      ..._cyl(base + const V3(0, 0, 0.67), const V3(0, 0, 1), 0.3, 0.27, colour, capR: 0.08), // the dome
    ], lines: [
      Line3([c + const V3(-0.13, 0, 0), base + const V3(-0.13, 0, 0)], const Color(0xFFB9B6AE), 0.05),
      Line3([c + const V3(0.13, 0, 0), base + const V3(0.13, 0, 0)], const Color(0xFFB9B6AE), 0.05),
    ]);
  }

  /// A resistor lying along x at [c], its legs bent down to [floor].
  static Obj3 _resistor(V3 c, double floor, {double span = 1.4}) {
    const body = Color(0xFFD9C08F);
    final a = c - const V3(0.35, 0, 0);
    return Obj3(2, [
      ..._cyl(a, const V3(1, 0, 0), 0.7, 0.13, body, n: 8),
      for (final (dx, col) in [(0.1, const Color(0xFFE5484D)), (0.24, const Color(0xFFE5484D)), (0.38, const Color(0xFF6B3E1F)), (0.56, const Color(0xFFC9A227))])
        ..._cyl(a + V3(dx, 0, 0), const V3(1, 0, 0), 0.07, 0.14, col, n: 8),
    ], lines: [
      Line3([c - const V3(0.35, 0, 0), c - V3(span / 2, 0, 0), V3(c.x - span / 2, c.y, floor)], const Color(0xFFB9B6AE), 0.04),
      Line3([c + const V3(0.35, 0, 0), c + V3(span / 2, 0, 0), V3(c.x + span / 2, c.y, floor)], const Color(0xFFB9B6AE), 0.04),
    ]);
  }

  static Obj3 _arduino(V3 c) {
    final top = c.z + 0.08;
    return Obj3(1, [
      ..._box(c, 6.9, 5.3, 0.16, const Color(0xFF0F5E9C), top: const Color(0xFF1B74B8)),
      ..._box(V3(c.x - 0.2, c.y + 2.35, top + 0.42), 5.4, 0.26, 0.85, const Color(0xFF1C1C1C)), // the digital header
      ..._box(V3(c.x + 0.6, c.y - 2.35, top + 0.42), 4.4, 0.26, 0.85, const Color(0xFF1C1C1C)),
      ..._box(V3(c.x - 3.2, c.y + 1.0, top + 0.55), 1.6, 1.2, 1.1, const Color(0xFFB8BCC2)), // USB
      ..._box(V3(c.x - 3.0, c.y - 1.6, top + 0.55), 1.4, 0.9, 1.1, const Color(0xFF222222)), // power jack
      ..._box(V3(c.x + 0.8, c.y - 0.6, top + 0.2), 3.5, 0.75, 0.4, const Color(0xFF2B2B2B)), // the chip
    ]);
  }

  static Obj3 _wire(List<V3> pts, Color colour) => Obj3(2, [], lines: [Line3(pts, colour, 0.12)]);

  /// All the parts spread on the table; photo 1 from above, photo 2 close over the resistor.
  factory GuideScene.gather() {
    const res = V3(-5.2, -6.4, 0.25);
    return GuideScene._([
      _board(const V3(-1.0, 3.6, 0.45)),
      _arduino(const V3(4.5, -4.0, 0.4)),
      _led(const V3(-1.6, -4.4, 0), const Color(0xFF3DBE52), legs: 1.0),
      _resistor(res, 0),
      _wire(const [V3(8.5, 1.5, 0.15), V3(10.5, 2.5, 1.5), V3(12.0, 0.5, 0.15)], const Color(0xFFE5484D)),
      _wire(const [V3(9.0, -0.6, 0.15), V3(11.0, 0.2, 1.3), V3(12.5, -2.0, 0.15)], const Color(0xFF2E9E57)),
    ], const V3(1.5, -1.0, 2.5), 46, -105, const PhonePose(V3(1.5, -1.0, 0), 90, 13), const PhonePose(res, 90, 6));
  }

  /// The LED on the board, its resistor beside it; photo 1 from above, photo 2 low from the near edge.
  factory GuideScene.ledSide() {
    const led = V3(1.0, -0.8, 0.9);
    return GuideScene._([
      _board(const V3(0, 0, 0.45)),
      _led(led, const Color(0xFF2F6BDB)),
      _resistor(const V3(-1.6, -0.8, 1.35), 0.9, span: 1.6),
    ], const V3(0, -0.6, 2.2), 30, -140, const PhonePose(led, 90, 7), const PhonePose(led, 30, 6.5), phoneSize: 0.6);
  }
}

/// Draws [scene] at moment [u]: the view turned a little, the phone at [phone], flashing by [flash] (0..1).
class Scene3dPainter extends CustomPainter {
  Scene3dPainter(this.scene, this.u, this.phone, this.flash);
  final GuideScene scene;
  final double u;
  final PhonePose phone;
  final double flash;

  static const _light = V3(-0.35, -0.55, 0.76);

  @override
  void paint(Canvas canvas, Size s) {
    // the view: turning slowly round the scene, from a little above
    final az = (scene.azimuth + 14 * math.sin(2 * math.pi * u)) * math.pi / 180;
    const el = 30 * math.pi / 180;
    final c = scene.centre;
    final eye = c + V3(math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)) * scene.viewDistance;
    final w = (c - eye).unit;
    final right = w.cross(const V3(0, 0, 1)).unit;
    final up = right.cross(w);
    final focal = s.shortestSide * 1.35;
    final mid = Offset(s.width / 2, s.height * 0.56);
    Offset? proj(V3 p) {
      final v = p - eye;
      final z = v.dot(w);
      if (z < 0.5) return null;
      return mid + Offset(v.dot(right) / z, -v.dot(up) / z) * focal;
    }
    double depth(V3 p) => (p - eye).dot(w);

    // the table: soft light wood, fading at its edges
    canvas.drawRect(Offset.zero & s, Paint()..color = const Color(0xFFE9E4DA));
    final table = [const V3(-30, -22, 0), const V3(30, -22, 0), const V3(30, 22, 0), const V3(-30, 22, 0)].map(proj).toList();
    if (table.every((p) => p != null)) {
      canvas.drawPath(Path()..addPolygon(table.cast<Offset>(), true), Paint()..color = const Color(0xFFF7F5F0));
    }

    // the phone: its axes from where it is and what it looks at
    final a = phone.elevation * math.pi / 180;
    final at = phone.target + V3(0, -math.cos(a), math.sin(a)) * phone.distance;
    final f = (phone.target - at).unit;
    const r = V3(1, 0, 0);
    final pu = r.cross(f).unit;
    final screen = Color.lerp(const Color(0xFF34495E), Colors.white, flash)!;
    final phoneObj = Obj3(3, _orientedBox(at, r, pu, f, 4.2 * scene.phoneSize, 8.6 * scene.phoneSize, 0.45 * scene.phoneSize, const Color(0xFF2A2A2E), front: screen));

    final objs = [...scene.objects, phoneObj]
      ..sort((p, q) => p.layer != q.layer ? p.layer.compareTo(q.layer) : depth(q.mid).compareTo(depth(p.mid)));

    // the phone's view on the table: a cone from its lens, brighter when it takes the photo
    final half = phone.distance * 0.32;
    final rect = [
      phone.target + r * -half + pu * (-half * 1.33),
      phone.target + r * half + pu * (-half * 1.33),
      phone.target + r * half + pu * (half * 1.33),
      phone.target + r * -half + pu * (half * 1.33),
    ];
    final lens = at + f * 0.25;

    for (final o in objs) {
      if (identical(o, phoneObj)) _cone(canvas, proj, lens, rect);
      final faces = [...o.faces]..sort((p, q) => depth(q.mid).compareTo(depth(p.mid)));
      for (final fc in faces) {
        if (fc.normal.dot(eye - fc.mid) <= 0) continue; // facing away
        final pts = fc.pts.map(proj).toList();
        if (pts.any((p) => p == null)) continue;
        final k = 0.62 + 0.38 * math.max(0, fc.normal.unit.dot(_light.unit));
        final col = Color.fromARGB(255, (fc.colour.r * 255 * k).round().clamp(0, 255),
            (fc.colour.g * 255 * k).round().clamp(0, 255), (fc.colour.b * 255 * k).round().clamp(0, 255));
        canvas.drawPath(Path()..addPolygon(pts.cast<Offset>(), true), Paint()..color = col);
      }
      if (o.dots.isNotEmpty) {
        final pts = [for (final d in o.dots) ?proj(d)];
        final size = math.max(1.2, focal * 0.11 / depth(o.mid));
        canvas.drawPoints(PointMode.points, pts,
            Paint()
              ..color = o.dotColour
              ..strokeWidth = size
              ..strokeCap = StrokeCap.square);
      }
      for (final l in o.lines) {
        final pts = [for (final p in l.pts) ?proj(p)];
        if (pts.length < 2) continue;
        final path = Path()..moveTo(pts.first.dx, pts.first.dy);
        for (final p in pts.skip(1)) {
          path.lineTo(p.dx, p.dy);
        }
        canvas.drawPath(
            path,
            Paint()
              ..color = l.colour
              ..style = PaintingStyle.stroke
              ..strokeCap = StrokeCap.round
              ..strokeJoin = StrokeJoin.round
              ..strokeWidth = math.max(1.0, focal * l.width / depth(l.pts.first)));
      }
    }
    // the lens, and its flash
    final lp = proj(lens);
    if (lp != null && f.dot(eye - lens) > 0) {
      canvas.drawCircle(lp, 2.5, Paint()..color = const Color(0xFF0B0B0B));
    }
    if (flash > 0 && lp != null) {
      canvas.drawCircle(lp, 6 + 22 * flash, Paint()..color = Colors.white.withValues(alpha: 0.7 * flash));
    }
  }

  void _cone(Canvas canvas, Offset? Function(V3) proj, V3 lens, List<V3> rect) {
    final l = proj(lens);
    final rs = rect.map(proj).toList();
    if (l == null || rs.any((p) => p == null)) return;
    final alpha = 0.10 + 0.35 * flash;
    final fill = Paint()..color = const Color(0xFF2A78D6).withValues(alpha: alpha);
    final edge = Paint()
      ..color = const Color(0xFF2A78D6).withValues(alpha: 0.35 + 0.5 * flash)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2;
    canvas.drawPath(Path()..addPolygon(rs.cast<Offset>(), true), fill);
    canvas.drawPath(Path()..addPolygon(rs.cast<Offset>(), true), edge);
    for (final p in rs) {
      canvas.drawLine(l, p!, edge);
    }
  }

  @override
  bool shouldRepaint(Scene3dPainter old) => old.u != u || old.flash != flash || old.phone != phone;
}
