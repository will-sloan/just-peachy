"""Selected application continuity plans. See README_CONTINUITY_APPLICATION_PLAN.md."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
import wave

from common import audio_only, bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from paced_child_admission import assert_plain_path
import paced_panel_plan as original
import paced_panel_plan_v3 as panels
import continuity_sequence_v2 as sequence
from review_scoring_bank import guard, require, shared_allowance
from scoring_bank import writer_lock

HERE=Path(__file__).resolve().parent
LOCAL=Path('G:/Just_Peachy_N1/20260924_campaign/local')
SCHEMA='n4-continuity-application-plan-v1'
STATUS='PREPARED_SELECTED_CONTINUITY_ONLY'
APPLICATION_POLICY=panels.APPLICATION_POLICY
POLICY=dict(schema='n4-continuity-application-policy-v1',minimum_seconds=1200,maximum_seconds=1300,
    initial_reset_only=True,reset_at_internal_joins=False,one_full_file_per_candidate=True,
    stop_restart_included=False,tap='O0',reference_scope='Evaluator only; no joins or actor labels in child payload')
OWN=('continuity_application_plan.py','test_continuity_application_plan.py',
    'probe_continuity_application_plan.py','README_CONTINUITY_APPLICATION_PLAN.md')


def code_bindings():
    entries=[bind(HERE/n) for n in OWN]+panels.code_bindings()+sequence.code_bindings()
    entries += [bind(HERE/n) for n in ('PACED_PANEL_PLAN_CHECK_V3.json',
        'CONTINUITY_SEQUENCE_CHECK_V2.json','CONTINUITY_INPUT_PREPARATION_V2.json')]
    unique={}
    for b in entries:
        require(b['path'] not in unique or unique[b['path']]==b,'Conflicting continuity dependency')
        unique[b['path']]=b
    return [v for _,v in sorted(unique.items())]


def validate_input_proof(public,qualified,admission,result,plan,audio,truth,copied,rebuilt,rebuilt_truth):
    """Pure joins; hashes, owners, headers and exact PCM are checked by read_input."""
    require(public['status']=='PREPARED_VERIFIED_CONTINUITY_INPUT_ONLY'
        and qualified['status']=='PASS_CONTINUITY_SEQUENCE_V2_DEVELOPMENT_ONLY'
        and result['status']=='PREPARED_LOSSLESS_CONTINUITY_INPUT_ONLY','Unqualified continuity preparation')
    require(admission['code']==qualified['code'] and admission['qualification']==public['qualification']
        and admission['owner']==public['exited_preparation_owner'] and admission['source_execution_authorized'] is False,
        'Continuity preparation code, owner or qualification differs')
    require(result['admission']==public['private_admission'] and plan==rebuilt
        and plan['inputs']==admission['inputs'] and plan['reset_at_joins'] is False
        and plan['adaptation'] is False,'Continuity metadata reconstruction differs')
    for key in ('plan','audio_only','evaluator_truth','copy_receipt'):
        require(result[key]==public[key],'Continuity output binding differs')
    require(audio['schema']=='n4-audio-only-v1' and len(audio['jobs'])==1,'One full continuity file required')
    job=audio_only(audio['jobs'][0])
    require(job['job_id']==plan['sequence_id'] and job['frames']==plan['frames']
        and job['audio_path']==public['waveform']['path'] and job['audio_sha256']==public['waveform']['sha256']
        and job['tap']==plan['tap']==POLICY['tap'] and 1200*16000<=job['frames']<=1300*16000,
        'Continuity audio identity, duration or tap differs')
    require(truth==dict(schema='n4-evaluator-truth-v1',NEVER_PASS_TO_RUNTIME=True,cells=[rebuilt_truth]),
        'Evaluator-only continuity truth differs')
    require(public['sessions']==result['sessions']==plan['original_sessions']==len(plan['segments'])
        and public['seconds']==result['seconds']==plan['actual_seconds']==job['frames']/16000
        and public['frames']==job['frames'] and public['distinct_global_actors']==result['distinct_actor_count']==plan['distinct_actor_count']
        and public['source_pcm_segments_independently_compared']==len(plan['segments'])
        and public['all_original_words_and_reference_offsets_reconstructed'] is True and public['no_join_reset'] is True,
        'Continuity population or summary differs')
    for record in (public,result):
        require(all(record[k] is False for k in ('actual_application_spawned','actual_source_execution','actual_continuity_test','N4_accepted'))
            and record['integrated_N4_cells']==0,'Input preparation cannot claim execution or acceptance')
    require(copied['status']=='COPIED_EXACT_SAVED_PCM_ONLY' and copied['output']==public['waveform']
        and copied['frames']==job['frames'] and copied['actual_source_execution'] is False
        and len(copied['segments'])==len(plan['segments']),'Continuity PCM copy receipt differs')
    offset=0
    for index,(segment,copy) in enumerate(zip(plan['segments'],copied['segments'])):
        source=audio_only(segment['job'])
        require(segment['index']==copy['index']==index and segment['destination_start_frame']==offset
            and segment['destination_end_frame']==offset+source['frames'] and copy['frames']==source['frames']
            and copy['original_waveform']['path']==source['audio_path']
            and copy['original_waveform']['sha256']==source['audio_sha256'],'Continuity segment identity or offset differs')
        offset+=source['frames']
    require(offset==job['frames'],'Continuity segment coverage differs')
    return deepcopy(job)


def verify_pcm(plan,copied,checkpoint=lambda:None):
    """Read-only byte comparison, bounded to four seconds; no playback or decoding."""
    combined=hashlib.sha256()
    with wave.open(copied['output']['path'],'rb') as destination:
        require((destination.getnchannels(),destination.getsampwidth(),destination.getframerate(),destination.getnframes(),destination.getcomptype())
            ==(1,2,16000,plan['frames'],'NONE'),'Continuity WAV header differs')
        for segment,copy in zip(plan['segments'],copied['segments']):
            checkpoint();verify(copy['original_waveform']);digest=hashlib.sha256();left=copy['frames']
            with wave.open(copy['original_waveform']['path'],'rb') as source:
                require((source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getnframes(),source.getcomptype())
                    ==(1,2,16000,left,'NONE'),'Original saved WAV header differs')
                while left:
                    count=min(left,64000);raw=source.readframes(count);observed=destination.readframes(count)
                    require(len(raw)==count*2 and observed==raw,'Continuity PCM is not the exact original segment')
                    combined.update(raw);digest.update(raw);left-=count
                require(not source.readframes(1),'Unexpected original audio tail')
            require(digest.hexdigest()==copy['pcm_sha256'],'Original PCM receipt differs');verify(copy['original_waveform'])
        require(not destination.readframes(1),'Unexpected continuity audio tail')
    require(combined.hexdigest()==copied['pcm_sha256'],'Combined continuity PCM digest differs')
    verify(copied['output'])


def read_input(checkpoint=lambda:None):
    public_binding=bind(HERE/'CONTINUITY_INPUT_PREPARATION_V2.json');public=load(public_binding['path'])
    for key in ('qualification','private_receipt','private_admission','plan','audio_only','evaluator_truth','copy_receipt','waveform'):
        verify(public[key])
    qualified=load(public['qualification']['path']);result=load(public['private_receipt']['path'])
    admission=load(public['private_admission']['path'])
    require(exact_process(admission['owner']) is None and qualified['code']==sequence.code_bindings(),
        'Continuity preparer is active or its code changed')
    for b in qualified['code']+[qualified['private_receipt'],qualified['private_admission'],qualified['tests']]:verify(b)
    preparation,bindings,docs=sequence.inputs();rebuilt,rebuilt_truth=sequence.build(docs,bindings)
    require(admission['preparation']==preparation and admission['inputs']==bindings,'Continuity source preparation differs')
    plan,audio,truth,copied=[load(public[k]['path']) for k in ('plan','audio_only','evaluator_truth','copy_receipt')]
    job=validate_input_proof(public,qualified,admission,result,plan,audio,truth,copied,rebuilt,rebuilt_truth)
    verify_pcm(plan,copied,checkpoint)
    for b in list(bindings.values())+[public_binding,*qualified['code']]:verify(b)
    return public_binding,public,job


def build_plan(panel_binding,panel,sequence_binding,job):
    """Pure development builder; production must use reconstruct/admit_plan."""
    audio_only(job)
    require(panel['schema']==panels.SCHEMA and panel['status']=='PREPARED_PANELS_AND_REPEATS_ONLY'
        and panel['execution']==original.EXECUTION_POLICY and panel['source_relationship']==panels.SOURCE_RELATIONSHIP
        and panel['context']['application_policy']==APPLICATION_POLICY,'Qualified V3 panel context required')
    candidates=original.validate_selection(panel['selection'],panel['reviews'])
    require(panel['candidates']==candidates and panel['required']==len(candidates)*40
        and len(panel['rows'])==panel['required'] and panel['integrated_N4_cells']==0 and panel['N4_accepted'] is False,
        'Source panel population differs')
    require(1200*16000<=job['frames']<=1300*16000 and job['tap']==POLICY['tap'],'Bounded O0 continuity file required')
    context=deepcopy(panel['context']);contracts={};counts={c:0 for c in candidates}
    for index,row in enumerate(panel['rows']):
        payload=panels.execution_payload(panel,index);candidate=row['composition']
        require(candidate in counts,'Unselected source panel composition')
        require(candidate=='_'.join(payload['contract'][k] for k in ('variant','diarization','encoder')),'Contract/composition differs')
        require(candidate not in contracts or contracts[candidate]==payload['contract'],'Inconsistent selected contract')
        counts[candidate]+=1;contracts[candidate]=payload['contract']
    require(set(counts.values())=={40},'Every selected composition needs 40 source panel cells')
    rows=[]
    for candidate in candidates:
        key=dict(schema=SCHEMA,job=job,contract=contracts[candidate],execution=original.EXECUTION_POLICY,
            continuity=POLICY,context_sha256=fingerprint(context),panel=panel_binding,sequence=sequence_binding)
        rows.append(dict(cell_id='continuity_0_'+job['job_id']+'_'+candidate,composition=candidate,job=deepcopy(job),
            contract=deepcopy(contracts[candidate]),kind='continuity',repeat=0,cache_key=fingerprint(key),collection_credit=0))
    return dict(schema=SCHEMA,status=STATUS,panel=deepcopy(panel_binding),sequence=deepcopy(sequence_binding),
        context=context,execution=deepcopy(original.EXECUTION_POLICY),continuity=deepcopy(POLICY),rows=rows,
        candidates=deepcopy(candidates),required=len(candidates),seconds_per_candidate=job['frames']/16000,
        continuity_included=True,stop_restart_included=False,source_execution_authorized=False,
        integrated_N4_cells=0,N4_accepted=False)


def execution_payload(plan,index):
    require(plan['schema']==SCHEMA and plan['status']==STATUS and plan['execution']==original.EXECUTION_POLICY
        and plan['continuity']==POLICY and plan['context']['application_policy']==APPLICATION_POLICY
        and type(index) is int and 0<=index<len(plan['rows']),'Invalid continuity execution request')
    row=plan['rows'][index];context=plan['context'];job=audio_only(row['job'])
    require(row['kind']=='continuity' and row['repeat']==0 and job['tap']=='O0'
        and 1200*16000<=job['frames']<=1300*16000,'Continuity row duration or reset scope differs')
    key=dict(schema=SCHEMA,job=job,contract=row['contract'],execution=plan['execution'],continuity=plan['continuity'],
        context_sha256=fingerprint(context),panel=plan['panel'],sequence=plan['sequence'])
    require(row['cache_key']==fingerprint(key),'Changed continuity row, source context or input lineage')
    require(set(context['runtimes'])=={'n2_runtime.json','n3_runtime.json'},'Exact application runtimes required')
    # Identical child allowlist. Evaluator-only sequence references and joins
    # remain solely in coordinator evidence, never in this inference payload.
    return dict(schema='n4-paced-cell-input-v1',cell_id=row['cell_id'],job=deepcopy(job),contract=deepcopy(row['contract']),
        execution=deepcopy(plan['execution']),source_receipt=deepcopy(context['source_receipt']),catalog=deepcopy(context['catalog']),
        runtimes=[deepcopy(context['runtimes'][n]) for n in sorted(context['runtimes'])],
        gallery_preparation=deepcopy(context['gallery_preparation']),models_root=context['models_root'],assets=deepcopy(context['assets']),
        source_execution_authorized=False,
        remaining_gate='Exact supervised exclusive-slot owner, frozen launcher and live resource/deadline admission required')


def reconstruct(panel_path,checkpoint=lambda:None):
    panel_binding,panel=panels.admit_plan(panel_path)
    sequence_binding,public,job=read_input(checkpoint)
    require(panel['context']['manifest']==load(public['plan']['path'])['inputs']['AUDIO_ONLY_480.json'],
        'Continuity and selected panel use different accepted audio banks')
    return build_plan(panel_binding,panel,sequence_binding,job)


def admit_plan(path):
    assert_plain_path(path,LOCAL/'n4');binding=bind(path);result=load(path.parent/'RESULT.json')
    verify(result['admission']);admission=load(result['admission']['path']);code=code_bindings()
    qualifier=bind(HERE/'CONTINUITY_APPLICATION_PLAN_CHECK_V1.json');q=load(qualifier['path'])
    require(q['status']=='PASS_CONTINUITY_APPLICATION_PLANNER_DEVELOPMENT_ONLY' and q['code']==code
        and admission['qualification']==qualifier and admission['code']==code and exact_process(admission['owner']) is None,
        'Continuity planner qualification, code or stopped preparer differs')
    require(result['status']==STATUS and result['plan']==binding and result['source_execution_authorized'] is False
        and result['integrated_N4_cells']==0 and result['N4_accepted'] is False,'Continuity plan receipt differs')
    verify(admission['panel']);rebuilt=reconstruct(Path(admission['panel']['path']))
    require(load(path)==rebuilt and result['required']==rebuilt['required'],'Continuity plan reconstruction differs')
    for b in code+[binding,qualifier]:verify(b)
    return binding,rebuilt


def prepare(args):
    process=pin();started=time.monotonic();assert_plain_path(args.output,LOCAL/'n4')
    require(not args.output.exists(),'Fresh private continuity planner output required')
    with writer_lock(LOCAL/'n4/metric-scoring.owner.lock'):
        check=lambda:guard(args.output,LOCAL,started,720)
        check();inventory=shared_allowance(LOCAL);code=code_bindings()
        qualifier=bind(HERE/'CONTINUITY_APPLICATION_PLAN_CHECK_V1.json');q=load(qualifier['path'])
        require(q['status']=='PASS_CONTINUITY_APPLICATION_PLANNER_DEVELOPMENT_ONLY' and q['code']==code,'Unqualified continuity planner')
        plan=reconstruct(args.panel_plan,check);check()
        freeze(args.output/'ADMISSION.json',dict(owner=identity(process),code=code,qualification=qualifier,panel=plan['panel'],inventory=inventory))
        for b in code+[qualifier]:verify(b)
        freeze(args.output/'PLAN.json',plan)
        freeze(args.output/'RESULT.json',dict(status=STATUS,utc=datetime.now(timezone.utc).isoformat(),
            admission=bind(args.output/'ADMISSION.json'),plan=bind(args.output/'PLAN.json'),required=plan['required'],
            source_execution_authorized=False,integrated_N4_cells=0,N4_accepted=False))
        print('Prepared selected full-file continuity cells; no application launch',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel-plan',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    prepare(parser.parse_args())
