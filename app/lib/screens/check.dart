import 'dart:async';

import 'package:confetti/confetti.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../api.dart';
import '../models.dart';
import '../progress.dart';
import '../theme.dart';
import '../widgets/bouncy.dart';
import 'capture.dart';
import 'lesson.dart';

/// The check: the photos go to the server, the checker looks, and the learner sees what was found.
/// Questions it could not settle come back as cards: show a close-up, or say "I don't have it".
class CheckScreen extends StatefulWidget {
  const CheckScreen({super.key, required this.lesson, required this.quest, required this.photos});

  final LessonSummary lesson;
  final Quest quest;
  final List<Shot> photos;

  @override
  State<CheckScreen> createState() => _CheckScreenState();
}

class _CheckScreenState extends State<CheckScreen> {
  final _api = Api.instance;
  final _confetti = ConfettiController(duration: const Duration(seconds: 2));
  String? _upload;
  CheckResult? _result;
  String? _error;
  String? _busyAsk; // the question a close-up is being checked for

  @override
  void initState() {
    super.initState();
    _run();
  }

  @override
  void dispose() {
    _confetti.dispose();
    super.dispose();
  }

  Future<void> _run() async {
    setState(() {
      _error = null;
      _result = null;
    });
    try {
      _upload ??= await _api.upload(widget.lesson.id, widget.photos);
      _show(await _api.firstLook(_upload!, widget.lesson.id, widget.quest.card));
    } catch (e) {
      if (mounted) setState(() => _error = e is ApiError ? e.message : "Couldn't reach the server: $e");
    }
  }

  void _show(CheckResult r) {
    if (!mounted) return;
    final wasDone = _result?.allFound ?? false;
    setState(() => _result = r);
    if (r.allFound) {
      Progress.markDone(widget.lesson.id, widget.quest.number);
      if (!wasDone) {
        HapticFeedback.heavyImpact();
        _confetti.play();
      }
    }
  }

  Future<void> _closeup(Ask a) async {
    final shot = await Navigator.of(context).push<List<Shot>>(MaterialPageRoute(
      fullscreenDialog: true,
      builder: (_) => CaptureScreen(prompt: a.message, max: 1),
    ));
    if (shot == null || shot.isEmpty) return;
    setState(() => _busyAsk = a.key);
    try {
      _show(await _api.closeup(_upload!, a.key, shot.first));
    } catch (e) {
      _toast(e is ApiError ? e.message : "Couldn't check the close-up: $e");
    } finally {
      if (mounted) setState(() => _busyAsk = null);
    }
  }

  Future<void> _dismiss(Ask a) async {
    setState(() => _busyAsk = a.key);
    try {
      _show(await _api.dismiss(_upload!, a.key));
    } catch (e) {
      _toast(e is ApiError ? e.message : '$e');
    } finally {
      if (mounted) setState(() => _busyAsk = null);
    }
  }

  void _toast(String m) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(m)));

  @override
  Widget build(BuildContext context) {
    final r = _result;
    return Scaffold(
      appBar: AppBar(title: Text(widget.quest.title, style: Theme.of(context).textTheme.titleMedium), centerTitle: true),
      body: Stack(children: [
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 450),
          switchInCurve: Curves.easeOutCubic,
          child: _error != null
              ? _Failed(key: const ValueKey('err'), error: _error!, retry: _run)
              : r == null
                  ? ScanningView(key: const ValueKey('scan'), photo: widget.photos.first.bytes, lego: widget.lesson.isLego)
                  : ResultsView(
                      key: const ValueKey('res'),
                      result: r,
                      accent: Pq.forLesson(widget.lesson),
                      busyAsk: _busyAsk,
                      onCloseup: _closeup,
                      onDismiss: _dismiss,
                    ),
        ),
        Align(
          alignment: Alignment.topCenter,
          child: ConfettiWidget(
            confettiController: _confetti,
            blastDirectionality: BlastDirectionality.explosive,
            numberOfParticles: 30,
            gravity: 0.25,
            colors: const [Pq.electronics, Pq.lego, Pq.booklet, Pq.have, Pq.swap],
          ),
        ),
      ]),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: r == null
          ? null
          : Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: BigButton(
                  label: r.allFound ? 'Done!' : r.asks.isEmpty ? 'Done for now' : 'Carry on anyway',
                  icon: r.allFound ? Icons.emoji_events_rounded : Icons.arrow_forward_rounded,
                  color: r.allFound ? Pq.have : Pq.muted,
                  onTap: () => Navigator.of(context)
                    ..pop() // the check
                    ..pop(), // the quest: back to the lesson's list
                ),
              ),
            ).animate().slideY(begin: 1.2, duration: 400.ms, curve: Curves.easeOutBack),
    );
  }

}

