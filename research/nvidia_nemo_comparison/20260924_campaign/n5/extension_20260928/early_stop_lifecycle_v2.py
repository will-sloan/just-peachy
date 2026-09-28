"""Isolated nemotron saved-file lifecycle. See README_EARLY_STOP_V2.md."""
import argparse
import ctypes as C
from dataclasses import replace
import traceback
import hashlib
import wave
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import time

CODE = Path(__file__).resolve().parent
HERE = CODE.parent
sys.path.append(str(HERE/'prepi_20260928'))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent/'n4'))
from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from private_application_two_cpu_v1 import PrivateApplicationProcess, api, checked


def require(value, message):
    if not value: raise ValueError(message)


def checked_inputs(path):
    a=load(path)
    require(a['scope']=='EXTENDED_WINDOWS_STOP_NEW_RESTART_V2','Wrong window scope')
    for row in a['code']+a['release_files']+a['assets']+[a['audio'],a['source_receipt'],a['acceptance'],a['census'],a['window']]+a['runtime_configs']:verify(row)
    from window_guard import window
    window()
    require(a['backend_key'] in ('nemotron_hybrid','nemotron_600m'),'Unadmitted backend')
    require(a['mode']=='anonymous_conversation' and a['arm']=='parent','Only E0 mode admitted')
    require(a['application_cpus']==[4,14] and a['numerical_threads_per_model']==1,'CPU contract differs')
    require(load(a['acceptance']['path'])['status']=='ACCEPTED_N3_OFFLINE_COMPONENT_SCOPE','N3 acceptance missing')
    d=load(a['source_receipt']['path'])
    require(d['schema']=='prepi-e0-runtime-derivative-v1' and d['parent_source_receipt']==a['parent_source_receipt'],'Shutdown ancestry differs')
    verify(a['parent_source_receipt']);verify(a['accepted_source_receipt'])
    shutdown=load(a['parent_source_receipt']['path'])
    require(shutdown['schema']=='prepi-shutdown-derivative-v1','Shutdown ancestry absent')
    stable=shutdown['parent_source_receipt'];verify(stable)
    require(load(stable['path'])['parent_source_receipt']==a['accepted_source_receipt'],'Accepted ancestry differs')
    runtime=next(row for row in a['runtime_configs'] if Path(row['path']).name=='n2_runtime.json')
    require(not {'titanet_manifest','titanet_manifest_sha256','embedding_namespace'} & set(load(runtime['path'])),'Retired E1 dependency remains in selected runtime')
    require(d['changed_code']==['app/controller.py','app/n2_models.py'],'Unexpected source mutation')
    verify(a['shadow_reference_review']);verify(a['shadow_reference_result'])
    reviewed=load(a['shadow_reference_review']['path'])
    require(reviewed['status']=='PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY' and reviewed['backend_key']==a['backend_key'],'Ungated reference not reviewed')
    require(reviewed['phases'][0]['result']==a['shadow_reference_result'],'Reference phase binding differs')
    return a


def desktop_name():
    kernel,user=api()
    kernel.GetCurrentThreadId.restype=C.c_ulong
    user.GetThreadDesktop.argtypes=[C.c_ulong]; user.GetThreadDesktop.restype=C.c_void_p
    handle=checked(user.GetThreadDesktop(kernel.GetCurrentThreadId()))
    buffer=C.create_unicode_buffer(256); needed=C.c_ulong()
    checked(user.GetUserObjectInformationW(handle,2,buffer,C.sizeof(buffer),C.byref(needed)))
    return buffer.value


