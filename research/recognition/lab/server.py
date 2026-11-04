"""Parts lab: a local page to try the parts check on your own photos with different models.

Pick a saved lesson (its parts list comes from data/lessons/store), add photos, tick models: every model looks at
the same photos with the same instruction (kit_test.look_nvidia), the code (checker.gather) compares what it saw
with the lesson's list, and the page shows each model's verdicts, time and cost side by side.
API keys stay in .env on this Mac; the page only talks to this server.

Pages: / is Parts Quest (game.html), the learner's flow as a game: choose a lesson, gather its parts (a checklist),
scan them (camera or upload), and the check (what you have, what can stand in, close-up quests). /lab is the lab
(index.html), in two modes: "Check flow" (the product flow: camera -> Haiku looks -> the learner is asked for close-ups of what
Haiku could not settle -> Opus on a close-up only when Haiku still cannot tell; checker.gather_flow) and "Compare models" (every ticked model on the same photos).

Run:  ./research/recognition/lab/run.sh                 then open http://127.0.0.1:8765 (camera works on this Mac)
      ./research/recognition/lab/run.sh --lan --https   from a phone on the same Wi-Fi, with the live camera (phones
                                                        allow it only over https: accept the certificate warning
                                                        once). Prints a link with a one-time key; anyone with the
                                                        link can spend your API credit.
Runs are saved in research/recognition/runs/lab/<time>/ (photos, one JSON per model run).
"""
import base64
import json
import re
import secrets
import socket
import statistics
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
REC = HERE.parent
ROOT = REC.parents[1]
sys.path[:0] = [str(ROOT / 'code'), str(REC)]

from checker import gather, gather_flow  # noqa: E402
from kit_test import look_nvidia  # noqa: E402

RUNS = REC / 'runs' / 'lab'
STORE = ROOT / 'data/lessons/store'

# label, price note (per 1M tokens in / out), which key in .env
MODELS = [
    ('claude-haiku-5-5', 'Claude Haiku 5.5', '$0.10 / $0.50', 'ANTHROPIC_API_KEY'),
    ('claude-sonnet-5-5', 'Claude Sonnet 5.5', '$2 / $10', 'ANTHROPIC_API_KEY'),
    ('claude-opus-5-5', 'Claude Opus 5.5', '$4 / $20', 'ANTHROPIC_API_KEY'),
    ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite', '$0.30 / $2.50', 'GEMINI_API_KEY'),
    ('gemini-3.8-flash', 'Gemini 3.8 Flash', '$0.75 / $3.75', 'GEMINI_API_KEY'),
    ('gemini-robotics-er-2-preview', 'Gemini Robotics-ER 2', '$1 / $5 (free tier: 20 a day)', 'GEMINI_API_KEY'),
    ('nvidia/nemotron-3.5-super-vl-120b-a12b', 'Nemotron 3.5 Super VL', 'free credits', 'NVIDIA_API_KEY'),
    ('nvidia/nemotron-3-nano-omni-30b-a3b-reasoning', 'Nemotron 3 Nano Omni', 'free credits', 'NVIDIA_API_KEY'),
]
TOKEN = None  # set with --lan


def env_keys():
    f = ROOT / '.env'
    have = set()
    if f.exists():
        for line in f.read_text().splitlines():
            k, _, v = line.partition('=')
            if v.strip().strip('"\''):
                have.add(k.strip())
    return have


def lessons():
    """The Arduino lessons (the parts check is for electronics; LEGO lessons gather step by step), listed from the
    lesson index and read through the lesson store: the database when it is set up (one query for all), else the
    files."""
    from graph import db, lesson_store
    db.prefetch()
    out = []
    for row in lesson_store.catalogue()["lessons"]:
        if row.get("lesson_type") != "arduino":
            continue
        try:
            rec, phys = gather.lesson(row["lesson_id"])
            parts = [{'type': r['type'], 'name': r['name'], 'count': r['count'],
                      'values': sorted({str(v) for v in r.get('values', []) if v})} for r in gather.needs(rec, phys)]
        except Exception:
            continue
        out.append({'id': row["lesson_id"], 'name': rec.get('name') or row["lesson_id"], 'type': 'arduino',
                    'parts': parts})
    return sorted(out, key=lambda x: x["name"].lower())


