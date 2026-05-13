# allocate.py — Optimal group allocation using branch-and-bound

from optimisation import Optimisation


def allocate(participants, votes, groups):
    """
    Allocates participants to groups using branch-and-bound optimisation
    with a greedy initial solution.

    Args:
        participants: list of dicts with at least {'id': str}
        votes:        dict { participant_id: {'first': gid, 'second': gid, 'third': gid} }
        groups:       list of dicts with at least {'id': str}

    Returns:
        dict { group_id: [participant_id, ...] }
    """
    if not groups:
        return {}

    group_ids = [g['id'] for g in groups]

    # Convert votes to ranked preference lists for the optimiser
    preferences = {}
    for p in participants:
        pid = p['id']
        v = votes.get(pid)
        if v:
            prefs = [v.get('first'), v.get('second'), v.get('third')]
            prefs = [gid for gid in prefs if gid in group_ids]
            # Append any unranked groups at the end
            for gid in group_ids:
                if gid not in prefs:
                    prefs.append(gid)
            preferences[pid] = prefs
        else:
            preferences[pid] = list(group_ids)

    init_groups = {gid: [] for gid in group_ids}
    init_scores = {gid: 0 for gid in group_ids}

    opt = Optimisation(preferences, init_groups, init_scores, timeout_seconds=10)
    opt.branch_and_bound(preferences, init_groups, init_scores)

    return opt.best_solution
