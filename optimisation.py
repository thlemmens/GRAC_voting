from math import ceil, floor
import time


class Optimisation:
    def __init__(self, preferences, groups, group_scores, timeout_seconds=10):
        self.preferences = preferences
        self.groups = groups
        self.group_scores = group_scores

        self.n_groups = len(groups)
        self.n_participants = len(preferences)+sum(len(g) for g in groups.values())

        self.timeout_seconds = timeout_seconds
        self.deadline = None
        self.timed_out = False

        initial_search = self.greedy(preferences, groups, group_scores)
        self.best_solution = initial_search[0]
        self.upper_bound = initial_search[1]
        self.lower_bound = self.bound(preferences, groups, group_scores)
        
    def bound(self, preferences, groups, group_scores):
        """
        preferences: dict of person -> list of group preferences, for people not assigned yet
        groups: dict of group -> list of assigned people
        """

        target_group_members = floor(self.n_participants / len(groups))
        lower_bound_scores = group_scores.copy()
        for group in groups:
            score = group_scores[group]
            spots_left = target_group_members - len(groups[group])

            if spots_left > 0:
                for pref_level in range(self.n_groups):
                    if spots_left <= 0:
                        break
                    for person in preferences:
                        if spots_left <= 0:
                            break
                        if preferences[person][pref_level] == group:
                            score += pref_level + 1
                            spots_left -= 1

            lower_bound_scores[group] = score
        
        return sum(lower_bound_scores.values())
    
    def score(self, groups, preferences):
        participant_group = {}
        for group, members in groups.items():
            for member in members:
                participant_group[member] = group
        
        scores = {pers: preferences[pers].index(participant_group[pers]) + 1 if participant_group[pers] in preferences[pers] else self.n_groups + 1 for pers in participant_group}
        return sum(scores.values())
    
    def greedy(self, preferences, groups, group_scores):
        """Greedy allocation: assign each participant to their highest-ranked non-full group."""
        max_capacity = ceil(self.n_participants / self.n_groups)
        greedy_groups = {g: members[:] for g, members in groups.items()}
        greedy_scores = group_scores.copy()

        for participant, prefs in preferences.items():
            assigned = False
            for group in prefs:
                if len(greedy_groups[group]) < max_capacity:
                    greedy_groups[group].append(participant)
                    pref_level = prefs.index(group)
                    greedy_scores[group] += pref_level + 1
                    assigned = True
                    break
            if not assigned:
                # All preferred groups full — assign to any non-full group with penalty
                for group in greedy_groups:
                    if len(greedy_groups[group]) < max_capacity:
                        greedy_groups[group].append(participant)
                        greedy_scores[group] += self.n_groups + 1
                        break

        score = sum(greedy_scores.values())
        return greedy_groups, score

    def branch_and_bound(self, preferences, groups, group_scores):
        # Start the timer on the first call
        if self.deadline is None:
            self.deadline = time.time() + self.timeout_seconds
            self.timed_out = False

        if self.timed_out or time.time() > self.deadline:
            self.timed_out = True
            return

        if not preferences:
            # All participants assigned
            score = sum(group_scores.values())
            if score < self.upper_bound:
                print(f"New best solution with score {score}")
                self.upper_bound = score
                self.best_solution = {g: members[:] for g, members in groups.items()}
            return

        # Pick a participant
        max_capacity = ceil(self.n_participants / self.n_groups)
        participant = next(iter(preferences))

        # Branch: try assigning this participant to each non-full group
        for group in groups:
            if len(groups[group]) >= max_capacity:
                continue  # group is full

            # Build new state
            new_preferences = {p: prefs[:] for p, prefs in preferences.items() if p != participant}
            new_groups = {g: members[:] for g, members in groups.items()}
            new_group_scores = group_scores.copy()

            new_groups[group].append(participant)
            if group in preferences[participant]:
                pref_level = preferences[participant].index(group)
                new_group_scores[group] += pref_level + 1
            else:
                new_group_scores[group] += self.n_groups + 1  # penalty for unranked group

            # Prune if lower bound lower than best known
            lower_bound = self.bound(new_preferences, new_groups, new_group_scores)
            if lower_bound < self.upper_bound:
                self.branch_and_bound(new_preferences, new_groups, new_group_scores)

if __name__ == "__main__":
    import random

    N_PARTICIPANTS = 50
    N_GROUPS = 3

    group_names = [f'Group {j+1}' for j in range(N_GROUPS)]
    group_weights = {f'Group {j+1}': w for j, w in enumerate([5, 3, 2])}

    preferences = {}
    for i in range(N_PARTICIPANTS):
        # Build a full ranking by weighted sampling without replacement
        remaining = list(group_names)
        prefs = []
        for _ in range(N_GROUPS):
            weights = [group_weights[g] for g in remaining]
            chosen = random.choices(remaining, weights=weights, k=1)[0]
            prefs.append(chosen)
            remaining.remove(chosen)
        preferences[f'Participant {i+1}'] = prefs

    groups = {g: [] for g in group_names}
    group_scores = {g: 0 for g in group_names}

    print(f"=== {N_PARTICIPANTS} participants, {N_GROUPS} groups ===")
    for name, prefs in preferences.items():
        print(f"  {name}: {prefs}")
    print()

    optimisation = Optimisation(preferences, groups, group_scores)
    print("Lower bound:", optimisation.lower_bound)

    greedy_groups, greedy_score = optimisation.greedy(preferences, groups, group_scores)
    print(f"Greedy score: {greedy_score}")
    

    optimisation.branch_and_bound(preferences, groups, group_scores)

    if optimisation.timed_out:
        print(f"Search timed out after {optimisation.timeout_seconds}s (best solution found so far)")
    else:
        print("Search completed (optimal solution found)")

    print("Score:",optimisation.score(optimisation.best_solution, preferences))
    
    print("Best allocation found:")
    for g, members in greedy_groups.items():
        print(f"  {len(members)} {g}: {members}")
   