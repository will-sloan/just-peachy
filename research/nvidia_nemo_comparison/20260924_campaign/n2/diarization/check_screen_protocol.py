"""Exercise screen admission, locking and timeout protocol without neural inference."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import queue
import subprocess
import sys
import time

import run_fixed_screen as screen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if output.exists() or not output.is_relative_to(screen.LOCAL.resolve()):
        raise ValueError('Use a new private local/n2 output directory')
    output.mkdir(parents=True)
    runner=Path(screen.__file__).resolve()
    prepared=output/'prepared-screen'
    base=[sys.executable,str(runner),'--output',str(prepared),'--profiles','very_low_latency','--prepare-only']
    observations=[]
    for name,command,expected in (
        ('prepare',base,0),('resume',base,0),
        ('changed-contract',base+['--timeout-sec','1801'],1)):
        started=time.monotonic()
        result=subprocess.run(command,capture_output=True,text=True,timeout=90,
            creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if screen.os.name=='nt' else 0)
        log=output/(name+'.log')
        log.write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        assert (result.returncode==0)==(expected==0), (name,result.returncode)
        observations.append({'name':name,'returncode':result.returncode,'wall_sec':time.monotonic()-started,
                             'log':screen.bind(log)})
    admission=screen.load(prepared/'ADMISSION.json')
    assert len(admission['contract']['jobs_by_id'])==96
    assert not (prepared/'workers').exists()
    assert screen.load(prepared/'PROGRESS.json')['numerical_workers']==0
    lock_dir=output/'lock-fixture'
    lock_dir.mkdir()
    code="""import pathlib,sys
sys.path.insert(0,sys.argv[1])
from run_fixed_screen import WriterLock
try:
    lock=WriterLock(pathlib.Path(sys.argv[2]))
except RuntimeError as exc:
    print(str(exc))
    raise SystemExit(7)
lock.close()
"""
    lock=screen.WriterLock(lock_dir)
    try:
        rejected=subprocess.run([sys.executable,'-c',code,str(runner.parent),str(lock_dir)],
                                capture_output=True,text=True,timeout=15)
        assert rejected.returncode==7, rejected.stdout+rejected.stderr
    finally:
        lock.close()
    second=screen.WriterLock(lock_dir)
    second.close()
    fixture=output/'hash-fixture.txt'
    fixture.write_text('synthetic protocol fixture only',encoding='utf-8')
    binding=screen.bind(fixture)
    fixture.write_text('changed synthetic protocol fixture',encoding='utf-8')
    try:
        screen.verify(binding)
    except ValueError:
        pass
    else:
        raise AssertionError('Changed evidence was accepted')
    dummy=screen.Worker.__new__(screen.Worker)
    dummy.messages=queue.Queue(maxsize=1)
    dummy.proc=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'])
    started=time.monotonic()
    try:
        try:
            dummy.receive(.05)
        except TimeoutError:
            pass
        else:
            raise AssertionError('Owned worker timeout did not fire')
    finally:
        dummy.proc.terminate()
        dummy.proc.wait(timeout=5)
    elapsed=time.monotonic()-started
    assert elapsed<5
    receipt={'status':'PASSED_PROTOCOL_ONLY','neural_inference':False,'cuda_execution':False,
        'runner':screen.bind(runner),'checker':screen.bind(__file__),
        'admission':screen.bind(prepared/'ADMISSION.json'),'commands':observations,
        'same_contract_resume':True,'changed_contract_rejected':True,'competing_writer_rejected':True,
        'released_lock_reacquired':True,'changed_evidence_rejected':True,
        'bounded_receive_timeout_sec':elapsed,'owned_fixture_child_returncode':dummy.proc.returncode,
        'numerical_workers_started':0}
    screen.atomic(output/'RECEIPT.json',receipt)
    screen.atomic(runner.parent/'SCREEN_PROTOCOL_RECEIPT.json',
                  {'status':receipt['status'],'local_receipt':screen.bind(output/'RECEIPT.json'),
                   'runner':receipt['runner'],'neural_inference':False})
    print(json.dumps({'status':receipt['status'],'output':str(output)}))


if __name__=='__main__':
    main()