def lego_lessons():
    """The LEGO lessons (3D model and booklet): no parts check (the learner has the set), straight to building."""
    from graph import lesson_store
    rows = [r for r in lesson_store.catalogue()["lessons"] if r.get("lesson_type") == "lego"]
    return sorted(({"id": r["lesson_id"], "name": r.get("name") or r["lesson_id"], "type": "lego",
                    "kind": "booklet" if r["lesson_id"].endswith("-pdf") else "3D model", "parts": []} for r in rows),
                  key=lambda x: (x["name"].lower(), x["kind"]))


def run_check(upload, lesson_id, model, research, repeat):
    """Look `repeat` times (for timing), check the first answer against the lesson."""
    photos = sorted(str(p) for p in (RUNS / upload).glob('photo_*.jpg'))
    times, costs, first = [], [], None
    t_start = time.perf_counter()
    for i in range(repeat):
        seen, stats = look_nvidia(photos, lesson_id, model)
        times.append(stats['seconds'])
        costs.append(stats.get('cost_usd') or 0)
        if first is None:
            first = (seen, stats)
    seen, stats = first
    t0 = time.perf_counter()
    res = gather.check(lesson_id, photos, research=research, seen=seen)
    res['look'] = stats
    out = {'model': model, 'lesson': lesson_id, 'photos': len(photos), 'times': times,
           'median_s': round(statistics.median(times), 1), 'cost_usd': round(sum(costs) / len(costs), 5),
           'check_s': round(time.perf_counter() - t0, 1), 'total_s': round(time.perf_counter() - t_start, 1),
           'tokens_in': stats.get('tokens_in'), 'tokens_out': stats.get('tokens_out'), 'parsed': stats.get('parsed'),
           'parts': res['parts'], 'not_needed': res['not_needed'], 'retake': res['retake'],
           'seen': res['seen'], 'report': gather.text(res), 'raw': stats.get('raw', '')[:4000]}
    (RUNS / upload / f"{model.split('/')[-1]}-{int(time.time())}.json").write_text(json.dumps(out, indent=1))
    return out