/// The photo, with a light sweeping across it and cheerful words while the checker looks.
class ScanningView extends StatefulWidget {
  const ScanningView({super.key, required this.photo, required this.lego});

  final Uint8List photo;
  final bool lego;

  @override
  State<ScanningView> createState() => _ScanningViewState();
}

class _ScanningViewState extends State<ScanningView> with SingleTickerProviderStateMixin {
  late final _sweep = AnimationController(vsync: this, duration: const Duration(milliseconds: 1600))..repeat(reverse: true);
  late final List<String> _lines = widget.lego
      ? ['Looking at your pieces…', 'Counting studs…', 'Checking the colours…', 'Telling plates from bricks…', 'Nearly there…']
      : ['Looking at your parts…', 'Reading resistor bands…', 'Finding the board…', 'Counting wires…', 'Nearly there…'];
  int _i = 0;
  Timer? _t;

  @override
  void initState() {
    super.initState();
    _t = Timer.periodic(const Duration(milliseconds: 2600), (_) {
      if (mounted) setState(() => _i = (_i + 1) % _lines.length);
    });
  }

  @override
  void dispose() {
    _sweep.dispose();
    _t?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420, maxHeight: 420),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(28),
                child: AspectRatio(
                  aspectRatio: 3 / 4,
                  child: Stack(fit: StackFit.expand, children: [
                    Image.memory(widget.photo, fit: BoxFit.cover),
                    ColoredBox(color: Colors.black.withValues(alpha: 0.15)),
                    AnimatedBuilder(
                      animation: _sweep,
                      builder: (_, _) => Align(
                        alignment: Alignment(0, -1 + 2 * Curves.easeInOut.transform(_sweep.value)),
                        child: Container(
                          height: 90,
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                Pq.have.withValues(alpha: 0),
                                Pq.have.withValues(alpha: 0.45),
                                Pq.have.withValues(alpha: 0),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ]),
                ),
              ),
            ).animate().scale(begin: const Offset(0.9, 0.9), curve: Curves.easeOutBack, duration: 500.ms),
            const SizedBox(height: 28),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 350),
              transitionBuilder: (w, a) =>
                  FadeTransition(opacity: a, child: SlideTransition(position: Tween(begin: const Offset(0, 0.4), end: Offset.zero).animate(a), child: w)),
              child: Text(_lines[_i], key: ValueKey(_i), style: Theme.of(context).textTheme.titleLarge),
            ),
            const SizedBox(height: 8),
            const Text('This takes about 15 seconds', style: TextStyle(color: Pq.muted)),
          ]),
        ),
      );
}

class ResultsView extends StatelessWidget {
  const ResultsView({
    super.key,
    required this.result,
    required this.accent,
    required this.busyAsk,
    required this.onCloseup,
    required this.onDismiss,
    this.onCloseupAll,
    this.bottom = 130,
  });

  final CheckResult result;
  final Color accent;
  final String? busyAsk;
  final void Function(Ask) onCloseup;
  final void Function(Ask) onDismiss;
  final VoidCallback? onCloseupAll; // two or more questions: one photo of all of them
  final double bottom;

  @override
  Widget build(BuildContext context) {
    final r = result;
    final t = Theme.of(context).textTheme;
    final order = [Verdict.check, Verdict.missing, Verdict.swap, Verdict.have, Verdict.skipped];
    final parts = [...r.parts]..sort((a, b) => order.indexOf(a.verdict).compareTo(order.indexOf(b.verdict)));
    return ListView(
      padding: EdgeInsets.fromLTRB(16, 4, 16, bottom),
      children: [
        _Score(found: r.found, total: r.parts.length),
        if (r.asks.isNotEmpty) ...[
          const SizedBox(height: 20),
          Text('I need your help', style: t.titleLarge),
          const SizedBox(height: 8),
          if (onCloseupAll != null && r.asks.length >= 2)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: SoftButton(
                label: 'One close-up of all ${r.asks.length}',
                icon: Icons.photo_camera_front_rounded,
                color: Pq.electronics,
                onTap: busyAsk == null ? onCloseupAll : null,
              ),
            ),
          for (final (i, a) in r.asks.indexed)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _AskCard(ask: a, busy: busyAsk == a.key, onCloseup: () => onCloseup(a), onDismiss: () => onDismiss(a))
                  .animate()
                  .fadeIn(delay: (80 * i + 200).ms)
                  .slideX(begin: 0.08),
            ),
        ],
        const SizedBox(height: 16),
        Text('Your pieces', style: t.titleLarge),
        const SizedBox(height: 8),
        for (final (i, p) in parts.indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: _PartRow(part: p).animate().fadeIn(delay: (40 * i + 300).ms).slideY(begin: 0.2),
          ),
        if (r.extra.isNotEmpty) ...[
          const SizedBox(height: 14),
          Text('Also on the table (not needed now)', style: t.titleSmall?.copyWith(color: Pq.muted)),
          const SizedBox(height: 8),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final e in r.extra.take(12))
              Chip(label: Text(e, style: const TextStyle(fontSize: 12)), visualDensity: VisualDensity.compact),
          ]),
        ],
      ],
    );
  }
}

