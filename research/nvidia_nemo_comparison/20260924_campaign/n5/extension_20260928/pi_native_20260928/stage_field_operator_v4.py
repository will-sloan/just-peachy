"""Fresh target staging only. Read README_FIELD_OPERATOR_QUALIFICATION_V2.md."""
import base64
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import time

ROOT=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')


def stage(request):
    import sys
    sys.dont_write_bytecode=True
    os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_STACK,(1048576,)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE,(33554432,)*2)
    signal.signal(signal.SIGALRM,signal.SIG_DFL);signal.alarm(30)
    a=request['admission'];root=ROOT/'field-operator-qualification-v1'
    if a['output_root']!=str(root) or root.exists() or root.is_symlink():
        raise ValueError('Fresh exact run root required; never retry an existing root')
    now=datetime.now(timezone.utc);expiry=datetime.fromisoformat(a['expires_utc'])
    if not 480<=(expiry-now).total_seconds()<=600 or expiry>datetime.fromisoformat('2026-10-01T17:42:44+00:00'):
        raise ValueError('Stage, live closure and backup must fit hard deadline')
    if a['capture'] is not True or a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION':
        raise ValueError('Genuine whole-live admission required')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    def ticks(pid):
        try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
        except FileNotFoundError:return None
    def sha(path):
        with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    if boot!=a['boot_id'] or ticks(1013)!=569 or ticks(1130)!=607:raise ValueError('Boot/baseline drift')
    if 'Compute Module 5' not in Path('/proc/device-tree/model').read_text() or os.uname().machine!='aarch64':
        raise ValueError('Wrong physical target')
    if Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()!='closed':raise ValueError('Capture busy')
    if shutil.disk_usage(root.parent).free<5*1024**3+a['target_maximum_bytes']:raise ValueError('Physical free floor')
    files=request['stage_files']
    if type(files) is not dict or not 1<=len(files)<=64:raise ValueError('Staging file cardinality')
    decoded={}
    for name,row in files.items():
        if not re.fullmatch(r'(code/[A-Za-z0-9_][A-Za-z0-9_.-]{0,100}|data/(live_config|settings|DATA_SCHEMA|n2_runtime)\.json)',name):
            raise ValueError('Unmapped staged file')
        raw=base64.b64decode(row['base64'],validate=True)
        if not 0<len(raw)<=128*1024 or hashlib.sha256(raw).hexdigest()!=row['sha256']:
            raise ValueError('Staging bytes/hash')
        decoded[name]=raw
    if sum(len(v) for v in decoded.values())>2*1024**2:raise ValueError('Compact capsule exceeded')
    pins={r['path']:r for r in a['files']}
    if len(pins)!=len(a['files']):raise ValueError('Duplicate admitted path')
    for name,raw in decoded.items():
        row=pins[str(root/name)]
        if row['bytes']!=len(raw) or row['sha256']!=hashlib.sha256(raw).hexdigest():
            raise ValueError('Staged bytes are not admitted')
    for path,row in pins.items():
        if Path(path).is_relative_to(root):continue
        p=Path(path)
        if p.is_symlink() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:
            raise ValueError('Existing input binding drift')
    import fcntl,subprocess
    with (ROOT/'B05_PREVIEW_DISPATCH.lock').open('r+b') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip():
            raise ValueError('Healthy research unit exists')
        import types,sys
        name='field_owner_binding_v1'
        m=types.ModuleType(name);m.__file__='<admitted-stage:'+name+'>';sys.modules[name]=m
        exec(compile(decoded['code/'+name+'.py'],m.__file__,'exec'),m.__dict__)
        for owner in m.decode(a['preflight_pi_owners']):
            if owner['boot_id']==boot and ticks(owner['pid'])==owner['start_ticks']:raise ValueError('Owned process alive')
        policy=json.loads(decoded['code/OPERATOR_RESOURCE_POLICY_V1.json'])
        if hashlib.sha256(decoded['code/WINDOW_V5.json']).hexdigest()!=a['old_policy_pin']['sha256']:raise ValueError('Old policy changed')
        total=int(subprocess.check_output(['du','-sb',str(ROOT)],text=True).split()[0])
        if a['host_window_bytes']+total+a['combined_request_bytes']>policy['combined_output_cap_bytes']:
            raise ValueError('Target-inclusive measured output projection')
        if a['payload_before_bytes']+max(0,total-a['target_before_bytes'])+a['combined_request_bytes']>policy['total_payload_cap_bytes']:
            raise ValueError('Target-inclusive payload projection')
        # Validate the selected exact layout from admitted source, before mkdir.
        import sys,types
        for name in ('field_live_layout_v2','field_live_layout_v3','field_live_paths_v1','field_transfer_v2','field_transfer_paths_v2','field_transfer_layout_v1','field_operator_layout_v2'):
            m=types.ModuleType(name);m.__file__='<admitted-stage:'+name+'>';sys.modules[name]=m
            exec(compile(decoded['code/'+name+'.py'],m.__file__,'exec'),m.__dict__)
        layout=sys.modules['field_operator_layout_v2'].specification()
        for key in ('target_maximum_bytes','host_maximum_bytes','combined_request_bytes'):
            if a[key]!=layout[key] or type(a[key]) is not int:raise ValueError('Whole producer maxima missing')
        def publish(path,raw):
            if len(raw)>65536 and path.parent.name!='code':raise ValueError('Staging metadata slot')
            with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            if path.read_bytes()!=raw:raise IOError('Target staged readback differs')
        def encoded(value):return json.dumps(value,separators=(',',':'),allow_nan=False).encode()
        root.mkdir()
        for name in layout['directories']:
            if name and '<' not in name:(root/name).mkdir(parents=True,exist_ok=True)
        owner=dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),boot_id=boot)
        publish(root/'control/MANIFEST.json',encoded(dict(stage_owner=owner,files=[dict(path=k,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in decoded.items()])))
        for name,raw in decoded.items():publish(root/name,raw)
        layout_raw=sys.modules['field_operator_layout_v2'].encoded(layout);layout_hash=hashlib.sha256(layout_raw).hexdigest()
        if layout_hash!=a['layout_sha256']:raise ValueError('Layout binding changed')
        publish(root/'control/LAYOUT.json',layout_raw)
        admission_raw=encoded(a);publish(root/'control/ADMISSION.json',admission_raw)
        issued=time.monotonic_ns()
        deadline=dict(schema='just-peachy.absolute-child-deadline.v1',boot_id=boot,issued_ns=issued,
            soft_ns=issued+270_000_000_000,hard_ns=issued+300_000_000_000,grace_ns=30_000_000_000)
        cfg=dict(schema='just-peachy.live-source.v1',capture=True,quiet_only=True,output_root=str(root),
            prototype=a['installed_release'],authority=str(root/'code/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'),
            alsa_config=a['installed_release']+'/config/alsa_hw_only_v1.conf',live_config=str(root/'data/live_config.json'),
            case_directory=str(root/'source'),admission_path=str(root/'control/ADMISSION.json'),
            admission_sha256=hashlib.sha256(admission_raw).hexdigest(),layout_path=str(root/'control/LAYOUT.json'),
            layout_sha256=layout_hash,deadline=deadline,source_module='field_live_source_factory_v6',
            source_factory='create',backpressure_seconds=1)
        publish(root/'config/CONFIG.json',encoded(cfg))
        for name in ('data/conversations','data/.archive-imports','conversation_exports','data/sessions','data/people'):
            directory=root/name
            if not directory.is_dir() or any(directory.iterdir()):raise ValueError('Fresh empty operator data required')
        publish(root/'receipts/DEPENDENCY_BINDING.json',encoded(dict(scope='Fresh empty live operator composition; no archive copied',
            admitted_files=len(a['files']),owner_count=len(sys.modules['field_owner_binding_v1'].decode(a['preflight_pi_owners'])),
            initial_capture_closed=True,source_factory='field_live_source_factory_v6')))
        publish(root/'closure/stage.json',encoded(dict(owner=owner,work_complete=True,readback_exact=True,
            files=len(decoded),bytes=sum(len(x) for x in decoded.values()),baseline_changed=False)))
        return dict(root=str(root),owner=owner,admission_sha256=sha(root/'control/ADMISSION.json'),
                    config_sha256=sha(root/'config/CONFIG.json'),files=len(decoded),staged_bytes=sum(len(x) for x in decoded.values()))
