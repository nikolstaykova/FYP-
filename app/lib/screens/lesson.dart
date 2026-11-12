import 'package:material_ui/material_ui.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../api.dart';
import '../models.dart';
import '../progress.dart';
import '../theme.dart';
import '../widgets/bouncy.dart';
import 'gather.dart';

/// One gather quest: the pieces to find, and which card the server checks them against.
class Quest {
  Quest({required this.title, required this.text, required this.pieces, required this.number, required this.card});

  final String title;
  final String text;
  final List<Piece> pieces;
  final int number; // where it is in the lesson (1-based), the key for the progress kept on the phone
  final int? card; // what /api/flow/first is told: the LEGO gather card, null for electronics

  int get pieceCount => pieces.fold(0, (a, p) => a + p.count);
}

/// A lesson's gather quests: one for an electronics lesson, one every few steps (or per bag) for LEGO.
class LessonScreen extends StatefulWidget {
  const LessonScreen({super.key, required this.summary});

  final LessonSummary summary;

  @override
  State<LessonScreen> createState() => _LessonScreenState();
}

class _LessonScreenState extends State<LessonScreen> {
  late final Future<LessonDetail> _detail = Api.instance.lesson(widget.summary.id);
  Set<int> _done = {};

  @override
  void initState() {
    super.initState();
    _loadDone();
  }

  Future<void> _loadDone() async {
    final d = await Progress.doneCards(widget.summary.id);
    if (mounted) setState(() => _done = d);
  }

  List<Quest> _quests(LessonDetail d) {
    final s = widget.summary;
    if (!s.isLego) {
      final g = d.gatherCards.isNotEmpty ? d.gatherCards.first : null;
      return [
        Quest(
          title: 'Gather the parts',
          text: g?.text ?? 'Find these parts and lay them on the table.',
          pieces: s.parts.isNotEmpty ? s.parts : (g?.parts ?? const []),
          number: g?.number ?? 1,
          card: null,
        ),
      ];
    }
    return [
      for (final g in d.gatherCards) Quest(title: g.title, text: g.text, pieces: g.parts, number: g.number, card: g.number),
    ];
  }

  Future<void> _open(Quest q, List<Quest> all) async {
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => GatherScreen(lesson: widget.summary, quest: q, index: all.indexOf(q), total: all.length),
    ));
    _loadDone();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.summary;
    final c = Pq.forLesson(s);
    final t = Theme.of(context).textTheme;
    return Scaffold(
      body: FutureBuilder<LessonDetail>(
        future: _detail,
        builder: (context, snap) {
          final quests = snap.hasData ? _quests(snap.data!) : <Quest>[];
          final done = quests.where((q) => _done.contains(q.number)).length;
          final next = quests.where((q) => !_done.contains(q.number)).firstOrNull;
          return CustomScrollView(slivers: [
            SliverAppBar(
              pinned: true,
              expandedHeight: 230,
              backgroundColor: c,
              foregroundColor: Colors.white,
              flexibleSpace: FlexibleSpaceBar(
                centerTitle: false,
                titlePadding: const EdgeInsetsDirectional.only(start: 56, bottom: 14, end: 16),
                title: Text(s.name, maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                background: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Color.lerp(c, Colors.white, 0.15)!, Color.lerp(c, Colors.black, 0.15)!],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: Stack(children: [
                    Positioned(
                      right: -30,
                      bottom: -30,
                      child: Icon(Pq.iconFor(s), size: 200, color: Colors.white.withValues(alpha: 0.12)),
                    ),
                    Positioned(
                      left: 20,
                      top: 92,
                      child: Hero(
                        tag: 'icon-${s.id}',
                        child: Container(
                          width: 56,
                          height: 56,
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.22),
                            borderRadius: BorderRadius.circular(18),
                          ),
                          child: Icon(Pq.iconFor(s), color: Colors.white, size: 30),
                        ),
                      ),
                    ),
                  ]),
                ),
              ),
            ),
            if (snap.hasError)
              SliverFillRemaining(
                hasScrollBody: false,
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Text("Couldn't load this lesson.\n${snap.error}",
                        textAlign: TextAlign.center, style: const TextStyle(color: Pq.muted)),
                  ),
                ),
              )
            else if (!snap.hasData)
              const SliverFillRemaining(hasScrollBody: false, child: Center(child: CircularProgressIndicator()))
            else ...[
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
                  child: Row(children: [
                    _Ring(done: done, total: quests.length, color: c),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(done == quests.length && quests.isNotEmpty ? 'Everything found!' : 'Find your parts',
                            style: t.titleLarge),
                        const SizedBox(height: 2),
                        Text(
                          '${quests.length} ${quests.length == 1 ? 'quest' : 'quests'} · '
                          '${quests.fold<int>(0, (a, q) => a + q.pieceCount)} pieces · ${Pq.kindLabel(s)}',
                          style: t.bodyMedium?.copyWith(color: Pq.muted),
                        ),
                      ]),
                    ),
                  ]),
                ).animate().fadeIn(duration: 300.ms),
              ),
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
                sliver: SliverList.separated(
                  itemCount: quests.length,
                  separatorBuilder: (_, _) => const SizedBox(height: 10),
                  itemBuilder: (_, i) => _QuestTile(
                    quest: quests[i],
                    index: i,
                    done: _done.contains(quests[i].number),
                    isNext: identical(quests[i], next),
                    color: c,
                    onTap: () => _open(quests[i], quests),
                  ).animate().fadeIn(delay: (40 * i).ms).slideX(begin: 0.06, curve: Curves.easeOutCubic),
                ),
              ),
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 4, 24, 120),
                  child: Row(children: [
                    const Icon(Icons.construction_rounded, color: Pq.muted, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text('Building steps come to the app next. For now: find the parts.',
                          style: t.bodySmall?.copyWith(color: Pq.muted)),
                    ),
                  ]),
                ),
              ),
            ],
          ]);
        },
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      floatingActionButton: FutureBuilder<LessonDetail>(
        future: _detail,
        builder: (context, snap) {
          if (!snap.hasData) return const SizedBox.shrink();
          final quests = _quests(snap.data!);
          final next = quests.where((q) => !_done.contains(q.number)).firstOrNull;
          if (next == null) return const SizedBox.shrink();
          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: BigButton(
                label: _done.isEmpty ? 'Start the quest' : 'Next: ${next.title}',
                icon: Icons.play_arrow_rounded,
                color: c,
                onTap: () => _open(next, quests),
              ),
            ),
          ).animate().slideY(begin: 1.2, duration: 400.ms, curve: Curves.easeOutBack);
        },
      ),
    );
  }
}

