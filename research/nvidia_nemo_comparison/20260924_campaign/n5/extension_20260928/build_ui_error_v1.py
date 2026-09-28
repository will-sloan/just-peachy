"""Preserve and repair the reproduced queued-notice masking bug. README_UI_ERROR_V1.md."""
from pathlib import Path
import ast
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin,exact_process
from window_guard import window,snapshot


def main():
    pin();window();local=HERE.parent.parents[4]/'local'
    failed=local/'n5/prepi-20260928/a0-controls-v1'
    a=load(failed/'ADMISSION.json');r=load(failed/'controls/RESULT.json');life=load(failed/'controls-lifetime/LIFETIME.json')
    assert r['errors']==['ValueError: Actual GUI hides the failure']
    assert r['cases'][0]['rendered_error']=='Backend selection queued. Start is explicit.'
    assert r['cases'][0]['error']=='ValueError: Unsupported N2 runtime binding'
    owners=[a['owner'],r['owner'],{k:a['supervisor'][k] for k in ('pid','create_time')}]
    assert all(exact_process(o) is None for o in owners)
    assert life['job_empty_verified'] and life['observed_members_exited'] and not life['forced']
    parent=bind(local/'n5/prepi-20260928/derivatives/e0-runtime-v1/DERIVATIVE.json');d=load(parent['path'])
    target=local/'n5/research-extension-20260928/derivatives/ui-error-v1'
    if target.exists():raise FileExistsError(target)
    observed=snapshot(local,16*1024**2)
    prototype=target/'prototype';prototype.mkdir(parents=True)
    source=Path(d['prototype'])
    for name,row in d['files'].items():
        verify(dict(path=str(source/name),**row));p=prototype/name;p.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,p)
    ui=prototype/'app/ui.py';text=ui.read_text(encoding='utf-8')
    old="error = self._notice or self.snapshot.get(\"error\") or"
    new="error = self.snapshot.get(\"error\") or self._notice or"
    assert text.count(old)==1
    text=text.replace(old,new);ast.parse(text);ui.write_text(text,encoding='utf-8',newline='\n')
    # Match the original line endings so the derivative changes one statement only.
    if b'\r\n' in (source/'app/ui.py').read_bytes():ui.write_bytes(ui.read_bytes().replace(b'\n',b'\r\n'))
    shutil.copyfile(HERE/'README_UI_ERROR_V1.md',prototype/'app/README_UI_ERROR_V1.md')
    files={}
    for p in sorted(prototype.rglob('*')):
        if p.is_file():b=bind(p);files[p.relative_to(prototype).as_posix()]={k:b[k] for k in ('sha256','bytes')}
    changed=[name for name,row in d['files'].items() if files[name]!=row]
    assert changed==['app/ui.py']
    freeze(target/'CENSUS.json',observed)
    freeze(target/'DERIVATIVE.json',dict(schema='extended-ui-error-priority-v1',status='PREPARED_NOT_RELEASE_ACCEPTED',
        parent_source_receipt=parent,e0_shutdown_parent=d['parent_source_receipt'],prototype=str(prototype),files=files,
        changed_code=changed,added_docs=['app/README_UI_ERROR_V1.md'],builder=bind(__file__),
        failure=bind(failed/'controls/RESULT.json'),closed_owners=owners,census=bind(target/'CENSUS.json')))
    print(dict(status='PREPARED_NOT_TESTED',path=str(target),files=len(files),changed=changed))


if __name__=='__main__':main()
