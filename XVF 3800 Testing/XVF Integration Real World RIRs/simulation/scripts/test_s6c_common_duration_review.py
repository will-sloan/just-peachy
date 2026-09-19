"""Independent completed-duration arithmetic. README_S6C_COMMON_DURATION_REVIEW.md."""
import argparse,csv,io,json,hashlib,math
from collections import Counter
from pathlib import Path
import numpy as np
import s6c_analysis_v3 as core

def exact(binding):
    raw=Path(binding['path']).read_bytes()
    if len(raw)!=binding['bytes'] or hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('Changed source buffer')
    return raw
def document(binding):return json.loads(exact(binding))
def table(binding):return list(csv.DictReader(io.StringIO(exact(binding).decode('utf-8-sig'))))
def number(row,key):
    v=row.get(key)
    if v in ('',None):return None
    x=float(v)
    if not math.isfinite(x):raise ValueError('Nonfinite metric')
    return x
def key(row):return row['case_id'],int(row['segment_index']),row['source_id'],row['metadata_identity']

def run(output):
    receipt=core.bind(core.REPORT/'common_duration_results_v1/DURATION_RESULTS_RECEIPT.json',
        'ff3407aaf7d9f02e43aff858f2820792c9ff86b7a95b605b79723420039d6aa4')
    result=document(receipt);checks=0
    def yes(condition):
        nonlocal checks
        if not condition:raise AssertionError('Independent duration check '+str(checks+1))
        checks+=1
    for b in result['sources']:exact(b);checks+=1
    nr=document(result['names']);cr=document(result['core'])
    yes(nr['scored']==nr['requested']==cr['scored']==cr['requested']==672)
    yes(nr['index']==cr['index']==result['index'])
    tb=next(b for b in result['source_tables'] if Path(b['path']).name=='TURNS.csv')
    rb=next(b for b in result['source_tables'] if Path(b['path']).name=='RETAINED_ROWS.csv')
    turns=table(tb);retained=table(rb)
    tables={Path(b['path']).name:table(b) for b in result['artifacts']}
    groups={}
    for row in turns:groups.setdefault((row['profile_id'],row['stream']),[]).append(row)
    yes(len(groups)==12 and len(turns)==2136)
    for rows in groups.values():yes(len(rows)==178 and len({key(r) for r in rows})==178)
    samples=('sole_active_samples','correct_name_samples','wrong_known_name_samples','unknown_name_samples')
    waits=('first_any_name_wait_sec','first_correct_name_wait_sec','first_confirmed_correct_name_wait_sec','first_stable_correct_name_wait_sec')
    for row in turns:
        yes(row['stream']==row['identity_tap'])
        values=[number(row,k) for k in samples]
        yes(values[0] is None or values[0]==sum(values[1:]))
    def subset(row,profile):
        return [r for r in groups[profile,row['stream']] if row['roster_status']=='ALL' or r['roster_status']==row['roster_status']]
    def stats(values):
        present=[x for x in values if x is not None]
        return dict(count=len(values),observed=len(present),missing=len(values)-len(present),
            maximum=max(present) if present else None,**{'p'+str(p):float(np.percentile(present,p)) if present else None for p in (50,90,95)})
    def same_stats(actual,expected):
        yes(set(actual)==set(expected))
        for k,v in expected.items():yes(actual[k] is None if v is None else abs(actual[k]-v)<1e-9)
    for out in tables['TIER_PROFILE_RESULTS.csv']:
        rows=subset(out,out['profile_id'])
        yes(int(out['source_occurrences'])==len(rows));yes(int(out['reference_people'])==len({r['metadata_identity'] for r in rows}))
        for metric in samples:yes(number(out,metric)==sum(number(r,metric) or 0 for r in rows))
        for metric in waits:
            values=[number(r,metric) for r in rows]
            same_stats(json.loads(out[metric+'_summary']),stats(values))
            yes(json.loads(out[metric+'_statuses'])==dict(Counter(r[metric.replace('_wait_sec','_status')] for r in rows)))
            yes(int(out[metric+'_observed'])==sum(v is not None for v in values))
            yes(int(out[metric+'_missing'])==sum(v is None for v in values))
    for out in tables['POOLED_TIER_DELTA.csv']:
        a={key(r):r for r in subset(out,out['left_profile'])};b={key(r):r for r in subset(out,out['right_profile'])}
        yes(a.keys()==b.keys());yes(int(out['paired_occurrences'])==len(a))
        for k in a:yes(a[k]['roster_status']==b[k]['roster_status'] and number(a[k],'sole_active_samples')==number(b[k],'sole_active_samples'))
        for metric in samples:
            left=sum(number(r,metric) or 0 for r in a.values());right=sum(number(r,metric) or 0 for r in b.values())
            yes(number(out,'left_'+metric)==left and number(out,'right_'+metric)==right and number(out,'right_minus_left_'+metric)==right-left)
    for out in tables['PAIRED_NAME_DELAY_RESULTS.csv']:
        a={key(r):r for r in subset(out,out['left_profile'])};b={key(r):r for r in subset(out,out['right_profile'])};metric=out['metric']
        counts=Counter();deltas=[]
        for k in a:
            left=number(a[k],metric);right=number(b[k],metric)
            name='both_observed' if left is not None and right is not None else 'left_only_observed' if left is not None else 'right_only_observed' if right is not None else 'neither_observed'
            counts[name]+=1
            if name=='both_observed':deltas.append(right-left)
        for name in ('both_observed','left_only_observed','right_only_observed','neither_observed'):yes(int(out[name])==counts[name])
        same_stats(json.loads(out['conditional_right_minus_left_wait_sec']),stats(deltas))
    for out in tables['RETAINED_ROW_EXPOSURE.csv']:
        rows=[r for r in retained if r['profile_id']==out['profile_id'] and r['stream']==out['stream']]
        yes(int(out['retained_rows'])==len(rows));yes(int(out['exposure_available_rows'])==sum(r['exposure_available']=='True' for r in rows))
        yes(int(out['exposure_missing_rows'])==sum(r['exposure_available']!='True' for r in rows))
        for metric in ('retained_row_sec','correct_name_row_sec','wrong_known_name_row_sec','unknown_name_row_sec','unidentifiable_reference_row_sec','empty_reference_assigned_name_row_sec'):
            yes(abs(number(out,metric)-sum(number(r,metric) or 0 for r in rows))<1e-9)
    # All six actual completed roster rows have the stated fixed competitors.
    gm=core.bind(core.REPORT/'enrollment/common30_v1/SCORER_GALLERY_MAP_EXTENSION.json')
    gallery=document(gm)
    for row in gallery['rows']:
        yes(row['loaded_count']==len(row['profiles'])==14)
        yes(Counter('CMU' if p['metadata_identity'].startswith('CMU') else 'HIFI' if p['metadata_identity'].startswith('HIFITTS') else 'OTHER' for p in row['profiles'])=={'CMU':9,'HIFI':5})
    out=dict(status='PASS_ACTUAL_COMPLETED_ARITHMETIC',schema='s6c_duration_independent_review.v1',checks=checks,source=receipt,
        reviewer=core.bind(__file__),readme=core.bind(Path(__file__).with_name('README_S6C_COMMON_DURATION_REVIEW.md')),gallery_map=gm,
        source_tables=result['source_tables'],artifacts=result['artifacts'],source_occurrences=2136,scored_outputs=672,
        scope='Exact source-buffer hashes; independently recomputed pooled support, name partition, tier deltas, censor/observed partitions, wait percentiles and separate retained-row exposure. No score/model rerun.',
        limit='Original collector table() read and later path hash were separate reads. Actual completed table buffers now match their exact authority. Future collector should hash the same bytes it parses; no cause or actual mutation is asserted.',
        naming_interpretation='Fixed14-person competitors per side; all source identities retained. Duration also changes E content/native centroid. Conditional waits never replace missing/censored values with zero; retained row-seconds are not live source samples.')
    if Path(output).exists():raise ValueError('Preserve earlier review; choose fresh output')
    core.save(output,out);return core.bind(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
