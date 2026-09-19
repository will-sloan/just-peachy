"""Versioned atomic-status I/O repair; README_S6B_LAUNCH.md describes scope and commands."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
import uuid

SIM=Path(os.environ.get('JP_S6B_SIM',Path(__file__).resolve().parents[1])).resolve()
RUN='20260909T230840Z'
REPORT=SIM/'reports/S6B'/RUN
OVERLAY=SIM/'staging/s6b'/RUN/'atomic_io_v1'


def atomic_save(path,value):
    """Same JSON bytes/atomic-replace contract; unique writer temp and bounded retry."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.'+uuid.uuid4().hex+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    for attempt in range(20):
        try:
            os.replace(tmp,path)
            return
        except PermissionError:
            if attempt==19:raise
            time.sleep(min(.025*2**attempt,.25))


def configure(epoch):
    spec=json.loads((REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json')).read_text(encoding='utf-8'))
    sys.path.insert(0,str(Path(spec['root'])/'scripts'))
    import s6b_common
    s6b_common.save=atomic_save
    import s6b_execution
    s6b_execution.save=atomic_save
    return s6b_execution


def test():
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch
    root=REPORT/'validation/atomic_io_v1';root.mkdir(parents=True,exist_ok=True)
    p=root/'concurrent.json'
    def writer(n):
        for i in range(40):atomic_save(p,dict(writer=n,index=i,unicode='é',values=list(range(50))))
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(writer,range(4)))
    assert json.loads(p.read_text(encoding='utf-8'))['index']==39
    original=os.replace;attempts=[]
    def blocked_twice(a,b):
        attempts.append(1)
        if len(attempts)<3:raise PermissionError('injected transient file sharing')
        return original(a,b)
    with patch('os.replace',blocked_twice):atomic_save(root/'retry.json',dict(complete=True))
    assert len(attempts)==3
    before=p.read_bytes()
    try:atomic_save(p,dict(bad=float('nan')))
    except ValueError:pass
    else:raise AssertionError('Nonfinite JSON accepted')
    assert p.read_bytes()==before
    result=dict(status='PASS',fixtures=['four concurrent writers/160 atomic replacements','unicode JSON preserved',
        'two actual PermissionErrors retried through replace','nonfinite rejection preserves previous target'],
        changes_to_neural_models_profiles_inputs_scheduler=False)
    atomic_save(root/'TEST_RECEIPT.json',result)
    return result


def prepare(epoch):
    if OVERLAY.exists():raise ValueError('Immutable overlay already exists; run its existing code')
    result=test()
    OVERLAY.mkdir(parents=True)
    target=OVERLAY/'s6b_launch.py';shutil.copy2(__file__,target)
    spec=REPORT/(epoch.upper()+'_EXECUTION_MANIFEST.json')
    value=dict(schema='jp_s6b_io_overlay_v1',epoch=epoch,path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        execution_manifest=dict(path=str(spec),sha256=hashlib.sha256(spec.read_bytes()).hexdigest()),
        scope='Only coordinator/evidence-cache atomic JSON persistence: unique temporary file per write, bounded sharing-denial retries. Frozen application, actual model calls, event contents, profiles and original execution snapshot remain unchanged.',
        cache_compatibility='Exact same neural job identities remain valid; this postprocessing/status I/O change cannot alter predictor decisions. Existing completed inference is reused after normal artifact/source hash checks.',
        preceding_faults=str(REPORT/'EXECUTION_FAULT_LEDGER.md'),tests=result)
    atomic_save(REPORT/'ATOMIC_IO_OVERLAY_V1.json',value)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','test','run'))
    p.add_argument('--epoch',default='epoch2');p.add_argument('--panel',choices=('pilot','challenge','all'),default='challenge')
    p.add_argument('--recipes',nargs='*');p.add_argument('--workers',type=int,default=4);p.add_argument('--limit',type=int)
    a=p.parse_args()
    if a.mode=='test':result=test()
    elif a.mode=='prepare':result=prepare(a.epoch)
    else:
        receipt=json.loads((REPORT/'ATOMIC_IO_OVERLAY_V1.json').read_text(encoding='utf-8'))
        if Path(__file__).resolve()!=Path(receipt['path']) or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=receipt['sha256']:
            raise ValueError('Run the bound immutable atomic-I/O overlay')
        sb=receipt['execution_manifest']
        if hashlib.sha256(Path(sb['path']).read_bytes()).hexdigest()!=sb['sha256']:raise ValueError('Epoch manifest changed')
        if not 1<=a.workers<=4:raise ValueError('One to four workers')
        os.environ['JP_S6B_SIM']=str(SIM);os.environ['JP_S6B_ATOMIC_OVERLAY']=a.epoch
        result=configure(a.epoch).run(a.epoch,a.panel,a.recipes,a.workers,a.limit)
    print(json.dumps(result,indent=2))


# Spawned Windows workers inherit this explicitly bound persistence adapter.
if os.environ.get('JP_S6B_ATOMIC_OVERLAY'):
    configure(os.environ['JP_S6B_ATOMIC_OVERLAY'])
if __name__=='__main__':main()
