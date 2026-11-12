import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:image_picker/image_picker.dart';

import '../models.dart';
import '../theme.dart';
import '../widgets/bouncy.dart';
import '../widgets/full_frame.dart';

/// Taking the photos: up to `max` (or picked from the gallery), then sent back. With max 1 (a close-up) the photo
/// goes back as soon as it is taken.
///
/// In a phone's browser the photo is taken with the phone's own camera app: full screen, its autofocus, full quality.
/// (A browser's live camera is a video frame: softer, worse focus, and the checker could not read it as well.)
/// In the installed app the camera is live in the app, full screen, and each photo is cropped to what was on screen.
class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key, required this.prompt, this.max = 3});

  final String prompt;
  final int max;

  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

/// The phone's own camera app (and the gallery): the best photos a browser can get.
Future<Shot?> phoneCameraShot() async {
  final f = await ImagePicker().pickImage(source: ImageSource.camera, maxWidth: 2400, maxHeight: 2400, imageQuality: 90);
  return f == null ? null : Shot(await f.readAsBytes());
}

Future<List<Shot>> galleryShots(int max) async {
  final picker = ImagePicker();
  final files = max > 1
      ? await picker.pickMultiImage(maxWidth: 2400, maxHeight: 2400, imageQuality: 90, limit: max)
      : [?await picker.pickImage(source: ImageSource.gallery, maxWidth: 2400, maxHeight: 2400, imageQuality: 90)];
  return [for (final f in files.take(max)) Shot(await f.readAsBytes())];
}

class _CaptureScreenState extends State<CaptureScreen> with WidgetsBindingObserver {
  CameraController? _cam;
  String? _camError;
  final List<Shot> _photos = [];
  final _visible = ValueNotifier<List<double>?>(null);
  bool _flash = false;
  bool _taking = false;

