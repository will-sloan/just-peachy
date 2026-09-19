"""File-only native execution preparation; see README_S6D_NATIVE_PRODUCTION_PREPARE_V1.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import wave

SIM=Path(__file__).resolve().parent.parent
REPO=SIM.parents[2]
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
EVIDENCE_SHA='bb1b5ff846f8edad386b573dea203df7b08e9c31b8126e7c3aa14a8cccb226d2'
SCORER_SHA='4260ba5d1ac59f1e5fc057b7fa105fd1f525982ccf546353b5f283c054f092d4'
CHECKED={}


def binding(path):
    path=Path(path).resolve();h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=h.hexdigest())


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify(bound):
    key=(bound['path'],bound['sha256'],bound['bytes'])
    if key not in CHECKED:
        if binding(bound['path'])!=bound:raise ValueError('Bound source changed: '+bound['path'])
        CHECKED[key]=True
    return bound


def write(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    return binding(path)


def pcm(bound):
    verify(bound);h=hashlib.sha256()
    with wave.open(bound['path'],'rb') as wav:
        if (wav.getnchannels(),wav.getsampwidth(),wav.getframerate(),wav.getcomptype())!=(1,2,16000,'NONE'):
            raise ValueError('Expected exact mono16k PCM16 input')
        frames=wav.getnframes();actual=0
        while part:=wav.readframes(524288):h.update(part);actual+=len(part)//2
    if actual!=frames:raise ValueError('Truncated PCM')
    return dict(audio=bound,expected_frames=frames,audio_pcm_sha256=h.hexdigest())


def prepare(output,host_binding):
    output=Path(output).resolve()
    if output.parent!=R/'application':raise ValueError('Fresh application report directory required')
    host=read(host_binding);affinity=host['proposed_affinity']
    if affinity!=[12,13,14,15] or not set(affinity)<=set(host['available_affinity']):raise ValueError('Root-agreed host affinity differs')
    output.mkdir(exist_ok=False);manifests=output/'manifests';manifests.mkdir()
    payload=G/'application'/output.name
    if payload.exists():raise ValueError('New payload root is already occupied')
    predecl=R/'application/native_confirmation_predecl_v1'
    proposal_path=predecl/'REVIEWED_SOURCE_PROPOSAL.json';proposal=read(proposal_path)
    prior_paths=[predecl/'ORIGINAL_PARENT_MANIFEST.json',predecl/'REPAIRED_GUIV3_MANIFEST.json']
    expected=['b2f8f52ea214b7dc9e95efa8e94100b5902e737811feb7c1ec47368ebca4058b','395dab640489f9e91545584fe17af60eb1b4e4332458c14ea1997da340769c8b']
    native=[];all_jobs={};proofs={};source_audit=[]
    evidence=binding(SIM/'scripts/s6d_native_evidence_v1.py')
    if evidence['sha256']!=EVIDENCE_SHA:raise ValueError('Accepted full-source guard changed')
    for path,pin in zip(prior_paths,expected):
        prior=binding(path)
        if prior['sha256']!=pin:raise ValueError('Predeclared native matrix changed')
        m=read(path);verify(m['helper']);verify(m['readme'])
        for b in m['execution_files']+m.get('support_files',[]):verify(b)
        source_audit.extend(m['execution_files'])
        m.update(created_utc=datetime.now(timezone.utc).isoformat(),prior_execution_proposal=prior,
                 status='PROPOSED_PRODUCTION_ROOT_ADOPTION_REQUIRED',approved=False,payload_root=str(payload/'headless176'),
                 evidence_helper=evidence,production_completion_guard_required=True)
        m['limits']['cpu_affinity']=affinity
        for job in m['jobs']:
            verify(job['profile_binding'])
            if read(job['profile_binding']['path'])!=job['profile']:raise ValueError('Inline original profile differs')
            if job['gallery']:verify(job['gallery'])
            key=job['audio']['path']
            if key not in proofs:proofs[key]=pcm(job['audio'])
            if any(job[k]!=proofs[key][k] for k in ['expected_frames','audio_pcm_sha256']):raise ValueError('Predeclared PCM differs')
            if job['expected_identity_frames']!=job['expected_frames']:raise ValueError('Identity input differs')
            job['output']=str(payload/'headless176'/job['job_id'])
            if job['job_id'] in all_jobs:raise ValueError('Duplicate native job')
            all_jobs[job['job_id']]=job
        mb=write(manifests/path.name,m);native.append(mb)
    literal_order=[x['job_id'] for x in proposal['literal_jobs']]
    if len(all_jobs)!=176 or set(literal_order)!=set(all_jobs) or len(literal_order)!=176:raise ValueError('Original176 population/order differs')
    reference_path=G/'review_fixtures/native_correctness_v1/prospective_matrix_v1/PROSPECTIVE_INPUT_MATRIX.json'
    if binding(reference_path)['sha256']!='abd28a08d67059ad159b4d56699d003632cfa2ef5f7e1e7daf6e1cee8499ee25':raise ValueError('Reviewed reference matrix changed')
    reference_matrix=read(reference_path)
    if {row['job_id'] for row in reference_matrix['rows']}!=set(all_jobs):raise ValueError('Reference population differs')
    owner_manifest={j['job_id']:mb for mb in native for j in read(mb['path'])['jobs']}
    rows=[]
    for row in reference_matrix['rows']:
        verify(row['reference']);job=all_jobs[row['job_id']]
        if row['audio']!=job['audio'] or row['expected_frames']!=job['expected_frames'] or row['gallery']!=job['gallery']:raise ValueError('Reference/scientific input differs')
        rows.append(dict(row,manifest=owner_manifest[job['job_id']],expected_result_path=str(Path(job['output'])/'RESULT.json'),expected_completion_audit_path=str(Path(job['output'])/'FULL_SOURCE_AUDIT.json')))
    # Freeze exact accepted scorer/dependencies in the relative layout its imports require.
    closure=G/'review_fixtures/native_correctness_independent_v2/INDEPENDENT_NATIVE_CORRECTNESS_REVIEW_V2.json'
    if binding(closure)['sha256']!='cf53ce755f1ade8f39ff38c6af4d4a4593bf95504e7e7ccb4a521e0edc32b8db':raise ValueError('Scorer review differs')
    source_bindings=read(closure.parent/'SOURCE_BINDINGS.json');scoring_files=[]
    for pair in source_bindings['files']:
        bound=verify(pair['original']);original=Path(bound['path']);dst=output/'scoring_tree/just-peachy'/original.relative_to(REPO)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,dst);scoring_files.append(binding(dst))
    scorer=next(b for b in scoring_files if b['path'].endswith('s6d_native_correctness_v1.py'))
    if scorer['sha256']!=SCORER_SHA:raise ValueError('Accepted scorer changed')
    dependency_names=['s4_h2_analysis.py','s5_text_metrics.py','s6c_name_analysis_v3.py','s6a_support_metrics.py','wer.py','s6d_native_evidence_v1.py']
    dependencies=[next(b for b in scoring_files if Path(b['path']).name==name) for name in dependency_names]
    # HOST inputs remain the already materialized, uninterrupted1827.426625-second waveform.
    host_manifest=deepcopy(read(native[1]['path']));host_manifest['jobs']=[];host_manifest['job_count']=2
    host_manifest['limits']['cell_timeout_sec']=7200.;host_manifest['payload_root']=str(payload/'host2')
    host_reference=verify(reference_matrix['host_reference']);host_ref=read(host_reference['path'])
    for outline in proposal['host_continuous_outline']:
        template=next(j for j in read(native[1]['path'])['jobs'] if j['candidate']==outline['candidate'] and j['asr_tap']=='O0')
        job=deepcopy(template);job.update(job_id=outline['job_id'],scene_id='HOST_CONTINUOUS_38_PIECES',scientific_role='UNINTERRUPTED_HOST_CORRECTNESS_AND_DRAIN',audio=outline['audio'],audio_duration_sec=outline['audio_duration_sec'],expected_frames=outline['expected_frames'],expected_identity_frames=outline['expected_frames'],output=str(payload/'host2'/outline['job_id']),composition=verify(outline['composition']),fixed_profile_through_whole_session=True,no_truth_resets=True)
        key=job['audio']['path']
        if key not in proofs:proofs[key]=pcm(job['audio'])
        job['audio_pcm_sha256']=proofs[key]['audio_pcm_sha256']
        if proofs[key]['expected_frames']!=job['expected_frames'] or host_ref['input_audio']!=job['audio']:raise ValueError('HOST PCM/reference differs')
        host_manifest['jobs'].append(job)
    host_manifest['source_audio_total_sec']=sum(j['audio_duration_sec'] for j in host_manifest['jobs'])
    host_bound=write(manifests/'HOST2_MANIFEST.json',host_manifest)
    # Tk executes accepted helper2ba27c61 with the same eight scientific jobs/views.
    tk_parent=R/'application/native_tk_consumer_v2/MANIFEST.json';tk=read(tk_parent)
    if binding(tk_parent)['sha256']!='cdbc1597cd5f6018b55949292cfd1ff791cbc554b65c00b384a4a56a9db8f1b5':raise ValueError('Accepted Tk proposal differs')
    for b in [tk['helper'],*tk['support_files'],*tk['execution_files']]:verify(b)
    tk.update(prior_execution_proposal=binding(tk_parent),created_utc=datetime.now(timezone.utc).isoformat(),status='PROPOSED_PRODUCTION_ROOT_ADOPTION_REQUIRED',approved=False,payload_root=str(payload/'tk8'))
    tk['limits']['cpu_affinity']=affinity
    for job in tk['jobs']:job['output']=str(payload/'tk8'/job['job_id'])
    tk_bound=write(manifests/'TK8_MANIFEST.json',tk)
    scoring=dict(schema='s6d-native-scoring-prospective-matrix.v2',status='PROSPECTIVE_CLOSED_OUTPUT_ADMISSION_REQUIRED',scorer=scorer,dependencies=dependencies,source_files=scoring_files,review=binding(closure),execution_manifests=native,declared_jobs=176,rows=rows,comparison_pairs=reference_matrix['comparison_pairs'],host_manifest=host_bound,host_reference=host_reference,tk_manifest=tk_bound,tk_render_scoring='Separate exact native-event/render joins required; headless scorer does not certify widget timing',owner_exit_verified=False,source_graph_verified=False,actual_native_outputs_scored=0)
    scoring_bound=write(output/'PROSPECTIVE_SCORING_BINDINGS.json',scoring)
    headless_receipt=write(output/'NATIVE176_READY_FOR_PROTOCOL.json',dict(status='EXACT_MANIFESTS_READY_PENDING_WRAPPER_AND_ROOT_ADOPTION',manifests=native,job_count=176,job_order=literal_order,scoring_bindings=scoring_bound,original_selection=binding(proposal_path),source_epochs_preserved=True,helper_unchanged=True,cpu_affinity=affinity,model_jobs_started=0))
    inventory={b['path']:b for b in source_audit}
    receipt=dict(schema='s6d-native-production-preparation.v1',status='FILE_ONLY_PREPARED_PENDING_PROTOCOL_QUEUE_AND_ROOT_ADOPTION',created_utc=datetime.now(timezone.utc).isoformat(),helper=binding(__file__),host=binding(host_binding),cpu_affinity=affinity,headless176=headless_receipt,manifests=[*native,tk_bound,host_bound],jobs=dict(headless=176,tk=8,host=2),scoring_bindings=scoring_bound,pcm_inputs=list(proofs.values()),source_files_verified=len(inventory),payload_root=str(payload),deadline_utc='2026-09-16T19:53:57+00:00',forecast_hours=dict(headless176=[3.77,4.05],tk8_pilot_extrapolation_only=[.18,.25],host2=[1.75,1.88],total_before_scoring_and_closeout=[5.70,6.18],planning_allowance=7.),forecast_scope='Actual12-job pilot extrapolation; four-logical-CPU affinity and Tk concurrent views were not benchmarked. No performance guarantee.',mandatory_full240_remaining=dict(repaired_C065_C088_both_taps_native_jobs=960,pilot_extrapolated_hours=[20.89,22.41],original_controls_if_cache_source_profile_waveform_proof_absent=960),no_launches=True)
    rb=write(output/'PREPARATION_RECEIPT.json',receipt);print(json.dumps(rb));return rb


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--host-receipt',type=Path,required=True)
    args=parser.parse_args();prepare(args.output,args.host_receipt)
