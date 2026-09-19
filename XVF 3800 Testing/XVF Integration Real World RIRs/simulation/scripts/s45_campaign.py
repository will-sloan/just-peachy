"""Finite single-owner S4.5 capture coordinator; README_S45.md."""
import argparse, ctypes, subprocess, sys
from s45_common import *

def receipts():
    return [(p,read(p)) for p in sorted(HARDWARE.glob('*/*/case_result.json')) if p.parent.name!='transport_regression']

def acceptance_errors(row,scene,contract,manifest_sha,policy):
    errors=[]
    for key,expected in [('status','PASS'),('audio_integrity_status','PASS'),('telemetry_status','PASS'),('final_recipe_capture',True),('recipe',policy['hardware_recipe']),('input_scene_sha256',scene['canonical_audio']['sha256']),('split',scene['split'])]:
        if row.get(key)!=expected:errors.append(key)
    if row.get('payload',{}).get('status')!='PASS':errors.append('payload')
    if row.get('reserve_task_scored') is not False:errors.append('reserve_task_scored')
    if contract.get('scene_manifest_sha256')!=manifest_sha:errors.append('scene_manifest')
    if contract.get('code_key')!=row.get('code_key'):errors.append('batch_code_key')
    if contract.get('recipe')!=policy['hardware_recipe'] or contract.get('final_recipe_capture') is not True:errors.append('batch_recipe')
    return errors

def selected_snapshot(manifest,reference=False):
    mb=bind(BANK/('REFERENCE_SCENE_MANIFEST.json' if reference else 'SCENE_MANIFEST.json'));policy=read(REPORT/'OUTPUT_LEVEL_POLICY.json')
    scenes={s['case_id']:s for s in manifest['scenes']};items=[];failed=[];chosen={};inflight={}
    current=receipts();counts={}
    for _,r in current:counts[r['case_id']]=counts.get(r['case_id'],0)+1
    for path,r in current:
        cid=r['case_id']
        if cid not in scenes:continue
        assert r['input_scene_sha256']==scenes[cid]['canonical_audio']['sha256']
        if r.get('status')=='STARTING':
            inflight[cid]={'case_id':cid,'status':'RUNNING','split':scenes[cid]['split'],'attempts':counts.get(cid,0)}
            continue
        contract=read(path.parent.parent/'batch_contract.json')
        errors=acceptance_errors(r,scenes[cid],contract,mb['sha256'],policy)
        if not errors:
            assert cid not in chosen,'Multiple accepted canonical attempts; selection must be explicit'
            chosen[cid]={'case_id':cid,'folder':str(path.parent),'case_result':bind(path),'input_scene_sha256':r['input_scene_sha256'],'code_key':r['code_key'],'split':scenes[cid]['split'],'audio_valid':True,'telemetry_valid':True,'task_scoring_allowed':False if reference else scenes[cid]['split']=='development','excluded_from_240':reference}
        else:
            assert r.get('status')!='PASS','PASS receipt violates frozen acceptance contract: '+cid+' '+str(errors)
            failed.append({'case_id':cid,'case_result':bind(path),'status':r.get('status'),'audio_valid':r.get('audio_integrity_status')=='PASS','telemetry_valid':r.get('telemetry_status')=='PASS','error':r.get('error'),'acceptance_failures':errors})
    for cid,scene in scenes.items():
        items.append(chosen.get(cid,inflight.get(cid,{'case_id':cid,'status':'PENDING','split':scene['split'],'attempts':counts.get(cid,0)})))
    output={'schema':'jp_s45_reference_captures_v1' if reference else 'jp_s45_accepted_captures_v1','updated_utc':now(),'reference_scene_manifest' if reference else 'scene_manifest':mb,'accepted':list(chosen.values()),'failed_attempts':failed,'rows':items,'accepted_count':len(chosen),'pending_count':len(scenes)-len(chosen),'in_progress_count':len(inflight),'reserve_task_scored':False,'excluded_from_240':reference}
    save(REPORT/('REFERENCE_CAPTURES.json' if reference else 'ACCEPTED_CAPTURES.json'),output);return output

def validate_restorations():
    from s45_hardware import verify_prior_restorations
    return verify_prior_restorations()

REPRESENTATIVES=['S45_01_02','S45_01_03','S45_01_05','S45_01_06','S45_01_08','S45_01_09']