class _QuestTile extends StatelessWidget {
  const _QuestTile(
      {required this.quest, required this.index, required this.done, required this.isNext, required this.color, required this.onTap});

  final Quest quest;
  final int index;
  final bool done;
  final bool isNext;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final badge = done ? Pq.have : color;
    return Bouncy(
      onTap: onTap,
      child: Card(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: isNext ? BorderSide(color: color, width: 2) : BorderSide.none,
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(children: [
            AnimatedContainer(
              duration: 300.ms,
              width: 46,
              height: 46,
              decoration: BoxDecoration(
                color: done ? Pq.have : badge.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(14),
              ),
              alignment: Alignment.center,
              child: done
                  ? const Icon(Icons.check_rounded, color: Colors.white)
                  : Text('${index + 1}', style: TextStyle(color: badge, fontSize: 18, fontWeight: FontWeight.w800)),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(quest.title, style: t.titleMedium),
                const SizedBox(height: 2),
                Text('${quest.pieceCount} pieces · ${quest.pieces.length} kinds',
                    style: t.bodySmall?.copyWith(color: Pq.muted)),
                const SizedBox(height: 8),
                _Swatches(pieces: quest.pieces),
              ]),
            ),
            Icon(Icons.chevron_right_rounded, color: Pq.muted.withValues(alpha: 0.6)),
          ]),
        ),
      ),
    );
  }
}

/// A row of little coloured bricks: a glance at what a LEGO card holds.
class _Swatches extends StatelessWidget {
  const _Swatches({required this.pieces});

  final List<Piece> pieces;

  @override
  Widget build(BuildContext context) {
    final withColour = pieces.where((p) => p.colour != null).take(10).toList();
    if (withColour.isEmpty) {
      return Text(pieces.map((p) => p.what).take(3).join(' · '),
          maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Pq.muted, fontSize: 12));
    }
    return Wrap(spacing: 4, runSpacing: 4, children: [
      for (final p in withColour)
        Container(
          width: 18,
          height: 12,
          decoration: BoxDecoration(
            color: Pq.brick(p.colour),
            borderRadius: BorderRadius.circular(3),
            border: Border.all(color: Colors.black.withValues(alpha: 0.12)),
          ),
        ),
    ]);
  }
}

class _Ring extends StatelessWidget {
  const _Ring({required this.done, required this.total, required this.color});

  final int done;
  final int total;
  final Color color;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 64,
        height: 64,
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: total == 0 ? 0 : done / total),
          duration: 900.ms,
          curve: Curves.easeOutCubic,
          builder: (_, v, _) => Stack(fit: StackFit.expand, children: [
            CircularProgressIndicator(
              value: v,
              strokeWidth: 7,
              strokeCap: StrokeCap.round,
              color: done == total && total > 0 ? Pq.have : color,
              backgroundColor: color.withValues(alpha: 0.12),
            ),
            Center(child: Text('$done/$total', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15))),
          ]),
        ),
      );
}
