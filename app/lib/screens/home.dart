import 'package:material_ui/material_ui.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../api.dart';
import '../models.dart';
import '../theme.dart';
import '../widgets/bouncy.dart';
import 'connect.dart';
import 'lesson.dart';

enum _Filter { all, electronics, lego }

/// Every lesson from the server (the lesson database), to choose from.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<LessonSummary>> _lessons = Api.instance.lessons();
  _Filter _filter = _Filter.all;
  String _q = '';

  Future<void> _refresh() async {
    final f = Api.instance.lessons(fresh: true);
    setState(() => _lessons = f);
    await f.catchError((_) => <LessonSummary>[]);
  }

  List<LessonSummary> _shown(List<LessonSummary> all) => all.where((l) {
        if (_filter == _Filter.electronics && l.isLego) return false;
        if (_filter == _Filter.lego && !l.isLego) return false;
        return _q.isEmpty || l.name.toLowerCase().contains(_q) || l.id.toLowerCase().contains(_q);
      }).toList();

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: SafeArea(
                bottom: false,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 18, 8, 14),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('Parts Quest', style: t.displaySmall?.copyWith(fontSize: 34))
                            .animate()
                            .fadeIn(duration: 300.ms)
                            .slideX(begin: -0.05),
                        const SizedBox(height: 2),
                        Text('What shall we build today?', style: t.titleMedium?.copyWith(color: Pq.muted))
                            .animate()
                            .fadeIn(delay: 120.ms),
                      ]),
                    ),
                    IconButton(
                      tooltip: 'Server',
                      icon: const Icon(Icons.settings_rounded, color: Pq.muted),
                      onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ConnectScreen())),
                    ),
                  ]),
                ),
              ),
            ),
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  TextField(
                    onChanged: (v) => setState(() => _q = v.trim().toLowerCase()),
                    decoration: InputDecoration(
                      hintText: 'Search lessons',
                      prefixIcon: const Icon(Icons.search_rounded),
                      filled: true,
                      isDense: true,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
                    ),
                  ),
                  const SizedBox(height: 12),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(children: [
                      _chip('All', _Filter.all, Icons.apps_rounded, Theme.of(context).colorScheme.onSurface),
                      _chip('Electronics', _Filter.electronics, Icons.memory_rounded, Pq.electronics),
                      _chip('LEGO', _Filter.lego, Icons.extension_rounded, Pq.lego),
                    ]),
                  ),
                ]),
              ),
            ),
            FutureBuilder<List<LessonSummary>>(
              future: _lessons,
              builder: (context, snap) {
                if (snap.hasError) {
                  return SliverFillRemaining(hasScrollBody: false, child: _Problem(error: '${snap.error}', retry: _refresh));
                }
                if (!snap.hasData) return const _Loading();
                final shown = _shown(snap.data!);
                if (shown.isEmpty) {
                  return SliverFillRemaining(
                    hasScrollBody: false,
                    child: Center(child: Text('No lessons match.', style: t.titleMedium?.copyWith(color: Pq.muted))),
                  );
                }
                return SliverPadding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                  sliver: SliverGrid.builder(
                    gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                      maxCrossAxisExtent: 260,
                      mainAxisExtent: 142,
                      crossAxisSpacing: 12,
                      mainAxisSpacing: 12,
                    ),
                    itemCount: shown.length,
                    itemBuilder: (_, i) => _LessonCard(lesson: shown[i])
                        .animate(key: ValueKey('${shown[i].id}$_filter'))
                        .fadeIn(delay: (24 * (i % 16)).ms, duration: 260.ms)
                        .slideY(begin: 0.12, curve: Curves.easeOutCubic),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, _Filter f, IconData icon, Color c) {
    final on = _filter == f;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Bouncy(
        onTap: () => setState(() => _filter = f),
        child: AnimatedContainer(
          duration: 200.ms,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            color: on ? c : c.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(40),
          ),
          child: Row(children: [
            Icon(icon, size: 18, color: on ? Colors.white : c),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(fontWeight: FontWeight.w700, color: on ? Colors.white : c)),
          ]),
        ),
      ),
    );
  }
}

class _LessonCard extends StatelessWidget {
  const _LessonCard({required this.lesson});

  final LessonSummary lesson;

  @override
  Widget build(BuildContext context) {
    final c = Pq.forLesson(lesson);
    final t = Theme.of(context).textTheme;
    return Bouncy(
      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => LessonScreen(summary: lesson))),
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: Stack(children: [
          Positioned(
            right: -18,
            top: -18,
            child: Icon(Pq.iconFor(lesson), size: 96, color: c.withValues(alpha: 0.08)),
          ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Hero(
                tag: 'icon-${lesson.id}',
                child: Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(14)),
                  child: Icon(Pq.iconFor(lesson), color: Colors.white),
                ),
              ),
              const Spacer(),
              Text(lesson.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: t.titleMedium?.copyWith(height: 1.15)),
              const SizedBox(height: 4),
              Text(
                lesson.isLego ? '${Pq.kindLabel(lesson)} · ${lesson.id.replaceAll('-pdf', '')}'
                    : '${Pq.kindLabel(lesson)} · ${lesson.parts.length} parts',
                style: t.bodySmall?.copyWith(color: c, fontWeight: FontWeight.w700),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _Loading extends StatelessWidget {
  const _Loading();

  @override
  Widget build(BuildContext context) => SliverPadding(
        padding: const EdgeInsets.all(16),
        sliver: SliverGrid.builder(
          gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: 260, mainAxisExtent: 142, crossAxisSpacing: 12, mainAxisSpacing: 12),
          itemCount: 8,
          itemBuilder: (_, i) => const Card(child: SizedBox.expand())
              .animate(onPlay: (c) => c.repeat(reverse: true))
              .fade(begin: 0.5, end: 1, duration: 700.ms, delay: (60 * i).ms),
        ),
      );
}

class _Problem extends StatelessWidget {
  const _Problem({required this.error, required this.retry});

  final String error;
  final VoidCallback retry;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.all(32),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.wifi_off_rounded, size: 56, color: Pq.muted),
          const SizedBox(height: 12),
          Text("Can't load the lessons", style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 6),
          Text(error, textAlign: TextAlign.center, style: const TextStyle(color: Pq.muted)),
          const SizedBox(height: 20),
          Wrap(spacing: 10, runSpacing: 10, alignment: WrapAlignment.center, children: [
            SoftButton(label: 'Try again', icon: Icons.refresh_rounded, onTap: retry),
            SoftButton(
              label: 'Change server',
              icon: Icons.settings_rounded,
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ConnectScreen())),
            ),
          ]),
        ]),
      );
}
