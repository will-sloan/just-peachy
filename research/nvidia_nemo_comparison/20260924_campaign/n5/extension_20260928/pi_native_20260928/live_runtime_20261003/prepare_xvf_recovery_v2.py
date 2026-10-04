"""Local independent restores and exact fault payload; no SSH. README_XVF_RECOVERY.md."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import time


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--fault-mirror',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--label',default='xvf-recovery-02')
    args=ap.parse_args()
    import psutil
    me=psutil.Process();me.cpu_affinity([14]);args.output.mkdir()
    def write(name,raw):
        path=args.output/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short recovery preparation write')
            stream.flush();os.fsync(stream.fileno())
        if path.read_bytes()!=raw:raise OSError('Independent PC recovery readback differs')
    def save(name,value):write(name,json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    from launch_xvf_recovery_action_v2 import qualifying_fault,SEQUENCE_SOURCE,PROBE_SHA256,PROBE_BYTES,load_reviewed_probe
    from monitor_native_job import floors
    floors(32*1024**2)
    baseline=json.loads(args.baseline.read_bytes())
    mirror=args.fault_mirror;result=json.loads((mirror/'RESULT.json').read_bytes())
    complete=json.loads((mirror/'MIRROR_COMPLETE.json').read_bytes());rows=json.loads((mirror/'MIRROR_MANIFEST.json').read_bytes())
    if (result['status']!='FULL_CLOSED_OUTPUT_MIRRORED' or complete['kind']!='COMPLETE' or
        not all(complete['closure'].get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty'))):
        raise ValueError('Actual full closed fault mirror required')
    probe_raw=(mirror/'NATIVE_PROBE.py.backup').read_bytes()
    source_closed=json.loads((mirror/'SOURCE_CLOSED.json').read_bytes())
    if (probe_raw!=(mirror/'NATIVE_PROBE.py.restore').read_bytes() or
        source_closed.get('independent_restore') is not True or source_closed.get('native_probe_sha256')!=PROBE_SHA256):
        raise ValueError('Actual reviewed monitor independent native probe restore differs')
    probe_payload=dict(native_probe_base64=base64.b64encode(probe_raw).decode(),
        native_probe_sha256=PROBE_SHA256,native_probe_bytes=PROBE_BYTES)
    load_reviewed_probe(probe_payload)
    write('NATIVE_PROBE.py.backup',probe_raw);write('NATIVE_PROBE.py.restore',probe_raw)
    job=result['job']
    if any(complete['closure'][key]!=job[key] for key in ('unit','owner','invocation_id','control_group')):
        raise ValueError('Actual fault mirror/job closure differs')
    if hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=complete['manifest_sha256']:
        raise ValueError('Full closed fault manifest pin differs')
    candidates=[row for row in rows if row['path'].endswith('/work/source/SOURCE_CLOSE.json')]
    if len(candidates)!=1:raise ValueError('One exact failed physical source required')
    entry=candidates[0];failed=(mirror/'closed-output'/entry['path']).read_bytes()
    if len(failed)!=entry['identity']['bytes'] or hashlib.sha256(failed).hexdigest()!=entry['sha256'] or not qualifying_fault(json.loads(failed)):
        raise ValueError('Actual active-stream AEC255 source failure does not qualify')
    if baseline['boot_id']!=job['boot_id']:raise ValueError('Same current baseline/fault boot required')
    base=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
    tool='/home/peachyprototype/JustPeachy/tools/native_xvf_usb/bin/xvf_host'
    tool_raw=(base/'xvf-recovery-v4-evidence/before/XVF_HOST_BACKUP').read_bytes()
    if ((base/'xvf-recovery-v4-evidence/restore-copy/XVF_HOST_BACKUP').read_bytes()!=tool_raw or
        len(tool_raw)!=1773304 or hashlib.sha256(tool_raw).hexdigest()!='8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982'):
        raise ValueError('Exact previously exercised tool/independent restore differs')
    files={tool:tool_raw}
    wanted={'/home/peachyprototype/JustPeachy/data/live_config.json',
        '/home/peachyprototype/JustPeachy/install/current.json','/home/peachyprototype/JustPeachy/data/settings.json',
        '/home/peachyprototype/.config/kanshi/config'}
    for row in baseline['files']:
        if row['path'] in wanted:
            raw=row['text'].encode()
            if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
                raise ValueError('Actual baseline configuration byte/hash differs')
            files[row['path']]=raw
    if set(files)!={tool}|wanted:raise ValueError('Actual current config/install/display bytes missing')
    pins={}
    for index,(path,raw) in enumerate(sorted(files.items())):
        pins[path]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        write('before/'+str(index),raw);write('restore/'+str(index),raw)
    admission=json.loads((mirror/'closed-output/ADMISSION.json').read_bytes())
    package=admission['payload']['package']
    payload=dict(package=package,package_manifest_sha256=job['package_manifest_sha256'],
        boot_id=job['boot_id'],expires_unix=time.time()+600,label=args.label,
        maximum_output_bytes=16*1024**2,maximum_restart_commands=1,fault_job=job,fault_entry=entry,
        pins=pins,tool=tool,host_backup_readback=True,sequence_sha256=hashlib.sha256(SEQUENCE_SOURCE.encode()).hexdigest())
    payload.update(probe_payload)
    save('PAYLOAD.json',payload);write('SOURCE_CLOSE.json',failed)
    for name in ('prepare_xvf_recovery_v2.py','launch_xvf_recovery_action_v2.py','README_XVF_RECOVERY.md'):
        raw=Path(__file__).with_name(name).read_bytes();write(name+'.backup',raw);write(name+'.restore',raw)
    save('HOST_BACKUP_VERIFIED.json',dict(pins=pins,index=sorted(files),independent_readbacks=True,
        actual_fault_sha256=entry['sha256'],baseline_sha256=hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
        payload_sha256=hashlib.sha256((args.output/'PAYLOAD.json').read_bytes()).hexdigest(),native_executed=False,
        volatile_state_restorable=False,cause_proven=False))
    print(json.dumps(dict(output=str(args.output),payload=str(args.output/'PAYLOAD.json'),native_executed=False)))


if __name__=='__main__':main()
