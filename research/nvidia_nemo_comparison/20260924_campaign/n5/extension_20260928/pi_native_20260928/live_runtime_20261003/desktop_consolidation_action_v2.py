"""Exact retained-shortcut archive/restore; README_DESKTOP_CONSOLIDATION_V2.md."""
import hashlib
import importlib.util
import sys
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time

IMPORTS = ('profiles', 'optional_refiner_admission', 'release_authorization', 'optional_refiner_dispatch')

def module_bytes(package, manifest, name):
    rows = [row for row in manifest['files'] if row['path'] == name+'.py']
    if len(rows) != 1: raise ValueError('Unique pinned import required: '+name)
    raw = read(package/(name+'.py'), 131072); row = rows[0]
    if (len(raw), sha(raw)) != (row['bytes'], row['sha256']):
        raise ValueError('Pinned import changed: '+name)
    return raw


class VerifiedImports:
    """Canonical package imports with previous module/path state restored."""
    def __init__(self, package, manifest):
        self.package = package; self.manifest = manifest; self.prior = {}; self.paths = None
        self.origins = {}

    def __enter__(self):
        self.paths = list(sys.path)
        try:
            for name in IMPORTS:
                old = sys.modules.get(name)
                if old is not None and Path(getattr(old, '__file__', '')).resolve() != self.package/(name+'.py'):
                    raise ValueError('Existing project import has a different origin: '+name)
                self.prior[name] = old
            sys.path.insert(0, str(self.package))
            for name in IMPORTS:
                raw = module_bytes(self.package, self.manifest, name)
                path = self.package/(name+'.py')
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec); sys.modules[name] = module
                exec(compile(raw, str(path), 'exec'), module.__dict__)
                if Path(module.__file__).resolve(strict=True) != path:
                    raise ValueError('Loaded import origin changed: '+name)
                self.origins[name] = dict(path=str(path), bytes=len(raw), sha256=sha(raw))
            return self
        except BaseException:
            self.__exit__(None, None, None); raise

    def __exit__(self, *args):
        if self.paths is not None: sys.path[:] = self.paths
        for name, old in self.prior.items():
            if old is None: sys.modules.pop(name, None)
            else: sys.modules[name] = old



# Literal actual post-soak-baseline02 membership; no prefix-based deletion.
OWNED = {
    'just-peachy-field-runtime-v28-baseline-anonymous.desktop': (414,'dfc1647fb5a2b152320b90be95cdf549d018f1193c620bd0fa81f14297c04082'),
    'just-peachy-field-runtime-v28-baseline-titanet.desktop': (390,'6dfb004d73b8cd93c5edf5ba91ce5ae8f9fde30d39fa1943c2eb75559802ce88'),
    'just-peachy-field-runtime-v28-baseline.desktop': (383,'ce12176a060b54506517f83e839d8dc1df920750afe5c2eb1024ae674bea9742'),
    'just-peachy-field-runtime-v28-d1-anonymous.desktop': (401,'9b112b185d40a526ba63982c49e62043f462806b8651789b8c1449f2b01c06e9'),
    'just-peachy-field-runtime-v28-d1-chunk52-saved.desktop': (401,'6850f8768be25b56aeb5bad0a64a2ed8de0a381512d40b05ef387bd8eaec67d3'),
    'just-peachy-field-runtime-v28-d1-chunk52-titanet-saved.desktop': (408,'cc31d3e3bb7740ebd46daac5a096d6699c6f22619e468d677716b766181b68fb'),
    'just-peachy-field-runtime-v28-d1-delayed-titanet.desktop': (390,'cc62e7d5f7235519727ecf5b1610f22e117cfd1919a8e060194d5044397ba8bd'),
    'just-peachy-field-runtime-v28-d1-delayed.desktop': (383,'6048dba91eb714256159d1ccc6bd97f8c6de64b99a1125a8b3e28bf2d916ef8e'),
    'just-peachy-field-runtime-v28-d1-streaming-saved.desktop': (405,'308408462d5c4aef06d8e67afc6ad68184863b58fb47e4b43307637891400cd8'),
    'just-peachy-field-runtime-v28-d1-streaming-titanet-saved.desktop': (412,'e2dd42a9e9eeff6eb69a3681906ab30040347d65c82beb15250cd70313817a56'),
    'just-peachy-field-runtime-v28-rollback.desktop': (249,'63f74b59a1afdf86b871d454e2895053399a21427e7e6d45f48c18915724b3fc'),
}
STARTUP = {
    '/home/peachyprototype/.config/autostart/just-peachy.desktop': (427,'8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206'),
    '/home/peachyprototype/JustPeachy/start-prototype.sh': (405,'79b7b08db6a67060bfc20a02ae8af437b37a938eb1f4e33817adcdb33d57f19f'),
}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def read(path, maximum=65536):
    path=Path(path);info=path.lstat()
    if path.resolve(strict=True)!=path or not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>maximum:
        raise ValueError('Canonical bounded single-link file required')
    with path.open('rb') as stream:raw=stream.read(maximum+1)
    if len(raw)>maximum:raise ValueError('File extent grew')
    return raw


