// The web: the viewer page in an iframe from the same server, spoken to with postMessage (as the web game does).
import 'dart:js_interop';

import 'package:material_ui/material_ui.dart';
import 'package:web/web.dart' as web;

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
  web.HTMLIFrameElement? _frame;
  JSFunction? _listener;

  @override
  void initState() {
    super.initState();
    final c = widget.controller;
    _listener = ((web.MessageEvent e) {
      if (_frame == null || e.source != _frame!.contentWindow) return;
      final d = e.data.dartify();
      if (d is Map && d['viewer'] == 'ready') c.onReady((d['steps'] as num?)?.toInt() ?? 0);
    }).toJS;
    web.window.addEventListener('message', _listener);
    c.sender = (msg) => _frame?.contentWindow?.postMessage(msg.jsify(), '*'.toJS);
  }

  @override
  void dispose() {
    web.window.removeEventListener('message', _listener);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => HtmlElementView.fromTagName(
        tagName: 'iframe',
        onElementCreated: (el) {
          final f = el as web.HTMLIFrameElement;
          f.style
            ..border = '0'
            ..width = '100%'
            ..height = '100%';
          f.src = Api.instance.link('/viewer/${Uri.encodeComponent(widget.lessonId)}/index.html?embed=1');
          _frame = f;
        },
      );
}
