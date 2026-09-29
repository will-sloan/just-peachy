"""Native import-only mapping census; see README_LIVE_ALSA_IMPORT_V1.md."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['ORT_DISABLE_TELEMETRY']='1'
import json
import hashlib
import resource
import sys
from pathlib import Path
from datetime import datetime, timezone


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    root=Path(__file__).resolve().parent;a=json.loads((root/'ADMISSION.json').read_text())
    resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    assert resource.getrlimit(resource.RLIMIT_STACK)==(1048576,1048576)
    assert sorted(os.sched_getaffinity(0))==[2,3] and os.getuid()!=0
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
    for row in a['files']:assert sha(Path(row['path']))==row['sha256']
    owner=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=a['boot_id'],admission_sha256=sha(root/'ADMISSION.json'))
    with (root/'OWNER.json').open('x') as f:json.dump(owner,f)
    samples=[]
    def sample(name):
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
        data={}
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith(('VmSize:','VmRSS:','VmPeak:','Threads:')):
                k,v=line.split(':',1);data[k]=int(v.split()[0])
        maps=Path('/proc/self/smaps').read_text();(root/(name+'.smaps')).write_text(maps)
        samples.append(dict(stage=name,process_status=data,smaps_sha256=sha(root/(name+'.smaps'))))
    assert 'ALSA_CONFIG_PATH' not in os.environ
    os.environ['ALSA_CONFIG_PATH']=str(root/'alsa_hw_only_v1.conf')
    sample('before_app')
    source=Path(a['prototype']);sys.path[:0]=[str(source),str(source/'vendor')]
    from app import live_audio
    from app.controller import Controller
    sample('after_app')
    assert not any(k=='scipy' or k.startswith('scipy.') for k in sys.modules)
    # Import initializes PortAudio host APIs. No stream is constructed/opened,
    # no microphone reads or control commands, and no model/controller exists.
    import sounddevice
    sample('after_sounddevice')
    config=live_audio.LiveConfig(**json.loads((Path.home()/'JustPeachy/data/live_config.json').read_text()))
    selected=live_audio.resolve_endpoint(config,live_audio.inventory())
    assert selected['name']==config.endpoint_name and selected['hostapi_name']=='ALSA' and selected['max_input_channels']==8
    assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
    (root/'RESULT.json').write_text(json.dumps(dict(status='COLLECTED_NATIVE_HW_ONLY_IMPORT_AND_ENDPOINT',selected_endpoint=selected,alsa_config_sha256=sha(root/'alsa_hw_only_v1.conf'),owner=owner,samples=samples,sounddevice_file=sounddevice.__file__,capture=False,models_loaded=False,stream_constructed=False,no_scipy=not any(k=='scipy' or k.startswith('scipy.') for k in sys.modules)),indent=2))


if __name__=='__main__':main()
