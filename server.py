# server.py — Flask + Flask-SocketIO server

import csv
import io
import os
import socket
from datetime import datetime, timezone

import base64
import subprocess
import qrcode
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_socketio import SocketIO, emit, join_room

import state as store
from allocate import allocate

# ── App setup ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, 'public'), static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# Render sets RENDER=true in the environment
IS_RENDER = os.environ.get('RENDER', '').lower() in ('true', '1')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')  # e.g. https://your-app.onrender.com

socketio = SocketIO(app, cors_allowed_origins='*', async_mode='gevent')

PORT = int(os.environ.get('PORT', 3000))


# ── Utility ────────────────────────────────────────────────────────────────────

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_all_ips():
    """Return list of {ip, name} for all non-loopback IPv4 interfaces."""
    results = []
    try:
        output = subprocess.check_output(
            ['powershell', '-Command',
             'Get-NetIPAddress -AddressFamily IPv4 '
             '| Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.PrefixOrigin -ne "WellKnown" } '
             '| Select-Object IPAddress, InterfaceAlias '
             '| ConvertTo-Json'],
            text=True, timeout=5
        )
        import json as _json
        data = _json.loads(output)
        if isinstance(data, dict):
            data = [data]
        for entry in data:
            ip = entry.get('IPAddress', '')
            name = entry.get('InterfaceAlias', '')
            # Skip link-local addresses (169.254.x.x)
            if ip.startswith('169.254.'):
                continue
            results.append({'ip': ip, 'name': name})
    except Exception:
        # Fallback
        results.append({'ip': get_local_ip(), 'name': 'Default'})
    if not results:
        results.append({'ip': get_local_ip(), 'name': 'Default'})
    return results


def get_public_url():
    """Return the public-facing URL for QR codes."""
    if IS_RENDER and RENDER_URL:
        return RENDER_URL  # e.g. https://your-app.onrender.com
    ip = get_local_ip()
    return f'http://{ip}:{PORT}'


def broadcast():
    socketio.emit('public-state', store.get_public_state())
    socketio.emit('admin-state', store.get_admin_state(), to='admin')


# ── Static files ───────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ── REST: Participant ──────────────────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    if len(name) > 80:
        return jsonify({'error': 'Name too long'}), 400
    if store.state['phase'] == 'setup':
        return jsonify({'error': 'Event has not started yet. Please wait.'}), 400
    participant = store.register_participant(name)
    broadcast()
    return jsonify({'participantId': participant['id']})


