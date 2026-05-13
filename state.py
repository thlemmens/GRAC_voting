# state.py — in-memory data store for the voting session

import json
import os
import uuid
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

GROUP_COLORS = ['#4F86C6', '#E07B54', '#57A773', '#9B5DE5', '#F4C430',
                '#FF6B6B', '#48DBFB', '#FF9FF3', '#1DD1A1', '#54A0FF']

# ── Shared mutable state ───────────────────────────────────────────────────────
state = {
    'phase': 'setup',       # setup | voting | closed | allocated | ideas
    'groups': [],           # [{ id, title, description, color }]
    'participants': {},     # { pid: { id, name, voted, allocatedGroup, ideas } }
    'votes': {},            # { pid: { first, second, third } }
    'allocations': {},      # { groupId: [pid, ...] }
}


# ── Read helpers ───────────────────────────────────────────────────────────────

def get_public_state():
    participants = list(state['participants'].values())
    return {
        'phase': state['phase'],
        'groups': state['groups'],
        'participantCount': len(participants),
        'votedCount': sum(1 for p in participants if p['voted']),
    }


def get_admin_state():
    return {
        'phase': state['phase'],
        'groups': state['groups'],
        'participants': [
            {
                'id': p['id'],
                'name': p['name'],
                'voted': p['voted'],
                'allocatedGroup': p['allocatedGroup'],
            }
            for p in state['participants'].values()
        ],
        'allocations': state['allocations'],
        'ideas': _get_all_ideas(),
    }


def get_participant_state(participant_id):
    p = state['participants'].get(participant_id)
    if not p:
        return None
    group = next((g for g in state['groups'] if g['id'] == p['allocatedGroup']), None) if p['allocatedGroup'] else None
    return {
        'phase': state['phase'],
        'participant': {
            'id': p['id'],
            'name': p['name'],
            'voted': p['voted'],
            'allocatedGroup': p['allocatedGroup'],
        },
        'allocatedGroupInfo': group,
        'ideas': p['ideas'],
        'groups': state['groups'],
    }


def _get_all_ideas():
    by_group = {g['id']: [] for g in state['groups']}
    for p in state['participants'].values():
        gid = p['allocatedGroup']
        if gid and gid in by_group:
            for idea in p['ideas']:
                by_group[gid].append({
                    'participantName': p['name'],
                    'text': idea['text'],
                    'submittedAt': idea['submittedAt'],
                })
    return by_group


# ── Mutations ──────────────────────────────────────────────────────────────────

def set_groups(groups_data):
    state['groups'] = [
        {
            'id': g.get('id') or str(uuid.uuid4()),
            'title': g['title'],
            'description': g.get('description', ''),
            'color': GROUP_COLORS[i % len(GROUP_COLORS)],
        }
        for i, g in enumerate(groups_data)
    ]
    state['allocations'] = {g['id']: [] for g in state['groups']}
    _save_snapshot()


def register_participant(name):
    pid = str(uuid.uuid4())
    state['participants'][pid] = {
        'id': pid,
        'name': name,
        'voted': False,
        'allocatedGroup': None,
        'ideas': [],
    }
    _save_snapshot()
    return state['participants'][pid]


def record_vote(participant_id, first, second, third):
    p = state['participants'].get(participant_id)
    if not p:
        raise ValueError('Participant not found')
    if p['voted']:
        raise ValueError('Already voted')
    if state['phase'] != 'voting':
        raise ValueError('Voting is not open')
    state['votes'][participant_id] = {'first': first, 'second': second, 'third': third}
    p['voted'] = True
    _save_snapshot()


def add_idea(participant_id, text):
    p = state['participants'].get(participant_id)
    if not p:
        raise ValueError('Participant not found')
    if not p['allocatedGroup']:
        raise ValueError('Not yet allocated to a group')
    if state['phase'] != 'ideas':
        raise ValueError('Ideas phase has not started')
    idea = {'text': text.strip(), 'submittedAt': datetime.now(timezone.utc).isoformat()}
    p['ideas'].append(idea)
    _save_snapshot()
    return idea


def set_phase(phase):
    state['phase'] = phase
    _save_snapshot()


def reset_state():
    state['phase'] = 'setup'
    state['groups'] = []
    state['participants'] = {}
    state['votes'] = {}
    state['allocations'] = {}
    _save_snapshot()


# ── Persistence ────────────────────────────────────────────────────────────────

def _save_snapshot():
    try:
        snapshot = {
            'savedAt': datetime.now(timezone.utc).isoformat(),
            'phase': state['phase'],
            'groups': state['groups'],
            'participants': state['participants'],
            'votes': state['votes'],
            'allocations': state['allocations'],
        }
        path = os.path.join(DATA_DIR, 'session.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2)
    except Exception as e:
        print(f'Failed to save snapshot: {e}')
