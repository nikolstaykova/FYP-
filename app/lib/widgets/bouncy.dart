import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';

/// Anything tappable that squashes a little when pressed, with a light tap of haptics.
class Bouncy extends StatefulWidget {
  const Bouncy({super.key, required this.child, this.onTap, this.scale = 0.96});

  final Widget child;
  final VoidCallback? onTap;
  final double scale;

  @override
  State<Bouncy> createState() => _BouncyState();
}

class _BouncyState extends State<Bouncy> {
  bool _down = false;

  void _set(bool v) {
    if (widget.onTap != null && v != _down) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) => GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => _set(true),
        onTapUp: (_) => _set(false),
        onTapCancel: () => _set(false),
        onTap: widget.onTap == null
            ? null
            : () {
                HapticFeedback.selectionClick();
                widget.onTap!();
              },
        child: AnimatedScale(
          scale: _down ? widget.scale : 1,
          duration: const Duration(milliseconds: 110),
          curve: Curves.easeOut,
          child: AnimatedOpacity(
            opacity: widget.onTap == null ? 0.45 : 1,
            duration: const Duration(milliseconds: 200),
            child: widget.child,
          ),
        ),
      );
}

/// The big, bright main button at the bottom of a screen.
class BigButton extends StatelessWidget {
  const BigButton({super.key, required this.label, required this.icon, this.onTap, this.color, this.busy = false});

  final String label;
  final IconData icon;
  final VoidCallback? onTap;
  final Color? color;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.primary;
    return Bouncy(
      onTap: busy ? null : onTap,
      child: Container(
        height: 62,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: LinearGradient(
            colors: [Color.lerp(c, Colors.white, 0.12)!, c],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          boxShadow: [BoxShadow(color: c.withValues(alpha: 0.35), blurRadius: 18, offset: const Offset(0, 8))],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (busy)
              const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.6, color: Colors.white))
            else
              Icon(icon, color: Colors.white, size: 26),
            const SizedBox(width: 12),
            Text(label, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
          ],
        ),
      ),
    );
  }
}

/// A soft second button.
class SoftButton extends StatelessWidget {
  const SoftButton({super.key, required this.label, this.icon, this.onTap, this.color});

  final String label;
  final IconData? icon;
  final VoidCallback? onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.primary;
    return Bouncy(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(16)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (icon != null) ...[Icon(icon, size: 20, color: c), const SizedBox(width: 8)],
          Text(label, style: TextStyle(color: c, fontWeight: FontWeight.w700, fontSize: 15)),
        ]),
      ),
    );
  }
}
