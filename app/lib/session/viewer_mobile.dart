// Phones: the viewer page in a web view. The web view cannot fetch from the server (its certificate is
// self-signed), so the app downloads the page and the model itself and hands both in.
import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../api.dart';
import 'viewer.dart';

class ViewerView extends StatefulWidget {
  const ViewerView({super.key, required this.lessonId, required this.controller});

  final String lessonId;
  final ViewerController controller;

  @override
  State<ViewerView> createState() => _ViewerViewState();
}

class _ViewerViewState extends State<ViewerView> {
  WebViewController? _web;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final c = widget.controller;
    try {
      final id = Uri.encodeComponent(widget.lessonId);
      final page = await Api.instance.text('/viewer/$id/index.html');
      final lesson = await Api.instance.text('/viewer/$id/lesson.json');
      // the lesson goes in as a JSON string literal: safe inside the page's script
      final head = '<script>window.PIP_EMBED = 1; window.PIP_LESSON = JSON.parse(${jsonEncode(lesson)});</script>';
      final html = page.replaceFirst('<head>', '<head>$head');
      final web = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..setBackgroundColor(Colors.transparent)
        ..addJavaScriptChannel('PipViewer', onMessageReceived: (m) {
          final d = jsonDecode(m.message);
          if (d is Map && d['viewer'] == 'ready') c.onReady((d['steps'] as num?)?.toInt() ?? 0);
        });
      c.sender = (msg) => web.runJavaScript('window.postMessage(${jsonEncode(msg)}, "*")');
      await web.loadHtmlString(html, baseUrl: 'https://parts-quest.app/viewer/');
      if (mounted) setState(() => _web = web);
    } catch (e) {
      c.fail('The 3D model could not load: $e');
    }
  }

  @override
  Widget build(BuildContext context) =>
      _web == null ? const SizedBox.expand() : WebViewWidget(controller: _web!);
}
