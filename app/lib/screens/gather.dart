
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../models.dart';
import '../progress.dart';
import '../theme.dart';
import '../widgets/bouncy.dart';
import 'capture.dart';
import 'check.dart';
import 'lesson.dart';

/// One quest: the pieces to find (tap to tick), then show them all to the camera.
class GatherScreen extends StatefulWidget {
  const GatherScreen({super.key, required this.lesson, required this.quest, required this.index, required this.total});

  final LessonSummary lesson;
  final Quest quest;
  final int index;
  final int total;

  @override
  State<GatherScreen> createState() => _GatherScreenState();
}

class _GatherScreenState extends State<GatherScreen> {
  Set<int> _got = {};
  int? _open;

  @override
  void initState() {
    super.initState();
    Progress.ticked(widget.lesson.id, widget.quest.number).then((g) {
      if (mounted) setState(() => _got = g);
    });
  }

  void _tick(int i) {
    HapticFeedback.lightImpact();
    setState(() => _got.contains(i) ? _got.remove(i) : _got.add(i));
    Progress.setTicked(widget.lesson.id, widget.quest.number, _got);
  }

  Future<void> _scan() async {
    final photos = await Navigator.of(context).push<List<Uint8List>>(MaterialPageRoute(
      fullscreenDialog: true,
      builder: (_) => CaptureScreen(
        prompt: widget.lesson.isLego ? 'Lay the pieces flat, a little apart' : 'Lay the parts out so I can see them all',
        max: 3,
      ),
    ));
    if (photos == null || photos.isEmpty || !mounted) return;
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => CheckScreen(lesson: widget.lesson, quest: widget.quest, photos: photos),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.quest;
    final c = Pq.forLesson(widget.lesson);
    final t = Theme.of(context).textTheme;
    final ticked = _got.length;
    return Scaffold(
      appBar: AppBar(
        title: Text('Quest ${widget.index + 1} of ${widget.total}', style: t.titleMedium),
        centerTitle: true,
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 130),
        children: [
          Text(q.title, style: t.headlineMedium).animate().fadeIn().slideY(begin: 0.2),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: c.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(18)),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(Icons.lightbulb_rounded, color: c),
              const SizedBox(width: 10),
              Expanded(child: Text(q.text, style: t.bodyMedium?.copyWith(height: 1.35))),
            ]),
          ).animate().fadeIn(delay: 80.ms),
          const SizedBox(height: 18),
          Row(children: [
            Text('Your list', style: t.titleLarge),
            const Spacer(),
            Text('$ticked / ${q.pieces.length} ticked', style: t.bodyMedium?.copyWith(color: Pq.muted)),
          ]),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: TweenAnimationBuilder<double>(
              tween: Tween(end: q.pieces.isEmpty ? 0 : ticked / q.pieces.length),
              duration: 400.ms,
              curve: Curves.easeOutCubic,
              builder: (_, v, _) => LinearProgressIndicator(
                value: v,
                minHeight: 8,
                color: ticked == q.pieces.length ? Pq.have : c,
                backgroundColor: c.withValues(alpha: 0.12),
              ),
            ),
          ),
          const SizedBox(height: 12),
          for (var i = 0; i < q.pieces.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: PieceRow(
                piece: q.pieces[i],
                got: _got.contains(i),
                expanded: _open == i,
                accent: c,
                onTick: () => _tick(i),
                onMore: q.pieces[i].about == null ? null : () => setState(() => _open = _open == i ? null : i),
              ).animate().fadeIn(delay: (30 * i + 120).ms).slideY(begin: 0.15, curve: Curves.easeOutCubic),
            ),
        ],
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: BigButton(label: 'Scan my pieces', icon: Icons.photo_camera_rounded, color: c, onTap: _scan),
        ),
      ).animate().slideY(begin: 1.2, duration: 400.ms, curve: Curves.easeOutBack),
    );
  }
}

class PieceRow extends StatelessWidget {
  const PieceRow({
    super.key,
    required this.piece,
    required this.got,
    required this.expanded,
    required this.accent,
    required this.onTick,
    this.onMore,
  });

  final Piece piece;
  final bool got;
  final bool expanded;
  final Color accent;
  final VoidCallback onTick;
  final VoidCallback? onMore;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Bouncy(
      onTap: onTick,
      scale: 0.98,
      child: AnimatedContainer(
        duration: 250.ms,
        padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
        decoration: BoxDecoration(
          color: Theme.of(context).cardTheme.color,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: got ? Pq.have : Colors.transparent, width: 2),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Brick(colour: piece.colour, count: piece.count, fallback: accent),
            const SizedBox(width: 12),
            Expanded(
              child: AnimatedDefaultTextStyle(
                duration: 250.ms,
                style: (t.titleSmall ?? const TextStyle()).copyWith(
                  fontWeight: FontWeight.w600,
                  color: got ? Pq.muted : t.titleSmall?.color,
                  decoration: got ? TextDecoration.lineThrough : null,
                  decorationColor: Pq.muted,
                ),
                child: Text(piece.what),
              ),
            ),
            if (onMore != null)
              IconButton(
                visualDensity: VisualDensity.compact,
                icon: AnimatedRotation(
                  turns: expanded ? 0.5 : 0,
                  duration: 200.ms,
                  child: const Icon(Icons.expand_more_rounded, color: Pq.muted),
                ),
                onPressed: onMore,
                tooltip: 'What does it look like?',
              ),
            AnimatedSwitcher(
              duration: 250.ms,
              transitionBuilder: (w, a) => ScaleTransition(scale: a, child: w),
              child: got
                  ? const Icon(Icons.check_circle_rounded, color: Pq.have, size: 28, key: ValueKey(1))
                  : Icon(Icons.radio_button_unchecked_rounded, color: Pq.muted.withValues(alpha: 0.5), size: 28, key: const ValueKey(0)),
            ),
          ]),
          AnimatedSize(
            duration: 220.ms,
            curve: Curves.easeOutCubic,
            child: expanded && piece.about != null
                ? Padding(
                    padding: const EdgeInsets.fromLTRB(56, 8, 8, 2),
                    child: Text(piece.about!, style: t.bodySmall?.copyWith(color: Pq.muted, height: 1.4)),
                  )
                : const SizedBox(width: double.infinity),
          ),
        ]),
      ),
    );
  }
}

/// The piece's colour as a little brick with its count on it.
class Brick extends StatelessWidget {
  const Brick({super.key, this.colour, required this.count, required this.fallback});

  final String? colour;
  final int count;
  final Color fallback;

  @override
  Widget build(BuildContext context) {
    final c = colour == null ? fallback : Pq.brick(colour);
    final light = c.computeLuminance() > 0.55;
    return Container(
      width: 44,
      height: 36,
      decoration: BoxDecoration(
        color: c,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.black.withValues(alpha: 0.12)),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.12), offset: const Offset(0, 3))],
      ),
      alignment: Alignment.center,
      child: Text('$count×', style: TextStyle(fontWeight: FontWeight.w800, color: light ? Pq.ink : Colors.white)),
    );
  }
}
