// What Pip is told after a check: plain facts it can say in its own words (as summary() in the web game).

String _kind(String s) => s.startsWith('have')
    ? 'have'
    : s.startsWith('use')
        ? 'swap'
        : s.startsWith('check')
            ? 'check'
            : 'missing';

Map<String, dynamic> summary(Map<String, dynamic> st) {
  final have = <String>[];
  final instead = <Map<String, dynamic>>[];
  final notSure = <Map<String, dynamic>>[];
  final missing = <Map<String, dynamic>>[];
  for (final r in (st['parts'] as List? ?? const []).cast<Map<String, dynamic>>()) {
    final uses = (r['use_instead'] as List? ?? const []).cast<Map<String, dynamic>>();
    final haves = (r['have'] as List? ?? const []).cast<Map<String, dynamic>>();
    final u = uses.where((x) => x['ok'] != false).firstOrNull;
    final bad = uses.where((x) => x['ok'] == false).firstOrNull;
    switch (_kind('${r['status']}')) {
      case 'have':
        have.add('${r['part']}');
      case 'swap':
        instead.add({'part': r['part'], 'use': u?['object'], 'why': u?['why']});
      case 'check':
        notSure.add({'part': r['part'], 'why': haves.firstOrNull?['why'] ?? u?['why'] ?? ''});
      default:
        missing.add({'part': r['part'], 'need': r['need'], 'status': r['status'], 'why': bad?['why'] ?? ''});
    }
  }
  final asks = (st['asks'] as List? ?? const []).cast<Map<String, dynamic>>();
  final extra = (st['not_needed'] as List? ?? const []).cast<Map<String, dynamic>>();
  return {
    'have': have,
    'can_use_instead': instead,
    'not_sure': notSure,
    'missing': missing,
    'questions': [for (final q in asks) {'key': q['key'], 'ask': q['message']}],
    'all_settled': asks.isEmpty,
    if (extra.isNotEmpty) 'also_on_the_table': [for (final x in extra.take(8)) x['object']],
  };
}
