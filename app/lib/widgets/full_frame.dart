// The camera preview showing the WHOLE frame the photo will have (never cropped to fill the screen), so the
// learner sees exactly what they are taking.
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:material_ui/material_ui.dart';

class FullFramePreview extends StatelessWidget {
  const FullFramePreview({super.key, required this.controller, this.overlay});

  final CameraController controller;
  final Widget? overlay; // drawn on the picture itself (guide corners)

  @override
  Widget build(BuildContext context) {
    final v = controller.value;
    // phones report the sensor's landscape size; the browser reports the video as it is shown
    final portrait = MediaQuery.of(context).orientation == Orientation.portrait;
    var ratio = v.aspectRatio; // width / height of the sensor's frame
    if (!kIsWeb && portrait) ratio = 1 / ratio;
    final preview = kIsWeb ? controller.buildPreview() : CameraPreview(controller);
    return Center(
      child: AspectRatio(
        aspectRatio: ratio,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(14),
          child: LayoutBuilder(
            builder: (context, box) => GestureDetector(
              onTapUp: (d) => focusAt(controller, d.localPosition, box.biggest),
              child: Stack(fit: StackFit.expand, children: [
            kIsWeb ? FittedBox(fit: BoxFit.contain, child: SizedBox(width: v.previewSize?.width ?? 1280, height: v.previewSize?.height ?? 720, child: preview)) : preview,
            ?overlay,
              ]),
            ),
          ),
        ),
      ),
    );
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