class _Score extends StatelessWidget {
  const _Score({required this.found, required this.total});

  final int found;
  final int total;

  @override
  Widget build(BuildContext context) {
    final all = found == total && total > 0;
    final c = all ? Pq.have : found >= total * 0.6 ? Pq.check : Pq.missing;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(children: [
          Text(all ? '🎉' : found >= total * 0.6 ? '👀' : '🔍', style: const TextStyle(fontSize: 44))
              .animate()
              .scale(curve: Curves.elasticOut, duration: 900.ms),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: found.toDouble()),
                duration: 800.ms,
                curve: Curves.easeOutCubic,
                builder: (_, v, _) => Text('${v.round()} of $total found',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontSize: 26)),
              ),
              const SizedBox(height: 2),
              Text(all ? 'Everything is here. Great job!' : 'Almost! Help me with the rest.',
                  style: const TextStyle(color: Pq.muted, fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0, end: total == 0 ? 0 : found / total),
                  duration: 900.ms,
                  curve: Curves.easeOutCubic,
                  builder: (_, v, _) => LinearProgressIndicator(
                    value: v,
                    minHeight: 10,
                    color: c,
                    backgroundColor: c.withValues(alpha: 0.15),
                  ),
                ),
              ),
            ]),
          ),
        ]),
      ),
    ).animate().fadeIn().scale(begin: const Offset(0.95, 0.95), curve: Curves.easeOutBack);
  }
}

class _AskCard extends StatelessWidget {
  const _AskCard({required this.ask, required this.busy, required this.onCloseup, required this.onDismiss});

  final Ask ask;
  final bool busy;
  final VoidCallback onCloseup;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Pq.check.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Pq.check.withValues(alpha: 0.5), width: 1.5),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const CircleAvatar(
              radius: 16,
              backgroundColor: Pq.check,
              child: Icon(Icons.priority_high_rounded, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 10),
            Expanded(child: Text(ask.message, style: const TextStyle(fontSize: 15, height: 1.35, fontWeight: FontWeight.w600))),
          ]),
          const SizedBox(height: 12),
          busy
              ? const Row(children: [
                  SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2.4)),
                  SizedBox(width: 10),
                  Text('Looking closely…', style: TextStyle(fontWeight: FontWeight.w600)),
                ])
              : Wrap(spacing: 8, runSpacing: 8, children: [
                  SoftButton(label: 'Show me', icon: Icons.center_focus_strong_rounded, color: Pq.electronics, onTap: onCloseup),
                  SoftButton(label: "I don't have it", icon: Icons.do_not_disturb_alt_rounded, color: Pq.muted, onTap: onDismiss),
                ]),
        ]),
      );
}

class _PartRow extends StatelessWidget {
  const _PartRow({required this.part});

  final PartResult part;

  @override
  Widget build(BuildContext context) {
    final v = part.verdict;
    final c = Pq.forVerdict(v);
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(color: c, shape: BoxShape.circle),
            child: Icon(Pq.verdictIcon(v), color: Colors.white, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${part.need}× ${part.name}', style: const TextStyle(fontWeight: FontWeight.w600)),
              if (part.note.isNotEmpty) ...[
                const SizedBox(height: 2),
                Text(part.note, style: const TextStyle(color: Pq.muted, fontSize: 12.5)),
              ],
            ]),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
            child: Text(Pq.verdictLabel(v), style: TextStyle(color: c, fontWeight: FontWeight.w700, fontSize: 12)),
          ),
        ]),
      ),
    );
  }
}

class _Failed extends StatelessWidget {
  const _Failed({super.key, required this.error, required this.retry});

  final String error;
  final VoidCallback retry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('😕', style: TextStyle(fontSize: 52)),
            const SizedBox(height: 10),
            Text('The check did not work', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 6),
            Text(error, textAlign: TextAlign.center, style: const TextStyle(color: Pq.muted)),
            const SizedBox(height: 18),
            SoftButton(label: 'Try again', icon: Icons.refresh_rounded, onTap: retry),
          ]),
        ),
      );
}
