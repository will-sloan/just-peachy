"""B3 recorded-terminal fresh restore; see README_S6D_CLOSED_TELEMETRY_RESTORE_V5.md."""
from __future__ import annotations
import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time

SCHEMA='edge-s6d-restoration-recovery.v2'
KIND='closed_recorded_telemetry_fresh_restore'
REVIEW_STATUS='ROOT_ACCEPTED_RECORDED_TELEMETRY_RECOVERY_V5_SOURCES_V1'
ROOT_THREAD='01a0812d-3ff0-7ed0-a06c-4df61b62a459'
SIM=next((p for p in Path(__file__).resolve().parents if p.name=='simulation'),Path('C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation'))
R=SIM/'reports/S6D/20260913T195357Z'
ROOT=SIM.parent
FIELDS=('AEC_AZIMUTH_VALUES','AEC_SPENERGY_VALUES','AUDIO_MGR_SELECTED_AZIMUTHS','PP_AGCGAIN','AEC_AECCONVERGED','AEC_AECPATHCHANGE','AEC_RT60','AEC_CURRENT_IDLE_TIME','AEC_MIN_IDLE_TIME','AUDIO_MGR_CURRENT_IDLE_TIME','AUDIO_MGR_MIN_IDLE_TIME','I2S_CURRENT_IDLE_TIME','I2S_MIN_IDLE_TIME','MAX_CONTROL_TIME')
COUNTS=(4,4,2,1,1,1,1,1,1,1,1,1,1,1)
CONTROL_MARKERS=('s6d_capture_owner','s6d_capture_supervisor_bridge','s6d_telemetry','s6dqueuedtelemetry','run-s6d-telemetry.ps1','s3_hardware.py','s4_restore.py','s6d_readonly_state_recovery','s6d_closed_telemetry_restore','measurement_app','xvf_host.exe','device_usb.dll')
CONTROL_NAMES=('python','pythonw','powershell','pwsh','cmd','dotnet','xvf_host')

def need(value,message):
    if not value:raise ValueError(message)
def positive(x):return type(x) in (int,float) and math.isfinite(x) and x>0
def utc():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'),parse_constant=lambda x:need(False,'Nonfinite JSON'))
def bind(path):
    p=Path(path).resolve();a=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    z=p.stat();need((a.st_size,a.st_mtime_ns)==(z.st_size,z.st_mtime_ns),'Input changed during hash')
    return dict(path=str(p),bytes=z.st_size,sha256=h.hexdigest())
