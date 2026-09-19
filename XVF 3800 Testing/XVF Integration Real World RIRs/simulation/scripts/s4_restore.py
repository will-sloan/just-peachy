"""Restore exposed settings with bounded float32 round-trip recovery. README_S4.md."""
import argparse, msvcrt, socket, sys
from s4_common import *
sys.path.insert(0,str(ROOT))
import measurement_app
import numpy as np
from measurement_app.core import Control
from s3_hardware import STATIC, OBSERVE_ONLY, values, set_verified

def restore_exposed(c,desired):
    observed={};changed=[];roundtrip=[]
    for name,want in desired.items():
        got=values(c,name)
        if got!=want:
            c.query(name,*want);got=values(c,name);changed.append(name)
            # Only the current AGC gain demonstrated a one-ULP setter mismatch.
            # Adjacent representable inputs must restore the EXACT original
            # decimal getter; there is no tolerance-based acceptance.
            if got!=want and name=='PP_AGCGAIN' and len(want)==1:
                x=np.float32(want[0]);step=abs(float(np.spacing(x)))
                if abs(got[0]-want[0])<=2*step:
                    for direction in [np.inf,-np.inf]:
                        candidate=float(np.nextafter(x,np.float32(direction)))
                        if not 1<=candidate<=1000:continue
                        c.query(name,candidate);got=values(c,name)
                        roundtrip.append({'command':name,'requested_original':want,'representable_setter_argument':candidate,'observed':got,'maximum_adjustment_float32_ulp':1})
                        if got==want:break
            if got!=want:raise RuntimeError(f'{name} exact readback {got} != {want}; no tolerance-based acceptance')
        observed[name]=got
    return {'observed':observed,'set_commands':changed,'exact_match':observed==desired,'float32_roundtrip_recovery':roundtrip}

def recover(batch):
    folder=REPORT/'hardware'/batch;failed=read(folder/'restoration.json');assert failed['status']=='FAIL'
    initial=read(folder/'initial_state.json');lock=None;owned=False
    result={'status':'FAIL','original_failure_binding':bind(folder/'restoration.json'),'original_failure':failed,'started_utc':now(),'playback_performed':False}
    try:
        for port in [8765,8766,8767]:
            with socket.socket() as sock:
                sock.settimeout(.2);assert sock.connect_ex(('127.0.0.1',port))!=0,'Recorder server active'
        for receipt in folder.glob('*/telemetry_summary.json'):
            r=read(receipt);assert r.get('exit_code')==0 and not r.get('forced_termination'),'Telemetry closure not proven'
        lock=(ROOT/'measurement_app/hardware.lock').open('r+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);owned=True
        c=Control(folder/'recovery_commands');set_verified(c,'I2S_INPUT_PACKED',[0])
        assert values(c,'USB_BIT_DEPTH')==initial['usb_bits'],'USB width unexpectedly changed; no blind reset'
        restored=restore_exposed(c,initial['settings'])
        after={'identity':c.identify(),'settings':{n:values(c,n) for n in STATIC},'observe_only':{n:values(c,n) for n in OBSERVE_ONLY}}
        same=after['identity']==initial['identity'] and after['settings']==initial['settings'] and after['observe_only']==initial['observe_only']
        result.update(status='PASS' if same else 'FAIL',exact_recorded_configuration_match=same,readback=after,reapply=restored,
            packed_input_disabled=after['identity']['I2S_INPUT_PACKED']==[0],audio_handles_closed=True,telemetry_process_closed=True,
            limitation='Original decimal getter equality restored; unexposed adaptive history and full underlying coefficient bits were not captured originally.')
    except BaseException as e:result['error']=repr(e)
    finally:
        if owned:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        if lock:lock.close()
        result.update(hardware_lease_released=True,ended_utc=now());save(folder/'restoration_recovery.json',result)
    print(json.dumps(result,indent=2));assert result['status']=='PASS'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);a=p.parse_args();recover(a.batch)