  @override
  void initState() {
    super.initState();
    if (kIsWeb) return; // the phone's camera app, opened by a tap
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
      final c = CameraController(pickBackCamera(cams), ResolutionPreset.max,
          enableAudio: false, imageFormatGroup: ImageFormatGroup.jpeg);
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
      _add(Shot(await f.readAsBytes(), _visible.value));
    } catch (e) {
      _toast('Could not take the photo: $e');
    } finally {
      _taking = false;
      if (mounted) setState(() => _flash = false);
    }
  }

  Future<void> _phone() async {
    final s = await phoneCameraShot();
    if (s != null) _add(s);
  }

  Future<void> _pick() async {
    for (final s in await galleryShots(widget.max - _photos.length)) {
      _add(s);
    }
  }

  void _add(Shot s) {
    if (!mounted) return;
    setState(() => _photos.add(s));
    if (widget.max == 1) Navigator.of(context).pop(_photos);
  }

  void _toast(String m) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) => kIsWeb ? _browser(context) : _live(context);

  // ---- a phone's browser: the phone's own camera app
  Widget _browser(BuildContext context) {
    final full = _photos.length >= widget.max;
    final t = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(widget.max == 1 ? 'Close-up' : 'Show me', style: t.titleMedium), centerTitle: true),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
          child: Column(children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: Pq.electronics.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(18)),
              child: Text(widget.prompt, textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: _photos.isEmpty
                  ? Center(
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                        const Icon(Icons.photo_camera_rounded, size: 72, color: Pq.muted)
                            .animate(onPlay: (c) => c.repeat(reverse: true))
                            .scale(begin: const Offset(0.94, 0.94), end: const Offset(1.04, 1.04), duration: 1200.ms),
                        const SizedBox(height: 12),
                        const Text('Your phone\'s camera opens full screen.\nOne clear photo, from above, is enough.',
                            textAlign: TextAlign.center, style: TextStyle(color: Pq.muted, height: 1.4)),
                      ]),
                    )
                  : GridView.count(
                      crossAxisCount: 2,
                      mainAxisSpacing: 10,
                      crossAxisSpacing: 10,
                      children: [
                        for (var i = 0; i < _photos.length; i++)
                          Stack(fit: StackFit.expand, children: [
                            ClipRRect(borderRadius: BorderRadius.circular(16), child: Image.memory(_photos[i].bytes, fit: BoxFit.cover)),
                            Positioned(
                              right: 6,
                              top: 6,
                              child: GestureDetector(
                                onTap: () => setState(() => _photos.removeAt(i)),
                                child: const CircleAvatar(radius: 14, backgroundColor: Colors.white, child: Icon(Icons.close_rounded, size: 16, color: Pq.ink)),
                              ),
                            ),
                          ]).animate().scale(curve: Curves.easeOutBack, duration: 300.ms),
                      ],
                    ),
            ),
            const SizedBox(height: 12),
            // one clear photo is enough: once there is one, checking is the big button
            if (_photos.isEmpty || widget.max == 1)
              BigButton(label: 'Take photo', icon: Icons.photo_camera_rounded, onTap: full ? null : _phone)
            else
              BigButton(
                label: 'Check (${_photos.length})',
                icon: Icons.check_rounded,
                color: Pq.have,
                onTap: () => Navigator.of(context).pop(_photos),
              ),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(child: SoftButton(label: 'From gallery', icon: Icons.photo_library_rounded, onTap: full ? null : _pick)),
              if (widget.max > 1 && _photos.isNotEmpty) ...[
                const SizedBox(width: 10),
                Expanded(child: SoftButton(label: 'Add another', icon: Icons.add_a_photo_rounded, onTap: full ? null : _phone)),
              ],
            ]),
          ]),
        ),
      ),
    );
  }

  // ---- the installed app: the camera live and full screen
  Widget _live(BuildContext context) {
    final c = _cam;
    final full = _photos.length >= widget.max;
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(fit: StackFit.expand, children: [
        if (c != null && c.value.isInitialized)
          CameraFill(controller: c, visible: _visible)
        else
          _NoCamera(error: _camError, onPick: _pick),
        IgnorePointer(
          child: AnimatedOpacity(opacity: _flash ? 0.8 : 0, duration: const Duration(milliseconds: 90), child: const ColoredBox(color: Colors.white)),
        ),
        const Positioned(top: 0, left: 0, right: 0, height: 150, child: IgnorePointer(child: Shade(top: true))),
        const Positioned(bottom: 0, left: 0, right: 0, height: 260, child: IgnorePointer(child: Shade(top: false))),
        SafeArea(
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(children: [
                _Round(icon: Icons.close_rounded, onTap: () => Navigator.of(context).pop()),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(widget.prompt,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 15, shadows: [Shadow(blurRadius: 8, color: Colors.black54)])),
                ),
                const SizedBox(width: 62),
              ]),
            ),
            const Spacer(),
            if (widget.max > 1 && _photos.isNotEmpty)
              SizedBox(
                height: 70,
                child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 16), children: [
                  for (var i = 0; i < _photos.length; i++)
                    Padding(
                      padding: const EdgeInsets.only(right: 10, top: 6),
                      child: GestureDetector(
                        onTap: () => setState(() => _photos.removeAt(i)),
                        child: ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.memory(_photos[i].bytes, width: 58, height: 58, fit: BoxFit.cover)),
                      ),
                    ),
                ]),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 10, 24, 6),
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
                    : const SizedBox(width: 52),
              ]),
            ),
            const Padding(
              padding: EdgeInsets.only(bottom: 6),
              child: Text('Tap the picture to focus', style: TextStyle(color: Colors.white70, fontSize: 12)),
            ),
          ]),
        ),
      ]),
    );
  }
}

/// A soft shadow at the top or bottom of the camera, so the controls show on any picture.
class Shade extends StatelessWidget {
  const Shade({super.key, required this.top});

  final bool top;

  @override
  Widget build(BuildContext context) => DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: top ? Alignment.topCenter : Alignment.bottomCenter,
            end: top ? Alignment.bottomCenter : Alignment.topCenter,
            colors: const [Color(0x99000000), Color(0x00000000)],
          ),
        ),
      );
}

class _Shutter extends StatelessWidget {
  const _Shutter({this.onTap});

  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => Bouncy(
        onTap: onTap,
        scale: 0.88,
        child: Container(
          width: 80,
          height: 80,
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
            width: 52,
            height: 52,
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
                  Text("The camera isn't available here.\n$error", textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70)),
                  const SizedBox(height: 18),
                  SoftButton(label: 'Choose photos instead', icon: Icons.photo_library_rounded, color: Colors.white, onTap: onPick),
                ]),
              ),
      );
}
