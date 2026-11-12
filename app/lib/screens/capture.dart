
import 'package:camera/camera.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:image_picker/image_picker.dart';

import '../theme.dart';
import '../widgets/bouncy.dart';
import '../widgets/full_frame.dart';

/// The camera, full screen: take up to `max` photos (or pick them), then send them back.
/// With max 1 (a close-up) the photo goes back as soon as it is taken.
class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key, required this.prompt, this.max = 3});

  final String prompt;
  final int max;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> with WidgetsBindingObserver {
  CameraController? _cam;
  String? _camError;
  final List<Uint8List> _photos = [];
  bool _flash = false;
  bool _taking = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _start();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cam?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    final c = _cam;
    if (c == null || !c.value.isInitialized) return;
    if (s == AppLifecycleState.inactive) {
      c.dispose();
      _cam = null;
    } else if (s == AppLifecycleState.resumed) {
      _start();
    }
  }

  Future<void> _start() async {
    try {
      final cams = await availableCameras();
      if (cams.isEmpty) throw CameraException('none', 'No camera on this device');
      final back = pickBackCamera(cams);
      // The camera's best resolution: the server shrinks the first look to 768 px; close-ups keep the detail.
      final c = CameraController(back, ResolutionPreset.max, enableAudio: false, imageFormatGroup: ImageFormatGroup.jpeg);
      await c.initialize();
      try {
        await c.setFocusMode(FocusMode.auto);
      } catch (_) {}
      if (!mounted) {
        await c.dispose();
        return;
      }
      setState(() => _cam = c);
    } catch (e) {
      if (mounted) setState(() => _camError = e is CameraException ? (e.description ?? e.code) : '$e');
    }
  }

  Future<void> _shoot() async {
    final c = _cam;
    if (c == null || _taking || _photos.length >= widget.max) return;
    _taking = true;
    HapticFeedback.mediumImpact();
    setState(() => _flash = true);
    try {
      final f = await c.takePicture();
      _add(await f.readAsBytes());
    } catch (e) {
      _toast('Could not take the photo: $e');
    } finally {
      _taking = false;
      if (mounted) setState(() => _flash = false);
    }
  }

  Future<void> _pick() async {
    final picker = ImagePicker();
    final left = widget.max - _photos.length;
    final files = left > 1
        ? await picker.pickMultiImage(maxWidth: 1600, maxHeight: 1600, imageQuality: 88, limit: left)
        : [?await picker.pickImage(source: ImageSource.gallery, maxWidth: 1600, maxHeight: 1600, imageQuality: 88)];
    for (final f in files.take(left)) {
      _add(await f.readAsBytes());
    }
  }

  /// The phone's own camera app: its best focus and quality (when the live picture will not focus).
  Future<void> _phoneCamera() async {
    final f = await ImagePicker().pickImage(source: ImageSource.camera, maxWidth: 2400, maxHeight: 2400, imageQuality: 90);
    if (f != null) _add(await f.readAsBytes());
  }

  void _add(Uint8List b) {
    if (!mounted) return;
    setState(() => _photos.add(b));
    if (widget.max == 1) Navigator.of(context).pop(_photos);
  }

  void _toast(String m) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    final c = _cam;
    final full = _photos.length >= widget.max;
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(children: [
                _Round(icon: Icons.close_rounded, onTap: () => Navigator.of(context).pop()),
                const SizedBox(width: 10),
                Expanded(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(color: Colors.white12, borderRadius: BorderRadius.circular(30)),
                    child: Text(widget.prompt,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                  ).animate().fadeIn(delay: 200.ms).slideY(begin: -0.5),
                ),
                const SizedBox(width: 56),
              ]),
            ),
            // the whole frame the photo will have: nothing outside it, nothing cut off
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: c != null && c.value.isInitialized
                    ? FullFramePreview(
                        controller: c,
                        overlay: Stack(fit: StackFit.expand, children: [
                          const IgnorePointer(child: _Frame()),
                          IgnorePointer(
                            child: AnimatedOpacity(
                              opacity: _flash ? 0.8 : 0,
                              duration: const Duration(milliseconds: 90),
                              child: const ColoredBox(color: Colors.white),
                            ),
                          ),
                        ]),
                      )
                    : _NoCamera(error: _camError, onPick: _pick),
              ),
            ),
            TextButton.icon(
              onPressed: full ? null : _phoneCamera,
              icon: const Icon(Icons.center_focus_strong_rounded, color: Colors.white70, size: 18),
              label: const Text("Blurry? Tap the picture to focus, or use the phone's camera",
                  style: TextStyle(color: Colors.white70, fontSize: 12.5)),
            ),
            if (widget.max > 1 && _photos.isNotEmpty)
              SizedBox(
                height: 76,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  children: [
                    for (var i = 0; i < _photos.length; i++)
                      Padding(
                        padding: const EdgeInsets.only(right: 10),
                        child: Stack(clipBehavior: Clip.none, children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: Image.memory(_photos[i], width: 64, height: 64, fit: BoxFit.cover, gaplessPlayback: true),
                          ),
                          Positioned(
                            right: -6,
                            top: -6,
                            child: GestureDetector(
                              onTap: () => setState(() => _photos.removeAt(i)),
                              child: const CircleAvatar(
                                radius: 11,
                                backgroundColor: Colors.white,
                                child: Icon(Icons.close_rounded, size: 14, color: Pq.ink),
                              ),
                            ),
                          ),
                        ]).animate().scale(curve: Curves.easeOutBack, duration: 300.ms),
                      ),
                  ],
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
              child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                _Round(icon: Icons.photo_library_rounded, onTap: full ? null : _pick, label: 'Photos'),
                _Shutter(onTap: c == null || full ? null : _shoot),
                widget.max > 1
                    ? _Round(
                        icon: Icons.check_rounded,
                        label: _photos.isEmpty ? 'Check' : 'Check (${_photos.length})',
                        color: _photos.isEmpty ? null : Pq.have,
                        onTap: _photos.isEmpty ? null : () => Navigator.of(context).pop(_photos),
                      )
                    : const SizedBox(width: 56),
              ]),
            ),
            if (widget.max > 1)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  full ? 'That\'s enough photos. Tap Check.' : 'Up to ${widget.max} photos if it doesn\'t fit in one',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ),
          ]),
        ),
    );
  }
}

