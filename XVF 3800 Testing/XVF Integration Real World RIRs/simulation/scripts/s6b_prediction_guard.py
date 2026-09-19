"""Validate completed replay-output bytes before reuse. README_S6B_PREDICTION_GUARD.md."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from s6b_common import *


def verify(index_paths,existing_folder=None):
    outputs={};indexes=[]
    for path in index_paths:
        path=Path(path);path=path if path.is_absolute() else REPORT/path
        index=read(path)
        if index['status']!='COMPLETE' or index['completed']!=index['requested']:raise ValueError('Incomplete prediction index')
        indexes.append(bind(path))
        for row in index['rows']:
            b=row['result'];key=str(Path(b['path']).resolve())
            if key in outputs and outputs[key]['sha256']!=b['sha256']:raise ValueError('Conflicting completed output binding')
            if key not in outputs:outputs[key]=bind(key,b['sha256'])
    if existing_folder:
        actual={str(p.resolve()) for p in Path(existing_folder).rglob('*.json')}
        orphans=actual-set(outputs)
        if orphans:raise ValueError('Existing replay files have no completed-index binding; diagnose before reuse: '+str(sorted(orphans)[:8]))
    return dict(status='PASS',indexes=indexes,unique_output_files=len(outputs),outputs=list(outputs.values()),
        guarantee='Current prediction bytes match prior completed index bindings. Native source/config/artifact identity validation remains separately enforced by frozen replay.',
        limitations='Incomplete unindexed replay files require a separate diagnosed admission, not silent reuse. This is not neural inference.')


def test():
    root=REPORT/'validation/prediction_guard_v1';root.mkdir(parents=True,exist_ok=True)
    pred=root/'prediction.json';save(pred,dict(prediction_key='unchanged-key',speaker='A'))
    b=bind(pred);idx=root/'index.json';save(idx,dict(status='COMPLETE',requested=1,completed=1,rows=[dict(result=b)]))
    assert verify([idx])['unique_output_files']==1
    old=pred.stat();data=pred.read_bytes();pred.write_bytes(data.replace(b'"A"',b'"B"'));os.utime(pred,ns=(old.st_atime_ns,old.st_mtime_ns))
    try:verify([idx])
    except RuntimeError:pass
    else:raise AssertionError('Same-size/mtime edited prediction accepted')
    pred.write_bytes(data);os.utime(pred,ns=(old.st_atime_ns,old.st_mtime_ns));assert verify([idx])['unique_output_files']==1
    result=dict(status='PASS',fixtures=['exact completed prediction reuse','same identity/key and same-size/mtime byte edit rejected','restored exact bytes accepted'])
    save(root/'TEST_RECEIPT.json',result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--indexes',nargs='+');p.add_argument('--existing-folder');p.add_argument('--receipt');p.add_argument('--test',action='store_true');a=p.parse_args()
    if a.test:result=test()
    else:
        if not a.indexes or not a.receipt:raise ValueError('Provide completed indexes and a new receipt filename')
        target=Path(a.receipt);target=target if target.is_absolute() else REPORT/target
        if target.exists():raise ValueError('Preserve prior guard receipt; use a new filename')
        result=verify(a.indexes,a.existing_folder);result['code']=bind(__file__);save(target,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('outputs','indexes')},indent=2))