def acceptance(result, lifetime):
    require(result.get('status') == 'PASS_NEMOTRON_PHASE', 'Phase incomplete')
    require(result.get('controller_closed') is True and result.get('worker_alive') is False
            and result.get('lock_released') is True and not result.get('errors'), 'Application did not close cleanly')
    require(result.get('rendered_rows',0)>0 and result.get('saved_audio_only') is True
            and result.get('sentinel_preserved') is True, 'Missing functional evidence')
    require(result.get('phase') in ('infer','reopen') and result.get('stored_rows',0)>0,'Missing persisted rows')
    require(result.get('pages')==[dict(requested=p,actual=p) for p in ('modes','backends','sessions','settings')], 'Navigation incomplete')
    require(result['phase']!='reopen' or result.get('test_session_deleted') is True,'Deletion unverified')
    require(result.get('backend_id','').startswith('sha256:') and result.get('mode') in ('caption_only','anonymous_conversation'),'Backend scope absent')
    if result['phase']=='infer':
        require(result.get('source_samples')==result.get('expected_samples')==result.get('asr_samples')
                and result.get('expected_samples',0)>0 and result.get('writers_drained') is True,'Incomplete sample/drain evidence')
        if result['mode']=='anonymous_conversation':
            require(result.get('identity_samples')==result['expected_samples'] and result.get('speaker_lag_sec')==0,'D1 did not finish')
    require(lifetime.get('status')=='OWNED_PROCESS_LIFETIME_CLOSED' and lifetime.get('forced') is False
            and lifetime.get('job_empty_verified') is True and lifetime.get('root_exit_code')==0
            and lifetime.get('observed_members_exited') is True, 'Process closure failed')


def bypass_acceptance(result, arm, reference=None):
    require(result['model_cache']['asr_loads']==1, 'ASR was not loaded once')
    t=result['telemetry']
    if arm=='candidate':
        require(result['model_cache']['speaker_loads']==0 and t['n2_embedding_calls']==0,
                'External encoder was loaded or called')
        require(t.get('n2_embedding_policy')=='BYPASSED_ANONYMOUS_NATIVE_SLOTS', 'Bypass policy absent')
        require(reference is not None, 'Paired parent evidence absent')
        for key in ('expected_samples','source_samples','asr_samples','identity_samples','speaker_lag_sec',
                    'activity_frame_count','activity_fingerprint','caption_fingerprint','stored_caption_fingerprint'):
            require(result[key]==reference[key], 'Paired parity differs: '+key)
    else:
        require(arm=='parent' and result['model_cache']['speaker_loads']==1 and t['n2_embedding_calls']>0,
                'Parent did not exercise the encoder')
    require(result['activity_frame_count']>0 and len(t['n2_seen_slots'])>=2, 'Native activity absent')


