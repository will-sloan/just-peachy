"""One bounded existing XVF soft reset; see README_S6D_RESET_RECOVERY_V1.md."""
from pathlib import Path
import datetime, hashlib, json, msvcrt, socket, sys

SIM = Path(__file__).resolve().parents[1]
ROOT = SIM.parent
R = SIM/'reports/S6D/20260913T195357Z'
OUT = R/'reset_recovery_after_confirmation_v1'

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def binding(p):
    p=Path(p).resolve(); b=p.read_bytes()
    return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def main():
    ack=read(R/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json')
    if ack.get('own_analog_outputs_disconnected_confirmed') is not True:
        raise RuntimeError('Fresh own-output confirmation required')
    frozen=read(R/'capture_implementation/review_v3/SOURCE_FREEZE.json')
    candidates=[]
    def walk(value):
        if isinstance(value,dict):
            if {'path','bytes','sha256'}<=value.keys(): candidates.append(value)
            for item in value.values(): walk(item)
        elif isinstance(value,list):
            for item in value: walk(item)
    walk(frozen)
    for p in (SIM/'scripts/s3_hardware.py',ROOT/'measurement_app/core.py'):
        actual=binding(p)
        if not any(Path(b['path']).resolve()==p.resolve() and b['sha256']==actual['sha256'] and b['bytes']==actual['bytes'] for b in candidates):
            raise RuntimeError('Recovery dependency differs from reviewed capture source')
    OUT.mkdir(exist_ok=False)
    result=dict(schema='s6d-bounded-device-reset-recovery.v1',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                source=binding(__file__),safety=binding(R/'FRESH_XVF_OUTPUT_CONFIRMATION_V1.json'),audio_streams_opened=0,
                packed_playback_attempts=0,charged_playback_seconds=0,firmware_or_driver_updated=False,
                scope='One existing TEST_CORE_BURN reset without packed input or audio. Pre-reset DSP fields are unavailable; no exact pre-reset DSP restoration claim. New read-only preflight required.',
                cause='Audio-core query unresponsive; evaluation duration is a possible explanation, not established cause',failure=None)
    lock=None;owned=False
    try:
        for port in (8765,8766,8767):
            with socket.socket() as sock:
                sock.settimeout(.2)
                if sock.connect_ex(('127.0.0.1',port))==0: raise RuntimeError('Recorder service active')
        lock=(ROOT/'measurement_app/hardware.lock').open('r+b');lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True
        sys.path.insert(0,str(ROOT))
        from measurement_app.core import Control
        from s3_hardware import reset,values
        control=Control(OUT/'commands')
        before=dict(version=values(control,'VERSION'),usb_bits=values(control,'USB_BIT_DEPTH'))
        result['readable_before']=before
        if before['version']!=[3,2,1] or before['usb_bits'] not in ([16,16],[24,24]):
            raise RuntimeError('Unexpected management identity/USB width')
        result['reset_started_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        result['reset']=reset(control,before['usb_bits'][0],change_width=False,isolate_packed=False)
        result['after']={name:values(control,name) for name in ('VERSION','USB_BIT_DEPTH','AEC_MIC_ARRAY_TYPE','AEC_NUM_MICS','I2S_INPUT_PACKED')}
        if result['after']['AEC_MIC_ARRAY_TYPE']!=[1] or result['after']['AEC_NUM_MICS']!=[4] or result['after']['I2S_INPUT_PACKED']!=[0]:
            raise RuntimeError('Post-reset linear DSP readiness not established')
        result['status']='RESET_AND_BASIC_DSP_READINESS_PASS_FULL_PREFLIGHT_REQUIRED'
    except BaseException as exc:
        result.update(status='RESET_RECOVERY_FAILED',failure=repr(exc))
    finally:
        if owned:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        if lock:lock.close()
        result['hardware_lock_released']=owned
        result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        (OUT/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    return 0 if result['failure'] is None else 2

if __name__=='__main__': raise SystemExit(main())
