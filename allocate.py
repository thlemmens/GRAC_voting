# allocate.py — Preferential voting allocation algorithm

import math


def allocate(participants, votes, groups):
    """
    Allocates participants to groups using a preferential (ranked-choice) approach.

    Args:
        participants: list of dicts with at least {'id': str}
        votes:        dict { participant_id: {'first': gid, 'second': gid, 'third': gid} }
        groups:       list of dicts with at least {'id': str}

    Returns:
        dict { group_id: [participant_id, ...] }
    """
    n = len(participants)
    g = len(groups)
    if g == 0:
        return {}

    base_sz = n // g
    remainder = n % g

    # First `remainder` groups get one extra slot
    capacity = {}
    for i, group in enumerate(groups):
        capacity[group['id']] = base_sz + (1 if i < remainder else 0)

    result = {group['id']: [] for group in groups}

    def least_full():
        return min(
            groups,
            key=lambda g: len(result[g['id']]) / max(capacity[g['id']], 1)
        )['id']

    def try_assign(pid, group_id):
        if group_id and len(result[group_id]) < capacity[group_id]:
            result[group_id].append(pid)
            return True
        return False

    # Count first-choice popularity so most-contested groups are processed first
    first_choice_counts = {g['id']: 0 for g in groups}
    for p in participants:
        v = votes.get(p['id'])
        if v and v.get('first'):
            first_choice_counts[v['first']] = first_choice_counts.get(v['first'], 0) + 1

    # Sort: participants whose 1st choice is most popular go first (greedy fill)
    def sort_key(p):
        v = votes.get(p['id'])
        return -(first_choice_counts.get(v['first'], 0) if v else 0)

    sorted_participants = sorted(participants, key=sort_key)

    unassigned = []
    for p in sorted_participants:
        v = votes.get(p['id'])
        assigned = (
            (v and try_assign(p['id'], v.get('first'))) or
            (v and try_assign(p['id'], v.get('second'))) or
            (v and try_assign(p['id'], v.get('third'))) or
            try_assign(p['id'], least_full())
        )
        if not assigned:
            unassigned.append(p['id'])

    # Safety net — should never happen
    for pid in unassigned:
        result[least_full()].append(pid)

    return result