def child(admission, output, phase, expected_desktop):
    require(not output.exists(), 'Fresh phase output required'); output.mkdir()
    errors=[]; result=dict(phase=phase,errors=errors); controller=ui=root=None
    # Child diagnostics are private; no transcript is emitted to the caller.
    with (output/'stdout.log').open('x',encoding='utf-8') as out, (output/'stderr.log').open('x',encoding='utf-8') as err:
        sys.stdout=out; sys.stderr=err
        try:
            require(desktop_name()==expected_desktop and expected_desktop.startswith('codex-n1-n4-'), 'Private desktop mismatch')
            a=checked_inputs(admission); release=Path(a['release']); data=Path(a['data'])
            import psutil
            process=psutil.Process()
            require(process.ppid()==a['owner']['pid'] and exact_process(a['owner']) is not None
                    and process.cpu_affinity()==[4,14],'Admitted parent or child CPU differs')
            registration=load(output.parent/(phase+'-OWNER.json'))
            require(registration['owner']==identity(process),'Child identity differs from registered owner')
            require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Child admission expired')
            sys.path[:0]=[str(release),str(release/'vendor')]
            import app.controller
            import app.pipeline
            from shadow_gate_v1 import install
            shadow_observers=install(app.pipeline) if phase=='infer' else []
            from app.controller import Controller
            from app.ui import PrototypeUI,prepare_dpi_awareness
            import tkinter as tk
            require(Path(app.controller.__file__).resolve()==release/'app/controller.py','Wrong application import')
            if phase=='infer':
                require(not data.exists(),'Fresh isolated data required'); data.mkdir()
                for item in a['runtime_configs']: shutil.copyfile(item['path'],data/Path(item['path']).name)
                (data/'people').mkdir(); (data/'people/SYNTHETIC_SENTINEL.txt').write_bytes(b'N5 isolated preservation fixture\n')
            sentinel=bind(data/'people/SYNTHETIC_SENTINEL.txt')
            require(sentinel['sha256']==a['sentinel_sha256'],'Sentinel changed before phase')
            prepare_dpi_awareness(); controller=Controller(data,Path(a['models']),saved_audio_only=True)
            controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
            root=tk.Tk(); root.report_callback_exception=lambda kind,value,tb:errors.append(''.join(traceback.format_exception(kind,value,tb)))
            ui=PrototypeUI(root,controller,allow_auto_start=False)
            deadline=time.monotonic()+240
            def pump(until):
                while not until():
                    require(time.monotonic()<deadline,'Phase deadline reached')
                    require(not (output.parent/'CANCEL').exists()
                            and not (output.parent/(phase+'-lifetime')/'CANCEL').exists(),'Parent cancelled')
                    require(not errors,'Tk callback failed')
                    require(not controller.error,'Controller reported error: '+str(controller.error))
                    root.update(); time.sleep(.02)
            def command(action,**values):
                controller.session_action(action,**values)
                pump(lambda:controller.commands.unfinished_tasks==0)
            root.update(); result['client']=ui.measure_client()
            require((result['client']['physical_width'],result['client']['physical_height'])==(480,800),'Client dimensions differ')
            from app.backends import backend_catalog
            selected=next(row['id'] for row in backend_catalog() if row['key']==a['backend_key'])
            controller.select_backend(selected); pump(lambda:controller.commands.unfinished_tasks==0)
            require(controller.snapshot()['backend_id']==selected,'Wrong selected backend')
            result.update(backend_id=selected,mode=a['mode'],source=bind(release/'app/n3_pipeline.py'))
            if phase=='infer':
                controller.switch(mode=a['mode'],recipe='fast' if a['mode']=='caption_only' else 'balanced',tap='O0')
                pump(lambda:controller.commands.unfinished_tasks==0)
                # First epoch: explicit user-style Stop while the source is still arriving.
                controller.start_file(a['audio']['path']); pump(lambda:controller.commands.unfinished_tasks==0)
                early_engine=controller.engine; require(early_engine is not None,'Early epoch absent')
                with wave.open(a['audio']['path'],'rb') as wav: full_samples=wav.getnframes()
                require(full_samples>16*16000,'Early-Stop fixture must exceed 16 seconds')
                pump(lambda:early_engine._journal.committed_samples>=8*16000)
                before_stop=early_engine._journal.committed_samples
                require(before_stop<full_samples,'Source already ended before Stop')
                early_identifier=controller.conversation_id
                requested_at=time.monotonic(); controller.stop()
                pump(lambda:controller.commands.unfinished_tasks==0 and controller.state=='STOPPED')
                early=early_engine.telemetry(); early_samples=early_engine._journal.committed_samples
                early_asr=(early['n3_input_samples'] if a['backend_key']=='nemotron_600m' else round(early['asr_cursor_sec']*16000))
                require(0<early_samples<full_samples,'Early Stop did not truncate source delivery')
                require(early_asr==early_samples==early['identity_audio_samples'],'Early epoch failed to drain accepted samples')
                require(early['speaker_lag_sec']==0,'Early speaker lane did not drain')
                require(all(w.accepted==w.completed and not w.error for w in early_engine.text_writers),'Early writers did not drain')
                require(controller.engine is None and controller.consumer is None,'Early epoch ownership retained')
                require(not early.get('live_lanes_at_finalization') and not early.get('bundle_retained_due_live_lanes'),'Early native lane retained')
                cleanup=controller.metrics.get('last_worker_cleanup',{})
                require(cleanup.get('owned_threads_joined') is True,'Early worker cleanup unverified')
                require(len(shadow_observers)==1,'Early source observation absent')
                early_shadow=shadow_observers[0].report()
                with wave.open(a['audio']['path'],'rb') as wav:
                    early_pcm=hashlib.sha256(wav.readframes(early_samples)).hexdigest()
                require(early_shadow['samples']==early_samples and early_shadow['source_pcm_sha256']==early_pcm,'Early prefix differs')
                require(early_shadow['actually_skipped_samples']==0,'Early observer skipped audio')
                result['early_stop']=dict(requested_after_samples=before_stop,source_samples=early_samples,
                    asr_samples=early_asr,identity_samples=early['identity_audio_samples'],
                    full_file_samples=full_samples,speaker_lag_sec=early['speaker_lag_sec'],
                    stop_to_drained_sec=time.monotonic()-requested_at,workers_joined=True,
                    accepted_prefix_sha256=early_pcm,actually_skipped_samples=0,
                    completed_sessions=controller.metrics.get('completed_sessions',0),
                    telemetry=early,cleanup=cleanup)
                require(controller.session_store.folder(early_identifier).exists(),'Early session archive absent')
                early_rows_hash=fingerprint(controller.session_store.rows(early_identifier))
                freeze(output/'EARLY_SESSION.json',dict(identifier=early_identifier,rows_fingerprint=early_rows_hash))
                command('new',audio=False,consent=False)
                require(controller.conversation_id!=early_identifier,'New transcript did not change conversation')
                require(not controller.snapshot()['rows'],'New transcript retained old visible rows')
                require(fingerprint(controller.session_store.rows(early_identifier))==early_rows_hash,'New transcript changed earlier draft')
                result['early_stop']['explicit_new_transcript']=True
                result['early_stop']['earlier_draft_preserved']=True
                prior_completed=controller.metrics.get('completed_sessions',0)
                # Second epoch: explicit start_file restarts at sample zero with cached models.
                controller.start_file(a['audio']['path']); pump(lambda:controller.commands.unfinished_tasks==0)
                engine=controller.engine; require(engine is not None,'No running engine')
                pump(lambda:controller.metrics.get('completed_sessions',0)>=prior_completed+1 and controller.state=='STOPPED'
                     and controller.commands.unfinished_tasks==0)
                require(controller.snapshot()['rows'],'No actual captions')
                telemetry=engine.telemetry()
                frames=[[start,end,list(active)] for start,end,active,_ in engine._n2_timeline.frames]
                require(frames and frames[0][0]==0, 'Full short-file activity was not retained')
                result.update(activity_frame_count=len(frames),activity_fingerprint=fingerprint(frames))
                with wave.open(a['audio']['path'],'rb') as wav: expected_samples=wav.getnframes()
                require(engine._journal.committed_samples==expected_samples,'Source samples incomplete')
                asr_samples=(telemetry['n3_input_samples'] if a['backend_key']=='nemotron_600m' else round(telemetry['asr_cursor_sec']*16000))
                require(asr_samples==expected_samples,'ASR samples incomplete')
                require(all(w.accepted==w.completed and not w.error for w in engine.text_writers),'Writers did not drain')
                if a['mode']=='anonymous_conversation':
                    require(telemetry['identity_audio_samples']==expected_samples and telemetry['speaker_lag_sec']==0,'D1 samples incomplete')
                result.update(expected_samples=expected_samples,source_samples=engine._journal.committed_samples,
                    asr_samples=asr_samples,identity_samples=telemetry.get('identity_audio_samples'),
                    speaker_lag_sec=telemetry.get('speaker_lag_sec'),writers_drained=True,telemetry=telemetry)
                identifier=controller.conversation_id
                command('save',identifier=identifier)
                require(controller.session_store.metadata(identifier)['pinned'] is True,'Save did not pin')
                stored=controller.session_store.rows(identifier)
                require(stored,'Empty saved transcript')
                freeze(output/'SAVED.json',dict(identifier=identifier,rows_fingerprint=fingerprint(stored),rows=len(stored),sentinel=sentinel))
            else:
                prior=load(output.parent/'infer/SAVED.json'); identifier=prior['identifier']
                stored=controller.session_store.rows(identifier)
                require(fingerprint(stored)==prior['rows_fingerprint'],'Saved rows changed across process restart')
                require(controller.session_store.metadata(identifier)['pinned'] is True,'Saved pin lost on restart')
                command('open',identifier=identifier)
                require(controller.opened_conversation==identifier,'Open did not select saved session')
            rows=controller.snapshot()['rows']; require(rows,'Opened view is empty')
            # Observe the real GUI poll/render path. This is Tk text evidence, not scanout/touch timing.
            pump(lambda:ui._render_order==[r['id'] for r in rows] and
                 all(ui._display_row(r)[1] in ui.caption_text.get('1.0','end-1c') for r in rows))
            result['rendered_rows']=len(rows); result['stored_rows']=len(stored)
            result['caption_fingerprint']=fingerprint([list(ui._display_row(r)) for r in rows])
            # Persist original private rows for independent semantic audit; never publish transcripts.
            freeze(output/'CAPTION_SEMANTICS.json',dict(display=[list(ui._display_row(r)) for r in rows],stored=stored))
            result['stored_caption_fingerprint']=fingerprint([
                {k:r.get(k) for k in ('text','display_text','source_start_sec','source_end_sec')} for r in stored])
            result['pages']=[]
            for page,show in [('modes',ui.show_modes),('backends',ui.show_backends),('sessions',ui.show_sessions),('settings',ui.show_settings)]:
                show(); root.update(); result['pages'].append(dict(requested=page,actual=ui.page))
                require(ui.page==page,'Navigation failed: '+page)
            if phase=='reopen':
                command('delete',identifier=identifier,confirmed=True)
                require(not controller.session_store.folder(identifier).exists(),'Test session not deleted')
                result['test_session_deleted']=True
                earlier=load(output.parent/'infer/EARLY_SESSION.json')
                require(fingerprint(controller.session_store.rows(earlier['identifier']))==earlier['rows_fingerprint'],'Earlier draft changed across restart')
                command('delete',identifier=earlier['identifier'],confirmed=True)
                require(not controller.session_store.folder(earlier['identifier']).exists(),'Early test session not deleted')
                result['early_test_session_deleted']=True
            require(bind(data/'people/SYNTHETIC_SENTINEL.txt')==sentinel,'Session operation altered people fixture')
            result.update(sentinel_preserved=True,saved_audio_only=controller.saved_audio_only,
                output_observations=controller.output_defaults,model_cache=controller.snapshot()['metrics'].get('model_cache'))
            require(all(r.get('status')=='DISABLED_SAVED_AUDIO_ONLY' for r in controller.output_defaults),'Audio enumeration was not disabled')
            if phase=='infer':
                reference=load(a['reference_inputs'][1]['path']) if a['arm']=='candidate' else None
                bypass_acceptance(result,a['arm'],reference)
                result['paired_parity_passed']=a['arm']=='candidate'
                require(len(shadow_observers)==2,'Expected early and restarted file sources')
                require(result['model_cache']['streams']==2,'Expected two streams with resident models')
                shadow=shadow_observers[1].report()
                with wave.open(a['audio']['path'],'rb') as wav:
                    pcm_hash=hashlib.sha256(wav.readframes(wav.getnframes())).hexdigest()
                require(shadow['samples']==result['expected_samples'] and shadow['source_pcm_sha256']==pcm_hash,'Observed PCM changed or incomplete')
                require(shadow['actually_skipped_samples']==0,'Shadow removed input')
                reference=load(a['shadow_reference_result']['path'])
                for key in ('expected_samples','source_samples','asr_samples','identity_samples',
                            'activity_frame_count','activity_fingerprint','caption_fingerprint','stored_caption_fingerprint'):
                    require(result[key]==reference[key],'Shadow changed matched output: '+key)
                freeze(output/'SHADOW.json',shadow)
                result['shadow']=bind(output/'SHADOW.json')
                result['shadow_parity_passed']=True

            ui.close(); pump(lambda:controller.closed and not controller.worker.is_alive())
        except Exception as exc:
            errors.append(type(exc).__name__+': '+str(exc)); traceback.print_exc()
        finally:
            if controller is not None:
                if not controller.closed and not (ui and ui._closing): controller.close()
                until=time.monotonic()+15
                while controller.worker.is_alive() and time.monotonic()<until: time.sleep(.05)
                result.update(controller_error=controller.error,controller_status=controller.status,controller_metrics=controller.metrics,
                              controller_closed=controller.closed,worker_alive=controller.worker.is_alive(),
                              lock_released=not (controller.data_root/'runtime.lock').exists())
            result.update(status='PASS_NEMOTRON_PHASE' if not errors else 'FAILED_NEMOTRON_PHASE',
                utc=datetime.now(timezone.utc).isoformat(),owner=identity(__import__('psutil').Process()),
                desktop=expected_desktop,CM5_tested=False,N4_accepted=False,N5_complete=False)
            freeze(output/'RESULT.json',result)
    return 0 if not errors else 1