def representative_levels(snapshot):
    import soundfile as sf
    from s4_h2_analysis import rail_metrics
    selected={r['case_id']:r for r in snapshot['accepted']};rows=[]
    assert all(cid in selected for cid in REPRESENTATIVES)
    for cid in REPRESENTATIVES:
        metrics={};item=selected[cid]
        receipt=read(item['case_result']['path'])
        bind(item['case_result']['path'],item['case_result']['sha256'])
        for stream in ['O0','O1']:
            path=Path(item['folder'])/(stream+'.wav');output_binding=bind(path,receipt['output_audio'][stream]['sha256'])
            x,rate=sf.read(path,dtype='int32');assert rate==16000 and x.ndim==1
            value=rail_metrics(x>>8);gross=value['maximum_contiguous_rail_run_samples']>=1600 or value['rail_samples']/max(1,value['sample_count'])>=.01
            metrics[stream]={'binding':output_binding,'level':value,'gross_saturation':bool(gross)}
        rows.append({'case_id':cid,'case_result':item['case_result'],'streams':metrics})
    proceed=not any(r['streams']['O0']['gross_saturation'] for r in rows)
    save(REPORT/'REPRESENTATIVE_LEVEL_CHECK.json',{'status':'PASS_WITH_OUTPUT_LIMITS' if proceed else 'BLOCKED_GROSS_O0','created_utc':now(),'cases':rows,'code':bind(Path(__file__)),'manifest':bind(BANK/'SCENE_MANIFEST.json'),'policy':bind(REPORT/'OUTPUT_LEVEL_POLICY.json'),'selection':'Predeclared nominal and +6 dB matched F01 controls across three corpus groups','rule':'Gross O0 stops expansion; gross O1 is retained but quarantined for task use. Residual rails are LIMITED. No gain or source selection is tuned from outputs.','hardware_recipe_unchanged':True,'H2_executed':False})
    return proceed

def verify_representative_gate(snapshot):
    gate=read(REPORT/'REPRESENTATIVE_LEVEL_CHECK.json');assert gate['status']=='PASS_WITH_OUTPUT_LIMITS'
    for key,path in [('code',Path(__file__)),('manifest',BANK/'SCENE_MANIFEST.json'),('policy',REPORT/'OUTPUT_LEVEL_POLICY.json')]:bind(path,gate[key]['sha256'])
    selected={r['case_id']:r for r in snapshot['accepted']}
    assert [r['case_id'] for r in gate['cases']]==REPRESENTATIVES
    for row in gate['cases']:assert row['case_result']['sha256']==selected[row['case_id']]['case_result']['sha256']
    return gate

