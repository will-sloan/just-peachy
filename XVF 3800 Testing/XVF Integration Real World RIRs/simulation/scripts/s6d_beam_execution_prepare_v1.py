"""Declare then bind bounded actual-capture native work; see README_S6D_BEAM_EXECUTION_V1.md."""
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import s6d_beam_native_run_v1 as N

SIM=next((p for p in Path(__file__).resolve().parents if p.name=='simulation' and (p/'reports/S6D/20260913T195357Z').is_dir()),Path('C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation'))
R=SIM/'reports/S6D/20260913T195357Z'
G=Path('G:/Just_Peachy_S6D/20260913T195357Z')
MAIN=['auto_asr_raw','auto_pp_raw','focus0_asr_raw','focus1_asr_raw','focus0_pp_raw','focus1_pp_raw']
SCAN=['auto_asr_raw','auto_pp_raw','focus0_asr_raw','focus1_asr_raw','scan_asr_raw','scan_pp_raw']
need=N.need;bind=N.bind;verified=N.verified;save=N.save

def declare(output):
    output=Path(output).resolve();need(not output.exists(),'Fresh declaration required')
    epoch=bind(R/'application/beam_native_interface_v3/MANIFEST.json');e=verified(epoch)
    beam=next(x for x in e['source_files'] if Path(x['path']).name=='research_beams_s6d.py');need(beam['sha256']==N.PINS['beam'],'Accepted beam changed')
    panel=bind(R/'listening/HARDWARE_CASE_PREDECLARATION_V1.json');p=verified(panel);ids=p['P_SCAN6']['case_ids'];need(len(ids)==len(set(ids))==48,'Exact original48 required')
    profile=bind(SIM/'reports/S6C/20260910T123540Z/profiles/C088/O0_ASR_O0_ID.json')
    gallery=bind(Path('G:/Just_Peachy_S6C/20260910T123540Z/enrollment/galleries/84f59413a02827ef445c66be/GALLERY.json'))
    selected=sorted(x['profile_id'] for x in verified(gallery)['profiles'])[:2]
    tasks=[]
    def add(stage,case,capture,mode,stream='auto_asr_raw'):
        tasks.append(dict(job_id=f'{stage}_{capture}_{case}_{mode}_{stream}',stage=stage,case_id=case,capture_profile=capture,mode=mode,asr_raw_stream=stream,capture_binding_status='PENDING_EXACT_ROOT_ACCEPTED_CAPTURE_CATALOG'))
    for capture in ('P_MAIN6','P_SCAN6'):
        for case in ('C30_calibration_R04','C30_calibration_R12','same_C_two_paths','C_ABA','C_overlap','C_overlap_source_swap'):add('C_collection',case,capture,'calibration_collection')
    for case in ids:
        add('main_core',case,'P_MAIN6','same_pass_auto_control');add('main_core',case,'P_MAIN6','mono_asr_beam_identity')
        for capture,names in (('P_MAIN6',MAIN[1:]),('P_SCAN6',SCAN)):
            for stream in names:add('stream_diagnostics',case,capture,'stream_diagnostic',stream)
    output.mkdir(parents=True)
    helpers=output/'helpers';helpers.mkdir()
    helper_files=[]
    for name in ('s6d_beam_native_run_v1.py','s6d_beam_execution_prepare_v1.py','s6d_beam_execution_checks_v1.py','README_S6D_BEAM_EXECUTION_V1.md'):
        shutil.copyfile(Path(__file__).with_name(name),helpers/name);helper_files.append(bind(helpers/name))
    supports=dict(protocol=bind(R/'runner/native_confirmation_protocol_v2/source_epoch/s6d_runner_native_confirmation_v2.py'),evidence=bind(SIM/'scripts/s6d_native_evidence_v1.py'),native_loop=bind(R/'application/native_pilot_v3/helpers/s6d_application_native.py'))
    limits={
      'BXR1':'All6 MAIN and6 SCAN diagnostic streams are declared; compare actor-conditioned text/voice omissions to same-pass auto. Best-beam selection is oracle-only, no deployable winner claim.',
      'BXR2':'96 MAIN calls:48 matched auto controls plus48 one-auto/two-focus native sessions. Mature-only focus bridge is a composite policy, not unchanged v3 identity.',
      'BXR3':'The same48 focus sessions emit selected-person association for the two fixed original A15 IDs; C-only calibration must bind actual opportunity count before selectors enable.',
      'BXR4':'Duplicate resolution disabled. Same-C/two-person controls are collected; any later enabling requires separate adequate C duplicate/competition proof, no correlated duration sum.',
      'BXR5':'MAIN same-beam ASR/PP and SCAN auto/scanner ASR/PP each get actual per-stream native diagnostics; conditional comparisons, no universal tap winner or independent votes.',
      'BXR6':'48 SCAN six-stream diagnostics are declared; scanner speech/voice changes can be analyzed. No new online scanner-trigger policy or claims beyond48.',
      'BXR7':'Current independent focus trackers plus calibrated current association only; no claim of fully implemented cross-beam global person-state transfer or physical arrows.',
      'BXR8':'One fixed auto decoder/shared serial speaker owner, at most2 focus states. Dynamic extra ASR/segmentation with hysteresis/pre-roll remains unimplemented; no truth-triggered runtime work.',
      'BXR9':'Core uses original A15 clean15s gallery unchanged. Original B15 and matched actual device E comparisons remain separate enrollment work; no Q threshold choice.',
      'BXR10':'Per-stream clipping/levels/resources retained; sparse/unsupported AGC telemetry cannot reconstruct pre-AGC audio or become identity/quiet-speech veto.',
      'BXR11':'Per-case source state continuous only. Two physical15min sessions and beam/voice recovery after longsilence require their separately admitted actual captures; HOST concatenations do not replace DSP continuity.',
      'BXR12':'No fixed-table user-assisted contrast added here; needs separately declared angles/gating and wrong-setup/relocation controls. No oracle seat-following.'}
    result=dict(schema='s6d-beam-prospective-execution.v1',status='DECLARED_INPUT_AND_ROOT_ADMISSION_PENDING',created_utc=datetime.now(timezone.utc).isoformat(),run_id='20260913T195357Z',source_epoch=epoch,source_files=e['source_files'],source_root=e['source_root'],assets=e['assets'],support=supports,helper_files=helper_files,runner_helper=next(b for b in helper_files if Path(b['path']).name=='s6d_beam_native_run_v1.py'),fixed_panel=panel,case_ids=ids,profile_binding=profile,gallery=gallery,selected_profile_ids=selected,selected_id_rule='First two sorted original A15 opaque profile IDs before new beam/model outcomes; never select from scene truth',settings=dict(schema_version='edge-s6d.v1',text_delivery=True,boundary_repair=True,transcript_mode='T0',direction_mode='V0'),raw_model_gain=1.0,representation='Raw lossless waveforms unchanged; existing journal PCM16 conversion once at unity for every compared stream; not historical O0+3dB predictions',tasks=tasks,counts=dict(C_collection=12,main_core=96,additional_stream_diagnostics=528,total_proposed_native_calls=636,per_stream_scene_profile_cells=576,reused_same_pass_MAIN_auto_controls=48),controls_reuse='Only successful matching actual MAIN auto controls may supply48 per-stream auto cells; same WAV/model/profile/window/representation/source epoch required, no old capture cache',execution_limits=dict(serial_jobs=True,cpu_affinity=[12,13,14,15],cpu_threads_each=1,cell_timeout_sec=900,source_paced=True,no_overlap_with_active176=True,maximum_resident_stacks=1,maximum_identity_focus_states=2),budget=dict(additional_physical_passes=0,payload_cap_gib=40,minimum_c_free_gib=50,minimum_g_free_gib=75,campaign_deadline_utc='2026-09-16T19:53:57Z',closeout_reserve_s=2700,execution_allocation_pending=True),BXR_limits=limits,model_calls=0,hardware_calls=0)
    save(output/'PROSPECTIVE_PLAN.json',result);print(json.dumps(bind(output/'PROSPECTIVE_PLAN.json')))

