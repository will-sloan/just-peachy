"""Existing XVF control getters and endpoint enumeration only; no stream or setter."""
import argparse, socket, sys, time
from s0_common import *

GETTERS=['VERSION','AEC_MIC_ARRAY_TYPE','AEC_NUM_MICS','AEC_MIC_ARRAY_GEO',
         'AUDIO_MGR_MIC_GAIN','AUDIO_MGR_REF_GAIN','AUDIO_MGR_SYS_DELAY','USB_BIT_DEPTH',
         'I2S_INPUT_PACKED','I2S_DAC_DSP_ENABLE','BLD_MSG']

def run(report):
    report=Path(report);cache=HashCache();sys.path.insert(0,str(ROOT))
    previous=report/'xvf_read_only_inventory.json'
    if previous.exists():
        save(report/('xvf_read_only_attempt_'+str(time.time_ns())+'.json'),read(previous))
    result={'observed_utc':now(),'policy':'READ_ONLY_NO_STREAM_NO_SETTER','queries':{},'errors':[]}
    with Progress(report,'xvf_read_only',len(GETTERS)) as progress:
        try:
            import measurement_app  # exposes recorder's bundled dependency directory
            import sounddevice as sd
            apis=sd.query_hostapis()
            result['endpoints']=[{'index_observed_this_desktop':i,**dict(d),'host_api_name':apis[d['hostapi']]['name']} for i,d in enumerate(sd.query_devices()) if any(t in d['name'].lower() for t in ['xvf','xmos','respeaker'])]
            result['endpoint_format_scope']='Enumerated default sample rate and channel capacities only; no stream negotiation. Firmware USB_BIT_DEPTH is separate from Windows negotiated format.'
        except Exception as exc:result['errors'].append('enumeration: '+str(exc))
        lock=None; locked=False
        try:
            with socket.socket() as sock:
                sock.settimeout(.4)
                if sock.connect_ex(('127.0.0.1',8767))==0:
                    raise RuntimeError('Measurement server is listening; skip control queries to avoid ownership conflict')
            import msvcrt
            lock=(ROOT/'measurement_app/hardware.lock').open('r+b')
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1);locked=True
            from measurement_app.core import Control, HOST
            result['implementation']=[cache.bind(ROOT/'measurement_app'/n) for n in ['core.py','server.py','acquisition.py','trial.py']]
            result['host_executable']=cache.bind(HOST)
            control=Control(report/'xvf_read_only_commands')
            for name in GETTERS:
                result['queries'][name]=control.query(name)  # no arguments: getters only
                progress.done+=1;progress.detail=name
        except Exception as exc:result['errors'].append('control: '+str(exc))
        finally:
            if locked:
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            if lock:lock.close()
    result['status']='OBSERVED_READ_ONLY' if len(result['queries'])==len(GETTERS) else 'PARTIAL_OR_UNAVAILABLE_OFFLINE_S1_UNBLOCKED'
    save(report/'xvf_read_only_inventory.json',result);cache.flush();print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