def flow(action, upload, body):
    """The check as the learner gets it. State lives in runs/lab/<upload>/flow_state.json:
    first   Haiku looks at the photos                                     ~0.1 cents
    closeup the learner sends a close-up for one question; Haiku answers it ~0.05 cents
    dismiss the learner says "I don't have it" (or skips a close-up)
            when Haiku still cannot tell from the close-up, Opus looks at it  ~1 cent, once per question
    Every action returns the current verdicts and the questions still open."""
    d = RUNS / upload
    sf = d / 'flow_state.json'
    if action == 'first':
        rec, _ = gather.lesson(body['lesson'])
        photos = sorted(str(p) for p in d.glob('photo_*.jpg'))
        seen, stats = gather_flow.first_look(photos, rec)
        st = {'lesson': body['lesson'], 'seen': seen, 'dismissed': [], 'closeups': [],
              'steps': [{'what': 'first look', **{k: stats.get(k) for k in ('model', 'seconds', 'cost_usd')}}]}
        res = gather.check(st['lesson'], photos, research=False, seen=seen)
        st['first_parts'] = [{'type': r['type'], 'status': r['status']} for r in res['parts']]
    else:
        st = json.loads(sf.read_text())
        rec, _ = gather.lesson(st['lesson'])
        photos = sorted(str(p) for p in d.glob('photo_*.jpg'))
        if action in ('closeup', 'dismiss'):
            res = gather.check(st['lesson'], photos, research=False, seen=st['seen'])
            objects, parts = gather_flow.flags(res, {r['type'] for r in res['parts']}, done=('closeup', 'opus'))
            open_qs = {q['key']: q for q in gather_flow.asks(res, objects, parts, st['dismissed'])}
        if action == 'dismiss':
            st['dismissed'].append(body['key'])
        elif action == 'closeup':
            q = open_qs.get(body['key'])
            if not q:
                raise ValueError('that question is no longer open')
            n = len(st['closeups']) + 1
            f = d / f'closeup_{n}.jpg'
            f.write_bytes(base64.b64decode(body['photo'].split(',', 1)[-1]))
            item = res['seen'][q['ref']] if q['kind'] == 'closeup' else None
            got, stats = gather_flow.closeup_look(str(f), q['message'], rec, item)
            kept = gather_flow.pick(st['seen'], q, got)
            name = q.get('object') or q.get('part')
            st['steps'].append({'what': f'close-up: {name}', 'answer': [g['name'] + (f" ({g['value']})" if g['value'] else '') for g in kept],
                                **{k: stats.get(k) for k in ('model', 'seconds', 'cost_usd')}})
            # Haiku still cannot tell from the close-up: Opus looks at that close-up, once per question
            if gather_flow.still_open(kept) and q['key'] not in st.setdefault('opus_keys', []):
                st['opus_keys'].append(q['key'])
                got2, stats2 = gather_flow.closeup_look(str(f), q['message'], rec, item, model=gather_flow.SECOND, effort='medium')
                kept2 = gather_flow.pick(st['seen'], q, got2)
                st['steps'].append({'what': f'close-up again: {name}', 'answer': [g['name'] + (f" ({g['value']})" if g['value'] else '') for g in kept2],
                                    **{k: stats2.get(k) for k in ('model', 'seconds', 'cost_usd')}})
                if kept2:
                    got = got2
            st['seen'] = gather_flow.apply_closeup(st['seen'], q, got)
            st['closeups'].append({'key': q['key'], 'photo': f.name})
    sf.write_text(json.dumps(st, indent=1))
    res = gather.check(st['lesson'], photos, research=False, seen=st['seen'])
    objects, parts = gather_flow.flags(res, {r['type'] for r in res['parts']}, done=('closeup', 'opus'))
    qs = gather_flow.asks(res, objects, parts, st['dismissed'])
    return {'parts': res['parts'], 'not_needed': res['not_needed'], 'asks': qs, 'steps': st['steps'],
            'first_parts': st['first_parts'], 'report': gather.text(res),
            'total_cost_usd': round(sum(x.get('cost_usd') or 0 for x in st['steps']), 6)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"{time.strftime('%H:%M:%S')} {fmt % args}\n")

    def send(self, code, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def allowed(self, q):
        return TOKEN is None or q.get('key', [''])[0] == TOKEN

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ('/', '/game', '/game.html'):  # the learner's flow, as a game: choose, gather, scan, check
            return self.send(200, (HERE / 'game.html').read_bytes(), 'text/html; charset=utf-8')
        if u.path in ('/lab', '/index.html'):  # the lab: the flow with every step shown, and models compared
            return self.send(200, (HERE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if not self.allowed(q):
            return self.send(403, {'error': 'wrong or missing key in the link'})
        if u.path == '/api/lessons':
            return self.send(200, lessons() + (lego_lessons() if q.get('all') else []))
        if u.path == '/api/lesson':  # a lesson's steps for the build screen and the tutor
            from tutor import live
            out = live.steps(q.get('id', [''])[0])
            for st in out['steps']:
                st['picture'] = f"/files/{st['picture']}" if st['picture'] else None
            return self.send(200, out)
        if u.path.startswith('/files/'):  # booklet step pictures only
            rel = u.path[len('/files/'):]
            f = (ROOT / rel).resolve()
            if not (rel.startswith('data/lessons/booklet/') and f.is_file() and f.suffix in ('.png', '.jpg')
                    and str(f).startswith(str((ROOT / 'data/lessons/booklet').resolve()))):
                return self.send(404, {'error': 'not found'})
            return self.send(200, f.read_bytes(), 'image/png' if f.suffix == '.png' else 'image/jpeg')
        if u.path == '/api/models':
            have = env_keys()
            return self.send(200, [{'id': m, 'label': lab, 'price': p, 'ready': k in have, 'key': k}
                                   for m, lab, p, k in MODELS])
        if u.path == '/api/history':
            rows = []
            for d in sorted(RUNS.glob('*/'), reverse=True)[:30]:
                for f in sorted(d.glob('*-*.json')):
                    if f.name.startswith('flow'):
                        continue
                    try:
                        r = json.loads(f.read_text())
                    except ValueError:
                        continue
                    rows.append({'upload': d.name, 'model': r['model'], 'lesson': r['lesson'], 'photos': r['photos'],
                                 'median_s': r['median_s'], 'cost_usd': r['cost_usd'],
                                 'statuses': {p['part']: p['status'] for p in r['parts']}})
            return self.send(200, rows)
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        u = urlparse(self.path)
        if not self.allowed(parse_qs(u.query)):
            return self.send(403, {'error': 'wrong or missing key in the link'})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if u.path == '/api/upload':
                up = time.strftime('%Y%m%d-%H%M%S') + '-' + secrets.token_hex(2)
                (RUNS / up).mkdir(parents=True, exist_ok=True)
                for i, p in enumerate(body['photos'], 1):
                    data = base64.b64decode(p['data'].split(',', 1)[-1])
                    (RUNS / up / f'photo_{i}.jpg').write_bytes(data)
                (RUNS / up / 'upload.json').write_text(json.dumps({'names': [p.get('name') for p in body['photos']],
                                                                   'lesson': body.get('lesson')}))
                return self.send(200, {'upload': up})
            if u.path == '/api/tutor/session':  # a Gemini Live session for the voice tutor (single-use token)
                from tutor import live
                return self.send(200, live.session(body['lesson'], body.get('resume'), bool(body.get('speakers')),
                                                   body.get('name') or None))
            if u.path == '/api/tutor/reply':  # the free-voices mode: Haiku writes the tutor's next words
                from tutor import live
                return self.send(200, live.reply(body['lesson'], body.get('history') or [], body.get('text') or '',
                                                 body.get('name') or None))
            if u.path.startswith('/api/flow/'):
                action = u.path.rsplit('/', 1)[1]
                if action not in ('first', 'closeup', 'dismiss', 'state') or \
                        not re.fullmatch(r'[\w-]+', body['upload']):
                    return self.send(400, {'error': 'unknown action or upload'})
                return self.send(200, flow(action, body['upload'], body))
            if u.path == '/api/check':
                ids = {m[0] for m in MODELS}
                if body['model'] not in ids or not re.fullmatch(r'[\w-]+', body['upload']):
                    return self.send(400, {'error': 'unknown model or upload'})
                out = run_check(body['upload'], body['lesson'], body['model'], bool(body.get('research')),
                                max(1, min(5, int(body.get('repeat', 1)))))
                return self.send(200, out)
        except Exception as e:
            traceback.print_exc()
            return self.send(500, {'error': f'{type(e).__name__}: {e}'[:600]})
        self.send(404, {'error': 'not found'})


def main():
    global TOKEN
    lan = '--lan' in sys.argv
    https = '--https' in sys.argv
    port = 8765
    RUNS.mkdir(parents=True, exist_ok=True)
    host = '0.0.0.0' if lan else '127.0.0.1'
    srv = ThreadingHTTPServer((host, port), Handler)
    ip = '127.0.0.1'
    if lan:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
    scheme = 'https' if https else 'http'
    if https:
        import ssl
        import subprocess
        cert, keyf = RUNS / 'cert.pem', RUNS / 'cert-key.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '30', '-subj',
                        '/CN=parts-lab', '-addext', f'subjectAltName=IP:{ip},IP:127.0.0.1',
                        '-keyout', str(keyf), '-out', str(cert)], check=True, capture_output=True)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, keyf)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    print(f'Parts lab: {scheme}://127.0.0.1:{port}', flush=True)
    if lan:
        TOKEN = secrets.token_urlsafe(8)
        print(f'On your phone (same Wi-Fi): {scheme}://{ip}:{port}/?key={TOKEN}')
        print(f'This Mac: {scheme}://127.0.0.1:{port}/?key={TOKEN}', flush=True)
        if not https:
            print('Without --https a phone can only take photos through its camera app, not the live preview.')
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == '__main__':
    main()
