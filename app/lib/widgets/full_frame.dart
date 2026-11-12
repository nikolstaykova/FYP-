// The camera preview showing the WHOLE frame the photo will have (never cropped to fill the screen), so the
// learner sees exactly what they are taking.
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:material_ui/material_ui.dart';

/// The camera filling its whole box (full screen), like the phone's camera app. What is cut off at the sides is
/// cut off the photo too: [visible] holds the part of the frame on screen, as [x0, y0, x1, y1] fractions, and the
/// server crops the photo to it, so the photo is exactly what the learner saw.
class CameraFill extends StatelessWidget {
  const CameraFill({super.key, required this.controller, required this.visible, this.overlay});

  final CameraController controller;
  final ValueNotifier<List<double>?> visible;
  final Widget? overlay;

  /// The frame's width / height as shown (phones report the sensor's landscape size; the browser the video's).
  static double ratioOf(CameraController c, BuildContext context) {
    var r = c.value.aspectRatio;
    if (!kIsWeb && MediaQuery.of(context).orientation == Orientation.portrait) r = 1 / r;
    return r;
  }

  /// The part of a frame of [ratio] that a [box] shows when the frame covers it.
  static List<double> shown(double ratio, Size box) {
    if (box.isEmpty || ratio <= 0) return [0, 0, 1, 1];
    final boxRatio = box.width / box.height;
    if (ratio > boxRatio) {
      final f = boxRatio / ratio; // the frame is wider: its sides are cut
      return [(1 - f) / 2, 0, (1 + f) / 2, 1];
    }
    final f = ratio / boxRatio; // the frame is taller: top and bottom are cut
    return [0, (1 - f) / 2, 1, (1 + f) / 2];
  }

  @override
  Widget build(BuildContext context) {
    final v = controller.value;
    final ratio = ratioOf(controller, context);
    final preview = kIsWeb
        ? SizedBox(width: v.previewSize?.width ?? 1280, height: v.previewSize?.height ?? 720, child: controller.buildPreview())
        : SizedBox(width: 1000 * ratio, height: 1000, child: CameraPreview(controller));
    return LayoutBuilder(builder: (context, box) {
      visible.value = shown(ratio, box.biggest);
      return GestureDetector(
        onTapUp: (d) {
          // the tap, in the frame's own fractions
          final c = visible.value!;
          final fx = c[0] + (c[2] - c[0]) * d.localPosition.dx / box.maxWidth;
          final fy = c[1] + (c[3] - c[1]) * d.localPosition.dy / box.maxHeight;
          focusAt(controller, Offset(fx, fy), const Size(1, 1));
        },
        child: Stack(fit: StackFit.expand, children: [
          ClipRect(child: FittedBox(fit: BoxFit.cover, child: preview)),
          ?overlay,
        ]),
      );
    });
  }
}

/// The back camera that focuses best. On iPhones with several lenses the browser lists the combined camera
/// ("Back Triple Camera", "Back Dual Wide Camera"): it switches lenses by itself, to macro for close-ups, like the
/// phone's own camera app. A plain lens on its own cannot focus close; the telephoto also looks zoomed in.
CameraDescription pickBackCamera(List<CameraDescription> cams) {
  final back = cams.where((c) => c.lensDirection == CameraLensDirection.back).toList();
  if (back.isEmpty) return cams.first;
  int rank(CameraDescription c) {
    final n = c.name.toLowerCase();
    if (n.contains('triple')) return 0;
    if (n.contains('dual wide')) return 1;
    if (n.contains('dual')) return 2;
    if (n.contains('tele')) return 9;
    if (n.contains('ultra')) return 8;
    return 3;
  }
  return ([...back]..sort((a, b) => rank(a).compareTo(rank(b)))).first;
}

/// Tap the picture to focus there (phones that allow it; the browser mostly focuses by itself).
Future<void> focusAt(CameraController c, Offset at, Size size) async {
  final p = Offset((at.dx / size.width).clamp(0, 1), (at.dy / size.height).clamp(0, 1));
  try {
    await c.setFocusPoint(p);
    await c.setExposurePoint(p);
  } catch (_) {}
}
