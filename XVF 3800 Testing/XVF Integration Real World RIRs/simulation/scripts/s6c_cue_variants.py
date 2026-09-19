"""Freeze uninformative/nominal cue controls, never operational truth. README_S6C_CUE_VARIANTS.md."""
import argparse
from copy import deepcopy
import hashlib
import math
import random
from s6c_common import *

def build():
    target=REPORT/'CUE_VARIANT_INDEX_V1.json'
    if target.exists():
        index=read(target)
        for r in index['rows']:bind(r['telemetry']['path'],r['telemetry']['sha256'])
        return dict(status=index['status'],rows=len(index['rows']),path=str(target))
    admit_work(full=True)
    inputs=read(S6B/'INPUT_INDEX.json')['rows'];bank={s['case_id']:s for s in read(BANK)['scenes']}
    physical={};angles=[];sources=[]
    for item in inputs:
        cid=item['case_id']
        if cid in physical:
            if item['telemetry']['sha256']!=physical[cid][0]['sha256']:raise ValueError('Canonical taps have different delivered cue schedules')
            continue
        bind(item['telemetry']['path'],item['telemetry']['sha256'])
        rows=[json.loads(line) for line in Path(item['telemetry']['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
        physical[cid]=(item['telemetry'],rows)
        for i,row in enumerate(rows):
            if row['valid'] and row['angle_deg'] is not None:
                angles.append(row['angle_deg']);sources.append((cid,i))
    # Independent packet reassignment across the whole bank keeps the aggregate
    # angle distribution and all destination delivery/validity fields. No fixed
    # rotation can retain source discrimination. Seeds are registered in advance.
    nulls={}
    for seed in (11,29,47):
        shuffled=list(range(len(angles)));random.Random(seed).shuffle(shuffled)
        nulls[seed]={destination:angles[source] for destination,source in zip(sources,shuffled)}
    index_rows=[];controls=[]
    for item in inputs:
        cid,tap=item['case_id'],item['stream'];source,rows=physical[cid]
        support=verified(item['support'])['support'];shift=support['output_mappings'][tap]['source_with_rir_to_output_offset_samples']
        spatial=read(S6A/'cues/shared_telemetry'/(cid+'.json'))['evidence']
        turns=spatial['turns'];segments=bank[cid]['segments']
        geometry={}
        for segment in segments:
            label=segment.get('utterance_label');row=turns.get(label)
            if row and 'source_angle_label' in row:geometry[segment['source_id'],segment['source_start_sample']]=row['source_angle_label']
        for condition in ['UNINFORMATIVE_SEED_'+str(s) for s in (11,29,47)]+['NOMINAL_GEOMETRY_DIAGNOSTIC']:
            out=deepcopy(rows);replacement_rows=[];changed=0;supported=0
            if condition.startswith('UNINFORMATIVE'):
                seed=int(condition.rsplit('_',1)[1])
                for i,row in enumerate(out):
                    if (cid,i) in nulls[seed]:
                        angle=nulls[seed][cid,i];changed+=angle!=row['angle_deg'];row['angle_deg']=angle
                        replacement_rows.append(i)
                scope='Bank-wide independently permuted angle contents; exact destination validity/energy/reliability/sequence/source/delivery schedule retained. Not a physical sensor fault model.'
            else:
                for i,row in enumerate(out):
                    if shift is None:continue # Source-empty/unidentifiable alignment has no nominal support.
                    if not row['valid'] or row['angle_deg'] is None:continue
                    sample=row.get('source_end_sec',row['available_at_sec'])*16000-shift
                    active=[t for t in support['turns'] if any(a<=sample<b for a,b in t['support_ranges'])]
                    if len({t['speaker_key'] for t in active})!=1:continue
                    active_geometries=[]
                    for turn in active:
                        segment=segments[turn['segment_index']]
                        g=geometry.get((turn['source_id'],segment['source_start_sample']))
                        if g is not None:active_geometries.append(g)
                    if not active_geometries:continue
                    values={round(g['expected_native_nominal_deg'],9) for g in active_geometries}
                    if len(values)!=1:continue
                    g=active_geometries[0];angle=float(g['expected_native_nominal_deg'])
                    supported+=1;changed+=angle!=row['angle_deg'];row['angle_deg']=angle
                    replacement_rows.append(dict(row=i,native_nominal_deg=angle,native_manual_interval_deg=g['expected_native_interval_deg']))
                scope='Oracle-like replacement only on supported sole-person estimated activity; same delivered valid/missing schedule. Outside supported regions numeric real cues remain unchanged, so this is a bounded supported-region intervention, not an ideal all-time sensor. Do not score unsupported regions as nominal geometry.'
            # No early packets, hidden truth fields or gains are inserted.
            if any({k:v for k,v in a.items() if k!='angle_deg'}!={k:v for k,v in b.items() if k!='angle_deg'} for a,b in zip(rows,out)):
                raise ValueError('Cue control changed destination observation schedule or validity')
            folder=REPORT/'cue_variants_v2'/condition;folder.mkdir(parents=True,exist_ok=True)
            path=folder/(cid+'_'+tap+'.jsonl')
            if path.exists():raise ValueError('Unreceipted existing cue variant')
            with path.open('w',encoding='utf-8',newline='\n') as f:
                for row in out:f.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n')
            entry=dict(case_id=cid,stream=tap,condition=condition,telemetry=bind(path),source=source,
                input_rows=len(rows),changed_angle_rows=changed,supported_nominal_rows=supported,
                destination_nonangle_fields_exact=True,scope=scope)
            index_rows.append(entry)
            if condition=='NOMINAL_GEOMETRY_DIAGNOSTIC':
                controls.append(dict(case_id=cid,stream=tap,support=item['support'],replacement_rows=replacement_rows,
                                     manual_uncertainty_half_width_deg=5,front_rear_resolved=False))
        if tap=='O1' and len(index_rows)%80==0:print(json.dumps(dict(stage='FREEZING_CUE_CONTROLS',rows=len(index_rows),case_id=cid)),flush=True)
    control=REPORT/'cue_variants_v2/NOMINAL_SUPPORTED_REGION_MASKS.json';save(control,dict(rows=controls),immutable=True)
    result=dict(status='FROZEN_BEFORE_S6C_OUTCOMES',schema='jp_s6c_cue_variants.v1',created_utc=utc(),rows=index_rows,
        code=bind(__file__),input_index=bind(S6B/'INPUT_INDEX.json'),nominal_supported_masks=bind(control),
        registered_seeds=[11,29,47],valid_angle_pool_rows=len(angles),
        nominal_policy='Numeric manual-angle intervention on supported nonoverlap rows only; original observation availability/missingness preserved and unsupported angles unchanged; interpret only named supported regions',
        oracle_is_not_deployable=True,no_person_ids_in_predictor_files=True)
    save(target,result,immutable=True)
    return dict(status=result['status'],rows=len(index_rows),path=str(target))

if __name__=='__main__':print(json.dumps(build(),indent=2))
