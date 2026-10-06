"""Current build26 shared microphone failure inspection; README_FIRST_START_REPAIR.md."""
import hashlib,json,os,re,stat,time
from pathlib import Path
DATA=Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PACKAGE=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-26')
PIN='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
def inspect(payload,baseline):
    if payload!={'package_manifest_sha256':PIN}:raise ValueError('Exact read-only build26 payload')
    if hashlib.sha256((PACKAGE/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest()!=PIN:raise ValueError('Package drift')
    rows=[];total=0
    def retain(path):
        nonlocal total
        if not path.exists():return None
        st=path.lstat()
        if path.is_symlink() or not stat.S_ISREG(st.st_mode) or st.st_size>262144:raise ValueError('Bounded real diagnostic')
        raw=path.read_bytes();after=path.stat();total+=len(raw)
        if total>180000 or len(rows)>28 or (st.st_ino,st.st_size,st.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Stable finite diagnostic required')
        rows.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),text=raw.decode('utf-8','replace')))
        return json.loads(raw)
    pointer=retain(DATA/'CURRENT_LAUNCH.json')
    if pointer:
        ident=pointer['launch_id']
        if not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError('Launch UUID')
        launch=DATA/'launches'/ident
        for name in ('REQUEST.json','HOST_CLOSURE.json','CHILD_LAUNCH.json','worker/REGISTERED_OWNER.json','worker/RESULT.json','worker/EXIT.json'):retain(launch/name)
        session=retain(launch/'worker/SESSION.json')
        if session:
            root=DATA/'recordings/sessions'/session['session_id']
            retain(root/'metadata.json');retain(root/'work/source/SOURCE_CLOSE.json')
    return dict(status='CURRENT26_SOURCE_FAILURE_READ',boot_id=baseline['boot_id'],records=rows,capture_started=False,device_commands=False)
if 'PAYLOAD' in globals():RESULT=inspect(PAYLOAD,BASELINE)

