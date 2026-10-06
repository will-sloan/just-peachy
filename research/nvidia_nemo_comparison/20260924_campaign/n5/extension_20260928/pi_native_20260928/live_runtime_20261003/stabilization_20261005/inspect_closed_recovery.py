"""Read only one closed XVF recovery tree. README_CLOSED_RECOVERY_INSPECTION.md."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

FAULT = '01beda380170956338c66b1489689e7c725cb0f74a6014b6793a96eb389f133a'
ROOT = Path('/home/peachyprototype/JustPeachy/data/runtime-v29/recovery')/FAULT


def inspect(payload, baseline):
    if payload != dict(schema='just-peachy.closed-recovery-inspection.v1', fault_sha256=FAULT,
                       maximum_tree_bytes=524288, maximum_file_bytes=262144):
        raise ValueError('Exact one-tree read-only recovery payload required')
    begun = time.monotonic()
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if boot != baseline['boot_id']:
        raise ValueError('Current boot changed before recovery inspection')
    listed=subprocess.run(['systemctl','--user','list-units','--all','--plain','--no-legend','--no-pager','jp-*'],
                          capture_output=True,text=True,timeout=3,check=True)
    if len(listed.stdout.encode())>32768 or len(listed.stderr.encode())>8192:
        raise ValueError('Finite current unit listing required')
    names=[line.split()[0] for line in listed.stdout.splitlines() if line.strip()]
    if len(names)>64 or len(set(names))!=len(names) or any(re.fullmatch(r'jp-[A-Za-z0-9@_.-]+\.service',name) is None for name in names):
        raise ValueError('Finite exact jp service names required')
    shown=subprocess.run(['systemctl','--user','show',*names,
        '--property=Id,MainPID,ActiveState,SubState,Result,ControlGroup,InvocationID,ExecMainCode,ExecMainStatus,RuntimeMaxUSec'],
        capture_output=True,text=True,timeout=3,check=True) if names else None
    if shown and (len(shown.stdout.encode())>65536 or len(shown.stderr.encode())>8192):
        raise ValueError('Finite current unit properties required')
    units=dict(list_stdout=listed.stdout,list_stderr=listed.stderr,names=names,
               show_stdout=shown.stdout if shown else '',show_stderr=shown.stderr if shown else '',
               commands_readonly=True)
    def identity_state(owner):
        if (type(owner) is not dict or set(owner) != {'pid','start_ticks','boot_id'}
                or type(owner['pid']) is not int or owner['pid'] <= 0
                or type(owner['start_ticks']) is not int or owner['start_ticks'] <= 0
                or type(owner['boot_id']) is not str
                or re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}',owner['boot_id']) is None):
            raise ValueError('Exact recorded native owner required')
        if owner['boot_id'] != boot:
            return dict(owner=owner,closed=True,current_boot=boot,reason='different_boot')
        try:
            raw = Path('/proc',str(owner['pid']),'stat').read_text()
            ticks = int(raw.rsplit(')',1)[1].split()[19])
        except (FileNotFoundError,ProcessLookupError):
            return dict(owner=owner,closed=True,current_boot=boot,reason='pid_absent')
        return dict(owner=owner,closed=ticks != owner['start_ticks'],current_boot=boot,
                    observed_start_ticks=ticks,reason='identity_changed' if ticks != owner['start_ticks'] else 'exact_owner_live')
    def strict(raw):
        def pairs(items):
            result={}
            for key,value in items:
                if key in result:raise ValueError('Duplicate recovery JSON field')
                result[key]=value
            return result
        return json.loads(raw,object_pairs_hook=pairs,
            parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
    absent = dict(status='CLOSED_RECOVERY_TREE_ABSENT',path=str(ROOT),fault_sha256=FAULT,
                  boot_id=boot,exists=False,current_jp_units=units,device_commands=False,native_writes=False)
    try: root_before=ROOT.lstat()
    except FileNotFoundError:return absent
    if ROOT.is_symlink() or not stat.S_ISDIR(root_before.st_mode) or ROOT.resolve(strict=True)!=ROOT:
        raise ValueError('Recovery root must be the exact real directory')
    rows=[];directories=[];total=0;values={};owners={};command_tokens=[]
    def collect_owners(value,relative,trail=''):
        if type(value) is dict:
            if set(value)=={'pid','start_ticks','boot_id'}:
                key=json.dumps(value,sort_keys=True,separators=(',',':'))
                if key not in owners:owners[key]=dict(identity_state(value),references=[])
                owners[key]['references'].append(relative+':'+trail)
            elif any(key in value for key in ('pid','start_ticks','boot_id')) and relative.endswith('OWNER.json'):
                raise ValueError('Unrecognized completed recovery owner schema')
            for key,item in value.items():
                if key in ('command','argv','args') and (item=='TEST_CORE_BURN' or
                        type(item) is list and 'TEST_CORE_BURN' in item):
                    command_tokens.append(relative+':'+trail+'.'+key)
                collect_owners(item,relative,trail+'.'+key)
        elif type(value) is list:
            if len(value)>4096:raise ValueError('Finite recovery JSON cardinality')
            for index,item in enumerate(value):collect_owners(item,relative,trail+'['+str(index)+']')
    def membership():
        files=[];dirs=[]
        for parent,children,names in os.walk(ROOT,followlinks=False):
            if time.monotonic()-begun>15:raise TimeoutError('Bounded read-only recovery inspection')
            for name in sorted(children):
                path=Path(parent)/name;info=path.lstat()
                if path.is_symlink() or not stat.S_ISDIR(info.st_mode):raise ValueError('Recovery directory link/type rejected')
                dirs.append(path.relative_to(ROOT).as_posix())
            for name in sorted(names):files.append((Path(parent)/name).relative_to(ROOT).as_posix())
            if len(files)>256 or len(dirs)>64:raise ValueError('Finite recovery tree cardinality')
        return sorted(files),sorted(dirs)
    files,directories=membership()
    for relative in files:
        path=ROOT/relative;before=path.lstat()
        if path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>262144:
            raise ValueError('Bounded real single-link recovery member required')
        raw=path.read_bytes();after=path.lstat();total+=len(raw)
        if total>524288 or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('Stable finite complete recovery tree required')
        row=dict(path=relative,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        if relative.endswith('.json'):
            value=strict(raw);collect_owners(value,relative)
            if relative in ('REQUEST.json','HOST_CLOSURE.json','RECOVERY.json','OWNER.json','CHILD_LAUNCH.json','RESTART_INTENT.json'):
                values[relative]=value
        if relative in ('HELPER.stderr','HELPER.stdout'):
            row.update(text_prefix=raw[:8192].decode('utf-8','replace'),text_prefix_complete=len(raw)<=8192)
        rows.append(row)
    if membership()!=(files,directories):raise ValueError('Recovery membership changed while inspecting')
    root_after=ROOT.lstat()
    if (root_before.st_dev,root_before.st_ino,root_before.st_mtime_ns)!=(root_after.st_dev,root_after.st_ino,root_after.st_mtime_ns):
        raise ValueError('Recovery root changed while inspecting')
    intents=[name for name in files if Path(name).name=='RESTART_INTENT.json']
    return dict(status='CLOSED_RECOVERY_TREE_READ',path=str(ROOT),fault_sha256=FAULT,
                boot_id=boot,exists=True,files=rows,directories=directories,total_bytes=total,
                selected_documents=values,owner_statuses=list(owners.values()),
                restart_intent_paths=intents,test_core_burn_command_references=command_tokens,
                completed_json_read=True,membership_stable=True,
                no_send_intent_observed=not intents and not command_tokens,
                current_jp_units=units,
                device_commands=False,native_writes=False)


if 'PAYLOAD' in globals():RESULT=inspect(PAYLOAD,BASELINE)
