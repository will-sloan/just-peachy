"""Count-weighted, missing-aware modeled-bank reports. README_SCORING_BANK.md."""
from collections import Counter,defaultdict
import json
from metrics import aggregate
from paired import paired_report


def value(score,key):
    v=score.get(key)
    return v.get('value') if key=='mimo' and v else v


def pool(rows):
    scores=[r['score'] for r in rows];result=aggregate(scores)
    missing=[s for s in scores if s['execution_status']=='COMPLETE' and s.get('metric_status')!='SCORED']
    result.update(metric_statuses=dict(Counter(s.get('metric_status','UNKNOWN') for s in scores)),
        unscored_metric_reference_words=sum(s['reference_words'] for s in missing),
        unscored_metric_audio_seconds=sum(s['audio_seconds'] for s in missing))
    result['word_metrics']={}
    for key in ('primary_wer','raw_wer','cpwer','mimo'):
        measured=[value(s,key) for s in scores if value(s,key) is not None]
        totals={k:sum(v[k] for v in measured) for k in ('errors','words','substitutions','deletions','insertions')}
        totals.update(scored_cells=len(measured),rate=totals['errors']/totals['words'] if totals['words'] else None)
        result['word_metrics'][key]=totals
    empty=[s for s in scores if s['reference_class']=='empty_control'];empty_scored=[s for s in empty if 'inserted_words' in s]
    seconds=sum(s['audio_seconds'] for s in empty_scored);insertions=sum(s['inserted_words'] for s in empty_scored)
    result['empty_controls']=dict(required=len(empty),scored=len(empty_scored),insertions=insertions,
        scored_seconds=seconds,insertions_per_minute=insertions/(seconds/60) if seconds else None)
    activity=[s['activity'] for s in scores if s.get('activity') and 'DER_components' in s['activity']]
    der={};jer={}
    for a in activity:
        for k,v in a['DER_components'].items():der[k]=der.get(k,0)+v
        for k,v in a['JER_components'].items():jer[k]=jer.get(k,0)+v
    result['estimated_activity']=dict(scored_cells=len(activity),DER_components=der,JER_components=jer,
        DER=sum(der.get(k,0) for k in ('missed detection','false alarm','confusion'))/der['total'] if der.get('total') else None,
        JER=jer.get('speaker error',0)/jer['speaker count'] if jer.get('speaker count') else None,
        status='ESTIMATED_ACTIVITY_ONLY_NO_PHONETIC_GOLD')
    result['naming_widget_resources']='UNAVAILABLE_MODELED_METHOD_BANK_ONLY'
    return result


def report(rows,strata,*,scope):
    keys=[(r['composition'],r['mode'],r['job_id']) for r in rows]
    if len(keys)!=len(set(keys)):raise ValueError('Duplicate composition/mode/job denominator')
    groups=defaultdict(list)
    for row in rows:
        meta=strata[row['case_id']]
        if meta['case_id']!=row['case_id']:raise ValueError('Scene metadata join differs')
        groups[(row['composition'],row['mode'],row['tap'])].append(row)
    cohorts=[]
    dimensions=('reference_class','room','family_id','actor_cluster','achieved_snr_db','orientation','has_short_turn')
    for (composition,mode,tap),members in sorted(groups.items()):
        stratified={}
        for dimension in dimensions:
            bins=defaultdict(list)
            for row in members:
                datum=row['score']['reference_class'] if dimension=='reference_class' else strata[row['case_id']].get(dimension,'UNAVAILABLE')
                bins[json.dumps(datum,sort_keys=True)].append(row)
            stratified[dimension]=[dict(value=json.loads(k),counts=pool(v)) for k,v in sorted(bins.items())]
        cohorts.append(dict(composition=composition,mode=mode,tap=tap,counts=pool(members),strata=stratified))
    index={(r['composition'],r['mode'],r['job_id']):r for r in rows};paired=[]
    for mode in sorted({r['mode'] for r in rows}):
        for composition in sorted({r['composition'] for r in rows}-{'A0_D0_E0'}):
            candidates=[r for r in rows if r['composition']==composition and r['mode']==mode]
            if not candidates:continue
            for metric in ('primary_wer','cpwer','mimo'):
                matched=[];excluded=Counter();words=0;seconds=0.
                for row in candidates:
                    baseline=index.get(('A0_D0_E0',mode,row['job_id']))
                    a=value(baseline['score'],metric) if baseline else None;b=value(row['score'],metric)
                    if a is None or b is None:
                        excluded['missing_baseline_and_candidate' if a is None and b is None else
                            'missing_baseline' if a is None else 'missing_candidate']+=1
                        words+=row['score']['reference_words'];seconds+=row['score']['audio_seconds'];continue
                    meta=strata[row['case_id']]
                    matched.append(dict(case_id=row['case_id'],tap=row['tap'],baseline_errors=a['errors'],baseline_words=a['words'],
                        candidate_errors=b['errors'],candidate_words=b['words'],
                        **{k:meta[k] for k in ('dependency_cluster','room','actor_cluster','family_id')}))
                paired.append(dict(composition=composition,mode=mode,metric=metric,required_pairs=len(candidates),
                    excluded=dict(excluded),excluded_reference_words=words,excluded_audio_seconds=seconds,
                    result=paired_report(matched)))
    return dict(scope=scope,required_cells=len(rows),cohorts=cohorts,paired=paired,integrated_N4_cells=0,
        interpretation='Seen engineering bank; modeled application methods. Both taps remain in the same dependency cluster. '
            'Partial metrics keep missing denominators; no hardware, widget, recognition or deployment acceptance.')
