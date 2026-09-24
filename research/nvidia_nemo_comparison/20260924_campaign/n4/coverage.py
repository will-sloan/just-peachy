"""Strict 16-composition status accounting, independent of scoring. README.md."""
from collections import Counter

STATUSES={'COMPLETE','FAILED','INCOMPATIBLE','NOT_TESTED'}


def coverage(profiles, jobs, results):
    expected={(p,j) for p in profiles for j in jobs}
    observed={}
    for result in results:
        key=result['profile'],result['job_id']
        if key not in expected or key in observed:
            raise ValueError('Unknown or duplicate result row: '+str(key))
        status=result['status']
        if status not in STATUSES:
            raise ValueError('Unrecognized status')
        if status=='COMPLETE' and not result.get('evidence_binding'):
            raise ValueError('Completion requires an execution evidence binding')
        if status in ('FAILED','INCOMPATIBLE') and not result.get('reason'):
            raise ValueError('Failure/incompatibility requires a reason')
        observed[key]=result
    by_profile=[]
    for profile in profiles:
        count=Counter(observed.get((profile,j),{}).get('status','NOT_TESTED') for j in jobs)
        by_profile.append(dict(profile=profile,required=len(jobs),
            **{s.lower():count[s] for s in sorted(STATUSES)}))
    total={s.lower():sum(r[s.lower()] for r in by_profile) for s in STATUSES}
    return dict(required=len(expected),**total,by_profile=by_profile,
        fully_complete=total['complete']==len(expected),
        unreported_are='NOT_TESTED; never excluded from denominator')