def verify(ref):need(bind(ref['path'])==ref,'Changed bound file: '+ref['path']);return read(ref['path'])
def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def policy_module():
    p=SIM/'scripts/s6d_restoration_policy_v1.py';need(bind(p)['sha256']=='72fe3e01e4dd1962de6f8603fe1d30e8dbaa5b175f66f565010a143f2822badd','Accepted pure policy changed')
    spec=importlib.util.spec_from_file_location('closed_telemetry_policy',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def json_lines(path):
    rows=[]
    with Path(path).open('rb') as f:
        for line in f:
            need(len(line)<=65536 and line.endswith(b'\n'),'Partial/oversized telemetry line')
            row=json.loads(line.decode('utf-8-sig'),parse_constant=lambda x:need(False,'Nonfinite telemetry JSON'));need(isinstance(row,dict),'Telemetry object required');rows.append(row)
    return rows

def native_closure(refs,expected_rows):
    need(type(expected_rows) is int and expected_rows>0,'Exact positive measurement population required')
    for b in refs.values():need(bind(b['path'])==b,'Changed telemetry file')
    native=read(refs['native_result']['path']);inspection=read(refs['native_inspection']['path'])
    need(native.get('status')=='PASS' and native.get('error') is None and type(native.get('cleanup_return')) is int and native['cleanup_return']==0,'Native cleanup did not pass')
    need(native.get('pending_reads_at_exit')==[False]*14 and all(type(x) is bool for x in native['pending_reads_at_exit']),'All14 pending-read flags must be false')
    need(native.get('no_firmware_or_parameter_writes') is True and inspection.get('process_bits')==32 and inspection.get('inspection_only_no_device_initialization') is True,'Unexpected native transport/source contract')
    need(refs['stderr']['bytes']==0,'Native stderr not empty')
    samples=json_lines(refs['native_samples']['path']);stdout=json_lines(refs['stdout']['path']);received=json_lines(refs['received']['path'])
    need(all(type(r.get('sequence')) is int for r in samples) and [r.get('sequence') for r in samples]==list(range(len(samples))),'Native sample sequence incomplete')
    measurement=[x for x in samples if x.get('phase')=='measurement'];live=[x for x in stdout if x.get('phase')=='measurement'];terminal=[x for x in stdout if x.get('phase')!='measurement']
    need(len(terminal)==1 and terminal[0]==native and stdout[-1]==native,'Exact native terminal result missing from stdout')
    need(measurement==live and len(live)==len(received)==expected_rows,'Native/stdout/received measurement population differs')
    counts=Counter()
    additions={'host_line_arrival_monotonic_ns','parse_ok','receipt_sequence','host_response_end_monotonic_ns'}
    for index,(a,b) in enumerate(zip(live,received)):
        name=a.get('command');need(name in FIELDS and len(a.get('values',[]))==COUNTS[FIELDS.index(name)],'Unknown native field/width')
        need(b.get('parse_ok') is True and type(b.get('receipt_sequence')) is int and b['receipt_sequence']==index,'Python received-row sequence/parse proof differs')
        need({k:v for k,v in b.items() if k not in additions}==a and b.get('host_response_end_monotonic_ns')==a.get('response_end_monotonic_ns'),'Received payload differs from actual native row')
        need(positive(b.get('host_line_arrival_monotonic_ns')) and b['host_line_arrival_monotonic_ns']>=a['response_end_monotonic_ns'],'Impossible telemetry receive clock')
        counts[name]+=1
    need(set(native['per_field'])==set(FIELDS) and all(type(native['per_field'][name]['count']) is int and native['per_field'][name]['count']==counts[name] for name in FIELDS),'Native per-field count differs')
    need(type(native.get('completed_cycles')) is int and native['completed_cycles']>0 and all(counts[n]==native['completed_cycles'] for n in FIELDS[:3]),'Required native cycles incomplete')
    with Path(refs['native_transactions']['path']).open('r',encoding='utf-8-sig') as f:lines=f.read().splitlines()
    need(lines and lines[0].split('\t')==['sequence','cycle','phase','field_index','attempt','request_start_monotonic_ns','response_end_monotonic_ns','transport_return','device_status','raw_response_base64'],'Native transaction header differs')
    last={};retry=0
    for index,line in enumerate(lines[1:]):
        cols=line.split('\t');need(len(cols)==10,'Partial transaction row');seq,field,start,end,transport,status=(int(cols[k]) for k in (0,3,5,6,7,8));packet=base64.b64decode(cols[9],validate=True)
        need(seq==index and 0<=field<14 and 0<start<=end and transport==0 and status in (0,64),'Invalid native transaction sequence/status')
        need(len(packet)==1+4*COUNTS[field] and packet[0]==status,'Native transaction response bytes differ');last[field]=status;retry+=status==64
    need(len(lines)-1==native['transactions'] and retry==native['retry_responses'] and all(s==0 for s in last.values()),'Native transaction population/pending terminal response differs')
    for b in refs.values():need(bind(b['path'])==b,'Telemetry changed during closure review')
    return dict(status='CLOSED_NATIVE_TELEMETRY_AND_RECEIVED_POPULATION_VERIFIED',native_result=refs['native_result'],bindings=refs,measurement_rows=expected_rows,counts=dict(counts),transactions=len(lines)-1,native_cleanup_return=0,pending_reads_at_exit=[False]*14,stderr_empty=True,native_stdout_terminal_present=True,historical_python_terminal_receipt_present=False,historical_python_manager_outcome='UNRECORDED; native completion and current process absence are separate evidence, not a reconstructed Python result')

def scan_decision(snapshot,known,current):
    need(snapshot.get('complete') is True and snapshot.get('errors')==[] and isinstance(snapshot.get('rows'),list) and positive(snapshot.get('observed_unix')),'Complete fresh process census required')
    need(type(current.get('pid')) is int and current['pid']>0 and positive(current.get('creation_time')),'Current process identity invalid')
    seen=set();hazards=[];opaque=[];known_states=[]
    for item in known:need(type(item.get('pid')) is int and item['pid']>0 and positive(item.get('creation_time')),'Original process identity invalid')
    for row in snapshot['rows']:
        pid=row.get('pid');need(type(pid) is int and pid>=0 and pid not in seen,'Invalid/duplicate census PID');seen.add(pid)
        if pid==current['pid']:
            need(positive(row.get('creation_time')) and abs(row['creation_time']-current['creation_time'])<.02,'Current PID creation mismatch');continue
        name=str(row.get('name') or '').casefold();cmd=row.get('cmdline');text=' '.join(cmd).casefold() if isinstance(cmd,list) and all(isinstance(x,str) for x in cmd) else None
        if any(name.removesuffix('.exe').startswith(n) for n in CONTROL_NAMES) and (text is None or not positive(row.get('creation_time'))):opaque.append(pid)
        if name=='xvf_host.exe' or text is not None and any(token in text for token in CONTROL_MARKERS):hazards.append(dict(pid=pid,creation_time=row.get('creation_time'),name=row.get('name'),cmdline=cmd))
    for item in known:
        rows=[x for x in snapshot['rows'] if x['pid']==item['pid']]
        same=bool(rows and positive(rows[0].get('creation_time')) and abs(rows[0]['creation_time']-item['creation_time'])<.02)
        need(not rows or positive(rows[0].get('creation_time')),'Original PID now unreadable')
        known_states.append(dict(original=item,same_instance_present=same,pid_reused=bool(rows and not same)))
    need(current['pid'] in seen and not opaque and not hazards and not any(x['same_instance_present'] for x in known_states),'Current control owner/process closure not proven')
    return dict(status='NO_MATCHING_TASK_CONTROL_PROCESSES',current=current,known_processes=known_states,matching_processes=[],unreadable_control_processes=[],processes_scanned=len(seen),excluded_only_current_pid=True,telemetry_pid_creation_persisted=True,scope='All inspectable command lines scanned for exact task-control markers; critical interpreter/control processes with unreadable command lines or creation times block. No process was stopped or killed.')


def recorded_terminal_closure(refs,expected_rows,bridge,summary):
    """Validate the preserved Python FAIL, recorded PID and complete native population."""
    keys=('native_result','native_inspection','native_samples','native_transactions','stdout','received','stderr')
    base=native_closure({k:refs[k] for k in keys},expected_rows)
    for b in refs.values():need(bind(b['path'])==b,'Recorded telemetry evidence changed')
    terminal=verify(refs['python_terminal']);identity=verify(refs['process_identity']);late=verify(refs['late_reader_closure']);events=json_lines(refs['lifecycle']['path'])
    need(terminal.get('status')=='FAIL' and terminal.get('exit_code') is None and terminal.get('errors')==['Native process exceeded bounded cooperative closure; no termination issued'],'Exact recorded cooperative-exit failure required')
    for key in ('native_process_exited','control_owner_closed_proven','actual_stdout_eof','stderr_closed','forced_termination','process_termination_issued'):need(terminal.get(key) is False,'Historical unproven exit/IO or no-termination flag differs')
    for key in ('reader_io_closed','reader_thread_closed','process_identity_persisted','verified_native_terminal_frame','native_cleanup_verified','terminal_receipt_persisted'):need(terminal.get(key) is True,'Recorded terminal/reader proof incomplete')
    need(terminal.get('native_evidence_errors')==[] and terminal.get('stderr_bytes')==0 and terminal.get('stop_reason')=='audio_closed','Recorded native/stop evidence differs')
    need(terminal.get('process_identity')==identity and type(identity.get('pid')) is int and identity['pid']>0 and positive(identity.get('creation_time')),'Recorded exact telemetry PID/creation required')
    need(identity.get('parent_pid')==bridge['pid'] and identity.get('parent_creation_time')==bridge['creation_time'] and terminal.get('argv')==identity.get('argv'),'Recorded telemetry owner/argv differs')
    need(terminal.get('source_bindings')==identity.get('sources') and terminal.get('library_bindings')==identity.get('libraries'),'Recorded producer/library identity differs')
    for b in identity['sources']+identity['libraries']:need(bind(b['path'])==b,'Recorded producer or DLL changed')
    need(terminal.get('native_result')==read(refs['native_result']['path']) and terminal.get('native_result_binding')==refs['native_result'] and terminal.get('inspection_binding')==refs['native_inspection'] and terminal.get('receipt_file')==refs['received'] and terminal.get('counts')==base['counts'],'Python/native/received binding or population differs')
    need(summary.get('telemetry_terminal_result')==terminal and summary.get('telemetry_terminal_wait_returned') is True and Path(summary.get('telemetry_output_directory','')).resolve()==Path(refs['received']['path']).parent,'Owner summary differs from exact persisted terminal FAIL')
    expected=['START_REQUESTED','PROCESS_CREATED','COOPERATIVE_STOP_WRITTEN','NATIVE_TERMINAL_FRAME_VERIFIED','READER_FINISHED','PROCESS_CLOSURE_UNPROVEN','MANAGER_SETTLING']
    need([r.get('stage') for r in events]==expected and [r.get('sequence') for r in events]==list(range(len(expected))),'Exact saved lifecycle sequence required')
    times=[r.get('monotonic_ns') for r in events];need(all(positive(t) for t in times) and times==sorted(times),'Invalid saved lifecycle clocks')
    need(events[1].get('identity')==events[5].get('identity')==identity and events[0].get('argv')==identity['argv'] and events[0].get('sources')==identity['sources'],'Lifecycle ownership/source differs')
    need(events[2].get('reason')=='audio_closed' and events[3].get('native_result')==refs['native_result'] and events[3].get('received_rows')==expected_rows and events[4].get('io_closed') is True and events[4].get('verified_terminal_frame') is True and events[4].get('actual_stdout_eof') is False and events[6].get('exit_code') is None,'Lifecycle stop/native/reader/exit evidence differs')
    need(late.get('status')=='DIAGNOSTIC_ONLY_ORIGINAL_FAILURE_PRESERVED' and late.get('original_terminal_status')=='FAIL' and late.get('process_identity')==identity and late.get('process_exited') is False and late.get('reader_io_closed') is True and late.get('verified_terminal_frame') is True and late.get('actual_stdout_eof') is False and late.get('recovery_or_playback_authorized') is False,'Late diagnostic cannot replace the recorded failure')
    return dict(base,bindings=refs,historical_python_terminal_receipt_present=True,historical_python_manager_outcome='FAIL; native process exit and stderr closure were unproven at the bounded stop deadline; no exit time or cause inferred',python_terminal=refs['python_terminal'],process_identity=refs['process_identity'],historical_telemetry_pid_creation=dict(pid=identity['pid'],creation_time=identity['creation_time']),terminal_to_unproven_seconds=(times[5]-times[3])/1e9,stop_to_unproven_seconds=(times[5]-times[2])/1e9)

def required_sources():
    producer=Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_04_19/P_MAIN6/P_MAIN6_S45_04_19/telemetry/source')
    return [Path(__file__),Path(__file__).with_name('README_S6D_CLOSED_TELEMETRY_RESTORE_V5.md'),SIM/'scripts/s6d_restoration_policy_v1.py',*[SIM/'scripts'/n for n in ('s3_hardware.py','s4_restore.py','s4_common.py','s0_common.py')],ROOT/'measurement_app/core.py',ROOT/'measurement_app/__init__.py',*[ROOT/'tools/xvf321/binary/host_v3.0.0/win32'/n for n in ('xvf_host.exe','device_usb.dll','command_map.dll')],*[producer/n for n in ('s6d_telemetry_v2.py','S6DQueuedTelemetry.cs','Run-S6D-Telemetry.ps1','s6d_capture_transport.py')]]


def tcp_census(provider):
    """Read the complete OS TCP table; never open a socket or infer idle from timeout."""
    rows=[];errors=[]
    try:
        for c in provider.net_connections(kind='tcp'):
            rows.append(dict(family=int(c.family),socket_type=int(c.type),status=c.status,
                             local_address=list(c.laddr),remote_address=list(c.raddr),pid=c.pid))
    except BaseException as e:errors.append(repr(e))
    return dict(schema='s6d-tcp-listener-census.v1',api="psutil.net_connections(kind='tcp')",complete=not errors,
                errors=errors,rows=rows,observed_unix=time.time(),observed_utc=utc())


def tcp_listener_decision(snapshot):
    """Pure saved-census verifier, covering IPv4/IPv6 loopback and wildcard binds."""
    need(snapshot.get('schema')=='s6d-tcp-listener-census.v1' and snapshot.get('api')=="psutil.net_connections(kind='tcp')" and snapshot.get('complete') is True and snapshot.get('errors')==[] and isinstance(snapshot.get('rows'),list) and positive(snapshot.get('observed_unix')),'Complete OS TCP census required')
    statuses={'LISTEN','ESTABLISHED','SYN_SENT','SYN_RECV','FIN_WAIT1','FIN_WAIT2','TIME_WAIT','CLOSE','CLOSE_WAIT','LAST_ACK','CLOSING','NONE','DELETE_TCB'}
    matches=[];listeners=0
    for row in snapshot['rows']:
        need(isinstance(row,dict) and type(row.get('family')) is int and row['family'] in (2,10,23) and type(row.get('socket_type')) is int and row['socket_type']==1 and row.get('status') in statuses,'Unknown TCP table row')
        local=row.get('local_address');need(isinstance(local,list) and (len(local)==2 or local==[] and row['status']!='LISTEN'),'Unknown local TCP address')
        if not local:continue
        need(isinstance(local[0],str) and type(local[1]) is int and 0<=local[1]<=65535,'Malformed local TCP endpoint')
        address=ipaddress.ip_address(local[0]);need((address.version==4)==(row['family']==2),'TCP family/address mismatch')
        if row['status']!='LISTEN':continue
        need(local[1]>0,'Listener port cannot be zero');listeners+=1
        mapped=getattr(address,'ipv4_mapped',None)
        accepts_loopback=address.is_loopback or address.is_unspecified or mapped is not None and (mapped.is_loopback or mapped.is_unspecified)
        if local[1] in (8765,8766,8767) and accepts_loopback:matches.append(row)
    need(not matches,'Recorder loopback/wildcard TCP listener present')
    return dict(status='NO_RECORDER_LOOPBACK_OR_WILDCARD_LISTENER',ports=[8765,8766,8767],rows_scanned=len(snapshot['rows']),listeners_scanned=listeners,matching_listeners=[],api=snapshot['api'],connection_probe_used=False,timeout_interpreted_as_idle=False)

def inspect_review(path,expected_hash,execute=False):
    ref=bind(path);need(ref['sha256']==expected_hash,'Exact root review hash required');a=read(path)
    need(a.get('status')==REVIEW_STATUS if execute else a.get('status') in (REVIEW_STATUS,'PROPOSED_SOURCE_REVIEW_ONLY'),'Root review status absent')
    if execute:need(a.get('allow_fresh_exposed_restore') is True,'Explicit fresh restore authority absent')
    need(a.get('owner_thread_id')==ROOT_THREAD and a.get('run_id')=='20260913T195357Z' and a.get('original_batch')=='bank_v3_P_MAIN6_B3' and a.get('recovery_kind')==KIND,'Wrong recovery owner/batch/kind')
    need(isinstance(a.get('historical_telemetry_pid_creation'),dict),'Recorded telemetry PID/creation is required for this distinct failure')
    by_path={b['path']:b for b in a['source_bindings']};need(len(by_path)==len(a['source_bindings']) and {str(p.resolve()) for p in required_sources()}<=set(by_path),'Required exact restoration source graph missing')
    for b in a['source_bindings']:need(bind(b['path'])==b,'Restoration source changed')
    original=a['original_bindings'];values={k:verify(b) for k,b in original.items()};batch=R/'hardware_batches'/a['original_batch']
    for key,name in (('owner','owner_acquired.json'),('restoration','restoration.json'),('initial_state','initial_state.json'),('admission','admission.json'),('summary','SUMMARY.json')):need(Path(original[key]['path']).resolve()==batch/name,'Original batch path mismatch')
    need(Path(original['ledger']['path']).resolve()==R/'physical_ledger.json','Wrong physical ledger')
    record=values['ledger']['batches'][a['original_batch']];need(record['owner']==original['owner'] and record['restoration']==original['restoration'],'Original ledger owner/restoration differs')
    failed=values['restoration'];need(failed.get('status')=='FAIL' and failed.get('audio_handles_closed') is True and failed.get('hardware_lease_released') is True and failed.get('telemetry_process_closed') is False,'Only this explicitly closed-audio/lease telemetry-unproven failure is supported')
    need(not any(r.get('status')=='STARTED' for r in values['ledger']['passes']),'Unclosed physical attempt in ledger')
    bridge=values['bridge_failure'];launch=values['supervisor_launch'];need(bridge['pid']==values['owner']['pid'] and bridge.get('status')=='FAILED' and bridge.get('protocol_observer_closed') is True and bridge.get('protocol_observer_errors')==[],'Original owner/bridge closure differs')
    need(bridge['plan']==values['admission']['plan'] and bridge['authorization']==values['admission']['authorization'] and bridge.get('job_id')==a['original_batch'] and bridge.get('capture_same_process') is True and values['summary'].get('status')=='BLOCKED','Original failed batch binding differs')
    known=[dict(role='capture_owner',pid=bridge['pid'],creation_time=bridge['creation_time']),dict(role='supervisor',pid=launch['pid'],creation_time=launch['creation_time'])]
    for x in known:need(type(x['pid']) is int and x['pid']>0 and positive(x['creation_time']),'Invalid persisted process identity')
    snapshot=verify(a['root_process_snapshot']);need(snapshot.get('no_matching_task_control_processes') is True and snapshot.get('matching_processes')==[] and snapshot.get('query_errors')==[],'Initial root process census incomplete')
    confirmation=verify(a['output_confirmation']);need(confirmation.get('own_analog_outputs_disconnected_confirmed') is True,'Bound XVF output confirmation absent')
    telemetry=a['telemetry_bindings'];folder=Path(telemetry['received']['path']).parent
    need(folder==Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_04_19/P_MAIN6/P_MAIN6_S45_04_19/telemetry'),'Wrong failed telemetry attempt')
    expected_paths={'native_result':folder/'native/result.json','native_inspection':folder/'native/command_map_inspection.json','native_samples':folder/'native/samples.jsonl','native_transactions':folder/'native/transactions.tsv','stdout':folder/'stdout.bin','received':folder/'received_telemetry.jsonl','stderr':folder/'stderr.bin','python_terminal':folder/'result.json','process_identity':folder/'PROCESS_IDENTITY.json','lifecycle':folder/'lifecycle.jsonl','late_reader_closure':folder/'late_reader_closure.json'}
    need(set(telemetry)==set(expected_paths) and all(Path(telemetry[k]['path']).resolve()==p for k,p in expected_paths.items()),'Telemetry source paths differ')
    proof=recorded_terminal_closure(telemetry,a['expected_measurement_rows'],bridge,values['summary']);inspection=read(telemetry['native_inspection']['path'])
    need(a['historical_telemetry_pid_creation']==proof['historical_telemetry_pid_creation'],'Root review recorded PID differs')
    known.append(dict(role='native_telemetry',**proof['historical_telemetry_pid_creation']))
    for name,key in (('device_usb.dll','device_usb_sha256'),('command_map.dll','command_map_sha256')):need(inspection[key]==by_path[str((ROOT/'tools/xvf321/binary/host_v3.0.0/win32'/name).resolve())]['sha256'],'Actual native DLL inspection differs')
    out=Path(a['recovery_output_root']).resolve();need(out.is_relative_to(R) and out.parent!=out and not out.exists(),'Fresh bounded recovery output required')
    configuration=failed_configuration_proof(original,values)
    return dict(review=a,review_ref=ref,original=original,values=values,known=known,native_proof=proof,output=out,failed_configuration_proof=configuration)


def failed_configuration_proof(originals,values):
    """Bind the recorded failed04_19 state to its admitted attempt and original ledger."""
    expected=Path('G:/Just_Peachy_S6D/20260913T195357Z/bank_captures_v1/beam_bank/S45_04_19/P_MAIN6/P_MAIN6_S45_04_19/configuration.json')
    ref=originals['failed_configuration'];need(Path(ref['path']).resolve()==expected,'Exact failed04_19 configuration path required')
    config=verify(ref);admission=values['admission'];plan=verify(admission['plan']);exact=policy_module().exact
    attempt_id='P_MAIN6_S45_04_19';rows=[x for x in plan['attempts'] if x.get('attempt_id')==attempt_id]
    need(len(rows)==1 and attempt_id in admission['attempt_ids'],'Unique original admitted failed attempt required');attempt=rows[0]
    need(attempt.get('case_id')=='S45_04_19' and attempt.get('profile')==config.get('profile')=='P_MAIN6','Failed configuration case/profile differs')
    source=config['source_input']['source'];need(source==attempt['source_audio'],'Failed configuration source differs from admitted attempt')
    charged=[x for x in values['ledger']['passes'] if x.get('attempt_id')==attempt_id]
    need(len(charged)==1 and all(charged[0].get(k)==v for k,v in dict(batch='bank_v3_P_MAIN6_B3',case_id=attempt['case_id'],profile=attempt['profile'],status='FAIL',input_sha256=source['sha256']).items()),'Original charged failure/source differs')
    need(config['reapply'].get('exact_match') is True and exact(config['reapply'].get('observed'),config['settings']),'Failed configured settings lacked exact immediate readback')
    metadata_ref=originals['failed_capture_metadata'];need(Path(metadata_ref['path']).resolve()==expected.with_name('capture_metadata.json'),'Exact failed capture metadata required')
    metadata=verify(metadata_ref);need(metadata.get('audio_handles_closed') is True and metadata.get('writer_closed') is True,'Failed capture audio/writer closure absent')
    return dict(status='EXACT_FAILED_CONFIGURATION_BOUND',configuration=ref,capture_metadata=metadata_ref,plan=admission['plan'],attempt_id=attempt_id,case_id=attempt['case_id'],profile=attempt['profile'],source_audio=source)


def pre_restore_identity_decision(initial,before,configuration):
    """Accept only either complete exact state; do not independently mix mutable fields."""
    exact=policy_module().exact;original=initial['identity'];expected=dict(original)
    keys=('AUDIO_MGR_MIC_GAIN','AUDIO_MGR_REF_GAIN','AUDIO_MGR_SYS_DELAY','I2S_INPUT_PACKED')
    need(set(before)==set(original),'Device identity keys differ before setters')
    need(exact(configuration['settings']['I2S_DAC_DSP_ENABLE'],original['I2S_DAC_DSP_ENABLE']),'Configured DAC differs from original')
    for key in keys:expected[key]=configuration['settings'][key]
    expected['USB_BIT_DEPTH']=configuration['usb_bits']
    original_match=exact(before,original);configured_match=exact(before,expected)
    delta={k:dict(original=original[k],observed=before[k],expected_configured=expected[k]) for k in sorted(original) if not exact(before[k],original[k])}
    return dict(accepted=original_match or configured_match,reason='EXACT_ORIGINAL_IDENTITY' if original_match else 'EXACT_RECORDED_FAILED_CONFIGURATION_IDENTITY' if configured_match else 'NEITHER_EXACT_ORIGINAL_NOR_RECORDED_FAILED_CONFIGURATION',exact_original_match=original_match,exact_configured_match=configured_match,expected_configured_identity=expected,deltas_from_original=delta,mutable_projection_fields=list(keys)+['USB_BIT_DEPTH'],tolerance_used=False)

IDENTITY_GETTERS=('VERSION','AEC_MIC_ARRAY_TYPE','AEC_NUM_MICS','AEC_MIC_ARRAY_GEO',
    'AUDIO_MGR_MIC_GAIN','AUDIO_MGR_REF_GAIN','AUDIO_MGR_SYS_DELAY','USB_BIT_DEPTH','I2S_INPUT_PACKED','I2S_DAC_DSP_ENABLE')


def pre_restore_identity(control):
    """Same eleven read-only queries as Control.identify; packed0/1 before restore."""
    d={name:control.values(name) for name in IDENTITY_GETTERS}
    d['build_reply']=control.query('BLD_MSG')
    exact=policy_module().exact
    need(exact(d['VERSION'],[3,2,1]) and exact(d['AEC_MIC_ARRAY_TYPE'],[1]) and exact(d['AEC_NUM_MICS'],[4]) and isinstance(d['build_reply'],str) and 'ua-io48-lin' in d['build_reply'],'Expected verified 3.2.1 ua-io48-lin / four-microphone linear firmware before restore')
    packed=d['I2S_INPUT_PACKED']
    need(isinstance(packed,list) and len(packed)==1 and type(packed[0]) is int and packed[0] in (0,1),'Pre-restore packed input must be exactly enum0 or1')
    need(exact(d['I2S_DAC_DSP_ENABLE'],[0]),'Unexpected DAC routing before restore')
    return d


class WindowsServices:
    fixture=False
    def __init__(self):
        import psutil
        self.psutil=psutil;self.identity=dict(pid=os.getpid(),creation_time=psutil.Process().create_time());self.lock=None;self.owned=False;self.control=None
    def census(self):
        rows=[];errors=[]
        try:
            for process in self.psutil.process_iter():
                try:
                    d=process.as_dict(attrs=['pid','name','cmdline','create_time'],ad_value=None);rows.append(dict(pid=d['pid'],name=d['name'],cmdline=d['cmdline'],creation_time=d['create_time']))
                except self.psutil.NoSuchProcess:continue
                except BaseException as e:errors.append(repr(e))
        except BaseException as e:errors.append(repr(e))
        return dict(complete=not errors,errors=errors,rows=rows,observed_unix=time.time(),observed_utc=utc())
    def ports_idle(self):
        return tcp_census(self.psutil)
    def acquire(self):
        import msvcrt
        self.lock=(ROOT/'measurement_app/hardware.lock').open('r+b');self.lock.seek(0);msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1);self.owned=True
    def release(self):
        import msvcrt
        if self.owned:self.lock.seek(0);msvcrt.locking(self.lock.fileno(),msvcrt.LK_UNLCK,1);self.owned=False
        if self.lock:self.lock.close()
        return True
    def initialize_control(self,commands):
        sys.dont_write_bytecode=True;sys.path.insert(0,str(SIM/'scripts'));sys.path.insert(0,str(ROOT))
        from measurement_app.core import Control
        from s3_hardware import STATIC,OBSERVE_ONLY,values,set_verified,reset
        from s4_restore import restore_exposed
        self.control=Control(commands);self.static=STATIC;self.observe_only=OBSERVE_ONLY;self.values=values;self.set_verified=set_verified;self.reset=reset;self.restore_exposed=restore_exposed
    def identify(self):return pre_restore_identity(self.control)
    def restore(self,initial):
        need(set(initial['settings'])==set(self.static) and set(initial['observe_only'])==set(self.observe_only),'Original full getter maps incomplete')
        self.set_verified(self.control,'I2S_INPUT_PACKED',[0])
        reset=self.reset(self.control,initial['usb_bits'][0],change_width=self.values(self.control,'USB_BIT_DEPTH')!=initial['usb_bits'])
        reapply=self.restore_exposed(self.control,initial['settings'])
        readback=dict(identity=self.control.identify(),settings={n:self.values(self.control,n) for n in self.static},observe_only={n:self.values(self.control,n) for n in self.observe_only})
        return dict(reset=reset,reapply=reapply,readback=readback)

def rehash(context):
    need(bind(context['review_ref']['path'])==context['review_ref'],'Root review changed')
    for b in context['review']['source_bindings']+list(context['original'].values())+list(context['review']['telemetry_bindings'].values()):need(bind(b['path'])==b,'Source/original data changed during recovery')

def recover_prevalidated(context,services):
    """Orchestration seam for fake-service fixtures. CLI supplies only real WindowsServices."""
    a=context['review'];out=context['output'];out.mkdir(parents=True,exist_ok=False);policy=policy_module();initial=context['values']['initial_state'];owned=False;error=None
    shutil.copyfile(context['original']['ledger']['path'],out/'ORIGINAL_LEDGER.json');ledger_snapshot=bind(out/'ORIGINAL_LEDGER.json');need((ledger_snapshot['bytes'],ledger_snapshot['sha256'])==(context['original']['ledger']['bytes'],context['original']['ledger']['sha256']),'Ledger snapshot differs')
    result=dict(schema='s6d-closed-telemetry-fresh-restore-result.v1',status='STARTED',recovery_kind=KIND,fixture_only=services.fixture,started_utc=utc(),recovery_identity=services.identity,source_review=context['review_ref'],original_bindings=context['original'],original_ledger_snapshot=ledger_snapshot,native_telemetry_closure=context['native_proof'],known_processes=context['known'],process_scans=[],hardware_lock_acquired=False,hardware_lock_released=False,device_restore_started=False,device_restore_completed=False,audio_streams_opened=0,packed_playback_attempts=0,processes_terminated=0,historical_python_terminal_receipt_present=True,original_telemetry_process_closed=False)
    def checkpoint(label):
        snapshot=services.census();decision=scan_decision(snapshot,context['known'],services.identity);ports=services.ports_idle()
        path=out/(label+'_PROCESS_SNAPSHOT.json');save(path,snapshot);tcp_path=out/(label+'_TCP_LISTENERS.json');save(tcp_path,ports)
        tcp_decision=tcp_listener_decision(ports)
        proof=dict(stage=label,snapshot=bind(path),decision=decision,ports_idle=True,tcp_listeners=bind(tcp_path),tcp_listener_decision=tcp_decision,hardware_lock_held=owned);result['process_scans'].append(proof);return proof
    try:
        rehash(context);checkpoint('before_lock');services.acquire();owned=True;result['hardware_lock_acquired']=True
        rehash(context);checkpoint('locked_before_getter');services.initialize_control(out/'commands');before=services.identify();result['before_identity']=before
        need(policy.exact(before.get('VERSION'),[3,2,1]) and policy.exact(before.get('AEC_MIC_ARRAY_TYPE'),[1]) and before.get('USB_BIT_DEPTH') in ([16,16],[24,24]),'Unexpected device identity before restore')
        configuration_proof=failed_configuration_proof(context['original'],context['values']);result['failed_configuration_proof']=configuration_proof
        before_decision=pre_restore_identity_decision(initial,before,context['values']['failed_configuration']);result['pre_restore_identity_comparison']=before_decision
        need(before_decision['accepted'] is True,'Device identity is neither exact original nor exact recorded failed configuration before setters')
        rehash(context);checkpoint('locked_before_setter');save(out/'RESTORE_STARTED.json',dict(recovery_identity=services.identity,source_review=context['review_ref'],utc=utc(),original_restoration=context['original']['restoration'],no_playback=True))
        result['device_restore_started']=True;fresh=services.restore(initial);result['fresh_restore']=fresh
        decision=policy.restoration_decision(initial,fresh['readback'],fresh['reapply']);result['policy_evaluation']=decision
        need(decision['accepted'] is True and fresh['readback']['identity']['I2S_INPUT_PACKED']==[0] and fresh['readback']['identity']['USB_BIT_DEPTH']==initial['usb_bits'],'Fresh restoration policy/packed/USB proof rejected')
        result['device_restore_completed']=True;checkpoint('locked_after_restore');rehash(context)
    except BaseException as e:error=repr(e);result['error']=error
    finally:
        try:services.release();result['hardware_lock_released']=owned;owned=False
        except BaseException as e:error=repr(e);result['release_error']=error
        result.update(status='FRESH_RESTORE_VERIFIED' if error is None else 'FAILED_UNRESOLVED',finished_utc=utc());save(out/'RESULT.json',result)
    if error:raise RuntimeError(error)
    need(result['hardware_lock_acquired'] and result['hardware_lock_released'],'Actual owned lease closure missing')
    rec=dict(schema_version=SCHEMA,recovery_kind=KIND,status='PASS',fixture_only=services.fixture,original_restoration=context['original']['restoration'],original_owner=context['original']['owner'],initial_state=context['original']['initial_state'],original_ledger=ledger_snapshot,original_ledger_origin=context['original']['ledger'],recovery_measurement=bind(out/'RESULT.json'),source_review=context['review_ref'],reapply_origin=bind(out/'RESULT.json'),reapply=result['fresh_restore']['reapply'],readback=result['fresh_restore']['readback'],policy_evaluation=result['policy_evaluation'],native_telemetry_closure=context['native_proof'],current_telemetry_processes_absent=True,hardware_lease_released=True,audio_handles_closed=True,packed_input_disabled=True,no_playback=True,no_setters_or_reset=False,original_telemetry_process_closed=False,historical_python_terminal_receipt_present=True,historical_telemetry_pid_creation=context['native_proof']['historical_telemetry_pid_creation'],original_strict_snapshot_status_preserved='FAIL',requires_explicit_new_queue_admission=True,scope='Fresh actual exposed-setting restore after proven native cleanup/current recorded owner absence. Original Python terminal FAIL/native-process-exit-unproven receipt, failed capture/restoration and charges remain unchanged; no retroactive telemetry or capture PASS.')
    save(out/'RECOVERY.json',rec);return bind(out/'RECOVERY.json')

def verify_recovery_record(receipt,*,owner_binding,restoration_binding,initial_binding):
    """File-only V10 admission API. No process census, ports, locks, getters or setters."""
    need(receipt.get('schema_version')==SCHEMA and receipt.get('recovery_kind')==KIND and receipt.get('status')=='PASS' and receipt.get('fixture_only') is False,'Exact nonfixture fresh-restoration recovery kind required')
    need(receipt.get('original_owner')==owner_binding and receipt.get('original_restoration')==restoration_binding and receipt.get('initial_state')==initial_binding,'Recovery original owner/state differs')
    owner=verify(owner_binding);failed=verify(restoration_binding);initial=verify(initial_binding);measurement=verify(receipt['recovery_measurement']);authority=verify(receipt['source_review']);policy=policy_module()
    need(authority.get('status')==REVIEW_STATUS and authority.get('allow_fresh_exposed_restore') is True and authority.get('owner_thread_id')==ROOT_THREAD and authority.get('recovery_kind')==KIND and authority.get('original_batch')=='bank_v3_P_MAIN6_B3' and authority.get('run_id')=='20260913T195357Z','Semantic root source/restore authority absent')
    by_path={b['path']:b for b in authority['source_bindings']};need({str(p.resolve()) for p in required_sources()}<=set(by_path),'Root authority source graph incomplete')
    for b in authority['source_bindings']:need(bind(b['path'])==b,'Recovery source graph changed')
    originals=authority['original_bindings'];need(originals['owner']==owner_binding and originals['restoration']==restoration_binding and originals['initial_state']==initial_binding and originals['ledger']==receipt['original_ledger_origin'],'Root authority original failure graph differs')
    need(Path(receipt['recovery_measurement']['path']).parent.resolve()==Path(authority['recovery_output_root']).resolve(),'Fresh measurement output differs from root authority')
    bridge=verify(originals['bridge_failure']);launch=verify(originals['supervisor_launch']);known=[dict(role='capture_owner',pid=bridge['pid'],creation_time=bridge['creation_time']),dict(role='supervisor',pid=launch['pid'],creation_time=launch['creation_time'])]
    closure=recorded_terminal_closure(authority['telemetry_bindings'],authority['expected_measurement_rows'],bridge,verify(originals['summary']))
    need(authority.get('historical_telemetry_pid_creation')==closure['historical_telemetry_pid_creation'],'Root recorded telemetry identity differs')
    known.append(dict(role='native_telemetry',**closure['historical_telemetry_pid_creation']))
    need(bridge['pid']==owner['pid'] and measurement['known_processes']==known,'Original process identity checks differ')
    need(failed.get('status')=='FAIL' and failed.get('telemetry_process_closed') is False and all(failed.get(k) is True for k in ('audio_handles_closed','hardware_lease_released')),'Original failure scope differs')
    need(measurement.get('status')=='FRESH_RESTORE_VERIFIED' and measurement.get('fixture_only') is False and measurement.get('source_review')==receipt['source_review'] and measurement['original_bindings']['owner']==owner_binding and measurement['original_bindings']['restoration']==restoration_binding and measurement['original_bindings']['initial_state']==initial_binding,'Fresh measurement identity differs')
    ledger=verify(receipt['original_ledger']);need((receipt['original_ledger']['bytes'],receipt['original_ledger']['sha256'])==(receipt['original_ledger_origin']['bytes'],receipt['original_ledger_origin']['sha256']) and measurement['original_ledger_snapshot']==receipt['original_ledger'],'Original immutable ledger differs')
    row=ledger['batches'][authority['original_batch']];need(row['owner']==owner_binding and row['restoration']==restoration_binding,'Original ledger lacks this exact owner/restoration')
    config=verify(originals['failed_configuration']);admission=verify(originals['admission'])
    config_proof=failed_configuration_proof(originals,dict(admission=admission,ledger=ledger))
    need(measurement['original_bindings']['failed_configuration']==originals['failed_configuration'] and measurement['failed_configuration_proof']==config_proof,'Fresh measurement configured-state binding differs')
    before_decision=pre_restore_identity_decision(initial,measurement['before_identity'],config)
    need(before_decision['accepted'] is True and policy.exact(measurement['pre_restore_identity_comparison'],before_decision),'Exact pre-restore identity decision differs')
    need(receipt['reapply_origin']==receipt['recovery_measurement'] and receipt['reapply']==measurement['fresh_restore']['reapply'] and receipt['readback']==measurement['fresh_restore']['readback'],'Fresh actual reapply/readback join differs')
    d=policy.restoration_decision(initial,receipt['readback'],receipt['reapply']);need(d['accepted'] and policy.exact(receipt['policy_evaluation'],d) and policy.exact(measurement['policy_evaluation'],d),'Fresh restoration policy invalid')
    need(receipt['native_telemetry_closure']==measurement['native_telemetry_closure']==closure,'Actual recorded terminal/native cleanup/population proof differs')
    need([x['stage'] for x in measurement['process_scans']]==['before_lock','locked_before_getter','locked_before_setter','locked_after_restore'],'Required complete process checks absent')
    for index,item in enumerate(measurement['process_scans']):
        snapshot=verify(item['snapshot']);decision=scan_decision(snapshot,measurement['known_processes'],measurement['recovery_identity']);need(item['decision']==decision and item['ports_idle'] is True and item['hardware_lock_held'] is (index>0),'Saved locked process closure proof invalid')
        tcp=verify(item['tcp_listeners']);need(item['tcp_listener_decision']==tcp_listener_decision(tcp),'Saved complete OS listener proof invalid')
    need(all(measurement.get(k) is True for k in ('hardware_lock_acquired','hardware_lock_released','device_restore_started','device_restore_completed')) and all(measurement.get(k)==0 for k in ('audio_streams_opened','packed_playback_attempts','processes_terminated')),'Fresh hardware ownership/action completion absent')
    need(all(receipt.get(k) is True for k in ('current_telemetry_processes_absent','hardware_lease_released','audio_handles_closed','packed_input_disabled','no_playback','requires_explicit_new_queue_admission','historical_python_terminal_receipt_present')) and all(receipt.get(k) is False for k in ('no_setters_or_reset','original_telemetry_process_closed')) and receipt.get('historical_telemetry_pid_creation')==closure['historical_telemetry_pid_creation'] and receipt.get('original_strict_snapshot_status_preserved')=='FAIL','New versus historical closure scope differs')
    need(receipt['readback']['identity']['I2S_INPUT_PACKED']==[0] and receipt['readback']['identity']['USB_BIT_DEPTH']==initial['usb_bits'],'Packed/USB state not restored')
    return dict(status='VERIFIED_CLOSED_RECORDED_TELEMETRY_FRESH_RESTORE',recovery_kind=KIND,original_owner=owner_binding,original_restoration=restoration_binding,recovery_measurement=receipt['recovery_measurement'],historical_python_terminal_receipt_present=True,old_failure_preserved=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['inspect-inputs','execute']);p.add_argument('--source-review',type=Path,required=True);p.add_argument('--source-review-sha256',required=True);a=p.parse_args();c=inspect_review(a.source_review,a.source_review_sha256,a.action=='execute')
    if a.action=='inspect-inputs':print(json.dumps(dict(status='INPUTS_VERIFIED_NO_PROCESS_OR_DEVICE_ACTION',review=c['review_ref'],native_closure=c['native_proof'],known_processes=c['known'])))
    else:print(json.dumps(recover_prevalidated(c,WindowsServices())))
