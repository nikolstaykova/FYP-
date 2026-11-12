import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../api.dart';
import '../theme.dart';
import '../widgets/bouncy.dart';
import 'home.dart';

/// First launch: paste the link the parts server prints ("On your phone (same Wi-Fi): https://...?key=...").
class ConnectScreen extends StatefulWidget {
  const ConnectScreen({super.key});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _link = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final a = Api.instance;
    if (a.ready) _link.text = a.url('/').toString();
  }

  Future<void> _paste() async {
    final d = await Clipboard.getData('text/plain');
    if (d?.text != null) setState(() => _link.text = d!.text!.trim());
  }

  Future<void> _go() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await Api.instance.save(_link.text);
      await Api.instance.lessons(fresh: true); // proves the address and the key
      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(MaterialPageRoute(builder: (_) => const HomeScreen()), (_) => false);
    } catch (e) {
      setState(() => _error = e is ApiError ? e.message : "Can't reach the server. Is it running, and on the same Wi-Fi?");
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: ListView(
              padding: const EdgeInsets.all(24),
              shrinkWrap: true,
              children: [
                const _Logo().animate().scale(duration: 600.ms, curve: Curves.elasticOut),
                const SizedBox(height: 28),
                Text('Parts Quest', style: t.displaySmall, textAlign: TextAlign.center)
                    .animate()
                    .fadeIn(delay: 150.ms)
                    .slideY(begin: 0.3),
                const SizedBox(height: 8),
                Text('Find the parts. Show the camera. Build something.',
                        style: t.titleMedium?.copyWith(color: Pq.muted, fontWeight: FontWeight.w500),
                        textAlign: TextAlign.center)
                    .animate()
                    .fadeIn(delay: 250.ms),
                const SizedBox(height: 36),
                Text('Connect to your parts server', style: t.titleMedium),
                const SizedBox(height: 6),
                Text('Start it on your computer (research/recognition/lab/run.sh --lan --https) and paste the '
                    '"On your phone" link it prints.', style: t.bodyMedium?.copyWith(color: Pq.muted)),
                const SizedBox(height: 14),
                TextField(
                  controller: _link,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  decoration: InputDecoration(
                    hintText: 'https://192.168.1.59:8765/?key=…',
                    filled: true,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
                    suffixIcon: IconButton(icon: const Icon(Icons.content_paste_rounded), onPressed: _paste, tooltip: 'Paste'),
                  ),
                  onSubmitted: (_) => _go(),
                ),
                AnimatedSize(
                  duration: 250.ms,
                  child: _error == null
                      ? const SizedBox(height: 18)
                      : Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: Text(_error!, style: const TextStyle(color: Pq.missing, fontWeight: FontWeight.w600)),
                        ),
                ),
                BigButton(label: "Let's go", icon: Icons.rocket_launch_rounded, busy: _busy, onTap: _go),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  const _Logo();

  @override
  Widget build(BuildContext context) => Center(
        child: SizedBox(
          width: 112,
          height: 112,
          child: Stack(children: [
            Positioned(left: 0, top: 18, child: _tile(Pq.electronics, Icons.memory_rounded, -0.18)),
            Positioned(right: 0, top: 0, child: _tile(Pq.lego, Icons.extension_rounded, 0.16)),
            Positioned(left: 30, bottom: 0, child: _tile(Pq.have, Icons.photo_camera_rounded, 0.04)),
          ]),
        ),
      );

  Widget _tile(Color c, IconData i, double turn) => Transform.rotate(
        angle: turn,
        child: Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            color: c,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [BoxShadow(color: c.withValues(alpha: 0.4), blurRadius: 12, offset: const Offset(0, 6))],
          ),
          child: Icon(i, color: Colors.white, size: 30),
        ),
      );
}
