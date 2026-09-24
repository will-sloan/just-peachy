"""Count-weighted paired uncertainty without pretending taps are independent. README.md."""
from collections import defaultdict
import math
import random


def pooled(rows, prefix):
    errors = sum(r[prefix+'_errors'] for r in rows)
    words = sum(r[prefix+'_words'] for r in rows)
    return dict(errors=errors, words=words, rate=errors/words if words else None)


def delta(rows):
    a, b = pooled(rows, 'baseline'), pooled(rows, 'candidate')
    return b['rate']-a['rate'] if a['rate'] is not None and b['rate'] is not None else None


def quantile(values, p):
    values = sorted(values)
    n = (len(values)-1)*p
    a, b = math.floor(n), math.ceil(n)
    return values[a]*(b-n)+values[b]*(n-a) if a != b else values[a]


def paired_report(rows, *, cluster='dependency_cluster', replicates=2000, seed=20260924):
    if type(replicates) is not int or replicates < 100:
        raise ValueError('At least 100 bootstrap replicates required')
    keys, groups = set(), defaultdict(list)
    scene_groups = {}
    for row in rows:
        key = row['case_id'], row['tap']
        if key in keys:
            raise ValueError('Duplicate scene/tap inflates paired denominator')
        keys.add(key)
        for prefix in ('baseline', 'candidate'):
            for field in ('errors', 'words'):
                value = row[prefix+'_'+field]
                if type(value) is not int or value < 0:
                    raise ValueError('Metrics require nonnegative integer counts')
        if row['baseline_words'] != row['candidate_words']:
            raise ValueError('Matched references differ')
        if row['case_id'] in scene_groups and scene_groups[row['case_id']] != row[cluster]:
            raise ValueError('Both taps must stay in the same resampling cluster')
        scene_groups[row['case_id']] = row[cluster]
        groups[row[cluster]].append(row)
    result = dict(pairs=len(rows), scenes=len(scene_groups), clusters=len(groups),
        baseline=pooled(rows, 'baseline'), candidate=pooled(rows, 'candidate'),
        candidate_minus_baseline=delta(rows), interval95=None,
        interpretation='Descriptive paired seen-bank sensitivity, not unseen-population validation')
    if len(groups) < 8:
        result['bootstrap_status'] = 'UNAVAILABLE_FEWER_THAN_8_DEPENDENCY_CLUSTERS'
    else:
        rng = random.Random(seed)
        ordered = [groups[k] for k in sorted(groups)]
        estimates = []
        for _ in range(replicates):
            selected = [row for group in rng.choices(ordered, k=len(ordered)) for row in group]
            value = delta(selected)
            if value is not None:
                estimates.append(value)
        result.update(bootstrap_status='DESCRIPTIVE' if estimates else 'UNAVAILABLE_NO_WORDS',
            replicates=replicates, valid_replicates=len(estimates), seed=seed,
            interval95=[quantile(estimates, .025), quantile(estimates, .975)] if estimates else None)
    for dimension in ('room', 'actor_cluster', 'family_id'):
        result['leave_one_'+dimension+'_out'] = [dict(omitted=k,
            remaining_pairs=sum(r[dimension] != k for r in rows),
            delta=delta([r for r in rows if r[dimension] != k])) for k in sorted({r[dimension] for r in rows})]
    return result
