"""Finite offline manager and native phase runner; README_FIELD_RUNTIME_MANAGER_V1.md."""
# Only standard-library imports before native early-owner registration.
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time
from datetime import datetime,timezone

MIB=1024**2
CAMPAIGN=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(raw):return hashlib.sha256(raw).hexdigest()


def ticks(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def owner():return dict(pid=os.getpid(),start_ticks=ticks(os.getpid()),
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def strict(raw):
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('Duplicate JSON key')
            out[k]=v
        return out
    def bad(value):raise ValueError('Nonfinite JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


def read(path,cap=65536):
    path=Path(path)
    for parent in path.parents:
        if parent.is_symlink() or not parent.is_dir():raise ValueError('Real source ancestors')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>cap:
        raise ValueError('Bounded unique real member')
    raw=path.read_bytes();after=path.lstat()
    if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or len(raw)!=before.st_size:
        raise RuntimeError('Source changed during read')
    return raw


def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish(path,raw,maximum):
    if len(raw)>maximum:raise ValueError('Allocated publication cap')
    path=Path(path)
    if path.exists() or path.is_symlink():raise FileExistsError('Preserve consumed publication')
    with path.open('xb') as f:
        for offset in range(0,len(raw),16384):
            block=raw[offset:offset+16384]
            if f.write(block)!=len(block):raise OSError('Short publication')
        f.flush();os.fsync(f.fileno())
    sync(path.parent)
    if read(path,maximum)!=raw:raise IOError('Independent publication readback')


def native_limits():
    os.sched_setaffinity(0,{3})
    for kind,limit in ((resource.RLIMIT_AS,128*MIB),(resource.RLIMIT_STACK,MIB),
                       (resource.RLIMIT_FSIZE,32*MIB),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(limit,limit))
    if os.uname().machine!='aarch64':raise ValueError('Native CM5 runtime only')
    sys.dont_write_bytecode=True


def verify_manager(root,policy_sha):
    if root.parent!=CAMPAIGN or root.resolve()!=root or not root.name.startswith('field-runtime-v'):
        raise ValueError('Canonical installed runtime root')
    raw=read(root/'control/RELEASE.json')
    if sha(raw)!=policy_sha:raise ValueError('Immutable manager policy pin')
    policy=strict(raw);manifest_raw=read(root/'control/MANIFEST.json',131072)
    if sha(manifest_raw)!=policy['runtime_manifest_sha256']:raise ValueError('Manager manifest drift')
    manifest=strict(manifest_raw);rows=manifest['files']
    if manifest['schema']!='just-peachy.local-release-manifest.v1' or not 1<=len(rows)<=16:
        raise ValueError('Complete finite manager capsule')
    names=set();total=0
    for row in rows:
        path=Path(row['path'])
        if set(row)!={'path','bytes','sha256'} or len(path.parts)!=2 or path.parts[0]!='code' or path.suffix!='.py' or path.as_posix()!=row['path']:
            raise ValueError('Exact manager code pin')
        if path.name.casefold() in names:raise ValueError('Manager case alias')
        names.add(path.name.casefold());data=read(root/path,131072);total+=len(data)
        if type(row['bytes']) is not int or len(data)!=row['bytes'] or sha(data)!=row['sha256']:
            raise ValueError('Manager source pin drift')
    if total>2*MIB or names!={p.name.casefold() for p in (root/'code').iterdir()}:
        raise ValueError('Complete manager code membership')
    return policy


def bootstrap_manager(root,policy_sha):
    # Actual early identity and immutable owner are persisted before project imports.
    native_limits();signal.alarm(60)
    policy=verify_manager(root,policy_sha)
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        who=owner();slots=policy['allocation']['launch_slots'];used=[]
        for index,slot in enumerate(slots):
            directory=root/'launches'/slot;names={p.name for p in directory.iterdir()}
            if not names:continue
            used.append(index)
            if not {'OWNER.json','EXIT.json'}<=names or any(n.endswith('.pending') for n in names):
                raise RuntimeError('Prior unfinished launch requires recovery')
            row=strict(read(directory/'OWNER.json',16384))
            old=row['owner']
            if old['boot_id']==who['boot_id'] and ticks(old['pid'])==old['start_ticks']:
                raise RuntimeError('Prior exact runtime owner is still alive')
        if used!=list(range(len(used))) or len(used)==len(slots):
            raise RuntimeError('Finite launch allocation exhausted or incomplete')
        slot=slots[len(used)]
        row=dict(policy_sha256=policy_sha,slot='launches/'+slot,utc=datetime.now(timezone.utc).isoformat(),
                 owner=who,purpose='USER_RUNTIME_MANAGER')
        target=root/'launches'/slot/'OWNER.json';pending=target.with_name('OWNER.json.pending')
        publish(pending,encoded(row),16384)
        os.link(pending,target,follow_symlinks=False);sync(target.parent);pending.unlink();sync(target.parent)
        if strict(read(target,16384))!=row:raise IOError('Early owner readback')
        sys.path.insert(0,str(root/'code'))
        from field_runtime_journal_v2 import RuntimeJournal
        journal=RuntimeJournal(root,policy_sha,inherited_lock_fd=fd,early_launch=slot)
        fd=None;journal.begin_launch();signal.alarm(0)
        return journal
    finally:
        if fd is not None:os.close(fd)


def bundle_for_operation(root,policy,operation):
    profile=operation['profile']
    if profile!='d1-delayed':raise ValueError('This integration currently implements Delayed only')
    asset=root.with_name(root.name+'-profiles')/profile/'BUNDLE.json'
    raw=read(asset,MIB)
    if sha(raw)!=policy['profiles'][profile]['manifest_sha256']:raise ValueError('Pinned installed profile template')
    value=strict(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    rows=value['manifest']['files'];pins={r['path']:r for r in rows}
    if len(pins)!=len(rows) or set(pins)!=set(files):raise ValueError('Complete profile template')
    for name,data in files.items():
        if pins[name]!=dict(path=name,bytes=len(data),sha256=sha(data)):raise ValueError('Profile member drift')
    activation=strict(read(root/'control/ACTIVATION.json',65536))
    fields={'schema','policy_sha256','settings_sha256','baseline_owners','baseline_expected','baseline','launch_slot'}
    if set(activation)!=fields or activation['schema']!='just-peachy.runtime-activation.v1' or activation['policy_sha256']!=sha(read(root/'control/RELEASE.json')):
        raise ValueError('Actual versioned activation record required')
    config=strict(files['broker/CONFIG.json']);config['baseline']=activation['baseline']
    if config['baseline']['boot_id']!=operation['owner']['boot_id']:raise ValueError('Fresh boot activation observation required')
    launch_matches=[]
    for launch_slot in policy['allocation']['launch_slots']:
        path=root/'launches'/launch_slot/'OWNER.json'
        if path.exists() and strict(read(path,16384)).get('owner')==operation['owner']:
            launch_matches.append(launch_slot)
    if len(launch_matches)!=1:raise ValueError('Unique actual current manager launch')
    config['runtime']=dict(root=str(root),policy_sha256=sha(read(root/'control/RELEASE.json')),
        operation_sha256=sha(encoded(operation)),slot=operation['slot'],manager_owner=operation['owner'],
        launch_slot=launch_matches[0],manager_unit='jp-'+root.name+'.service',
        slice='jpfield'+root.name.replace('-','')+'.slice',settings_sha256=activation['settings_sha256'],
        baseline_owners=activation['baseline_owners'],baseline_expected=activation['baseline_expected'])
    template=strict(files['broker/TEMPLATE.json']);a=template['admission']
    a.update(boot_id=operation['owner']['boot_id'],created_utc=operation['issued_utc'],
        expires_utc=operation['expires_utc'],quiet_only=False,
        install_sha256=config['baseline']['install_sha256'],live_config_sha256=config['baseline']['live_config_sha256'],
        host_window_bytes=policy['measured_host_bytes'],target_before_bytes=policy['measured_target_bytes'],
        payload_before_bytes=policy['measured_payload_bytes'],
        authority_sha256=sha(files['code/OFFLINE_RUNTIME_AUTHORITY_V1.json']))
    files['broker/CONFIG.json']=encoded(config);files['broker/TEMPLATE.json']=encoded(template)
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[
        dict(path=name,bytes=len(data),sha256=sha(data)) for name,data in sorted(files.items())])
    broker=dict(schema='just-peachy.offline-broker-policy.v1',root=operation['root'],
        issued_utc=operation['issued_utc'],expires_utc=operation['expires_utc'],
        allocation=policy['allocation']['broker_allocation'],combined_output_cap_bytes=policy['combined_output_cap_bytes'],
        total_payload_cap_bytes=policy['total_payload_cap_bytes'],mode='delayed',
        release_manifest_sha256=sha(encoded(manifest)),boot_id=operation['owner']['boot_id'],
        host_window_bytes=policy['measured_host_bytes'],target_before_bytes=policy['measured_target_bytes'],
        payload_before_bytes=policy['measured_payload_bytes'],runtime_policy_sha256=sha(read(root/'control/RELEASE.json')),
        runtime_operation_sha256=sha(encoded(operation)),runtime_root=str(root),slot=operation['slot'],profile=profile)
    from field_runtime_policy_v2 import validate_broker_policy
    validate_broker_policy(broker,policy,operation)
    return broker,config,manifest,files


def stage_phase(root,policy_sha,slot):
    policy=verify_manager(root,policy_sha)
    sys.path.insert(0,str(root/'code'))
    from field_runtime_policy_v2 import validate_operation
    operation=strict(read(root/'recordings'/slot/'RESERVED.json',16384))['operation']
    validate_operation(operation,policy,now=datetime.now(timezone.utc))
    broker,config,manifest,files=bundle_for_operation(root,policy,operation)
    destination=Path(operation['root'])
    if destination.parent!=CAMPAIGN or destination.exists() or destination.is_symlink():
        raise ValueError('Fresh canonical broker destination')
    if not 575<=(datetime.fromisoformat(operation['expires_utc'])-datetime.now(timezone.utc)).total_seconds()<=600:
        raise TimeoutError('Full stage/gate/backup time reservation')
    code=[n for n in files if n.startswith('code/')]
    if len(code)>64 or sum(len(files[n]) for n in code)>2*MIB or any(len(v)>131072 for v in files.values()):
        raise ValueError('Original capsule resource caps')
    import types,shutil
    module=types.ModuleType('runtime_stage_common')
    exec(compile(files['code/field_operator_broker_common_v1.py'],'<runtime-stage-injected:common>','exec'),module.__dict__)
    module.physical(config)
    locks=[]
    try:
        for path in (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock'):
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException:os.close(fd);raise
            locks.append(fd)
        ram=next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))
        if ram<850*MIB or shutil.disk_usage(CAMPAIGN).free<5*1024**3+policy['allocation']['target_maximum_bytes']:
            raise RuntimeError('Initial RAM and complete remaining reservation')
        total=int(subprocess.check_output(['du','-sb',str(CAMPAIGN)],timeout=10,text=True).split()[0])
        # Count existing manager and completed independent roots once; retain all full reservations.
        own=int(subprocess.check_output(['du','-sb',str(root)],timeout=10,text=True).split()[0])
        outside=total-own
        for source in policy['recording_roots']:
            p=Path(source)
            if p.exists():outside-=int(subprocess.check_output(['du','-sb',source],timeout=10,text=True).split()[0])
        full=policy['allocation']['combined_request_bytes']
        if (policy['measured_host_bytes']+outside+full>policy['combined_output_cap_bytes']
            or policy['measured_payload_bytes']+max(0,outside-policy['measured_target_bytes'])+full>policy['total_payload_cap_bytes']):
            raise RuntimeError('Fresh target-inclusive complete allocation')
        destination.mkdir();(destination/'code').mkdir();(destination/'broker').mkdir()
        publish(destination/'broker/STAGE_OWNER.json',encoded(owner()),16384)
        publish(destination/'RELEASE.json',encoded(broker),65536)
        publish(destination/'broker/MANIFEST.json',encoded(manifest),131072)
        for name,data in files.items():publish(destination/name,data,65536 if name=='broker/CONFIG.json' else 131072)
        for path in (destination/'code',destination/'broker',destination,CAMPAIGN):sync(path)
        module.bundle(destination)
        return dict(root=str(destination),policy_sha256=sha(encoded(broker)),owner=owner(),
            complete_readback=True,files=len(files))
    finally:
        for fd in locks:os.close(fd)


def copy_phase(root,policy_sha,slot):
    policy=verify_manager(root,policy_sha);sys.path.insert(0,str(root/'code'))
    from field_runtime_policy_v2 import validate_operation
    from field_runtime_backup_v1 import copy_closed
    operation=strict(read(root/'recordings'/slot/'RESERVED.json',16384))['operation']
    validate_operation(operation,policy,now=datetime.now(timezone.utc))
    source=Path(operation['root']);pins={}
    deadline=time.monotonic()+90
    from field_operator_broker_streamed_mirror_v1 import inventory
    observed,_=inventory(source,deadline)
    for name in observed:
        path=source/name;h=hashlib.sha256();count=0
        with path.open('rb') as f:
            while True:
                if time.monotonic()>=deadline:raise TimeoutError('Whole copy preparation deadline')
                data=f.read(16384)
                if not data:break
                h.update(data);count+=len(data)
        pins[name]=dict(bytes=count,sha256=h.hexdigest())
    remaining=(datetime.fromisoformat(operation['expires_utc'])-datetime.now(timezone.utc)).total_seconds()
    if remaining<10:raise TimeoutError('No complete copy reserve')
    return copy_closed(source,root/'backups'/slot,sha(read(source/'RELEASE.json')),
        'jp-'+source.name+'.service',pins,operation=operation,runtime=policy,
        deadline=min(deadline,time.monotonic()+remaining-3),
        maximum_bytes=policy['allocation']['local_backup_per_recording'])


def helper(phase):
    native_limits();signal.alarm(80)
    who=owner()
    print(encoded(dict(type='HELLO',owner=who,phase=phase)).decode(),flush=True)
    line=sys.stdin.buffer.readline(4097)
    if len(line)>4096 or not line.endswith(b'\n'):raise ValueError('Bounded parent acknowledgment')
    request=strict(line)
    if set(request)!={'owner','root','policy_sha256','slot'} or request['owner']!=who:
        raise ValueError('Early helper owner must be durably registered before project imports')
    root=Path(request['root']);policy=verify_manager(root,request['policy_sha256'])
    slot=request['slot']
    if slot not in policy['allocation']['recording_slots']:raise ValueError('Allocated operation')
    if phase=='stage':
        signal.alarm(45);result=stage_phase(root,request['policy_sha256'],slot)
    elif phase=='copy':
        signal.alarm(110);result=copy_phase(root,request['policy_sha256'],slot)
    elif phase=='gate':
        operation=strict(read(root/'recordings'/slot/'RESERVED.json',16384))['operation']
        source=Path(operation['root']);broker=strict(read(source/'RELEASE.json'))
        manifest=strict(read(source/'broker/MANIFEST.json',131072))
        if sha(encoded(manifest))!=broker['release_manifest_sha256']:raise ValueError('Gate manifest')
        for row in manifest['files']:
            raw=read(source/row['path'],131072)
            if len(raw)!=row['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Gate project graph pin')
        sys.path.insert(0,str(source/'code'))
        from field_operator_broker_gate_v8 import main
        signal.alarm(0)
        rc=main(source,sha(read(source/'RELEASE.json')))
        if rc:raise RuntimeError('Broker gate failed; preserve complete tree')
        result=dict(root=str(source),natural_gate_success=True)
    else:raise ValueError('Exact native helper phase')
    raw=encoded(dict(type='RESULT',phase=phase,value=result))
    if len(raw)>262144:raise ValueError('Complete helper result framing cap')
    print(raw.decode(),flush=True)


class Manager:
    def __init__(self,journal,selected):
        import tkinter as tk
        self.journal=journal;self.root=journal.root;self.proc=None;self.phase=None
        self.operation=None;self.child_owner=None;self.helper_slot=None;self.buffer=b'';self.error_bytes=b''
        self.result=None;self.closed=False;self.fault=None;self.started_record=False
        self.stop_requested=False;self.failure_stop_time=None;self.failure_output_discarded=0
        signal.signal(signal.SIGTERM,lambda signum,frame:setattr(self,'stop_requested',True))
        self.ui=tk.Tk(screenName=':0');self.ui.title('Just Peachy')
        self.ui.geometry('480x800+0+0');self.ui.attributes('-fullscreen',True)
        self.ui.configure(bg='#111827')
        tk.Label(self.ui,text='Just Peachy',fg='white',bg='#111827',font=('DejaVu Sans',24)).pack(pady=18)
        tk.Label(self.ui,text='Offline recording',fg='white',bg='#111827',font=('DejaVu Sans',16)).pack()
        self.status=tk.Label(self.ui,text='Capture is off',fg='white',bg='#111827',wraplength=440,font=('DejaVu Sans',13))
        self.status.pack(pady=15)
        self.profiles=tk.Listbox(self.ui,font=('DejaVu Sans',13),height=7,exportselection=False)
        self.profiles.pack(fill='x',padx=16)
        self.names=list(journal.policy['profiles'])
        for name in self.names:
            row=journal.policy['profiles'][name]
            self.profiles.insert('end',name+('' if row['available'] else ' — unavailable'))
        if selected in self.names:self.profiles.selection_set(self.names.index(selected))
        self.start=tk.Button(self.ui,text='New recording',command=self.new,font=('DejaVu Sans',16),height=2)
        self.start.pack(fill='x',padx=16,pady=18)
        self.notice=tk.Label(self.ui,text='Each recording is limited to 2 minutes.\nUse Start and Stop in the recording screen.\nA verified local copy is kept before another recording.',fg='white',bg='#111827',wraplength=440,font=('DejaVu Sans',12))
        self.notice.pack(pady=15)
        self.exit=tk.Button(self.ui,text='Close',command=self.close,font=('DejaVu Sans',16),height=2)
        self.exit.pack(side='bottom',fill='x',padx=16,pady=18)
        self.ui.protocol('WM_DELETE_WINDOW',self.close)
        self.ui.report_callback_exception=lambda k,v,t:self.fail(k.__name__+': '+str(v))
        self.refresh()

    def refresh(self):
        rows=self.journal.inspect()
        count=sum(bool(rows['recordings/'+s]) for s in self.journal.plan['recording_slots'])
        self.status.configure(text='Capture is off. '+str(len(self.journal.plan['recording_slots'])-count)+' recording slots remain.')
        self.start.configure(state='normal' if count<len(self.journal.plan['recording_slots']) else 'disabled')

    def new(self):
        if self.proc is not None or self.fault:return
        selection=self.profiles.curselection()
        if len(selection)!=1:self.status.configure(text='Select a recording profile.');return
        profile=self.names[selection[0]];row=self.journal.policy['profiles'][profile]
        if not row['available']:self.status.configure(text=row['reason']);return
        if profile!='d1-delayed':self.status.configure(text='This runtime build has not integrated that profile yet.');return
        self.operation=self.journal.reserve_recording(profile)
        self.start.configure(state='disabled');self.status.configure(text='Preparing the recording screen…')
        self.spawn('stage')

    def spawn(self,phase):
        self.phase=phase;self.child_owner=None;self.helper_slot=None;self.buffer=b'';self.error_bytes=b'';self.result=None
        self.stdout_eof=False;self.stderr_eof=False
        self.phase_start=time.monotonic()
        self.proc=subprocess.Popen([sys.executable,'-B',str(Path(__file__)), '--helper',phase],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,close_fds=True)
        os.set_blocking(self.proc.stdout.fileno(),False);os.set_blocking(self.proc.stderr.fileno(),False)

    def register(self,who):
        from field_runtime_policy_v2 import identity
        identity(who)
        if who!=dict(pid=self.proc.pid,start_ticks=ticks(self.proc.pid),boot_id=owner()['boot_id']):
            raise ValueError('Exact actual helper process before payload')
        rows=self.journal.inspect();used=[]
        for i,slot in enumerate(self.journal.plan['launch_slots']):
            r=rows['launches/'+slot]
            if not r:continue
            used.append(i)
            if slot==self.journal.launch_slot:continue
            if set(r)!={'OWNER','EXIT'}:raise RuntimeError('Unclosed earlier helper')
            prior=r['OWNER']['owner']
            if prior['boot_id']==who['boot_id'] and ticks(prior['pid'])==prior['start_ticks']:
                raise RuntimeError('Earlier helper is still alive')
        slots=self.journal.plan['launch_slots']
        if used!=list(range(len(used))) or len(used)==len(slots):raise RuntimeError('Helper launches exhausted')
        slot=slots[len(used)]
        self.journal._publish('launches/'+slot,'OWNER',dict(owner=who,purpose='USER_RUNTIME_'+self.phase.upper()))
        self.child_owner=who;self.helper_slot=slot
        packet=encoded(dict(owner=who,root=str(self.root),policy_sha256=self.journal.policy_sha,
            slot=self.operation['slot']))+b'\n'
        if len(packet)>4096:raise ValueError('Bounded helper payload')
        if self.proc.stdin.write(packet)!=len(packet):raise IOError('Incomplete helper acknowledgment')
        self.proc.stdin.close()

    def poll(self):
        if self.proc is None:return
        limit={'stage':55,'gate':570,'copy':120}[self.phase]
        if time.monotonic()-self.phase_start>limit:raise TimeoutError('Native phase deadline')
        for pipe,is_error in ((self.proc.stdout,False),(self.proc.stderr,True)):
            while True:
                data=pipe.read(16384)
                if data is None:break
                if not data:
                    if is_error:self.stderr_eof=True
                    else:self.stdout_eof=True
                    break
                if is_error:
                    if len(self.error_bytes)+len(data)>8192:raise RuntimeError('Bounded helper stderr overflow')
                    self.error_bytes+=data
                else:
                    self.buffer+=data
                    if len(self.buffer)>262145:raise RuntimeError('Bounded helper frame overflow')
                    while b'\n' in self.buffer:
                        line,self.buffer=self.buffer.split(b'\n',1)
                        if not line:raise ValueError('Empty helper frame')
                        value=strict(line)
                        if value.get('type')=='HELLO':
                            if self.child_owner is not None or value.get('phase')!=self.phase:raise ValueError('Duplicate helper identity')
                            self.register(value['owner'])
                        elif value.get('type')=='RESULT':
                            if self.result is not None or value.get('phase')!=self.phase:raise ValueError('Duplicate helper result')
                            self.result=value['value']
                        elif self.phase!='gate' or set(value)!={'logical_success','returncode','failure'}:
                            raise ValueError('Unknown helper output')
        if self.phase=='gate' and not self.started_record:
            source=Path(self.operation['root'])
            if (source/'broker/ENVELOPE.json').exists():
                self.journal.recording_started(self.operation['slot']);self.started_record=True
        if self.proc.poll() is None:return
        if not (self.stdout_eof and self.stderr_eof):return
        rc=self.proc.wait(timeout=1)
        if self.child_owner is None or ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
            raise RuntimeError('Exact helper closure unverified')
        self.proc.stdout.close();self.proc.stderr.close()
        if self.buffer or rc or self.result is None or self.error_bytes:
            raise RuntimeError('Helper failed: '+self.error_bytes.decode(errors='replace')[-1024:])
        self.journal._publish('launches/'+self.helper_slot,'EXIT',dict(owner=self.child_owner,
            purpose='USER_RUNTIME_'+self.phase.upper(),natural_returncode=rc,exact_process_dead=True))
        phase=self.phase;result=self.result;self.proc=None
        if phase=='stage':
            self.ui.withdraw();self.started_record=False;self.spawn('gate')
        elif phase=='gate':
            self.journal.recording_closed(self.operation['slot'])
            self.ui.deiconify();self.status.configure(text='Recording closed. Verifying the local backup…')
            self.spawn('copy')
        else:
            self.journal.accept_local_backup(self.operation['slot'],result)
            self.operation=None;self.refresh()

    def fail(self,reason):
        if self.fault:return
        self.fault=str(reason)[:512]
        self.failure_stop_time=time.monotonic()
        # Target only the current exact owned child/unit. Preserve failure evidence.
        if self.operation is not None:
            unit='jp-'+Path(self.operation['root']).name+'.service'
            subprocess.run(['systemctl','--user','stop','--no-block',unit],timeout=5,check=False)
        if self.phase!='gate' and self.proc is not None and self.child_owner and ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
            self.proc.terminate()
        self.start.configure(state='disabled');self.ui.deiconify()
        self.status.configure(text='Recording stopped. Preserved files need recovery. '+self.fault)

    def failure_poll(self):
        if self.proc is None:return
        for pipe in (self.proc.stdout,self.proc.stderr):
            while True:
                data=pipe.read(16384)
                if not data:break
                keep=min(len(data),max(0,8192-len(self.error_bytes)))
                self.error_bytes+=data[:keep];self.failure_output_discarded+=len(data)-keep
        if self.proc.poll() is None:
            if time.monotonic()-self.failure_stop_time<35:return
            if self.child_owner and ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
                self.proc.kill()
            elif self.child_owner is None:
                # Popen's unreaped child handle is exact even if HELLO failed.
                self.proc.kill()
            return
        rc=self.proc.wait(timeout=1);self.proc.stdout.close();self.proc.stderr.close()
        if self.proc.stdin and not self.proc.stdin.closed:self.proc.stdin.close()
        if self.child_owner and ticks(self.child_owner['pid'])==self.child_owner['start_ticks']:
            raise RuntimeError('Failed helper exact identity remains alive')
        if self.helper_slot:
            try:
                self.journal._publish('launches/'+self.helper_slot,'FAILURE',dict(reason=self.fault,
                    bounded_output=self.error_bytes.decode(errors='replace'),discarded_bytes=self.failure_output_discarded))
                self.journal._publish('launches/'+self.helper_slot,'EXIT',dict(owner=self.child_owner,
                    purpose='USER_RUNTIME_'+self.phase.upper(),returncode=rc,exact_process_dead=True,
                    successful=False))
            except BaseException:
                pass  # Preserved pending/failed publication continues to fence recovery.
        self.proc=None

    def close(self):
        if self.proc is not None:
            self.status.configure(text='Return from the recording screen and wait for the backup first.');return
        if self.fault:
            self.journal._physical_idle()
            try:
                self.journal._publish('launches/'+self.journal.launch_slot,'FAILURE',dict(reason=self.fault,recovery_required=True))
                self.journal._publish('launches/'+self.journal.launch_slot,'EXIT',dict(owner=self.journal.owner,
                    status='RECOVERY_REQUIRED_CAPTURE_OFF',exit_is_intent=True,successful=False))
            finally:
                self.closed=True;self.ui.destroy();self.journal.close()
            return
        self.journal.end_launch();self.closed=True;self.ui.destroy();self.journal.close()

    def run(self):
        while not self.closed:
            try:
                if self.stop_requested and not self.fault:self.fail('Runtime service Stop requested')
                if self.fault:self.failure_poll()
                else:self.journal._live();self.poll()
                self.ui.update()
                if self.stop_requested and self.proc is None:self.close()
            except BaseException as exc:self.fail(type(exc).__name__+': '+str(exc))
            time.sleep(.01)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path);parser.add_argument('--policy-sha256')
    parser.add_argument('--profile',default='d1-delayed');parser.add_argument('--helper',choices=('stage','gate','copy'))
    args=parser.parse_args()
    if args.helper:return helper(args.helper)
    if args.root is None or args.policy_sha256 is None:parser.error('Installed root and exact policy SHA required')
    journal=bootstrap_manager(args.root,args.policy_sha256)
    Manager(journal,args.profile).run()


if __name__=='__main__':main()
