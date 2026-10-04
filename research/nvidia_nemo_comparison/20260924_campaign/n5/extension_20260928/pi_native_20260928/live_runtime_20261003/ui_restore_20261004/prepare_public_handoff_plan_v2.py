"""Prepare an unapproved build17 public handoff whitelist; see README_PUBLIC_HANDOFF_PLAN_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import time
import uuid

ROOT=Path('G:/Just_Peachy_N1/20260924_campaign/worktree')
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation')
BASE=PRIVATE/'final-handoff-v29-build16-20261004/REVIEWED_PLAN.json'
BASE_SHA='7aa2e1a319b16c646f376f8d1f21c3b030132a586954f1eadd910ad5d439c6f3'
MIB=1024**2
COMPLETION='research/nvidia_nemo_comparison/20260924_campaign/n5/completion_20261001/'
OLD_START=COMPLETION+'START_HERE.md'
CURRENT_START=COMPLETION+'START_HERE_CURRENT.md'
GIT_TRACKED={'DELIVERY_START_HERE.md',COMPLETION+'BACKEND_COMBINATIONS.md',
    COMPLETION+'CURRENT_RUNTIME_PROGRESS.md',COMPLETION+'DESKTOP_GUIDE.md',
    COMPLETION+'FINAL_OPERATOR_GUIDE.md',COMPLETION+'INSTALL_HEALTH_AND_RECOVERY.md',
    COMPLETION+'MODE_GUIDE.md',
    'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/README_FINAL_PUBLICATION.md'}


def encoded(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True,help='Never-used private plan label; no ZIP is built')
    args=parser.parse_args()
    if not args.label or len(args.label)>64 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.label):
        raise ValueError('Canonical fresh plan label required')
    out=PRIVATE/(args.label+'-'+uuid.uuid4().hex);out.mkdir()
    me=psutil.Process();written=0;started=time.monotonic()
    def put(name,raw):
        nonlocal written
        if time.monotonic()-started>600 or written+len(raw)>16*MIB:raise OSError('Finite host plan allocation exceeded')
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:
            if stream.write(raw)!=len(raw):raise OSError('Short plan write')
            stream.flush();os.fsync(stream.fileno())
        if path.read_bytes()!=raw:raise OSError('Plan readback differs')
        written+=len(raw)
    put('REGISTERED_OWNER.json',encoded(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    if shutil.disk_usage('C:/').free<50*1024**3 or shutil.disk_usage('G:/').free<75*1024**3+128*MIB:
        raise OSError('Existing handoff free-space floors')
    raw=BASE.read_bytes()
    if len(raw)>MIB or digest(raw)!=BASE_SHA:raise ValueError('Exact reviewed build16 whitelist required')
    base=json.loads(raw)
    if base.get('schema')!='just-peachy.reviewed-public-handoff.v1' or base.get('reviewed_publication') is not True:
        raise ValueError('Closed prior reviewed plan required')
    sources={row['member']:Path(row['source']) for row in base['files']}
    repair=Path(__file__).resolve().parent
    if OLD_START not in sources:raise ValueError('Prior locked Start Here whitelist entry required')
    # The only reviewed member alias: current guide replaces the locked old
    # document in the archive, without reading or changing that old document.
    sources[OLD_START]=ROOT/CURRENT_START
    sources[CURRENT_START]=ROOT/CURRENT_START
    additions=[CURRENT_START]
    for path in sorted(repair.iterdir()):
        if path.suffix.lower() not in {'.py','.md'} or not path.is_file():continue
        name=path.relative_to(ROOT).as_posix()
        if name not in sources:additions.append(name)
        sources[name]=path
    rows=[];total=0;aliases=set();changes=[]
    old={row['member']:row for row in base['files']}
    for name,path in sorted(sources.items()):
        if name.casefold() in aliases:raise ValueError('Case-aliased public member')
        aliases.add(name.casefold())
        resolved=path.resolve(strict=True);relative=resolved.relative_to(ROOT)
        before=path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink!=1
            or os.path.normcase(str(path.absolute()))!=os.path.normcase(str(resolved))
            or (relative.as_posix()!=name and (name,relative.as_posix())!=(OLD_START,CURRENT_START)) or before.st_size>2*MIB):
            raise ValueError('Exact regular repository-relative public source required: '+name)
        raw=path.read_bytes();after=path.stat();raw.decode('utf-8')
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('Source changed during public plan snapshot: '+name)
        total+=len(raw)
        if total>20*MIB or len(rows)>=4096:raise ValueError('Existing public handoff source bounds')
        row=dict(member=name,source=str(path),bytes=len(raw),sha256=digest(raw));rows.append(row)
        if name in old and (row['bytes'],row['sha256'])!=(old[name]['bytes'],old[name]['sha256']):changes.append(name)
    plan=dict(schema=base['schema'],reviewed_publication=False,
        scope='Build17 classic frontend/source-readiness repair; prior build16 measured scopes retained; current actual repair outcomes require final reviewer approval.',
        files=rows)
    plan_raw=encoded(plan);put('PROPOSED_PLAN_REQUIRES_FINAL_REVIEW.json',plan_raw)
    # Git publication is deliberately narrower than the historical handoff:
    # only the 8 repaired tracked docs, new current Start Here and R sources.
    git_names=sorted(GIT_TRACKED|{CURRENT_START}|{name for name in sources if name.startswith(repair.relative_to(ROOT).as_posix()+'/')})
    if any(name not in sources for name in git_names):raise ValueError('Git publication path absent from reviewed public sources')
    put('GIT_WHITELIST.txt',('\n'.join(git_names)+'\n').encode())
    summary=dict(utc=datetime.now(timezone.utc).isoformat(),prior_plan_sha256=BASE_SHA,
        prior_members=len(base['files']),members=len(rows),source_bytes=total,
        added_members=additions,changed_existing_members=changes,reviewed_publication=False,
        proposed_plan_sha256=digest(plan_raw),native_action=False,zip_built=False,
        private_media_models_galleries_configs_owners_included=False,
        final_refresh_required_after_documentation_ready=True,
        exact_locked_member_alias=dict(member=OLD_START,source=CURRENT_START),
        locked_original_read_or_modified=False,git_publication_members=len(git_names))
    put('PLAN_REVIEW.json',encoded(summary))
    print(json.dumps(dict(output=str(out),members=len(rows),source_bytes=total,
        added_members=len(additions),changed_existing_members=len(changes),zip_built=False)))


if __name__=='__main__':main()
