"""Locked getter-only recovery review for one closed S6D batch; see README."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import msvcrt
import socket
import sys
import psutil

sys.dont_write_bytecode = True
SIM = Path(__file__).resolve().parents[1]
ROOT = SIM.parent
R = SIM / 'reports/S6D/20260913T195357Z'
BATCH = R / 'hardware_batches/bank_v1_P_MAIN6_B1_pre_QA'

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def bind(p):
    p=Path(p).resolve();data=p.read_bytes()
    return dict(path=str(p),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())

def verify(b):
    actual=bind(b['path'])
    if actual['bytes']!=b['bytes'] or actual['sha256']!=b['sha256']:
        raise ValueError('Changed recovery input/source: '+b['path'])
    return actual

def require(condition,message):
    if not condition: raise ValueError(message)

def save(p,obj):
    with Path(p).open('x',encoding='utf-8') as f:
        json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')

def matching_process(pid,created):
    require(type(pid) is int and pid>0,'positive integer PID required')
    require(type(created) in (int,float) and math.isfinite(created) and created>0,'positive finite creation time required')
    try: return abs(psutil.Process(pid).create_time()-created)<.02
    except psutil.NoSuchProcess: return False

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source-review',type=Path,required=True)
    ap.add_argument('--output',type=Path,default=R/'hardware_state_recovery_v1')
    args=ap.parse_args()
    out=args.output.resolve()
    require(not out.exists() and out.is_relative_to(R),'fresh bounded report destination required')
    review=read(args.source_review)
    require(review.get('status')=='ROOT_ACCEPTED_DYNAMIC_GAIN_RESTORATION_SOURCES_V1','actual root source review required')
    bindings=[verify(b) for b in review['source_bindings']]
    needed=[Path(__file__),Path(__file__).with_name('README_S6D_READONLY_STATE_RECOVERY_V1.md'),SIM/'scripts/s6d_restoration_policy_v1.py',SIM/'scripts/s3_hardware.py',ROOT/'measurement_app/core.py']
    require({str(p.resolve()) for p in needed}<={b['path'] for b in bindings},'recovery source graph incomplete')
    ack=read(R/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json')
    require(ack.get('own_analog_outputs_disconnected_confirmed') is True,'recorded XVF output confirmation required')
    failed=read(BATCH/'restoration.json');initial=read(BATCH/'initial_state.json')
    ledger_record=read(R/'physical_ledger.json')['batches']['bank_v1_P_MAIN6_B1_pre_QA']
    verify(ledger_record['restoration']);verify(ledger_record['owner'])
    require(ledger_record['restoration']==bind(BATCH/'restoration.json') and ledger_record['owner']==bind(BATCH/'owner_acquired.json'),'original ledger owner/restoration binding differs')
    require(failed.get('initial_state')==bind(BATCH/'initial_state.json'),'original failure initial-state binding differs')
    require(failed['status']=='FAIL','original failure must remain explicit')
    for field in ('packed_input_disabled','audio_handles_closed','telemetry_process_closed','hardware_lease_released'):
        require(failed.get(field) is True,'original closure incomplete: '+field)
    bridge=read(R/'physical_supervisor/bank_v1_P_MAIN6_B1_pre_QA/CAPTURE_BRIDGE_FAILURE.json')
    supervisor=read(R/'runner/bank_queue_v2/ROOT_LAUNCH_V1.json')
    require(bridge['pid']==read(ledger_record['owner']['path'])['pid'],'original capture owner and bridge PID differ')
    require(not matching_process(bridge['pid'],bridge['creation_time']),'original capture owner still active')
    require(not matching_process(supervisor['pid'],supervisor['creation_time']),'original supervisor still active')
    spec=importlib.util.spec_from_file_location('s6d_reviewed_restoration_policy',SIM/'scripts/s6d_restoration_policy_v1.py')
    policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
    retrospective=policy.restoration_decision(initial,failed['readback'],failed['reapply'])
    require(retrospective['accepted'] is True,'original failure not limited to reviewed autonomous gain state')
    out.mkdir(parents=True)
    result=dict(schema='s6d-readonly-state-recovery.v1',status='STARTED',started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        original_batch='bank_v1_P_MAIN6_B1_pre_QA',source_review=bind(args.source_review),sources=bindings,
        original_failure=bind(BATCH/'restoration.json'),initial_state=bind(BATCH/'initial_state.json'),
        bridge_failure=bind(R/'physical_supervisor/bank_v1_P_MAIN6_B1_pre_QA/CAPTURE_BRIDGE_FAILURE.json'),
        original_supervisor_launch=bind(R/'runner/bank_queue_v2/ROOT_LAUNCH_V1.json'),
        original_owners_absent=True,original_failure_preserved=True,original_strict_snapshot_status='FAIL',
        original_immediate_gain_set_proof_used=True,no_new_gain_set_claim=True,original_policy_reassessment=retrospective,
        control_actions='GETTERS_ONLY',audio_streams_opened=0,device_setters=0,device_resets=0,packed_playback_attempts=0,
        hardware_lock_acquired=False,hardware_lock_released=False)
    lock=None;owned=False;error=None
    try:
        for port in (8765,8766,8767):
            with socket.socket() as sock:
                sock.settimeout(.2)
                require(sock.connect_ex(('127.0.0.1',port))!=0,'recorder service active')
        lock=(ROOT/'measurement_app/hardware.lock').open('r+b');lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True;result['hardware_lock_acquired']=True
        sys.path.insert(0,str(ROOT))
        from measurement_app.core import Control
        from s3_hardware import STATIC,OBSERVE_ONLY,values
        control=Control(out/'commands')
        after=dict(identity=control.identify(),settings={n:values(control,n) for n in STATIC},observe_only={n:values(control,n) for n in OBSERVE_ONLY})
        result['fresh_readback']=after
        result['decision']=policy.restoration_decision(initial,after,failed['reapply'])
        require(result['decision']['accepted'] is True,'fresh state outside reviewed restoration policy')
        require(after['identity']['I2S_INPUT_PACKED']==[0] and after['identity']['USB_BIT_DEPTH']==initial['usb_bits'],'safe packing/width not restored')
        for b in bindings: verify(b)
        result.update(status='FRESH_STATIC_STATE_VERIFIED_AUTONOMOUS_GAIN_EXPLICIT',packed_input_disabled=True,usb_width_restored=True)
    except BaseException as exc:
        error=repr(exc);result.update(status='RECOVERY_REVIEW_FAILED',error=error)
    finally:
        try:
            if owned: lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            if lock: lock.close()
            result['hardware_lock_released']=owned
        except BaseException as exc:
            error=repr(exc);result.update(status='RECOVERY_REVIEW_FAILED',release_error=error)
        result['finished_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
        save(out/'RESULT.json',result)
    if error: raise RuntimeError(error)
    recovery=dict(schema_version='edge-s6d-restoration-recovery.v1',status='PASS',
        original_restoration=ledger_record['restoration'],original_owner=ledger_record['owner'],
        reapply_origin=ledger_record['restoration'],initial_state=bind(BATCH/'initial_state.json'),
        reapply=failed['reapply'],readback=result['fresh_readback'],policy_evaluation=result['decision'],
        hardware_lease_released=result['hardware_lock_released'],audio_handles_closed=True,
        telemetry_process_closed=True,packed_input_disabled=True,no_playback=True,no_setters_or_reset=True,
        recovery_measurement=bind(out/'RESULT.json'),source_review=bind(args.source_review),
        original_strict_snapshot_status_preserved='FAIL',requires_explicit_new_queue_admission=True,
        scope='Fresh getter-only state verification under exact-static and verified-original-gain-request policy; not a retroactive V4 PASS or new gain setter.')
    save(out/'RECOVERY.json',recovery)
    print(json.dumps(dict(status=result['status'],receipt=bind(out/'RESULT.json'),recovery=bind(out/'RECOVERY.json'),device_setters=0,audio_streams_opened=0)))

if __name__=='__main__': main()
