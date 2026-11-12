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
          child: Stack(fit: StackFit.expand, children: [
            kIsWeb ? FittedBox(fit: BoxFit.contain, child: SizedBox(width: v.previewSize?.width ?? 1280, height: v.previewSize?.height ?? 720, child: preview)) : preview,
            ?overlay,
          ]),
        ),
      ),
    );
  }
}

/// The normal back camera: phones with several lenses list a telephoto (looks zoomed in) or an ultra-wide too.
CameraDescription pickBackCamera(List<CameraDescription> cams) {
  final back = cams.where((c) => c.lensDirection == CameraLensDirection.back).toList();
  if (back.isEmpty) return cams.first;
  bool plain(CameraDescription c) => !RegExp(r'tele|ultra|dual|triple|macro|depth', caseSensitive: false).hasMatch(c.name);
  return back.where(plain).firstOrNull ?? back.first;
}