def run(reference=False):
    manifest=read(BANK/('REFERENCE_SCENE_MANIFEST.json' if reference else 'SCENE_MANIFEST.json'));assert manifest['validation']['status']=='PASS'
    if reference:assert read(REPORT/'ACCEPTED_CAPTURES.json')['accepted_count']==240,'All 240 canonical captures take priority'
    total=len(manifest['scenes'])
    order=[s['case_id'] for s in manifest['scenes']]
    # Six nominal/louder different-corpus representatives first, then sentinels,
    # then remaining development and reserve. Inputs/policies stay frozen.
    reps=[] if reference else REPRESENTATIVES
    sent=[] if reference else read(REPORT/'SENTINEL_PLAN.json')['scene_ids']
    order=list(dict.fromkeys(reps+sent+order))
    keep_awake=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    assert keep_awake,'Failed to establish scoped system keep-awake'
    save(REPORT/'keep_awake.json',{'active':True,'started_utc':now(),'scope':'S4.5 coordinator process thread; system-required only, prior state restored in finally'})
    reason=None;failure_streak=0;before_good=0;child=None
    try:
        while launch_allowed(180):
            check_storage();validate_restorations();snap=selected_snapshot(manifest,reference)
            chosen={x['case_id'] for x in snap['accepted']};attempt_counts=collections_counter()
            if len(chosen)>before_good:failure_streak=0
            before_good=len(chosen)
            pending=[cid for cid in order if cid not in chosen and attempt_counts.get(cid,0)<2]
            if not pending:break
            if reference and not launch_allowed(sum(s['duration_s']+45 for s in manifest['scenes'] if s['case_id'] in pending)+2700):reason='OPTIONAL_REFERENCE_SKIPPED_TO_PRESERVE_ANALYSIS';break
            if failure_streak>=3:reason='THREE_CONSECUTIVE_SYSTEMIC_FAILURES';break
            if (REPORT/'STOP_REQUEST.json').exists():reason='WATCHDOG_OR_USER_STOP';break
            ledger=read(REPORT/'physical_ledger.json')
            if len(ledger['passes'])>=320 or sum(x['charged_playback_s'] for x in ledger['passes'])>=16200:reason='PHYSICAL_BUDGET';break
            batch=('references_' if reference else 'canonical_')+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]
            # First use six controls for measured overhead/level review.
            todo=pending
            if not reference and not (REPORT/'REPRESENTATIVE_LEVEL_CHECK.json').exists():
                todo=[cid for cid in reps if cid not in chosen and attempt_counts.get(cid,0)<2]
                if not todo:
                    if not all(cid in chosen for cid in reps):reason='REPRESENTATIVE_CAPTURE_INCOMPLETE';break
                    if not representative_levels(snap):reason='REPRESENTATIVE_LEVEL_GATE';break
                    todo=pending
            elif not reference:verify_representative_gate(snap)
            args=[str(RECORDER_PYTHON),str(SIM/'scripts/s45_hardware.py'),'--batch',batch,'--cases',*todo,'--recipe','limiter_and_agc_headroom','--final']
            logs=REPORT/'campaign_logs';logs.mkdir(exist_ok=True)
            started=time.monotonic()
            with (logs/(batch+'.log')).open('w',encoding='utf-8') as log:
                child=subprocess.Popen(args,cwd=SIM/'scripts',env=single_thread_env(),stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                save(REPORT/'owned_process.json',{'pid':child.pid,'argv':args,'started_utc':now(),'stage':'physical','hardware_owner':'child only'})
                while child.poll() is None:
                    if not launch_allowed(90):save(REPORT/'STOP_REQUEST.json',{'reason':'Preserve30-minute closing reserve','utc':now()})
                    snap=selected_snapshot(manifest,reference)
                    ledger=read(REPORT/'physical_ledger.json')
                    done=len(snap['accepted']);wall=elapsed_s();active=sum(x['charged_playback_s'] for x in ledger['passes'])
                    statuses=[read(p) for p in (REPORT/'progress').glob('hardware_*.json')]
                    latest=max(statuses,key=lambda r:r['updated_utc']) if statuses else None
                    save(REPORT/'status.json',{'stage':'OPTIONAL_REFERENCE_CAPTURE' if reference else 'PHYSICAL_CAPTURE','status':'RUNNING','updated_utc':now(),'rendered':240,'accepted':240 if reference else done,'pending':0 if reference else total-done,'optional_reference_accepted':done if reference else 0,'failed_attempts':len(snap['failed_attempts']),'physical_passes':len(ledger['passes']),'active_playback_s':active,'elapsed_s':wall,'deadline_remaining_s':remaining_s(),'hardware_progress':latest,'ssd':storage(),'reserve_task_scored':False})
                    time.sleep(20)
                code=child.returncode
            validate_restorations();after=selected_snapshot(manifest,reference);new_good=after['accepted_count']-before_good
            save(REPORT/'campaign_logs'/(batch+'.json'),{'argv':args,'exit_code':code,'elapsed_s':time.monotonic()-started,'new_accepted':new_good,'restore_verified':True})
            save(REPORT/'owned_process.json',{'pid':None,'closed_utc':now(),'exit_code':code,'hardware_owner':None})
            if code:
                failure_streak=1 if new_good else failure_streak+1
                results=read(HARDWARE/batch/'hardware_summary.json')
                if any(r.get('payload',{}).get('status')=='FAIL' for r in results.get('cases',[])):reason='CORRUPT_TRANSPORT';break
                if 'Deadline' in (results.get('error') or ''):reason='TIME_BUDGET';break
            else:failure_streak=0
            before_good=after['accepted_count']
    except BaseException as e:
        reason=repr(e);save(REPORT/'campaign_error.json',{'error':reason,'utc':now()});raise
    finally:
        if child is not None and child.poll() is None:
            save(REPORT/'STOP_REQUEST.json',{'reason':'Coordinator cleanup requests finite owner stop','utc':now()})
            try:child.wait(timeout=240)
            except subprocess.TimeoutExpired:reason='OWNER_STOP_TIMEOUT_DO_NOT_CLAIM_RELEASE'
        owner_closed=child is None or child.poll() is not None
        ctypes.windll.kernel32.SetThreadExecutionState(keep_awake)
        save(REPORT/'keep_awake.json',{'active':False,'released_utc':now(),'prior_state_restored':True,'prior_flags':keep_awake})
        restoration='UNVERIFIED_ACTIVE_OWNER'
        if owner_closed:
            save(REPORT/'owned_process.json',{'pid':None,'closed_utc':now(),'exit_code':child.returncode if child else None,'hardware_owner':None})
            try:validate_restorations();restoration='PASS'
            except BaseException as e:reason=repr(e);restoration='UNVERIFIED'
        snap=selected_snapshot(manifest,reference)
        status='CAPTURE_COMPLETE' if snap['accepted_count']==total and restoration=='PASS' else 'PARTIAL_TIME_BUDGET' if not launch_allowed() else 'BLOCKED'
        receipt_path=REPORT/('reference_campaign_receipt.json' if reference else 'campaign_receipt.json')
        save(receipt_path,{'status':status,'reason':reason,'accepted':snap['accepted_count'],'pending':snap['pending_count'],'failed_attempts':len(snap['failed_attempts']),'elapsed_s':elapsed_s(),'ended_utc':now(),'restoration':restoration,'hardware_owner':None if owner_closed else child.pid,'reserve_task_scored':False,'excluded_from_240':reference})
        print(json.dumps(read(receipt_path),indent=2))

def collections_counter():
    import collections
    return collections.Counter(r['case_id'] for _,r in receipts())

if __name__=='__main__':
    run()
    if read(REPORT/'campaign_receipt.json')['status']=='CAPTURE_COMPLETE' and (BANK/'REFERENCE_SCENE_MANIFEST.json').exists():run(reference=True)