def project(row,out):
    """Alias metadata only after exact original physical acceptance. Never bless a transport pass."""
    original=verified(row['case_result']);q=verified(row['qualification'])
    need(q.get('schema_version')=='edge-s6d-route-qualification.v1' and q.get('status')=='PASS','Root route qualification not accepted')
    need(q.get('case_result')==row['case_result'] and q.get('configuration')==original['configuration'],'Qualification belongs to another case')
    need(all(q.get(k) is True for k in ('stream_identity_verified','common_frame_origin_verified','source_tail_validity_verified')),'Required physical proof absent')
    need(original.get('status')==original.get('transport_integrity_status')=='PASS','Physical transport rejected')
    N.validate_original_identity(original,row['case_id'],row['capture_profile'])
    configuration=verified(original['configuration']);need(configuration['profile']==row['capture_profile'],'Capture profile changed')
    names=MAIN if row['capture_profile']=='P_MAIN6' else SCAN
    need([s['name'] for s in original['streams']]==names,'Exact recorded six-stream order differs')
    projected=deepcopy(original);projected.update(schema_version='s6d-original-capture-native-view.v1',original_case_result=row['case_result'],projection='Declared raw logical-name aliases only; no waveform, sample, gain, order or route changes')
    for s in projected['streams']:
        need((s['category'],s['source'])==N.ROUTES[s['name']] and s['raw_gain']==1,'Original stream route/gain differs')
        s['original_stream_name']=s['name'];s['name']=s['name'].removesuffix('_raw')
    out.mkdir(parents=True);save(out/'NATIVE_CASE_VIEW.json',projected);pb=bind(out/'NATIVE_CASE_VIEW.json')
    qp=deepcopy(q);qp.update(case_result=pb,original_qualification=row['qualification'],original_case_result=row['case_result'],stream_names=[n.removesuffix('_raw') for n in q['stream_names']],projection='Logical-name aliases only; all physical decisions inherited unchanged')
    save(out/'NATIVE_QUALIFICATION_VIEW.json',qp)
    import soundfile as sf
    frames=sf.info(original['streams'][0]['audio']['path']).frames
    admission=dict(schema_version='edge-s6d-capture-admission.v1',status='ACCEPTED_FOR_NATIVE_ANALYSIS',original_case_result=row['case_result'],original_qualification=row['qualification'],case_result=pb,qualification=bind(out/'NATIVE_QUALIFICATION_VIEW.json'),configuration=original['configuration'],capture_source_id=row['case_result']['sha256'],route_id=original['configuration']['sha256'],capture_epoch='20260913T195357Z',common_origin='unchanged_shared_native_capture_frame',sample_count=frames,stream_names=[n.removesuffix('_raw') for n in names],direction_observations=None)
    if row.get('calibration_partition'):
        cp=verified(row['calibration_partition']);need(cp.get('partition')=='C' and cp.get('Q_used') is False and cp.get('disjoint_from_E_Q_verified') is True and row['case_result'] in cp.get('accepted_case_results',[]),'Actual disjoint-C partition missing')
        cp=deepcopy(cp);cp.update(original_partition=row['calibration_partition'],accepted_case_results=[pb],projection='One exact accepted case with unchanged audio and declared stream aliases')
        save(out/'NATIVE_C_PARTITION_VIEW.json',cp);admission['calibration_partition']=bind(out/'NATIVE_C_PARTITION_VIEW.json')
    save(out/'CAPTURE_ADMISSION.json',admission);return bind(out/'CAPTURE_ADMISSION.json'),original