class _Shutter extends StatelessWidget {
  const _Shutter({this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Bouncy(
        onTap: onTap,
        scale: 0.88,
        child: Container(
          width: 82,
          height: 82,
          decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 5)),
          padding: const EdgeInsets.all(5),
          child: const DecoratedBox(decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white)),
        ),
      );
}

class _Round extends StatelessWidget {
  const _Round({required this.icon, this.onTap, this.label, this.color});

  final IconData icon;
  final VoidCallback? onTap;
  final String? label;
  final Color? color;

  @override
  Widget build(BuildContext context) => Bouncy(
        onTap: onTap,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 250),
            width: 56,
            height: 56,
            decoration: BoxDecoration(shape: BoxShape.circle, color: color ?? Colors.white24),
            child: Icon(icon, color: Colors.white),
          ),
          if (label != null) ...[
            const SizedBox(height: 4),
            Text(label!, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600)),
          ],
        ]),
      );
}

/// Four soft corners: where to put the pieces.
class _Frame extends StatelessWidget {
  const _Frame();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(14),
        child: CustomPaint(painter: _CornerPainter()),
      );
}

class _CornerPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size s) {
    final p = Paint()
      ..color = Colors.white.withValues(alpha: 0.85)
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    const l = 34.0;
    for (final (x, y, dx, dy) in [(0.0, 0.0, 1.0, 1.0), (s.width, 0.0, -1.0, 1.0), (0.0, s.height, 1.0, -1.0), (s.width, s.height, -1.0, -1.0)]) {
      canvas.drawPath(
        Path()
          ..moveTo(x, y + dy * l)
          ..lineTo(x, y + dy * 10)
          ..quadraticBezierTo(x, y, x + dx * 10, y)
          ..lineTo(x + dx * l, y),
        p,
      );
    }
  }

  @override
  bool shouldRepaint(_) => false;
}

class _NoCamera extends StatelessWidget {
  const _NoCamera({this.error, required this.onPick});

  final String? error;
  final VoidCallback onPick;

  @override
  Widget build(BuildContext context) => Center(
        child: error == null
            ? const CircularProgressIndicator(color: Colors.white)
            : Padding(
                padding: const EdgeInsets.all(32),
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.no_photography_rounded, color: Colors.white54, size: 56),
                  const SizedBox(height: 12),
                  Text("The camera isn't available here.\n$error",
                      textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70)),
                  const SizedBox(height: 18),
                  SoftButton(label: 'Choose photos instead', icon: Icons.photo_library_rounded, color: Colors.white, onTap: onPick),
                ]),
              ),
      );
}