@app.route('/api/vote', methods=['POST'])
def vote():
    data = request.get_json(silent=True) or {}
    pid   = data.get('participantId')
    first  = data.get('first')
    second = data.get('second')
    third  = data.get('third')
    if not all([pid, first, second, third]):
        return jsonify({'error': 'participantId, first, second, third are required'}), 400
    group_ids = [g['id'] for g in store.state['groups']]
    choices = [first, second, third]
    if len(set(choices)) != 3:
        return jsonify({'error': 'Each preference must be a different group'}), 400
    for c in choices:
        if c not in group_ids:
            return jsonify({'error': f'Invalid group id: {c}'}), 400
    try:
        store.record_vote(pid, first, second, third)
        broadcast()
        return jsonify({'ok': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/idea', methods=['POST'])
def idea():
    data = request.get_json(silent=True) or {}
    pid  = data.get('participantId')
    text = (data.get('text') or '').strip()
    if not pid or not text:
        return jsonify({'error': 'participantId and text are required'}), 400
    if len(text) > 1000:
        return jsonify({'error': 'Idea text too long (max 1000 chars)'}), 400
    try:
        saved_idea = store.add_idea(pid, text)
        broadcast()
        return jsonify({'ok': True, 'idea': saved_idea})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/participant/<participant_id>')
def get_participant(participant_id):
    ps = store.get_participant_state(participant_id)
    if not ps:
        return jsonify({'error': 'Participant not found'}), 404
    return jsonify(ps)


@app.route('/api/state')
def get_state():
    return jsonify(store.get_public_state())


# ── REST: Admin ────────────────────────────────────────────────────────────────

@app.route('/api/admin/groups', methods=['POST'])
def admin_set_groups():
    data = request.get_json(silent=True) or {}
    groups = data.get('groups')
    if not isinstance(groups, list) or len(groups) != 5:
        return jsonify({'error': 'Exactly 5 groups required'}), 400
    for g in groups:
        title = (g.get('title') or '').strip()
        if not title:
            return jsonify({'error': 'Each group must have a title'}), 400
        if len(title) > 100:
            return jsonify({'error': 'Group title too long (max 100 chars)'}), 400
    cleaned = [
        {'id': g.get('id'), 'title': g['title'].strip(), 'description': (g.get('description') or '').strip()}
        for g in groups
    ]
    store.set_groups(cleaned)
    broadcast()
    return jsonify({'ok': True, 'groups': store.state['groups']})


@app.route('/api/admin/open', methods=['POST'])
def admin_open():
    if len(store.state['groups']) != 5:
        return jsonify({'error': 'Configure 5 groups first'}), 400
    store.set_phase('voting')
    broadcast()
    return jsonify({'ok': True})


@app.route('/api/admin/close', methods=['POST'])
def admin_close():
    store.set_phase('closed')
    broadcast()
    return jsonify({'ok': True})


@app.route('/api/admin/allocate', methods=['POST'])
def admin_allocate():
    if store.state['phase'] != 'closed':
        return jsonify({'error': 'Close voting first'}), 400
    participants = list(store.state['participants'].values())
    if not participants:
        return jsonify({'error': 'No participants registered'}), 400

    result = allocate(participants, store.state['votes'], store.state['groups'])
    store.state['allocations'] = result
    for group_id, pids in result.items():
        for pid in pids:
            if pid in store.state['participants']:
                store.state['participants'][pid]['allocatedGroup'] = group_id

    store.set_phase('allocated')
    broadcast()
    socketio.emit('allocated', store.get_public_state())
    return jsonify({'ok': True, 'allocations': result})


@app.route('/api/admin/ideas', methods=['POST'])
def admin_open_ideas():
    if store.state['phase'] != 'allocated':
        return jsonify({'error': 'Run allocation first'}), 400
    store.set_phase('ideas')
    broadcast()
    return jsonify({'ok': True})


@app.route('/api/admin/reset', methods=['POST'])
def admin_reset():
    store.reset_state()
    broadcast()
    return jsonify({'ok': True})


@app.route('/api/admin/state')
def admin_state():
    return jsonify(store.get_admin_state())


@app.route('/api/admin/qr')
def admin_qr():
    if IS_RENDER:
        # On Render, always use the public URL
        url = get_public_url()
        interfaces = [{'ip': url, 'name': 'Render (public)'}]
    else:
        # Local: allow admin to pick which IP to encode
        ip = request.args.get('ip') or get_local_ip()
        url = f'http://{ip}:{PORT}'
        interfaces = get_all_ips()
    img = qrcode.make(url).convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('ascii')
    data_url = f'data:image/png;base64,{b64}'
    return jsonify({'url': url, 'dataUrl': data_url, 'interfaces': interfaces})


@app.route('/api/admin/export')
def admin_export():
    def title_of(gid):
        if not gid:
            return ''
        g = next((x for x in store.state['groups'] if x['id'] == gid), None)
        return g['title'] if g else ''

    rows = []
    for p in store.state['participants'].values():
        v = store.state['votes'].get(p['id'], {})
        rows.append({
            'name': p['name'],
            'allocated_group': title_of(p['allocatedGroup']),
            'choice_1': title_of(v.get('first')),
            'choice_2': title_of(v.get('second')),
            'choice_3': title_of(v.get('third')),
            'ideas_submitted': len(p['ideas']),
        })

    output = io.StringIO()
    fields = ['name', 'allocated_group', 'choice_1', 'choice_2', 'choice_3', 'ideas_submitted']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    csv_content = output.getvalue()

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    filename = f'session-{timestamp}.csv'
    filepath = os.path.join(store.DATA_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(csv_content)

    return send_file(
        io.BytesIO(csv_content.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


# ── Socket.io ──────────────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    emit('public-state', store.get_public_state())


@socketio.on('join-admin')
def on_join_admin():
    join_room('admin')
    emit('admin-state', store.get_admin_state())


@socketio.on('join-participant')
def on_join_participant(data):
    pid = (data or {}).get('participantId')
    if pid:
        join_room(f'participant:{pid}')
        ps = store.get_participant_state(pid)
        if ps:
            emit('participant-state', ps)


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if IS_RENDER:
        print(f'\n✅ Server running on Render')
        print(f'   Public URL: {RENDER_URL}')
        print(f'   Admin:      {RENDER_URL}/admin.html\n')
    else:
        ip = get_local_ip()
        print(f'\n✅ Server running')
        print(f'   Local:    http://localhost:{PORT}')
        print(f'   Network:  http://{ip}:{PORT}')
        print(f'   Admin:    http://localhost:{PORT}/admin.html')
        print(f'\n   Participants scan: http://{ip}:{PORT}\n')
    socketio.run(app, host='0.0.0.0', port=PORT, debug=False)
