"""Finish ordered N1 checks after the active baseline; no LLM polling. See README.md."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
EXTERNAL=Path('G:/Just_Peachy_N1/20260924_campaign')
LOCAL=EXTERNAL/'local';STATE=LOCAL/'supervision'
SOURCE=LOCAL/'releases/n1-common-v1/prototype'
spec=importlib.util.spec_from_file_location('n1_supervisor',ROOT/'supervision/supervisor.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)


def report(status,**extra):
    s.atomic(LOCAL/'FINISHER_STATUS.json',dict(status=status,utc=s.now(),pid=os.getpid(),**extra))


def wait_index(path,total,deadline):
    while time.monotonic()<deadline:
        index=s.read(path,{})
        worker=s.read(STATE/'worker.json',{})
        if index.get('status')=='COMPLETE' and len(index.get('completed',{}))==total and not index.get('failed'):
            try:s.require_no_active_worker(worker)
            except RuntimeError:time.sleep(2);continue
            return
        if worker.get('status','').startswith('FAILED') or index.get('status')=='FAILED':
            raise RuntimeError('Numerical worker failed; preserve checkpoints for explicit review')
        time.sleep(5)
    raise TimeoutError('N1 numerical completion exceeded the bounded wait; worker retained for review')


def run(arguments,log_name,timeout=600):
    flags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' else 0
    with (LOCAL/log_name).open('ab') as log:
        result=subprocess.run([sys.executable,'-B',*map(str,arguments)],cwd=ROOT.parents[2],
            stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=flags,timeout=timeout)
    if result.returncode:raise RuntimeError(log_name+' exited '+str(result.returncode))


def main():
    import psutil
    process=psutil.Process();process.cpu_affinity(process.cpu_affinity()[-2:])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    with s.lock(LOCAL/'finisher-owner.lock'):
        report('WAITING_FOR_MAIN_SCREEN')
        wait_index(LOCAL/'baseline_screen_v1/RESULT_INDEX.json',96,time.monotonic()+7200)
        report('MAIN_SCREEN_COMPLETE_STARTING_SUPPLEMENTAL')
        regression=LOCAL/'baseline_regressions_v1/RESULT_INDEX.json'
        if s.read(regression,{}).get('status')!='COMPLETE':
            s.start(STATE,ROOT/'supervision/regression_worker_spec.json')
        report('RENDERING_MAIN_GUI_WITH_SUPPLEMENTAL_RUNNING')
        gui=EXTERNAL/'evidence/frontend/baseline_full_gui_v1'
        if s.read(gui/'GUI_REPLAY_REPORT.json',{}).get('status')!='COMPLETE':
            run([ROOT/'frontend/replay_baseline_gui.py','--source',SOURCE,
                '--index',LOCAL/'baseline_screen_v1/RESULT_INDEX.json','--output',gui],
                'final-gui-replay.log',660)
        report('AUDITING_MAIN_SCREEN')
        run([ROOT/'data/summarize_baseline.py','--run',LOCAL/'baseline_screen_v1',
            '--source',SOURCE,'--include-lexical'],'baseline-final-analysis.log')
        report('WAITING_FOR_SUPPLEMENTAL')
        wait_index(regression,8,time.monotonic()+1200)
        report('AUDITING_SUPPLEMENTAL')
        run([ROOT/'data/summarize_baseline.py','--run',LOCAL/'baseline_regressions_v1',
            '--source',SOURCE,'--prefix','REGRESSION_ANALYSIS','--include-lexical'],'regression-final-analysis.log')
        report('CHECKS_READY_FOR_FINAL_REVIEW',main_cells=96,regression_cells=8,gui_cells=96)


if __name__=='__main__':
    try:main()
    except BlockingIOError:
        raise SystemExit('Another N1 finisher owns the continuation; no state changed')
    except BaseException as exc:
        report('FAILED_REVIEW_REQUIRED',error=repr(exc))
        raise
