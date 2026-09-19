"""V8 cooperative telemetry and separately reviewed fresh restoration; README_S6D_CAPTURE_V8.md. No import-time I/O."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import queue
import shutil
import socket
import sys
import threading
import time
import traceback
import wave
import numpy as np
from s6d_capture_transport import PROFILES,binding,verify,mux_arguments,pack,pcm24_bytes,unpack_pcm24,input_qa,processed_qc,timing,guarded_input,terminal_packed_silence,audio_gate,MAX_CALLBACK_FRAMES
from s6d_restoration_policy_v1 import restoration_decision,record_policy_valid,exact,POLICY,NO_MUTATION_POLICY,SCHEMA,RECOVERY_SCHEMA

SIM=Path(__file__).resolve().parents[1]
ROOT=SIM.parent
MAX_ATTEMPTS=480
MAX_PLAYBACK_SEC=21600.
MAX_PAYLOAD_BYTES=40*2**30
ROLES={'canonical','qualification','repeat','enrollment','continuous','stress'}


def utc():return datetime.now(timezone.utc).isoformat()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path,value,immutable=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if immutable:
        with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
    else:
        temporary=path.with_name(path.name+'.tmp.'+str(os.getpid()))
        with temporary.open('x',encoding='utf-8') as f:
            json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)


def contained(root,path):
    root=Path(root).resolve();path=Path(path).resolve()
    if path==root or root not in path.parents:raise ValueError('Output must be a child of the bound root')
    return path


def check_budget(ledger,seconds):
    if not math.isfinite(seconds) or not 0<seconds<=960:raise ValueError('Finite attempt duration must be0..960seconds')
    rows=ledger['passes']
    if any(r['status']=='STARTED' for r in rows):raise RuntimeError('Unresolved STARTED attempt; reviewed recovery required')
    if len(rows)>=MAX_ATTEMPTS or sum(r['charged_playback_s'] for r in rows)+seconds>MAX_PLAYBACK_SEC:
        raise RuntimeError('Global physical attempt/playback ceiling reached')


def storage(report,payload,estimate_bytes=0):
    report=Path(report);payload=Path(payload)
    free_c=shutil.disk_usage(report).free
    free_g=shutil.disk_usage(payload).free
    total=sum(p.stat().st_size for p in payload.rglob('*') if p.is_file())
    if free_c<50*2**30 or free_g-estimate_bytes<75*2**30 or total+estimate_bytes>MAX_PAYLOAD_BYTES:
        raise RuntimeError('C50GiB/G75GiB/new40GiB storage reserve would be crossed')
    return dict(c_free_bytes=free_c,g_free_bytes=free_g,new_payload_bytes=total,reserved_attempt_bytes=estimate_bytes)


def validate_plan(plan_path,authorization=None):
    plan=read(plan_path)
    if plan.get('schema')!='s6d-capture-plan.v1':raise ValueError('Explicit S6D capture plan required')
    report=Path(plan['report_root']).resolve();payload=Path(plan['payload_root']).resolve()
    if not report.is_relative_to(SIM/'reports/S6D') or not payload.is_relative_to(Path('G:/Just_Peachy_S6D')) or payload==Path('G:/Just_Peachy_S6D'):
        raise ValueError('Wrong S6D report/verified payload root')
    if plan.get('limits')!={'attempts':480,'charged_playback_seconds':21600,'payload_bytes':MAX_PAYLOAD_BYTES}:raise ValueError('Exact authorized ceilings required')
    for field in ('safety','baseline','output_level_policy','initialization_policy','audio_acceptance_policy'):
        verify(plan[field])
    ack=read(plan['safety']['path'])
    if ack.get('xvf_own_analog_outputs_off_or_disconnected') is not True or not ack.get('user_confirmation_text'):
        raise ValueError('Recorded setup acknowledgement must scope silencing to the XVF own analog outputs')
    level=read(plan['output_level_policy']['path']);initialization=read(plan['initialization_policy']['path'])
    if not level.get('frozen') or level.get('hardware_recipe')!='limiter_and_agc_headroom' or not initialization.get('frozen'):
        raise ValueError('Exact accepted S4.5 DSP/gain/init policy required')
    acceptance=read(plan['audio_acceptance_policy']['path'])
    audio_gate(dict(streams=[]),acceptance,[])
    attempts=plan['attempts'];ids=set()
    if not attempts or len(attempts)>480:raise ValueError('Bounded attempts required')
    for row in attempts:
        if row['attempt_id'] in ids:raise ValueError('Attempt identifiers must be unique')
        ids.add(row['attempt_id'])
        if any(not s or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in s) for s in (row['attempt_id'],row['case_id'])):raise ValueError('Safe exact case/attempt names required')
        if row['profile'] not in PROFILES or row['role'] not in ROLES:raise ValueError('Unsupported profile or role')
        if row.get('reset_before') is not True:raise ValueError('Each independent pass begins from declared reset; one continuous recording is one pass')
        if row['role']=='continuous' and (row.get('continuous_dsp_seconds')!=900 or row['duration_sec']!=900):raise ValueError('A continuous conversation must declare one uninterrupted900-second pass')
        check_budget({'passes':[]},timing(row['duration_sec'])['charged_playback_seconds'])
        if row.get('payload_expectation') not in ('nonzero','silence'):raise ValueError('Predeclared payload expectation required')
        required=row.get('required_nonzero_streams')
        names={s[0] for s in PROFILES[row['profile']]}
        if not isinstance(required,list) or not set(required)<=names:raise ValueError('Predeclare required nonzero streams from this exact profile')
        if row['payload_expectation']=='nonzero' and not {'auto_asr_raw','auto_pp_raw'}<=set(required):raise ValueError('A nonzero scene must require both automatic output taps to contain payload')
        if row['payload_expectation']=='silence' and required:raise ValueError('Silence controls cannot require nonzero payload')
        verify(row['source_audio'])
    if authorization is not None:
        auth=read(authorization)
        if auth.get('root_review_passed') is not True or auth.get('plan_sha256')!=binding(plan_path)['sha256']:
            raise ValueError('Coordinator review must bind this exact plan')
        if not auth.get('source_bindings'):raise ValueError('Coordinator must bind executed source versions')
        for b in auth['source_bindings']:verify(b)
        for recovery in auth.get('reviewed_recoveries',[]):verify(recovery)
        required=[Path(__file__),SIM/'scripts/README_S6D_CAPTURE_V8.md',SIM/'scripts/README_S6D_CAPTURE_V5.md',SIM/'scripts/s6d_restoration_policy_v1.py',SIM/'scripts/s6d_capture_transport.py',SIM/'scripts/s6d_telemetry_v2.py',
            SIM/'scripts/README_S6D_TELEMETRY_V2.md',SIM/'scripts/s6d_closed_telemetry_restore_v3.py',SIM/'scripts/README_S6D_CLOSED_TELEMETRY_RESTORE_V3.md',
            SIM/'scripts/s6d_native/S6DQueuedTelemetry.cs',SIM/'scripts/s6d_native/Run-S6D-Telemetry.ps1',SIM/'scripts/README_S6D_CAPTURE.md',
            ROOT/'measurement_app/core.py',ROOT/'measurement_app/__init__.py',ROOT/'measurement_app/queued_telemetry.py',ROOT/'measurement_app/telemetry.py',
            SIM/'scripts/s3_hardware.py',SIM/'scripts/s4_restore.py',SIM/'scripts/s0_common.py',SIM/'scripts/s4_common.py',
            ROOT/'tools/xvf321/binary/host_v3.0.0/win32/xvf_host.exe',ROOT/'tools/xvf321/binary/host_v3.0.0/win32/device_usb.dll',ROOT/'tools/xvf321/binary/host_v3.0.0/win32/command_map.dll']
        if not set(p.resolve() for p in required)<=set(Path(b['path']).resolve() for b in auth['source_bindings']):
            raise ValueError('Coordinator review omits one or more executed S6D sources')
    return plan


def prepare_input(attempt,folder):
    import soundfile as sf
    verify(attempt['source_audio'])
    x,rate=sf.read(attempt['source_audio']['path'],dtype='float64',always_2d=True)
    if rate!=16000 or x.shape[1]!=4 or len(x)!=round(attempt['duration_sec']*16000):raise ValueError('Bound four-microphone source format/duration mismatch')
    q,original=guarded_input(x);carrier=pack(q);path=folder/'input_packed.pcm24';path.write_bytes(pcm24_bytes(carrier))
    if attempt['payload_expectation']=='nonzero' and not np.any(original):raise ValueError('Declared nonzero source is all zero')
    if attempt['payload_expectation']=='silence' and np.any(original):raise ValueError('Declared silence source contains nonzero payload')
    support=np.flatnonzero(np.any(original[:,2:6]!=0,axis=1))
    return path,q,dict(source=attempt['source_audio'],packed=binding(path),native_frames=len(carrier),timing=timing(attempt['duration_sec']),
        source_nonzero_first_frame=int(support[0]) if len(support) else None,source_nonzero_last_frame=int(support[-1]) if len(support) else None,
        existing_source_leading_zero_frames=int(support[0]) if len(support) else len(original),existing_source_trailing_zero_frames=len(original)-1-int(support[-1]) if len(support) else len(original),
        logical_input_order=['zero_far_end','zero_ignored','MIC0','MIC1','MIC2','MIC3'],source_gain=1.,
        quantization_step_fs=2**-22,applied_RIR_origin_additions=0,recipe='preserved_source_quantized_evenPCM24_once_with_common_1s_pre_3s_post_guard')


def restoration_permitted(audio_state,telemetry_closed):
    return telemetry_closed is True and audio_state.get('audio_handles_closed') is True


def stop_requested(stop_path,external_stop_event=None):
    return external_stop_event is not None and external_stop_event.is_set() or stop_path.exists()


def recorder_port_preflight(batch_dir,provider):
    """Persist a complete host TCP table and fail closed before hardware lease."""
    from s6d_closed_telemetry_restore_v3 import tcp_census,tcp_listener_decision
    path=Path(batch_dir)/'RECORDER_TCP_LISTENERS.json'
    snapshot=tcp_census(provider);save(path,snapshot,True)
    receipt=dict(schema='s6d-owner-recorder-port-preflight.v1',status='FAIL',census=binding(path),
        checked_before_hardware_lock=True,connection_probe_used=False,timeout_interpreted_as_idle=False)
    try:receipt.update(status='PASS',decision=tcp_listener_decision(snapshot))
    except BaseException as exc:
        receipt['error']=repr(exc);save(Path(batch_dir)/'RECORDER_PORT_PREFLIGHT.json',receipt,True);raise
    save(Path(batch_dir)/'RECORDER_PORT_PREFLIGHT.json',receipt,True)
    return binding(Path(batch_dir)/'RECORDER_PORT_PREFLIGHT.json')


def capture_to_disk(attempt,packed_path,folder,stop_path,telemetry,sd,endpoints,storage_check=None,audio_state=None,external_stop_event=None):
    """Bounded callback queue; complete disk journal, hard abort on any backlog loss."""
    if audio_state is None:audio_state=dict(audio_open_attempted=False,audio_handles_closed=True)
    inp,out=endpoints()
    for io,dev in [('input',inp),('output',out)]:getattr(sd,'check_'+io+'_settings')(device=dev['index'],channels=2,dtype='int24',samplerate=48000)
    plan_timing=timing(attempt['duration_sec']);total=plan_timing['native_carrier_frames']
    payload=np.memmap(packed_path,dtype=np.uint8,mode='r')
    if len(payload)!=total*6:raise ValueError('Packed byte count mismatch')
    pending=queue.Queue(maxsize=64);done=threading.Event();writer_done=threading.Event()
    errors=[];flags=[];times=[];position=0;captured_frames=0;max_depth=0;writer_failed=threading.Event()
    native_path=folder/'native_packed.wav'
    def writer():
        try:
            with wave.open(str(native_path),'wb') as wf:
                wf.setnchannels(2);wf.setsampwidth(3);wf.setframerate(48000)
                while True:
                    item=pending.get()
                    if item is None:break
                    wf.writeframesraw(item)
        except BaseException as e:errors.append('writer: '+repr(e));writer_failed.set()
        finally:writer_done.set()
    thread=threading.Thread(target=writer,name='s6d-pcm-writer',daemon=True);thread.start()
    def callback(indata,outdata,frames,driver_times,status):
        nonlocal position,captured_frames,max_depth
        arrival=time.perf_counter_ns()
        try:
            if frames<=0 or frames>MAX_CALLBACK_FRAMES:raise RuntimeError('Callback exceeds declared fixed queue block bound')
            if external_stop_event is not None and external_stop_event.is_set():
                outdata[:]=terminal_packed_silence(position,frames)
                raise RuntimeError('Coordinated in-memory STOP before next output block')
            if writer_failed.is_set():raise RuntimeError('PCM writer unavailable')
            take=min(frames,total-position)
            if take<0:raise RuntimeError('Callback after source completion')
            chunk=payload[position*6:(position+take)*6].tobytes()
            outdata[:]=chunk+terminal_packed_silence(position+take,frames-take)
            pending.put_nowait(bytes(indata))
            max_depth=max(max_depth,pending.qsize())
            times.append(dict(first_native_frame=position,frames=take,callback_capacity_frames=frames,
                host_callback_monotonic_ns=arrival,host_copy_complete_monotonic_ns=time.perf_counter_ns(),
                input_adc_time=driver_times.inputBufferAdcTime,output_dac_time=driver_times.outputBufferDacTime,stream_current_time=driver_times.currentTime))
            if len(times)>200000:raise RuntimeError('Callback metadata bound exceeded')
            if status:flags.append(dict(native_frame=position,flags=str(status)))
            position+=take;captured_frames+=frames
            if position>=total:raise sd.CallbackStop
        except sd.CallbackStop:raise
        except BaseException as e:errors.append('callback: '+repr(e));raise sd.CallbackAbort
    start=time.perf_counter_ns();start_utc=utc();actual={};last_disk_check=time.perf_counter();stream_object=None;audio_closed=True
    try:
        if stop_requested(stop_path,external_stop_event) or not telemetry.healthy():raise RuntimeError('STOP or unhealthy telemetry before audio open')
        # The owner sees this before even the constructor: constructor failure
        # can leave an OS handle without returning an inspectable Python object.
        audio_state.update(audio_open_attempted=True,audio_handles_closed=False)
        audio_closed=False
        stream_object=sd.RawStream(samplerate=48000,channels=2,dtype='int24',device=(inp['index'],out['index']),blocksize=0,
                latency=.15,dither_off=True,clip_off=True,callback=callback,finished_callback=done.set)
        audio_closed=False
        with stream_object as stream:
            actual=dict(samplerate=stream.samplerate,latency=list(stream.latency),blocksize=stream.blocksize)
            while not done.wait(.05):
                if storage_check is not None and time.perf_counter()-last_disk_check>=5:
                    try:storage_check()
                    except BaseException as e:errors.append('Storage watchdog: '+repr(e));stream.abort();break
                    last_disk_check=time.perf_counter()
                if stop_requested(stop_path,external_stop_event) or writer_failed.is_set() or not telemetry.healthy():
                    errors.append('Coordinated STOP, writer failure or telemetry stall');stream.abort();break
                if time.perf_counter_ns()-start>(plan_timing['charged_playback_seconds']+15)*1e9:
                    errors.append('Finite audio deadline exceeded');stream.abort();break
    except BaseException as e:errors.append('stream: '+repr(e))
    finally:
        if stream_object is not None:
            audio_closed=bool(getattr(stream_object,'closed',False))
            if not audio_closed:
                try:stream_object.abort();stream_object.close();audio_closed=bool(stream_object.closed)
                except BaseException as e:errors.append('Audio close proof unavailable: '+repr(e))
            if not audio_closed:errors.append('Audio stream remains open; restoration must not compete')
        # Publish independently of metadata I/O or this function returning.
        audio_state['audio_handles_closed']=audio_closed
        if not writer_failed.is_set():
            try:pending.put(None,timeout=5)
            except queue.Full:errors.append('PCM writer drain deadline exceeded')
        thread.join(timeout=10)
        if thread.is_alive():errors.append('PCM writer still alive after bounded drain')
        del payload
    metadata=dict(requested_source_seconds=attempt['duration_sec'],timing=plan_timing,captured_frames=captured_frames,carrier_frames_submitted=position,
        callback_playback_seconds=captured_frames/48000,source_payload_frames_submitted=max(0,min(plan_timing['source_frames'],position//3-plan_timing['source_start_logical_frame'])),
        terminal_padding_frames=max(0,captured_frames-total),native_rate_hz=48000,container_bits=24,
        start_utc=start_utc,start_monotonic_ns=start,end_monotonic_ns=time.perf_counter_ns(),
        callback_flags=flags,callback_errors=errors,callback_times=times,actual_stream=actual,input_device=inp,output_device=out,
        queue_capacity_blocks=64,max_callback_frames=16384,maximum_pcm_queue_bytes=64*16384*6,observed_queue_peak_blocks=max_depth,
        writer_closed=not thread.is_alive(),audio_handles_closed=audio_closed,source_clock_origin='Original source sample 0 follows common 16000-frame guard; no resampling or independent offsets',
        timestamps_calibrated_to_acoustics=False,device_DSP_source_timestamps=None)
    save(folder/'capture_metadata.json',metadata,True)
    return metadata


def prior_closure(report,reviewed_recoveries=()):
    ledger=read(report/'physical_ledger.json') if (report/'physical_ledger.json').exists() else {'schema':'s6d-physical-ledger.v1','passes':[]}
    if any(r['status']=='STARTED' for r in ledger['passes']):raise RuntimeError('Unresolved prior physical attempt blocks ownership')
    for acquired in (report/'hardware_batches').glob('*/owner_acquired.json'):
        path=acquired.parent/'restoration.json'
        if not path.exists():raise RuntimeError('Missing prior restoration; process exit alone is insufficient')
        receipt=read(path)
        record=ledger.get('batches',{}).get(acquired.parent.name)
        if not record:raise RuntimeError('Restoration exists without a closed binding; coordinator recovery review required')
        verify(record['restoration']);verify(record['owner'])
        if Path(record['restoration']['path']).resolve()!=path.resolve() or Path(record['owner']['path']).resolve()!=acquired.resolve():raise RuntimeError('Prior owner/restoration ledger path mismatch')
        valid=receipt.get('schema_version')!=SCHEMA and receipt.get('status')=='PASS' and receipt.get('exact_recorded_configuration_match') is True and receipt.get('telemetry_process_closed') is True
        if receipt.get('schema_version')==SCHEMA:
            if receipt.get('policy')==POLICY:
                verify(receipt['initial_state'])
                if Path(receipt['initial_state']['path']).resolve()!=(acquired.parent/'initial_state.json').resolve():raise RuntimeError('Prior V5 initial-state path differs')
                valid=record_policy_valid(read(receipt['initial_state']['path']),receipt) and all(receipt.get(k) is True for k in ('telemetry_process_closed','audio_handles_closed','hardware_lease_released','packed_input_disabled'))
            elif receipt.get('policy')==NO_MUTATION_POLICY:
                valid=receipt.get('status')=='PASS' and receipt.get('scope')=='No setters or playback occurred under this owner' and all(receipt.get(k) is True for k in ('telemetry_process_closed','hardware_lease_released')) and not any(r.get('batch')==acquired.parent.name for r in ledger['passes'])
        if not valid:
            matches=[]
            for ref in reviewed_recoveries:
                verify(ref);recovery=read(ref['path'])
                if recovery.get('original_restoration')==record['restoration']:matches.append((ref,recovery))
            if len(matches)!=1:raise RuntimeError('Unproven prior restoration; exact authorized recovery binding required')
            ref,recovery=matches[0]
            if recovery.get('schema_version')=='edge-s6d-restoration-recovery.v2':
                # A separate reviewed fresh restore can close this original failure;
                # it does not manufacture the missing historical Python receipt.
                from s6d_closed_telemetry_restore_v3 import verify_recovery_record
                proof=verify_recovery_record(recovery,owner_binding=record['owner'],restoration_binding=record['restoration'],initial_binding=binding(acquired.parent/'initial_state.json'))
                if proof.get('status')!='VERIFIED_CLOSED_NATIVE_TELEMETRY_FRESH_RESTORE' or proof.get('old_failure_preserved') is not True:
                    raise RuntimeError('Fresh-restoration recovery verifier did not prove separate closure')
                continue
            if not all(receipt.get(k) is True for k in ('hardware_lease_released','audio_handles_closed','telemetry_process_closed','packed_input_disabled')):
                raise RuntimeError('Original owner closure is not proven; gain-only recovery is insufficient')
            if recovery.get('schema_version')!=RECOVERY_SCHEMA or recovery.get('status')!='PASS' or recovery.get('original_owner')!=record['owner'] or recovery.get('reapply_origin')!=record['restoration']:
                raise RuntimeError('Recovery owner/immediate-proof provenance mismatch')
            verify(recovery['initial_state'])
            if Path(recovery['initial_state']['path']).resolve()!=(acquired.parent/'initial_state.json').resolve() or recovery['initial_state']!=receipt.get('initial_state'):
                raise RuntimeError('Recovery initial-state binding differs')
            if not exact(recovery.get('reapply'),receipt.get('reapply')):raise RuntimeError('Recovery must retain actual original immediate readback proof')
            decision=restoration_decision(read(recovery['initial_state']['path']),recovery.get('readback'),recovery.get('reapply'))
            if not decision['accepted'] or not exact(recovery.get('policy_evaluation'),decision) or not all(recovery.get(k) is True for k in ('hardware_lease_released','audio_handles_closed','telemetry_process_closed','packed_input_disabled','no_playback','no_setters_or_reset')):
                raise RuntimeError('Reviewed getter-only recovery policy/closure incomplete')
    return ledger


def execute(plan_path,authorization,batch,attempt_ids,external_stop_event=None):
    plan=validate_plan(plan_path,authorization)
    if external_stop_event is not None and external_stop_event.is_set():raise RuntimeError('In-memory STOP before hardware imports/ownership')
    # Hardware imports are below explicit reviewed execution admission only.
    import msvcrt
    sys.path.insert(0,str(ROOT))
    import measurement_app
    from measurement_app.core import Control,HOST,xvf_endpoints,decode_packed,save_counts
    from s3_hardware import STATIC,OBSERVE_ONLY,FROZEN,values,set_verified,reset
    from s4_restore import restore_exposed
    from s6d_telemetry_v2 import S6DQueuedTelemetryLogger
    import soundfile as sf
    import sounddevice as sd
    report=Path(plan['report_root']);payload=Path(plan['payload_root'])
    report.mkdir(parents=True,exist_ok=True);payload.mkdir(parents=True,exist_ok=True)
    selected=[r for r in plan['attempts'] if r['attempt_id'] in attempt_ids]
    if len(selected)!=len(attempt_ids) or len(attempt_ids)!=len(set(attempt_ids)):raise ValueError('Select exact unique plan attempts')
    if not batch or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in batch):raise ValueError('Safe batch name required')
    batch_dir=contained(report,report/'hardware_batches'/batch);batch_dir.mkdir(parents=True,exist_ok=False)
    save(batch_dir/'admission.json',dict(plan=binding(plan_path),authorization=binding(authorization),attempt_ids=attempt_ids),True)
    source_dir=batch_dir/'source_epoch';source_dir.mkdir()
    for b in read(authorization)['source_bindings']:
        verify(b);p=Path(b['path']);dest=source_dir/p.name
        if dest.exists():raise ValueError('Source snapshot filename collision')
        shutil.copy2(p,dest)
    lock=None;owned=False;initial=None;mutated=False;control=None;telem=None;telem_result=None;active=None;ledger=None;meta=None
    audio_state=dict(audio_open_attempted=False,audio_handles_closed=True)
    summary=dict(status='STARTING',batch=batch,started_utc=utc(),completed_attempts=[],error=None)
    restoration=dict(status='NOT_NEEDED',exact_recorded_configuration_match=True,telemetry_process_closed=True)
    try:
        storage(report,payload)
        if stop_requested(report/'STOP_REQUEST.json',external_stop_event):raise RuntimeError('STOP before hardware lease acquisition')
        import psutil
        summary['recorder_port_preflight']=recorder_port_preflight(batch_dir,psutil)
        lock=(ROOT/'measurement_app/hardware.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True
        ledger=prior_closure(report,read(authorization).get('reviewed_recoveries',()))
        if any(r['attempt_id'] in attempt_ids for r in ledger['passes']):raise ValueError('Existing attempt must be preserved')
        save(batch_dir/'owner_acquired.json',dict(pid=os.getpid(),acquired_utc=utc(),plan=binding(plan_path)),True)
        control=Control(batch_dir/'owner_commands');identity=control.identify()
        initial=dict(identity=identity,settings={n:values(control,n) for n in STATIC},observe_only={n:values(control,n) for n in OBSERVE_ONLY},usb_bits=identity['USB_BIT_DEPTH'])
        save(batch_dir/'initial_state.json',initial,True)
        if values(control,'VERSION')!=[3,2,1] or values(control,'AEC_MIC_ARRAY_TYPE')!=[1] or initial['usb_bits'] not in ([16,16],[24,24]):raise RuntimeError('Device version, linear-array type or width mismatch')
        if initial['settings']['I2S_INPUT_PACKED']!=[0]:raise RuntimeError('Unexpected pre-existing packed-input owner/state')
        baseline=read(plan['baseline']['path'])['settings']
        for attempt in selected:
            if stop_requested(report/'STOP_REQUEST.json',external_stop_event):raise RuntimeError('Stop requested before next attempt')
            plan_timing=timing(attempt['duration_sec'])
            check_budget(ledger,plan_timing['charged_playback_seconds'])
            estimate=math.ceil(plan_timing['charged_playback_seconds']*16000*6*3*4.2)+16*2**20
            storage(report,payload,estimate)
            folder=contained(payload,payload/'beam_bank'/attempt['case_id']/attempt['profile']/attempt['attempt_id']);folder.mkdir(parents=True,exist_ok=False)
            packed_path,expected,input_receipt=prepare_input(attempt,folder)
            active=dict(batch=batch,attempt_id=attempt['attempt_id'],case_id=attempt['case_id'],profile=attempt['profile'],role=attempt['role'],
                status='STARTED',charged_playback_s=plan_timing['charged_playback_seconds'],source_duration_s=attempt['duration_sec'],
                transport_timing=plan_timing,started_utc=utc(),input_sha256=attempt['source_audio']['sha256'])
            ledger['passes'].append(active);save(report/'physical_ledger.json',ledger)
            mutated=True
            reset_receipt=reset(control,24,change_width=values(control,'USB_BIT_DEPTH')!=[24,24],isolate_packed=True)
            if stop_requested(report/'STOP_REQUEST.json',external_stop_event):raise RuntimeError('STOP after reset before applying DSP recipe')
            desired=dict(baseline);desired.update(FROZEN)
            desired.update(PP_LIMITPLIMIT=[.1175],PP_AGCDESIREDLEVEL=[.001125],PP_AGCMAXGAIN=[62.5],PP_AGCGAIN=[62.5],AUDIO_MGR_OP_ALL=mux_arguments(attempt['profile']))
            reapplied=restore_exposed(control,desired)
            set_verified(control,'PP_AGCGAIN',[62.5])
            observed={n:values(control,n) for n in STATIC}
            if observed!=desired or {n:values(control,n) for n in OBSERVE_ONLY}!=initial['observe_only']:raise RuntimeError('Frozen settings/readback mismatch')
            save(folder/'configuration.json',dict(settings=observed,usb_bits=values(control,'USB_BIT_DEPTH'),reset=reset_receipt,reapply=reapplied,
                profile=attempt['profile'],decoded_streams=PROFILES[attempt['profile']],mux_api_arguments=mux_arguments(attempt['profile']),
                source_input=input_receipt,original_level_policy=plan['output_level_policy'],hidden_state_identical_proven=False,
                continuous_DSP=attempt['role']=='continuous',no_midpass_reset=True,
                guarded_preroll_changes_adaptive_history_relative_to_historical=True,same_pass_new_outputs_share_guarded_history=True),True)
            rates=attempt.get('telemetry_rates',dict(fast_hz=20.,gain_hz=2.,slow_hz=.2))
            telem=S6DQueuedTelemetryLogger(HOST.parent,folder/'telemetry',plan_timing['charged_playback_seconds']+15,**rates);telem_result=None;meta=None
            telem.start()
            if not telem.wait_ready(10):raise RuntimeError('Required telemetry not ready; no playback')
            audio_state=dict(audio_open_attempted=False,audio_handles_closed=True)
            meta=capture_to_disk(attempt,packed_path,folder,report/'STOP_REQUEST.json',telem,sd,xvf_endpoints,lambda:storage(report,payload),audio_state,external_stop_event)
            telem.stop('audio_closed');telem_result=telem.wait(20)
            if telem_result is None or telem_result.get('control_owner_closed_proven') is not True or telem_result.get('terminal_receipt_persisted') is not True:raise RuntimeError('Telemetry cleanup unproven; competing control forbidden')
            if not meta['writer_closed']:raise RuntimeError('Native PCM writer has not closed')
            with wave.open(str(folder/'native_packed.wav'),'rb') as wf:raw=unpack_pcm24(wf.readframes(wf.getnframes()))
            decoded,framing=decode_packed(raw,24)
            save_counts(folder/'decoded_six.wav',decoded,16000,24)
            streams=[]
            for i,(name,cat,source) in enumerate(PROFILES[attempt['profile']]):
                path=folder/(name+'.wav');save_counts(path,decoded[:,i],16000,24)
                streams.append(dict(name=name,category=cat,source=source,audio=binding(path),raw_gain=1.,
                    common_capture_start_native_frame=framing.get('startup_frames_excluded'),original_source_start_logical_frame=16000,
                    processed_source_to_capture_delay_samples=None))
            qa=input_qa(decoded,expected) if attempt['profile']=='P_INPUT_QA6' else dict(status='NOT_OBSERVABLE_PROCESSED_ONLY',exact_mic_recovery_claim=False)
            flags=[f for f in meta['callback_flags'] if f['flags'].strip().lower()!='priming output']
            qc=processed_qc(decoded,attempt['profile']);level=audio_gate(qc,read(plan['audio_acceptance_policy']['path']),attempt['required_nonzero_streams'])
            passed=not framing['marker_error_count'] and not flags and not meta['callback_errors'] and meta['carrier_frames_submitted']==plan_timing['native_carrier_frames'] and meta['terminal_padding_frames']<=plan_timing['maximum_terminal_padding_frames'] and telem_result['status']=='PASS' and (attempt['profile']!='P_INPUT_QA6' or qa['status']=='PASS')
            result=dict(status='PASS' if passed else 'FAIL',attempt=attempt,source_input=input_receipt,configuration=binding(folder/'configuration.json'),
                metadata=binding(folder/'capture_metadata.json'),native_packed=binding(folder/'native_packed.wav'),decoded=binding(folder/'decoded_six.wav'),
                streams=streams,framing=framing,input_qa=qa,output_qc=qc,level_screen=level,audio_acceptance_policy=plan['audio_acceptance_policy'],
                transport_integrity_status='PASS' if passed else 'FAIL',
                processed_source_tail_qualification='PENDING_BOUND_PHYSICAL_DELAY_AND_TAGGED_CONTROL_REVIEW',
                exact_MIC_samples_per_processed_scene_proven=False,telemetry=telem_result,
                physical_stream_identity_qualification=attempt.get('stream_identity_qualification','NOT_YET_QUALIFIED'),finished_utc=utc())
            save(folder/'case_result.json',result,True)
            active.update(status=result['status'],actual_callback_playback_s=meta['callback_playback_seconds'],
                actual_callback_source_progress_s=meta['source_payload_frames_submitted']/16000,result=binding(folder/'case_result.json'),ended_utc=utc())
            save(report/'physical_ledger.json',ledger);active=None;telem=None
            summary['completed_attempts'].append(binding(folder/'case_result.json'));save(batch_dir/'SUMMARY.json',summary)
            if not passed:raise RuntimeError('Physical attempt failed integrity/telemetry gate; preserve and diagnose')
        summary['status']='CAPTURED_PENDING_RESTORATION'
    except BaseException as e:
        summary['status']='BLOCKED';summary['error']=repr(e)
        (batch_dir/'FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8')
        if active is not None:
            active.update(status='FAIL',error=repr(e),ended_utc=utc(),actual_callback_playback_s=meta['callback_playback_seconds'] if meta else None,
                actual_callback_source_progress_s=meta['source_payload_frames_submitted']/16000 if meta else None)
            save(report/'physical_ledger.json',ledger)
    finally:
        if telem is not None and telem_result is None:
            try:telem.stop('owner_final_cleanup');telem_result=telem.wait(20)
            except BaseException as e:summary['telemetry_cleanup_error']=repr(e)
        if telem is not None:
            summary['telemetry_terminal_result']=telem_result
            summary['telemetry_terminal_wait_returned']=telem_result is not None
            summary['telemetry_output_directory']=str(telem.output_dir)
        telemetry_safe=telem is None or telem_result is not None and telem_result.get('control_owner_closed_proven') is True and telem_result.get('terminal_receipt_persisted') is True
        safe=restoration_permitted(audio_state,telemetry_safe)
        if mutated and initial and safe:
            try:
                set_verified(control,'I2S_INPUT_PACKED',[0])
                reset_receipt=reset(control,initial['usb_bits'][0],change_width=values(control,'USB_BIT_DEPTH')!=initial['usb_bits'])
                reapplied=restore_exposed(control,initial['settings'])
                after=dict(identity=control.identify(),settings={n:values(control,n) for n in STATIC},observe_only={n:values(control,n) for n in OBSERVE_ONLY})
                decision=restoration_decision(initial,after,reapplied)
                restoration=dict(schema_version=SCHEMA,**decision,status='PASS' if decision['accepted'] else 'FAIL',exact_recorded_configuration_match=decision['exact_full_snapshot_match'],readback=after,reset=reset_receipt,reapply=reapplied,
                    initial_state=binding(batch_dir/'initial_state.json'),packed_input_disabled=after['identity']['I2S_INPUT_PACKED']==[0],audio_handles_closed=True,
                    telemetry_process_closed=True,scope='Exact static/identity/ancillary/USB restoration plus immediate exact requested gain; later current AGC observation separate. Hidden adaptive history is not restored.')
            except BaseException as e:restoration=dict(status='FAIL',error=repr(e),initial_state_path=str(batch_dir/'initial_state.json'),telemetry_process_closed=safe)
        elif mutated:restoration=dict(status='FAIL',error='Telemetry or audio closure unproven; no competing restoration command issued',telemetry_process_closed=telemetry_safe,audio_handles_closed=audio_state.get('audio_handles_closed'),audio_state=audio_state)
        elif owned:restoration=dict(schema_version=SCHEMA,policy=NO_MUTATION_POLICY,status='PASS',exact_recorded_configuration_match=True,telemetry_process_closed=True,scope='No setters or playback occurred under this owner')
        try:
            if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            if lock:lock.close()
            restoration['hardware_lease_released']=True
        except BaseException as e:restoration.update(status='FAIL',lease_release_error=repr(e))
        save(batch_dir/'restoration.json',restoration,True)
        if owned and ledger is not None and (batch_dir/'owner_acquired.json').exists():
            ledger.setdefault('batches',{})[batch]=dict(restoration=binding(batch_dir/'restoration.json'),owner=binding(batch_dir/'owner_acquired.json'))
            save(report/'physical_ledger.json',ledger)
        if summary['status']=='CAPTURED_PENDING_RESTORATION' and restoration['status']=='PASS':summary['status']='COMPLETE_CAPTURE_BATCH'
        try:
            for b in read(authorization)['source_bindings']:verify(b)
            summary['executed_source_bytes_unchanged_after_batch']=True
        except BaseException as e:
            summary.update(status='BLOCKED',executed_source_bytes_unchanged_after_batch=False,source_epoch_error=repr(e))
        summary.update(ended_utc=utc(),restoration=restoration['status']);save(batch_dir/'SUMMARY.json',summary)
    print(json.dumps(summary,indent=2),flush=True)
    if summary['status']!='COMPLETE_CAPTURE_BATCH':raise RuntimeError('Capture batch incomplete; inspect preserved exact results/restoration')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['check-plan','execute'])
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--authorization',type=Path);p.add_argument('--batch');p.add_argument('--attempt-ids',nargs='+')
    a=p.parse_args()
    if a.action=='check-plan':
        plan=validate_plan(a.plan,a.authorization);print(json.dumps(dict(status='PLAN_VALIDATED_NO_HARDWARE',attempts=len(plan['attempts']),plan=binding(a.plan))))
    else:
        if not a.authorization or not a.batch or not a.attempt_ids:p.error('execute requires authorization, batch and exact attempt IDs')
        execute(a.plan,a.authorization,a.batch,a.attempt_ids)
