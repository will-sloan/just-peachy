"""Prepare all predeclared bank/E/continuous capture groups; see matching README."""
import copy,datetime,hashlib,json,math
from pathlib import Path
import numpy as np
import soundfile as sf
SIM=Path(__file__).resolve().parents[1];R=SIM/'reports/S6D/20260913T195357Z';G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
OUT=R/'physical_bank_preparation_v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def bind(p):
    p=Path(p).resolve();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def verify(b):
    v=bind(b['path'])
    if (v['bytes'],v['sha256'])!=(b['bytes'],b['sha256']):raise ValueError('Changed source '+b['path'])
    return v
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def main():
    if OUT.exists():raise ValueError('Preserve preparation')
    grouped_path=R/'physical_preparation_v2/CAMPAIGN_BATCH_PROPOSAL.json';grouped=read(grouped_path)
    for k in ('base_authority','enrollment_authority','continuous_authority'):verify(grouped[k])
    original=read(grouped['base_authority']['path']);rows={x['case_id']:x for x in original['P_MAIN6']['cases']}
    adopt_path=G/'enrollment_continuous_inputs_v1/ROOT_ADOPTION_MAP.json';adopt=read(adopt_path);special={x['planned_id']:x for x in adopt['entries']}
    base=read(R/'physical_preparation_review_v2/CAPTURE_PLAN_PROPOSAL.json')
    template=base['attempts'][1];qa=copy.deepcopy(base['attempts'][0]);verified={};groups=[];total_seconds=0.;count=0
    def attempt(aid,case,profile,role,binding,duration):
        key=binding['path']
        if key not in verified:
            b=verify(binding)
            peak=0.;nonzero=False
            with sf.SoundFile(b['path']) as audio:
                if audio.samplerate!=16000 or audio.channels!=4 or len(audio)!=round(duration*16000):raise ValueError('Whole4MIC16k input extent')
                for block in audio.blocks(blocksize=65536,dtype='float32',always_2d=True):
                    if not np.isfinite(block).all():raise ValueError('Nonfinite source')
                    peak=max(peak,float(np.max(np.abs(block))));nonzero|=bool(np.any(block!=0))
                frames=len(audio)
            if peak>=1:raise ValueError('No automatic source gain adjustment allowed')
            verified[key]=dict(binding=b,frames=frames,peak_abs=peak,nonzero=nonzero)
        evidence=verified[key]
        if evidence['frames']!=round(duration*16000):raise ValueError('Conflicting duplicate source extent')
        row=copy.deepcopy(template);row.update(attempt_id=aid,case_id=case,profile=profile,role=role,duration_sec=duration,source_audio=evidence['binding'],payload_expectation='nonzero' if evidence['nonzero'] else 'silence',required_nonzero_streams=['auto_asr_raw','auto_pp_raw'] if evidence['nonzero'] else [],stream_identity_qualification='PENDING_ROOT_ACTUAL_MAIN_SCAN_QUALIFICATION')
        row.pop('timing',None)
        if role=='continuous':row['continuous_dsp_seconds']=900
        return row
    for group in grouped['groups']:
        gid=group['batch_id'];items=[]
        for suffix in ('PRE',):
            item=copy.deepcopy(qa);item.update(attempt_id=f'QA_{gid}_{suffix}',stream_identity_qualification='OWN_PASS_EXACT_MIC_QA');items.append(item)
        if 'source_case_ids' in group:
            for case in group['source_case_ids']:
                original_case=rows[case]
                items.append(attempt(f'{group["profile"]}_{case}',case,group['profile'],'canonical',original_case['input_binding'],original_case['duration_s']))
            for case in group.get('matched_repeat_cases',[]):
                original_case=rows[case]
                items.append(attempt(f'{group["profile"]}_{case}_REPEAT',case,group['profile'],'repeat',original_case['input_binding'],original_case['duration_s']))
        elif 'enrollment_pass_ids' in group:
            for pid in group['enrollment_pass_ids']:
                row=special[pid];items.append(attempt(pid,pid,group['profile'],'enrollment',row['source_audio'],row['duration_sec']))
        else:
            pid=group['continuous_session_id'];row=special[pid]
            items.append(attempt(pid,pid,group['profile'],'continuous',row['source_audio'],row['duration_sec']))
        item=copy.deepcopy(qa);item.update(attempt_id=f'QA_{gid}_POST',stream_identity_qualification='OWN_PASS_EXACT_MIC_QA');items.append(item)
        seconds=sum(x['duration_sec']+4+16383/48000 for x in items)
        plan=copy.deepcopy(base);plan.update(schema='s6d-bank-capture-proposal.v1',status='PENDING_ACTUAL_ROUTE_TAIL_OBSERVER_QUALIFICATION',attempts=items,safety=None,no_execution_authorization_created=True,payload_root=str(G/'bank_captures_v1'),qualification_batches=[],source_group=grouped_path.name)
        stages=[dict(batch_id=gid+'_pre_QA',attempt_ids=[items[0]['attempt_id']]),dict(batch_id=gid,attempt_ids=[x['attempt_id'] for x in items[1:-1]]),dict(batch_id=gid+'_post_QA',attempt_ids=[items[-1]['attempt_id']])]
        groups.append(dict(group_id=gid,plan=plan,stages=stages,attempts=len(items),charged_playback_seconds=seconds));count+=len(items);total_seconds+=seconds
    ids=[x['attempt_id'] for g in groups for x in g['plan']['attempts']]
    if len(ids)!=len(set(ids)) or count!=394 or len(groups)!=20:raise ValueError('Predeclared whole bank matrix coverage')
    main={x['case_id'] for g in groups for x in g['plan']['attempts'] if x['profile']=='P_MAIN6' and x['role']=='canonical'}
    scan={x['case_id'] for g in groups for x in g['plan']['attempts'] if x['profile']=='P_SCAN6' and x['role']=='canonical'}
    if main!=set(original['P_MAIN6']['case_ids']) or scan!=set(original['P_SCAN6']['case_ids']):raise ValueError('Predeclared case coverage changed')
    qualification_seconds=sum(x['duration_sec']+4+16383/48000 for x in base['attempts'])
    if count+len(base['attempts'])!=427 or total_seconds+qualification_seconds>21600:raise ValueError('Unchanged forecast')
    OUT.mkdir();plan_bindings=[]
    for g in groups:
        directory=OUT/g['group_id'];directory.mkdir();save(directory/'CAPTURE_PLAN_PROPOSAL.json',g.pop('plan'));g['plan']=bind(directory/'CAPTURE_PLAN_PROPOSAL.json');plan_bindings.append(g)
    report=dict(status='ALL_MANDATORY_INPUTS_PREPARED_NO_EXECUTION_AUTHORITY',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),groups=plan_bindings,source_verification=list(verified.values()),grouped_authority=bind(grouped_path),enrollment_continuous_adoption=bind(adopt_path),helper=bind(__file__),main_unique=len(main),scan_unique=len(scan),additional_repeats=4,E_passes=60,continuous_passes=2,QA_passes=40,bank_attempts=count,bank_charged_seconds=total_seconds,full_forecast_attempts=427,full_forecast_charged_seconds=total_seconds+qualification_seconds,unchanged_audio=True,hardware_calls=0,models=0,new_RIRs=0,execution_authorized=False)
    save(OUT/'PREPARATION_RESULT.json',report);print(json.dumps({k:report[k] for k in ('status','main_unique','scan_unique','bank_attempts','bank_charged_seconds','full_forecast_attempts','full_forecast_charged_seconds','execution_authorized')}))
if __name__=='__main__':main()