def sync(path):
    if os.name!='nt':
        fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)


def write(path,raw,mode=0o600):
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short independent desktop copy')
        stream.flush();os.fsync(stream.fileno())
    os.chmod(path,mode);sync(path.parent)
    if read(path)!=raw:raise OSError('Independent desktop readback differs')


def save(path,value):
    write(path,json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def inventory(desktop):
    """Bounded full Desktop membership, including hashes of unrelated files."""
    result={}
    with os.scandir(desktop) as entries:
        for entry in entries:
            if len(result)>=128:raise ValueError('Bounded full Desktop membership required')
            info=entry.stat(follow_symlinks=False)
            if entry.is_symlink():raise ValueError('Review Desktop symlinks before consolidation')
            row=dict(mode=stat.S_IMODE(info.st_mode),kind='directory' if entry.is_dir(follow_symlinks=False) else 'file')
            if row['kind']=='file':
                raw=read(Path(entry.path),1024**2);row.update(bytes=len(raw),sha256=sha(raw))
            result[entry.name]=row
    return result


def archive_shortcuts(desktop,archive,selected,original_selected,expected_current_sha,*,owned=OWNED):
    """Only exact owned bytes can leave Desktop, after two complete readbacks."""
    if selected not in owned or len(owned)!=11:raise ValueError('One reviewed selected shortcut among all11 required')
    before=inventory(desktop);originals={};current=read(desktop/selected)
    if sha(current)!=expected_current_sha:raise ValueError('Activated selected shortcut changed')
    for name,pin in owned.items():
        raw=original_selected if name==selected else read(desktop/name)
        if (len(raw),sha(raw))!=tuple(pin):raise ValueError('Exact11 retained shortcut pins required')
        originals[name]=raw
    archive.mkdir(mode=0o700)
    for directory in ('before','restore','archived'):(archive/directory).mkdir(mode=0o700)
    for name,raw in originals.items():
        for directory in ('before','restore'):write(archive/directory/name,raw,before[name]['mode'])
    write(archive/'unified.desktop.backup',current,before[selected]['mode'])
    write(archive/'unified.desktop.restore',current,before[selected]['mode'])
    plan=dict(schema='just-peachy.desktop-consolidation.v1',desktop=str(desktop),archive=str(archive),
        selected=selected,current_sha256=expected_current_sha,owned={name:list(pin) for name,pin in owned.items()},
        before=before,autostart_changed=False,process_started=False)
    save(archive/'PLAN.json',plan)
    if inventory(desktop)!=before:raise ValueError('Desktop changed before any removal')
    for index,name in enumerate(sorted(owned)):
        if name==selected:continue
        if read(desktop/name)!=originals[name]:raise ValueError('Owned shortcut changed before archive')
        save(archive/('MOVE_INTENT_%02d.json'%index),dict(name=name,sha256=sha(originals[name])))
        os.rename(desktop/name,archive/'archived'/name);sync(desktop);sync(archive/'archived')
        if read(archive/'archived'/name)!=originals[name]:raise OSError('Archived shortcut readback differs')
    expected={name:row for name,row in before.items() if name not in owned or name==selected}
    after=inventory(desktop)
    if after!=expected:raise ValueError('Desktop final membership/content differs')
    result=dict(status='ONE_UNIFIED_SHORTCUT_NOT_STARTED',before=before,after=after,
        archive=str(archive),selected=selected,owned_shortcuts_remaining=1,unrelated_entries_unchanged=True,
        autostart_changed=False,process_started=False)
    save(archive/'CONSOLIDATED.json',result);return result


def restore_shortcuts(desktop,archive,*,owned=OWNED):
    plan=json.loads(read(archive/'PLAN.json'));selected=plan['selected']
    if (plan['desktop']!=str(desktop) or plan['archive']!=str(archive) or
        plan['owned']!={name:list(pin) for name,pin in owned.items()} or selected not in owned):
        raise ValueError('Exact consolidation plan required')
    before=inventory(desktop);current=read(desktop/selected)
    if sha(current)!=plan['current_sha256'] or current!=read(archive/'unified.desktop.restore'):
        raise ValueError('Current unified shortcut changed; refuse restore')
    expected={name:row for name,row in plan['before'].items() if name not in owned or name==selected}
    if before!=expected:raise ValueError('Restore requires exact consolidated Desktop membership')
    originals={}
    for name,pin in owned.items():
        raw=read(archive/'restore'/name)
        if raw!=read(archive/'before'/name) or (len(raw),sha(raw))!=tuple(pin):
            raise ValueError('Independent exact original shortcut restores required')
        originals[name]=raw
    save(archive/'RESTORE_INTENT.json',dict(selected=selected,before=before))
    for name,raw in originals.items():
        if name==selected:continue
        write(desktop/name,raw,plan['before'][name]['mode'])
    staged=archive/'selected-original.restore-ready'
    write(staged,originals[selected],plan['before'][selected]['mode'])
    if read(desktop/selected)!=current:raise ValueError('Selected launcher changed before restore')
    os.replace(staged,desktop/selected);sync(desktop)
    after=inventory(desktop);expected=dict(plan['before'])
    expected[selected]=dict(expected[selected],bytes=len(originals[selected]),sha256=sha(originals[selected]))
    if after!=expected:raise ValueError('Restored11 shortcut membership/readback differs')
    result=dict(status='ALL11_RETAINED_SHORTCUTS_RESTORED_NOT_STARTED',before=before,after=after,
        archive=str(archive),autostart_changed=False,process_started=False)
    save(archive/'RESTORED.json',result);return result


def dispatch(p,baseline):
    import fcntl
    if any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners')):
        raise ValueError('All runtime owners must close before Desktop changes')
    if (Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=p['boot_id'] or
        not time.time()<p['expires_unix']<=time.time()+600):raise ValueError('Fresh exact boot/deadline required')
    base=Path('/home/peachyprototype/JustPeachy');campaign=base/'research/nemotron-20260928'
    desktop=Path('/home/peachyprototype/Desktop');package=Path(p['package']);archive=Path(p['archive'])
    if (package.parent!=campaign or not re.fullmatch(r'field-runtime-v29-build-[0-9]{2}',package.name) or
        archive.parent!=campaign or not re.fullmatch(r'field-runtime-v29-desktop-consolidation-[0-9a-f]{32}',archive.name)):
        raise ValueError('Exact candidate and off-Desktop archive paths required')
    for path in (desktop,campaign,package):
        if path.resolve(strict=True)!=path:raise ValueError('Canonical native directories required')
    if p.get('maximum_output_bytes')!=16*1024**2 or shutil.disk_usage(campaign).free<5*1024**3+16*1024**2:
        raise ValueError('Independent16MiB allocation above5GiB floor required')
    manifest_raw=read(package/'PACKAGE_MANIFEST.json',262144)
    if sha(manifest_raw)!=p['package_manifest_sha256']:raise ValueError('Package manifest changed')
    manifest=json.loads(manifest_raw)
    def load(name):
        row=next(row for row in manifest['files'] if row['path']==name+'.py');raw=read(package/row['path'],131072)
        if (len(raw),sha(raw))!=(row['bytes'],row['sha256']):raise ValueError('Pinned package helper differs')
        namespace=dict(__name__='verified_'+name,__file__=str(package/row['path']))
        exec(compile(raw,str(package/row['path']),'exec'),namespace);return namespace
    installer=load('install_candidate');installer['check_native']();installer['verify_tree'](package,p['package_manifest_sha256'])
    binding=json.loads(read(package/'BINDING.json',262144))
    if binding.get('authorization_kind')!='production' or binding.get('native_launch_enabled') is not True:
        raise ValueError('Separate production acceptance required before shortcut consolidation')
    acceptance_raw=read(package/'PRODUCTION_ACCEPTANCE.json',262144)
    if sha(acceptance_raw)!=binding['production_acceptance_sha256']:raise ValueError('Production acceptance changed')
    with VerifiedImports(package,manifest) as imported:
        acceptance=sys.modules['release_authorization'].validate_acceptance(json.loads(acceptance_raw),binding)
        import_origins=dict(imported.origins)
    backup_manifest=read(package/'PRODUCTION_BACKUP_MANIFEST.json',2*1024**2)
    backup_complete=read(package/'PRODUCTION_BACKUP_COMPLETE.json',262144)
    full=acceptance['full_backup'];completion=json.loads(backup_complete)
    if (sha(backup_manifest)!=full['manifest_sha256'] or sha(backup_complete)!=full['completion_sha256'] or
        completion.get('kind')!='COMPLETE' or not all(completion.get('closure',{}).get(k) is True for k in ('closed','exact_owner_gone','cgroup_empty'))):
        raise ValueError('Accepted complete closed full-backup proof required')
    rows={row.get('source'):row for row in json.loads(backup_manifest)}
    required={str(desktop/name):pin for name,pin in OWNED.items()};required.update(STARTUP)
    for name,pin in required.items():
        row=rows.get(name,{})
        if (row.get('identity',{}).get('bytes'),row.get('sha256'))!=pin:
            raise ValueError('Complete backup must include all11 original shortcuts and both startup files')
    leases=[]
    try:
        for path in (campaign/'B05_PREVIEW_DISPATCH.lock',base/'data/xvf-hardware.lock'):
            lease=path.open('rb');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);leases.append(lease)
        for name,pin in STARTUP.items():
            raw=read(Path(name))
            if (len(raw),sha(raw))!=pin:raise ValueError('Exact disabled startup files changed')
        if p['mode']=='consolidate':
            selected=p['selected'];activation=Path(p['activation_backup'])
            if activation.parent!=campaign or not re.fullmatch(r'field-runtime-v29-desktop-backup-[0-9a-f]{32}',activation.name):
                raise ValueError('Actual activation backup required')
            plan=json.loads(read(activation/'ACTIVATION_PLAN.json'))
            if (selected not in OWNED or plan['desktop']!=str(desktop/selected) or
                plan['manifest_sha256']!=p['package_manifest_sha256'] or plan['next_sha256']!=p['expected_current_sha256'] or
                plan['previous_sha256']!=OWNED[selected][1] or plan['backup']!=str(activation)):
                raise ValueError('Exact selected activation plan required')
            old=read(activation/(selected+'.backup'))
            if old!=read(activation/(selected+'.restore')):raise ValueError('Independent activation restore differs')
            result=archive_shortcuts(desktop,archive,selected,old,p['expected_current_sha256'])
        elif p['mode']=='restore':result=restore_shortcuts(desktop,archive)
        else:raise ValueError('Explicit consolidate or restore mode required')
        for name,pin in STARTUP.items():
            raw=read(Path(name))
            if (len(raw),sha(raw))!=pin:raise ValueError('Startup bytes changed during Desktop operation')
        result['verified_import_origins']=import_origins
        return result
    finally:
        for lease in reversed(leases):fcntl.flock(lease,fcntl.LOCK_UN);lease.close()


if 'PAYLOAD' in globals():RESULT=dispatch(PAYLOAD,BASELINE)