def output_bytes(output):
    # The application legitimately deletes its own session during reopen.
    # A disappearing file contributes zero retained bytes; other errors fail closed.
    total=0
    for path in output.rglob('*'):
        try:
            if path.is_file(): total+=path.stat().st_size
        except FileNotFoundError:
            continue
    return total


def host(precheck, output):
    own=identity(pin()); local=HERE.parents[4]/'local'
    require(not output.exists() and output.resolve().is_relative_to(local/'n5'),'Fresh private output required')
    a=checked_inputs(precheck); now=datetime.now(timezone.utc)
    require(0 <= (now-datetime.fromisoformat(a['admitted_utc'])).total_seconds()<120,'Admission stale')
    require(now<datetime.fromisoformat(a['expires_utc'])<datetime.fromisoformat(load(a['window']['path'])['checkpoint_utc']),'Invalid cutoff')
    require(0 < (datetime.fromisoformat(a['expires_utc'])-datetime.fromisoformat(a['admitted_utc'])).total_seconds()<=600
            and a['output_cap_bytes']==128*1024**2,'Execution bound differs')
    require(all(exact_process(o) is None for o in a['closed_prior_owners']),'Prior owner active')
    for _ in range(50):
        worker=load(local/'supervision/worker.json')
        if worker.get('child_pid')==own['pid'] and worker.get('child_create_time')==own['create_time']:break
        time.sleep(.1)
    require(worker.get('child_pid')==own['pid'] and worker.get('child_create_time')==own['create_time'],'Not supervised owner')
    require(exact_process({k:worker[k] for k in ('pid','create_time')}) is not None,'Supervisor absent')
    require(load(local/'supervision/worker_spec.json')['argv']==__import__('psutil').Process().cmdline(),'Worker argv differs')
    require(Path(a['data']).resolve()==output/'data','Isolated data root differs')
    output.mkdir(); a.update(owner=own,precheck=bind(precheck),supervisor=worker); freeze(output/'ADMISSION.json',a)
    phases=[]; error=None
    try:
        for phase in ('infer','reopen'):
            process=PrivateApplicationProcess(output/(phase+'-lifetime'),executable_binding=bind(sys.executable),
                script_binding=bind(__file__),cpu=(4,14))
            # Desktop is known only after construction; the actual suspended argv is then frozen.
            arguments=['--child','--admission',str(output/'ADMISSION.json'),'--output',str(output/phase),
                       '--phase',phase,'--desktop',process.desktop_name]
            process.argv=[sys.executable,'-B',str(Path(__file__).resolve()),*arguments]
            with process:
                process.spawn_suspended()
                process.resume(lambda who,**values:freeze(output/(phase+'-OWNER.json'),dict(owner=who,**values)))
                began=time.monotonic()
                while not process.root_exited():
                    require(time.monotonic()-began<285,'Process deadline reached')
                    require(datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Allocation expired')
                    require(not (output/'CANCEL').exists(),'Stage cancelled')
                    require(all(shutil.disk_usage(d+':/').free>gib*1024**3 for d,gib in [('C',50),('G',75)]),'Drive reserve breached')
                    require(output_bytes(output)<a['output_cap_bytes'],'Output cap exceeded')
                    time.sleep(1)
            result=load(output/phase/'RESULT.json'); acceptance(result,process.receipt)
            if phase=='infer':
                bypass_acceptance(result,a['arm'],load(a['reference_inputs'][1]['path']) if a['arm']=='candidate' else None)
            phases.append(dict(phase=phase,result=bind(output/phase/'RESULT.json'),lifetime=bind(process.output/'LIFETIME.json')))
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    for row in a['code']+a['release_files']+a['assets']+a['runtime_configs']:verify(row)
    freeze(output/'RESULT.json',dict(status='PASS_NEMOTRON_WINDOWS_LIFECYCLE_SMOKE' if error is None else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),owner=own,error=error,phases=phases,admission=bind(output/'ADMISSION.json'),
        scope='Early Stop, accepted-prefix drain and full-file restart with resident E0/ASR models; paired shadow diagnostics with every source sample retained; one saved source, '+a['backend_key']+' '+a['mode']+', two real Windows processes; Tk render/save/reopen/delete smoke only.',
        microphone=False,playback=False,personal_store_used=False,CM5_tested=False,N4_accepted=False,N5_complete=False))
    return int(error is not None)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--precheck',type=Path)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--child',action='store_true')
    parser.add_argument('--admission',type=Path); parser.add_argument('--phase',choices=['infer','reopen']); parser.add_argument('--desktop')
    args=parser.parse_args()
    raise SystemExit(child(args.admission,args.output,args.phase,args.desktop) if args.child else host(args.precheck,args.output))
