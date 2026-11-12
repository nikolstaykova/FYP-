import 'package:material_ui/material_ui.dart';

import 'viewer.dart';

class ViewerView extends StatelessWidget {
  const ViewerView({super.key, required this.lessonId, required this.controller});

  final String lessonId;
  final ViewerController controller;

  @override
  Widget build(BuildContext context) => const Center(child: Text('3D needs a phone or a browser'));
}