def bind_stage(plan_path,catalog_path,stage,output,calibration_path=None):
    plan_ref=bind(plan_path);p=verified(plan_ref);cat_ref=bind(catalog_path);cat=verified(cat_ref)
    need(cat.get('schema')=='s6d-native-capture-catalog.v1' and cat.get('status')=='ROOT_ACCEPTED_CASES','Actual root-accepted capture catalog required')
    selected=[t for t in p['tasks'] if t['stage']==stage];need(selected,'Unknown/empty stage')
    rows={(r['case_id'],r['capture_profile']):r for r in cat['rows']};need(len(rows)==len(cat['rows']),'Duplicate admitted case/profile')
    missing=sorted({(t['case_id'],t['capture_profile']) for t in selected}-set(rows));need(not missing,'Missing declared captures; no silent panel shrinking: '+repr(missing))
    out=Path(output).resolve();need(not out.exists() and out.is_relative_to(R/'application'),'Fresh application preparation epoch required');out.mkdir(parents=True)
    payload=G/'application'/out.name;need(not payload.exists(),'Native payload occupied')
    calibration=bind(calibration_path) if calibration_path else None
    if stage=='main_core':need(calibration and verified(calibration).get('status')=='ACCEPTED_C_ONLY','Reviewed C-only selector calibration required')
    jobs=[];case_cache={};proof_cache={}
    for t in selected:
        key=(t['case_id'],t['capture_profile']);row=rows[key]
        if key not in case_cache:case_cache[key]=project(row,out/'captures'/(key[1]+'_'+key[0]))
        admission,original=case_cache[key];actual={s['name']:s for s in original['streams']}
        names=[t['asr_raw_stream']] if t['mode'] in ('same_pass_auto_control','stream_diagnostic') else ['auto_asr_raw','focus0_asr_raw','focus1_asr_raw']
        proofs={}
        for name in names:
            audio=actual[name]['audio'];cache_key=(audio['path'],audio['sha256'])
            if cache_key not in proof_cache:proof_cache[cache_key]=N.journal_representation(audio)
            proofs[name]=proof_cache[cache_key]
        frames=proofs[names[0]]['frames'];need(all(x['frames']==frames for x in proofs.values()),'Unequal captured full stream lengths')
        bsettings=dict(schema_version='edge-s6d-beams.v1',mode=t['mode'],asr_stream='auto_asr',identity_streams=['auto_asr'] if t['mode']=='same_pass_auto_control' else ['focus0_asr','focus1_asr'],selected_profile_ids=p['selected_profile_ids'],maximum_evidence_age_sec=.75,calibration=calibration if t['mode']=='mono_asr_beam_identity' else None)
        jobdir=out/'jobs'/t['job_id'];jobdir.mkdir(parents=True)
        save(jobdir/'S6D_SETTINGS.json',p['settings'])
        if t['mode']!='stream_diagnostic':save(jobdir/'BEAM_SETTINGS.json',bsettings)
        j=dict(t,admission=admission,profile_binding=p['profile_binding'],profile=verified(p['profile_binding']),gallery=p['gallery'],settings=p['settings'],s6d_settings=bind(jobdir/'S6D_SETTINGS.json'),beam_settings=bind(jobdir/'BEAM_SETTINGS.json') if t['mode']!='stream_diagnostic' else None,stream_proofs=proofs,expected_frames=frames,expected_identity_frames=frames,audio=actual[names[0]]['audio'],audio_pcm_sha256=proofs[names[0]]['sha256'],audio_duration_sec=frames/16000,output=str(payload/t['job_id']),telemetry=None)
        if t['mode']=='calibration_collection':need(row.get('calibration_partition') is not None,'C proof required before collection')
        jobs.append(j)
    result=dict(schema='s6d-beam-execution.v1',status='FROZEN_PENDING_SOURCE_PROTOCOL_AND_ROOT_REVIEW',run_id=p['run_id'],declaration=plan_ref,capture_catalog=cat_ref,runner_helper=p['runner_helper'],support=p['support'],source_root=p['source_root'],source_files=p['source_files'],assets=p['assets'],limits=p['execution_limits'],jobs=jobs,job_count=len(jobs),stage=stage,model_calls=0,hardware_calls=0)
    save(out/'MANIFEST.json',result);print(json.dumps(bind(out/'MANIFEST.json')))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);sp=a.add_subparsers(dest='cmd',required=True)
    d=sp.add_parser('declare');d.add_argument('--output',type=Path,required=True)
    b=sp.add_parser('bind');b.add_argument('--plan',type=Path,required=True);b.add_argument('--catalog',type=Path,required=True);b.add_argument('--stage',choices=['C_collection','main_core','stream_diagnostics'],required=True);b.add_argument('--output',type=Path,required=True);b.add_argument('--calibration',type=Path)
    x=a.parse_args();declare(x.output) if x.cmd=='declare' else bind_stage(x.plan,x.catalog,x.stage,x.output,x.calibration)
