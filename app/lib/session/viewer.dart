// The 3D step viewer of a 3D LEGO lesson (code/graph/lego_3d/lesson_viewer.html, embed mode), driven like the web
// game: {step: n, play: true} shows step n with its pieces going on. Phones use a web view, the web an iframe.
import 'package:material_ui/material_ui.dart';

import 'viewer_stub.dart' if (dart.library.io) 'viewer_mobile.dart' if (dart.library.js_interop) 'viewer_web.dart';

class ViewerController extends ChangeNotifier {
  bool ready = false;
  int steps = 0;
  String? error;
  Map<String, dynamic>? _want;
  void Function(Map<String, dynamic>)? sender;

  void send(Map<String, dynamic> msg) {
    _want = msg;
    if (ready) sender?.call(_fill(msg));
  }

  Map<String, dynamic> _fill(Map<String, dynamic> m) => m['whole'] == true ? {...m, 'step': steps} : m;

  /// The viewer says it has loaded the model.
  void onReady(int n) {
    ready = true;
    steps = n;
    notifyListeners();
    final w = _want;
    if (w != null) sender?.call(_fill(w));
  }

  void fail(String why) {
    error = why;
    notifyListeners();
  }
}

class Viewer3D extends StatelessWidget {
  const Viewer3D({super.key, required this.lessonId, required this.controller});

  final String lessonId;
  final ViewerController controller;

  @override
  Widget build(BuildContext context) => ViewerView(lessonId: lessonId, controller: controller);
}
