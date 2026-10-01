"""CPU14 physical file guard checks; README_FIELD_LIVE_FILES_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from array import array
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--admission',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    a=json.loads(args.admission.read_bytes())
    if datetime.now(timezone.utc)>=datetime.fromisoformat(a['expires_utc']) or a['native_dispatch'] is not False:
        raise ValueError('Fresh host-only admission required')
    from field_live_files_v1 import PhysicalFiles,PathBudgetError
    from field_live_layout_v3 import specification
    root=args.output.absolute();root.mkdir(exist_ok=False)
    for name in specification()['directories']:
        if name and '<' not in name:(root/name).mkdir(parents=True,exist_ok=True)
    (root/'code/fixture.py').write_bytes(b'# fixture\n')
    stops=[];results=[]
    guard=PhysicalFiles(root,{'fixture.py':10},lambda:stops.append(len(results))).install()
    def rejected(name,call):
        count=len(stops)
        try:call()
        except PathBudgetError:
            assert len(stops)>count;results.append(dict(name=name,rejected=True,stop_before_return=True))
        else:raise AssertionError('Accepted '+name)
    token='a'*32;tmp=root/('data/.runtime.'+token+'.tmp');lock=root/'data/runtime.lock'
    with tmp.open('x',encoding='utf-8') as stream:json.dump(dict(pid=os.getpid(),token=token,purpose='application'),stream)
    os.link(tmp,lock);assert lock.read_bytes()==tmp.read_bytes();tmp.unlink();lock.unlink()
    results.append(dict(name='runtime_exclusive_link_and_owned_cleanup',passed=True))
    pending=root/'data/.settings.json.pending';primary=root/'data/settings.json'
    with pending.open('xb') as stream:stream.write(b' '*32768)
    os.replace(pending,primary);assert primary.stat().st_size==32768
    with primary.open('ab') as stream:rejected('file_byte_overflow',lambda:stream.write(b'x'))
    assert primary.stat().st_size==32768
    results.append(dict(name='pending_publication_and_exact_retained_primary',passed=True))
    append=root/'failure/entry.json';fd=os.open(append,os.O_WRONLY|os.O_CREAT|os.O_APPEND)
    try:
        assert os.write(fd,b'x'*8190)==8190
        os.lseek(fd,0,os.SEEK_SET)
        rejected('descriptor_append_uses_actual_end',lambda:os.write(fd,b'xxxx'))
    finally:os.close(fd)
    assert append.stat().st_size==8190
    viewpath=root/'failure/native.json'
    with viewpath.open('xb') as stream:
        stream.write(b'x'*8190)
        rejected('memoryview_counts_bytes',lambda:stream.write(memoryview(array('I',[1,2]))))
    assert viewpath.stat().st_size==8190
    rejected('unknown_file',lambda:(root/'data/unmapped.txt').open('wb'))
    rejected('unknown_directory',lambda:(root/'unmapped').mkdir())
    rejected('code_overwrite',lambda:(root/'code/fixture.py').open('wb'))
    assert (root/'code/fixture.py').read_bytes()==b'# fixture\n'
    conv=root/('data/conversations/'+'b'*32);conv.mkdir()
    rejected('second_conversation',lambda:(root/('data/conversations/'+'c'*32)).mkdir())
    session=root/'data/sessions/edge_open_20260930T000000Z_12345678';session.mkdir()
    rejected('second_native_session',lambda:(root/'data/sessions/edge_open_20260930T000000Z_87654321').mkdir())
    rejected('delete_retained_failure',lambda:append.unlink())
    rejected('audit_catches_cached_open',lambda:guard.original['open'](root/'receipts/GUI_STOP.json','wb'))
    assert not (root/'receipts/GUI_STOP.json').exists()
    census=guard.census();assert census['open_writable_descriptors']==0
    report=dict(status='PASS_HOST_PHYSICAL_FILE_INTERCEPTION_ONLY',cases=results,census=census,
                native_execution=False,source_capture=False,installed_controller=False,
                completed_utc=datetime.now(timezone.utc).isoformat())
    assert datetime.now(timezone.utc)<datetime.fromisoformat(a['expires_utc'])
    with (root/'receipts/RESULT.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    assert json.loads((root/'receipts/RESULT.json').read_bytes())==report
    print(json.dumps(dict(status=report['status'],cases=len(results),rejects=sum(bool(r.get('rejected')) for r in results),file_bytes=guard.census()['file_bytes'])))


if __name__=='__main__':main()
