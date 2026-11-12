// Pip's panel at the bottom of the session: the orb (listening / thinking / talking), the last words, and the
// controls. Tap the words to see the whole conversation.
import 'dart:math' as math;

import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';

import '../theme.dart';
import '../widgets/bouncy.dart';
import 'pip.dart';

class PipBar extends StatelessWidget {
  const PipBar({super.key, required this.pip, required this.onStart});

  final Pip pip;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
        listenable: pip,
        builder: (context, _) {
          final dark = Theme.of(context).brightness == Brightness.dark;
          final last = pip.lines.where((l) => l.who != 'sys').toList();
          final sys = pip.lines.isNotEmpty && pip.lines.last.who == 'sys' ? pip.lines.last.text : null;
          return Container(
            decoration: BoxDecoration(
              color: dark ? const Color(0xFF1E1E1C) : Colors.white,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(26)),
              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.10), blurRadius: 24, offset: const Offset(0, -6))],
            ),
            child: SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 12, 10, 10),
                child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                  Bouncy(onTap: pip.on ? null : onStart, child: Orb(state: pip.state)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: GestureDetector(
                      onTap: () => _transcript(context),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                        Text(_label(pip), style: TextStyle(fontWeight: FontWeight.w800, color: _colour(pip.state))),
                        const SizedBox(height: 2),
                        Text(
                          sys ?? (last.isEmpty ? (pip.on ? 'Just talk to me.' : "Tap me and I'll guide you through it.") : last.last.text.trim()),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: sys != null ? Pq.missing : (last.isNotEmpty && last.last.who == 'learner' ? Pq.muted : null),
                            fontStyle: last.isNotEmpty && last.last.who == 'learner' ? FontStyle.italic : null,
                            height: 1.25,
                          ),
                        ),
                      ]),
                    ),
                  ),
                  if (pip.on) ...[
                    IconButton(
                      tooltip: pip.muted ? 'Unmute' : 'Mute',
                      onPressed: () => pip.setMuted(!pip.muted),
                      icon: Icon(pip.muted ? Icons.mic_off_rounded : Icons.mic_rounded, color: pip.muted ? Pq.missing : null),
                    ),
                    IconButton(
                      tooltip: 'Type to Pip',
                      onPressed: () => _type(context),
                      icon: const Icon(Icons.keyboard_rounded),
                    ),
                    IconButton(
                      tooltip: 'End',
                      onPressed: pip.stop,
                      icon: const Icon(Icons.stop_circle_rounded, color: Pq.missing),
                    ),
                  ] else
                    SoftButton(label: 'Start', icon: Icons.graphic_eq_rounded, onTap: onStart),
                ]),
              ),
            ),
          );
        },
      );

  static String _label(Pip p) => switch (p.state) {
        PipState.off => p.lines.isEmpty ? 'Pip' : 'Pip · paused',
        PipState.connecting => 'Pip · connecting…',
        PipState.listening => p.muted ? 'Pip · muted' : 'Pip · listening',
        PipState.thinking => 'Pip · thinking…',
        PipState.speaking => 'Pip · talking',
      };

  static Color _colour(PipState s) => switch (s) {
        PipState.off => Pq.muted,
        PipState.connecting || PipState.thinking => Pq.booklet,
        PipState.listening => Pq.have,
        PipState.speaking => Pq.electronics,
      };

  void _type(BuildContext context) {
    final c = TextEditingController();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(16, 0, 16, MediaQuery.of(ctx).viewInsets.bottom + 16),
        child: TextField(
          controller: c,
          autofocus: true,
          textInputAction: TextInputAction.send,
          decoration: InputDecoration(
            hintText: 'Say something to Pip',
            filled: true,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
          ),
          onSubmitted: (t) {
            if (t.trim().isEmpty) return;
            pip.caption('learner', t.trim());
            pip.tell(t.trim());
            Navigator.pop(ctx);
          },
        ),
      ),
    );
  }

  void _transcript(BuildContext context) {
    HapticFeedback.selectionClick();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (ctx) => DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.6,
        maxChildSize: 0.92,
        builder: (_, scroll) => ListenableBuilder(
          listenable: pip,
          builder: (_, _) => Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
              child: Row(children: [
                Text('Talking with Pip', style: Theme.of(ctx).textTheme.titleLarge),
                const Spacer(),
                Text('${(pip.cost * 100).toStringAsFixed(1)}¢ of €4', style: const TextStyle(color: Pq.muted)),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: (pip.cost / pip.cap).clamp(0, 1),
                  minHeight: 5,
                  color: pip.cost >= pip.warn ? Pq.check : Pq.have,
                  backgroundColor: Pq.have.withValues(alpha: 0.12),
                ),
              ),
            ),
            Expanded(
              child: ListView(
                controller: scroll,
                padding: const EdgeInsets.all(16),
                children: [
                  if (pip.lines.isEmpty) const Text('Nothing said yet.', style: TextStyle(color: Pq.muted)),
                  for (final l in pip.lines) _Bubble(line: l),
                ],
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.line});

  final PipLine line;

  @override
  Widget build(BuildContext context) {
    if (line.who == 'sys') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Text(line.text, textAlign: TextAlign.center, style: const TextStyle(color: Pq.muted, fontSize: 12.5)),
      );
    }
    final me = line.who == 'learner';
    return Align(
      alignment: me ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        constraints: const BoxConstraints(maxWidth: 320),
        decoration: BoxDecoration(
          color: me ? Pq.electronics : Pq.electronics.withValues(alpha: 0.09),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(me ? 18 : 4),
            bottomRight: Radius.circular(me ? 4 : 18),
          ),
        ),
        child: Text(line.text.trim(), style: TextStyle(color: me ? Colors.white : null, height: 1.3)),
      ),
    );
  }
}

/// Pip itself: a soft ball that breathes while listening, swirls while thinking and pulses while talking.
class Orb extends StatefulWidget {
  const Orb({super.key, required this.state, this.size = 52});

  final PipState state;
  final double size;

  @override
  State<Orb> createState() => _OrbState();
}

class _OrbState extends State<Orb> with SingleTickerProviderStateMixin {
  late final _t = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat();

  @override
  void dispose() {
    _t.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.state;
    final c = PipBar._colour(s);
    return AnimatedBuilder(
      animation: _t,
      builder: (_, _) {
        final v = _t.value * 2 * math.pi;
        final scale = switch (s) {
          PipState.speaking => 1 + 0.09 * math.sin(v * 3).abs(),
          PipState.listening => 1 + 0.04 * math.sin(v),
          _ => 1.0,
        };
        return Transform.scale(
          scale: scale,
          child: Container(
            width: widget.size,
            height: widget.size,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: SweepGradient(
                transform: GradientRotation(s == PipState.thinking || s == PipState.connecting ? v : 0),
                colors: s == PipState.off
                    ? [Pq.muted.withValues(alpha: 0.5), Pq.muted.withValues(alpha: 0.3), Pq.muted.withValues(alpha: 0.5)]
                    : [c, Color.lerp(c, Colors.white, 0.45)!, Pq.lego.withValues(alpha: 0.85), c],
              ),
              boxShadow: s == PipState.off ? null : [BoxShadow(color: c.withValues(alpha: 0.45), blurRadius: 16 * scale)],
            ),
            child: Center(
              child: Icon(
                s == PipState.off ? Icons.graphic_eq_rounded : Icons.auto_awesome_rounded,
                color: Colors.white,
                size: widget.size * 0.44,
              ),
            ),
          ),
        );
      },
    );
  }
}
