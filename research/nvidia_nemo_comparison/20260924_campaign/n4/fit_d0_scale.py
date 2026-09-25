"""One predeclared C-only association scale fit. See README_FIT_D0_SCALE.md."""
from collections import defaultdict
from copy import deepcopy
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
import numpy as np
from common import bind,load,verify,freeze,fingerprint
from review_d0_collection import validate_pair

PROTOCOL_SHA='ad9c6a9a953d9931a2f2e2bb4ce3d7d79b254952ccfcebad404ac4e0bde954e1'


def partition(identity):
    return 'validation' if int(hashlib.sha256(identity.encode('utf-8')).hexdigest()[:8],16)%3==0 else 'fit'


def representatives(vectors):
    result={}
    for role in ('short','mature'):
        selected=sorted((r for r in vectors if r['evidence_kind']==role),
                        key=lambda r:(r['end_sample'],r['start_sample']))
        indices=sorted({0,(len(selected)-1)//2,len(selected)-1}) if selected else []
        result[role]=np.asarray([selected[i]['normalized_embedding'] for i in indices],np.float64).reshape(-1,192)
    return result


def collect_groups(sources):
    groups=defaultdict(list);counts=defaultdict(int)
    for left,right in itertools.combinations(sources,2):
        if left['source_id']==right['source_id'] or left['pcm']==right['pcm']:
            counts['same_source_or_pcm_excluded']+=1;continue
        split=partition(left['identity'])
        if split!=partition(right['identity']):
            counts['cross_partition_excluded']+=1;continue
        ids=tuple(sorted((left['identity'],right['identity'])))
        for label,roles in [('short/short',[('short','short')]),
                            ('short/mature',[('short','mature'),('mature','short')]),
                            ('mature/mature',[('mature','mature')])]:
            scores=[]
            for encoder in (0,1):
                parts=[]
                for a,b in roles:
                    x,y=left['vectors'][encoder][a],right['vectors'][encoder][b]
                    if len(x) and len(y):parts.append((x@y.T).reshape(-1))
                scores.append(np.concatenate(parts) if parts else np.empty(0))
            if len(scores[0])!=len(scores[1]):raise ValueError('Unmatched pair geometry')
            if not len(scores[0]):counts['unavailable_source_role_pairs']+=1;continue
            if any(not np.isfinite(a).all() or np.any(np.abs(a)>1.000002) for a in scores):
                raise ValueError('Invalid cosine pair scores')
            groups[(split,*ids,label)].append(scores)
            counts['included_source_role_pairs']+=1
            counts['included_window_pairs_per_encoder']+=len(scores[0])
    return groups,dict(counts)


def summarize(groups, split, encoder, threshold=None, role=None):
    """Median centers or equal source/role/identity weighted error rates."""
    identity_groups=defaultdict(list)
    for (part,left,right,kind),source_pairs in groups.items():
        if part!=split or role is not None and kind!=role:continue
        same=left==right
        if threshold is None:
            value=float(np.median([np.median(pair[encoder]) for pair in source_pairs]))
        else:
            value=float(np.mean([np.mean(pair[encoder]<threshold if same else pair[encoder]>=threshold)
                                 for pair in source_pairs]))
        identity_groups[(left,right)].append(value)
    reduce=np.median if threshold is None else np.mean
    positives=[float(reduce(rows)) for (a,b),rows in identity_groups.items() if a==b]
    negatives=[float(reduce(rows)) for (a,b),rows in identity_groups.items() if a!=b]
    summary=dict(positive_identity_groups=len(positives),negative_identity_pairs=len(negatives),
                 same=float(reduce(positives)) if positives else None,
                 different=float(reduce(negatives)) if negatives else None)
    if threshold is not None:
        summary.update(threshold=threshold,balanced_mean=(summary['same']+summary['different'])/2
                       if positives and negatives else None,
                       same_meaning='same-speaker pair rejection',different_meaning='different-speaker pair acceptance')
    return summary


def transform_profile(profile, centers0, centers1, protocol):
    fit=protocol['fit']; n0,p0=centers0['different'],centers0['same']; n1,p1=centers1['different'],centers1['same']
    if any(v is None or not np.isfinite(v) for v in (n0,p0,n1,p1)):
        raise ValueError('Missing/nonfinite C fit centers')
    if min(p0-n0,p1-n1)<=fit['require_center_gap_greater_than']:
        raise ValueError('C center gap too small for one affine proposal')
    slope=(p1-n1)/(p0-n0);intercept=n1-slope*n0
    candidate=deepcopy(profile);changes={}
    for field in fit['raw_cosine_threshold_fields']:
        old=candidate['tracker'][field];new=slope*old+intercept
        if not -1<=new<=1:raise ValueError('Mapped cosine outside [-1,1]: '+field)
        candidate['tracker'][field]=new;changes[field]=dict(old=old,new=new,units='raw E1 cosine')
    for field in fit['cosine_difference_fields']:
        old=candidate['tracker'][field];new=slope*old
        candidate['tracker'][field]=new;changes[field]=dict(old=old,new=new,units='E1 cosine difference')
    return candidate,dict(slope=slope,intercept=intercept,changes=changes)


def gate(nominal,candidate):
    if any(row[k] is None for row in (nominal,candidate) for k in ('same','different','balanced_mean')):
        return False
    return candidate['balanced_mean']<=nominal['balanced_mean']+.02 and candidate['different']<=nominal['different']+.01


def main(args):
    import psutil
    process=psutil.Process();process.cpu_affinity([14]);process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if args.output.exists():raise ValueError('Fresh fit directory required; no refitting in place')
    protocol=load(args.protocol)
    if bind(args.protocol)['sha256']!=PROTOCOL_SHA:raise ValueError('Frozen protocol changed')
    review=load(args.review)
    if review['status']!='PASS_MATCHED_C_COLLECTION_ONLY':raise ValueError('Passed matched collection review required')
    for row in review['input_bindings']+review['code']:verify(row)
    run=Path(review['input_bindings'][0]['path']).parent
    stamp=load(run/'SCALE_PROTOCOL_FREEZE.json')
    if stamp['protocol']!=bind(args.protocol) or stamp['new_C_vector_scores_examined'] is not False:
        raise ValueError('Pre-fit protocol freeze missing')
    admission=load(run/'ADMISSION.json');labels_doc=load(run/'C_LABELS_EVALUATOR_ONLY.json')
    verify(labels_doc['split_manifest']);verify(labels_doc['protected_split']);verify(labels_doc['query_manifest'])
    original={r['window_id']:r for r in load(labels_doc['split_manifest']['path'])['windows'] if r['role']=='C'}
    labels={r['window_id']:r for r in labels_doc['rows']}
    if len(labels)!=len(labels_doc['rows']) or set(original)!=set(labels):raise ValueError('Protected C population differs')
    final=load(run/'RESULT.json')
    for binding in final['encoders']:verify(binding)
    profile=load(run/'E0/RESULT.json')['profile']
    if profile!=load(run/'E1/RESULT.json')['profile']:raise ValueError('Encoder profiles differ')
    source_receipt=load(admission['source_receipt']['path'])
    for rel,row in source_receipt['files'].items():
        current=bind(Path(admission['source'])/rel)
        if current['sha256']!=row['sha256'] or current['bytes']!=row['bytes']:
            raise ValueError('Bound source changed')
    sources=[]
    for reviewed in review['cells']:
        cells=[]
        for binding in reviewed['results']:
            verify(binding);cell=load(binding['path']);cells.append(cell)
        geometry=validate_pair(*cells)
        if any(c['profile_sha256']!=fingerprint(profile) for c in cells):raise ValueError('Cell/profile mismatch')
        if fingerprint(geometry)!=reviewed['matching_geometry_sha256']:raise ValueError('Reviewed geometry changed')
        wid=reviewed['window_id'];label=labels[wid]
        for field in ('identity','source_id','unique_source_pcm_sha256'):
            if label[field]!=original[wid][field]:raise ValueError('Protected C label changed')
        sources.append(dict(window_id=wid,source_id=label['source_id'],identity=label['identity'],
            pcm=label['unique_source_pcm_sha256'],vectors=[representatives(c['vectors']) for c in cells]))
    if len(sources)!=len(labels) or len({s['window_id'] for s in sources})!=len(labels):
        raise ValueError('Missing/duplicate reviewed C source')
    groups,counts=collect_groups(sources)
    centers=[summarize(groups,'fit',i) for i in (0,1)]
    nominal=profile['tracker']['cosine_threshold'];failures=[];mapping=None;candidate=None
    for split in ('fit','validation'):
        support=summarize(groups,split,0)
        if support['positive_identity_groups']<protocol['C_partition']['minimum_'+split+'_positive_identity_groups']:
            failures.append(split+' insufficient positive identity groups')
        if support['negative_identity_pairs']<protocol['C_partition']['minimum_'+split+'_negative_identity_pairs']:
            failures.append(split+' insufficient negative identity pairs')
    try:
        candidate,mapping=transform_profile(profile,*centers,protocol)
        source=Path(admission['source']);sys.path[:0]=[str(source),str(source/'vendor')]
        from edge_speech_pipeline.research_profiles import ResearchProfile
        ResearchProfile.from_dict(candidate).validate()
    except ValueError as exc:
        failures.append(str(exc))
    scores={}
    choices=[('E0_nominal',0,nominal),('E1_inherited_nominal',1,nominal)]
    if candidate is not None:choices.append(('E1_C_affine',1,candidate['tracker']['cosine_threshold']))
    for key,encoder,threshold in choices:
        scores[key]={split:dict(overall=summarize(groups,split,encoder,threshold),
            roles={r:summarize(groups,split,encoder,threshold,r) for r in protocol['pair_admission']['role_pairs']})
            for split in ('fit','validation')}
    if 'E1_C_affine' in scores and not gate(scores['E1_inherited_nominal']['validation']['overall'],scores['E1_C_affine']['validation']['overall']):
        failures.append('Fixed validation error-rate gate failed')
    if candidate is None:failures.append('No valid candidate profile')
    output=dict(schema='n4-d0-C-scale-fit-v1',status='UNQUALIFIED_C_SCALE' if failures else 'PASS_C_SCALE_SCREEN_ONLY',
        protocol=bind(args.protocol),review=bind(args.review),protected_labels=bind(run/'C_LABELS_EVALUATOR_ONLY.json'),
        code=[bind(__file__),bind(Path(__file__).with_name('common.py')),bind(Path(__file__).with_name('review_d0_collection.py'))],
        source_receipt=admission['source_receipt'],source_changed=False,integrated_N4_cells=0,
        calibration_source_clips=len(sources),source_split_counts={p:sum(partition(s['identity'])==p for s in sources) for p in ('fit','validation')},
        identity_split_counts={p:len({s['identity'] for s in sources if partition(s['identity'])==p}) for p in ('fit','validation')},
        source_role_representatives={role:sum(len(s['vectors'][0][role]) for s in sources) for role in ('short','mature')},
        pair_admission=counts,fit_centers=dict(E0=centers[0],E1=centers[1]),mapping=mapping,scores=scores,
        failures=failures,application_profile_accepted=False,processed_query_naming='UNCALIBRATED_REJECT_ALL',
        limitations=['Clean C association scale only; processed query behavior unknown',
            'Pair score screening does not validate online tracker dynamics or name recognition',
            'Correlated engineering sources; no independent-trial accuracy guarantee'])
    args.output.mkdir(parents=True)
    if candidate is not None:
        freeze(args.output/'PROPOSED_PROFILE.json',candidate);output['proposal']=bind(args.output/'PROPOSED_PROFILE.json')
    freeze(args.output/'RESULT.json',output)
    freeze(args.output/'PRIVATE_SPLIT.json',dict(rows=[dict(window_id=s['window_id'],identity=s['identity'],
        source_id=s['source_id'],partition=partition(s['identity'])) for s in sources]))
    print(json.dumps(dict(status=output['status'],centers=output['fit_centers'],mapping=mapping,
        validation={k:v['validation']['overall'] for k,v in scores.items()},failures=failures),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('protocol','review','output'):parser.add_argument('--'+name,type=Path,required=True)
    main(parser.parse_args())
