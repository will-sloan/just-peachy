"""Actual private-desktop controls and deliberate startup faults. README_EMPTY_STORE_V1.md."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import sys
import time
import traceback

from early_stop_lifecycle_v2 import desktop_name, require, bind, freeze, load, identity, exact_process


def child(admission, output, phase, expected_desktop):
    from empty_store_harness_v1 import checked_inputs
    require(not output.exists(), 'Fresh phase required'); output.mkdir()
    errors=[]; result=dict(phase=phase,errors=errors,cases=[],controls=[])
    controller=ui=None
    with (output/'stdout.log').open('x',encoding='utf-8') as out, (output/'stderr.log').open('x',encoding='utf-8') as err:
        sys.stdout=out;sys.stderr=err
        try:
            require(desktop_name()==expected_desktop and expected_desktop.startswith('codex-n1-n4-'),'Private desktop mismatch')
            a=checked_inputs(admission); release=Path(a['release']);data=Path(a['data'])
            import psutil
            own=identity(psutil.Process())
            require(psutil.Process().cpu_affinity()==[4,14] and psutil.Process().ppid()==a['owner']['pid']
                and exact_process(a['owner']) is not None,'Owner or affinity mismatch')
            require(load(output.parent/(phase+'-OWNER.json'))['owner']==own,'Registered identity differs')
            require(not data.exists(),'Fresh isolated data required');data.mkdir()
            for row in a['runtime_configs']:shutil.copyfile(row['path'],data/Path(row['path']).name)
            (data/'people').mkdir();(data/'people/SYNTHETIC_SENTINEL.txt').write_bytes(b'N5 isolated preservation fixture\n')
            sentinel=bind(data/'people/SYNTHETIC_SENTINEL.txt')
            require(sentinel['sha256']==a['sentinel_sha256'],'Sentinel differs')
            sys.path[:0]=[str(release),str(release/'vendor')]
            import tkinter as tk
            import app.controller
            from app.controller import Controller
            from app.ui import PrototypeUI,prepare_dpi_awareness
            from app.backends import backend_catalog,BASELINE_BACKEND_ID
            require(Path(app.controller.__file__).resolve()==release/'app/controller.py','Wrong application import')
            prepare_dpi_awareness();controller=Controller(data,Path(a['models']),saved_audio_only=True)
            controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
            root=tk.Tk();root.report_callback_exception=lambda kind,value,tb:errors.append(''.join(traceback.format_exception(kind,value,tb)))
            ui=PrototypeUI(root,controller,allow_auto_start=False)
            deadline=time.monotonic()+240
            def pump(until):
                while not until():
                    require(time.monotonic()<deadline and datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc']),'Phase expired')
                    require(not (output.parent/'CANCEL').exists() and not errors,'Cancelled or Tk error')
                    root.update();time.sleep(.02)
                if not ui._closed:
                    ui.poll()
                    if not ui._closed:root.update()
            def idle():pump(lambda:controller.commands.unfinished_tasks==0)
            def select(key):
                ui.show_backends();ui.actions['backend_'+key].invoke();idle()
            def check_error(case,expected_id):
                idle();snap=controller.snapshot()
                observed=dict(case=case,state=snap['state'],error=snap['error'],backend_id=snap['backend_id'],
                    rendered_error=ui.error_label.cget('text'),status=snap['status'],model_type=type(controller.models).__name__,
                    engine_retained=controller.engine is not None,models=dict(asr_loads=controller.models.asr_loads,
                        speaker_loads=controller.models.speaker_loads,streams=controller.models.streams))
                result['cases'].append(observed)
                freeze(output/(case+'.json'),observed)
                require(snap['state']=='ERROR' and snap['error'],'Fault was not reported')
                require(snap['backend_id']==expected_id,'Silent backend fallback')
                require(str(snap['error'])[:120] in observed['rendered_error'],'Actual GUI hides the failure')
                return observed
            idle();selected=next(row['id'] for row in backend_catalog() if row['key']==a['backend_key'])
            select(a['backend_key'])
            require(controller.error is None and controller.backend_id==selected,'Backend selection failed')
            from empty_store_protocol_v1 import exercise,naming_proof
            result.update(exercise(controller,ui,a,output,idle,require,check_error))
            controller.session_action('new',audio=False,consent=False);idle()
            controller.start_file(a['audio']['path']);idle();engine=controller.engine
            require(engine is not None,'Recovery failed to start')
            pump(lambda:engine._journal.committed_samples>=128000 or controller.error is not None)
            require(controller.error is None,'Recovery inference failed')
            controller.stop();idle();t=engine.telemetry()
            samples=engine._journal.committed_samples
            asr=t['n3_input_samples'] if a['backend_key']=='nemotron_600m' else round(t['asr_cursor_sec']*16000)
            require(samples==asr==t['identity_audio_samples'] and t['speaker_lag_sec']==0,'Recovery prefix did not drain')
            require(controller.metrics['last_worker_cleanup']['owned_threads_joined'],'Recovery workers remain')
            require(t['n2_embedding_calls']>0 and controller.snapshot()['rows'],'Recovery produced no speaker/caption evidence')
            result['recovery']=dict(source_samples=samples,asr_samples=asr,identity_samples=t['identity_audio_samples'],
                embedding_calls=t['n2_embedding_calls'],caption_rows=len(controller.snapshot()['rows']),
                cleanup=controller.metrics['last_worker_cleanup'],backend_id=controller.backend_id)
            result['naming_proof']=naming_proof(controller,engine,output,require)
            select('baseline');require(controller.backend_id==BASELINE_BACKEND_ID and controller.engine is None
                and controller.error is None,'Explicit baseline rollback failed')
            result['baseline_rollback']=True;result['backend_id']=selected
            result['sentinel_preserved']=bind(sentinel['path'])==sentinel
            result['saved_audio_only']=controller.saved_audio_only
            result['output_observations']=controller.output_defaults
            ui.close();pump(lambda:controller.closed and not controller.worker.is_alive())
        except Exception as exc:
            errors.append(type(exc).__name__+': '+str(exc));traceback.print_exc()
        finally:
            if controller is not None:
                if not controller.closed:controller.close()
                until=time.monotonic()+15
                while controller.worker.is_alive() and time.monotonic()<until:time.sleep(.05)
                result.update(controller_closed=controller.closed,worker_alive=controller.worker.is_alive(),
                    lock_released=not (controller.data_root/'runtime.lock').exists(),controller_error=controller.error)
            result.update(status='PASS_CONTROLS_PHASE' if not errors else 'FAILED_CONTROLS_PHASE',
                utc=datetime.now(timezone.utc).isoformat(),owner=identity(__import__('psutil').Process()),desktop=expected_desktop,
                CM5_tested=False,N4_accepted=False,N5_complete=False)
            freeze(output/'RESULT.json',result)
    return int(bool(errors))
