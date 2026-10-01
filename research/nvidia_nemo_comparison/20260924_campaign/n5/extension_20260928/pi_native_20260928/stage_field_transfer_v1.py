"""Fresh target staging only. Read README_FIELD_TRANSFER_UI_V1.md."""
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
    a=request['admission'];root=ROOT/'field-transfer-ui-v1'
    if a['output_root']!=str(root) or root.exists() or root.is_symlink():
        raise ValueError('Fresh exact run root required; never retry an existing root')
    now=datetime.now(timezone.utc);expiry=datetime.fromisoformat(a['expires_utc'])
    if not 480<=(expiry-now).total_seconds()<=600 or expiry>datetime.fromisoformat('2026-10-01T17:42:44+00:00'):
        raise ValueError('Stage, live closure and backup must fit hard deadline')
    if a['capture'] is not False or a['scope']!='SAVED_COPY_VISIBLE_TRANSFER':
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
        for owner in a['preflight_pi_owners']:
            if owner['boot_id']==boot and ticks(owner['pid'])==owner['start_ticks']:raise ValueError('Owned process alive')
        policy=json.loads(decoded['code/TRANSFER_RESOURCE_POLICY_V1.json'])
        if hashlib.sha256(decoded['code/WINDOW_V5.json']).hexdigest()!=a['old_policy_pin']['sha256']:raise ValueError('Old policy changed')
        total=int(subprocess.check_output(['du','-sb',str(ROOT)],text=True).split()[0])
        if a['host_window_bytes']+total+a['combined_request_bytes']>policy['combined_output_cap_bytes']:
            raise ValueError('Target-inclusive measured output projection')
        if a['payload_before_bytes']+max(0,total-a['target_before_bytes'])+a['combined_request_bytes']>policy['total_payload_cap_bytes']:
            raise ValueError('Target-inclusive payload projection')
        # Validate the selected exact layout from admitted source, before mkdir.
        import sys,types
        for name in ('field_live_layout_v2','field_live_layout_v3','field_live_paths_v1','field_transfer_v2','field_transfer_paths_v2','field_transfer_layout_v1'):
            m=types.ModuleType(name);m.__file__='<admitted-stage:'+name+'>';sys.modules[name]=m
            exec(compile(decoded['code/'+name+'.py'],m.__file__,'exec'),m.__dict__)
        layout=sys.modules['field_transfer_layout_v1'].specification()
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
        layout_raw=sys.modules['field_transfer_layout_v1'].encoded(layout);layout_hash=hashlib.sha256(layout_raw).hexdigest()
        if layout_hash!=a['layout_sha256']:raise ValueError('Layout binding changed')
        publish(root/'control/LAYOUT.json',layout_raw)
        admission_raw=encoded(a);publish(root/'control/ADMISSION.json',admission_raw)
        issued=time.monotonic_ns()
        deadline=dict(schema='just-peachy.absolute-child-deadline.v1',boot_id=boot,issued_ns=issued,
            soft_ns=issued+270_000_000_000,hard_ns=issued+300_000_000_000,grace_ns=30_000_000_000)
        cfg=dict(schema='just-peachy.saved-actions.v1',capture=False,quiet_only=True,output_root=str(root),
            prototype=a['installed_release'],authority=str(root/'code/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'),
            alsa_config=a['installed_release']+'/config/alsa_hw_only_v1.conf',live_config=str(root/'data/live_config.json'),
            case_directory=str(root/'source'),admission_path=str(root/'control/ADMISSION.json'),
            admission_sha256=hashlib.sha256(admission_raw).hexdigest(),layout_path=str(root/'control/LAYOUT.json'),
            layout_sha256=layout_hash,deadline=deadline,source_module='field_live_source_factory_v4',
            source_factory='create',backpressure_seconds=1)
        publish(root/'config/CONFIG.json',encoded(cfg))
        # Copy only the exact complete conversation; original target remains read-only.
        selected=a['saved_copy'];source_root=Path(selected['source_root'])
        if source_root!=ROOT/'field-saved-actions-v3':raise ValueError('Exact immutable source required')
        conversation=selected['conversation'];epoch=selected['epoch']
        prefix='data/conversations/'+conversation
        actual={p.relative_to(source_root).as_posix() for p in (source_root/prefix).rglob('*') if p.is_file()}
        if actual!={r['relative'] for r in selected['files']}:raise ValueError('Exact source membership changed')
        sys.path.insert(0,str(root/'code'))
        from field_transfer_files_v2 import make_class
        code_files={Path(n).name:len(v) for n,v in decoded.items() if n.startswith('code/')}
        guard=make_class(a['transfer']['import_token'])(root,code_files,lambda:None).install()
        for name in (prefix,prefix+'/epochs',prefix+'/epochs/'+epoch):(root/name).mkdir()
        for row in selected['files']:
            original=Path(row['source']);destination=root/row['relative']
            if original!=source_root/row['relative'] or destination.exists():raise ValueError('Copy binding/exclusive destination')
            if sha(original)!=row['sha256'] or original.stat().st_size!=row['bytes']:raise ValueError('Source bytes changed')
            count=0
            with original.open('rb') as source,destination.open('xb') as out:
                while block:=source.read(16384):
                    count+=len(block)
                    if count>row['bytes']:raise ValueError('Source grew')
                    if out.write(block)!=len(block):raise IOError('Short copy retained')
                out.flush();os.fsync(out.fileno())
            if count!=row['bytes'] or sha(destination)!=row['sha256'] or sha(original)!=row['sha256']:raise ValueError('Copy readback')
        physical=guard.census()
        if physical['failures'] or physical['open_writable_descriptors']:raise ValueError('Staging copy physical closure')
        publish(root/'receipts/DEPENDENCY_BINDING.json',encoded(dict(scope='Exact immutable archive copied before installed constructor',
            source_root=str(source_root),files=selected['files'],copy_bytes=sum(r['bytes'] for r in selected['files']),
            original_preserved=True,physical=physical)))
        publish(root/'closure/stage.json',encoded(dict(owner=owner,work_complete=True,readback_exact=True,
            files=len(decoded),bytes=sum(len(x) for x in decoded.values()),baseline_changed=False)))
        return dict(root=str(root),owner=owner,admission_sha256=sha(root/'control/ADMISSION.json'),
                    config_sha256=sha(root/'config/CONFIG.json'),files=len(decoded),staged_bytes=sum(len(x) for x in decoded.values()))
