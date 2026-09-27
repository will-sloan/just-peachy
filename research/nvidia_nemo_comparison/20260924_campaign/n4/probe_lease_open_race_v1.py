"""Bounded model-free rename/open diagnostic. README_LEASE_OPEN_RACE_V1.md."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import threading
import time

from common import bind, freeze, load, verify
from metric_process import exact_process, identity, pin
from reservation_budget_v1 import calculate, require
import guarded_execution_v1 as resource
from paced_slot import competitors, process_census
import paced_child_admission_v6 as gate

HERE = Path(__file__).resolve().parent
LOCAL = HERE.parents[4]/'local'


def exercise(folder, *, reader=gate.bounded_json, iterations=10000, seconds=30):
    require(0 < iterations <= 10000 and 0 < seconds <= 30, 'Diagnostic bound differs')
    folder.mkdir(exist_ok=False)
    target = folder/'LEASE.json'; pending = folder/'LEASE.pending'
    target.write_text('{"sequence":0}', encoding='utf-8')
    stop = threading.Event(); started = time.monotonic(); errors = []; counts = {'reads': 0, 'writes': 0}
    def writer():
        try:
            for index in range(1, iterations+1):
                if stop.is_set() or time.monotonic()-started >= seconds: break
                with pending.open('x', encoding='utf-8') as stream: json.dump({'sequence': index}, stream)
                gate.replace_lease_file(pending, target)
                counts['writes'] = index
        except BaseException as exc:
            errors.append(dict(role='writer', error=repr(exc), winerror=getattr(exc,'winerror',None)))
        finally: stop.set()
    thread = threading.Thread(target=writer, name='lease-rename-fixture')
    thread.start(); last = -1
    try:
        while not stop.is_set() and time.monotonic()-started < seconds:
            try:
                value = reader(target, 4096)
                require(set(value) == {'sequence'} and type(value['sequence']) is int and value['sequence'] >= last,
                    'Torn, invalid or decreasing fixture')
                last = value['sequence']; counts['reads'] += 1
            except FileNotFoundError as exc:
                if len(errors) < 32:
                    errors.append(dict(role='reader', error=repr(exc), winerror=getattr(exc,'winerror',None),
                        target_exists_after_error=target.exists()))
            except BaseException as exc:
                errors.append(dict(role='reader', error=repr(exc), winerror=getattr(exc,'winerror',None)))
                break
    finally:
        stop.set(); thread.join(timeout=2)
    require(not thread.is_alive(), 'Diagnostic writer did not close')
    return dict(**counts, errors=errors, writer_closed=True, elapsed_seconds=time.monotonic()-started,
        final=gate.bounded_json(target,4096), maximum_seconds=seconds, maximum_writes=iterations,
        no_models_or_application=True)


def main():
    process = pin(); sys.path.insert(0,str(HERE.parent/'supervision')); import supervisor
    supervisor.require_no_active_worker(load(LOCAL/'supervision/worker.json'))
    output = LOCAL/'n4/lease-open-race-v1'; require(not output.exists(),'Fresh diagnostic directory required')
    from application_family_v9 import code_bindings
    code = code_bindings(); census = resource.snapshot(LOCAL,load(LOCAL/'n4/integrated-main-v3/RESULT.json')['plan'])
    require(not census['active_allocations'] and census['supervisor']['state']=='CLOSED','Prior allocation remains active')
    calculation = calculate(census['inventory'],census['closed_components'],[],16*1024**2,
        load(census['policy']['path']),census['free_bytes'],datetime.now(timezone.utc),peak_bytes=1024**2)
    pc = process_census(LOCAL.parent); require(not competitors(pc,[identity(process)]),'Competitor remains')
    freeze(output/'PRECHECK.json',dict(census=census,calculation=calculation,process_census=pc,owner=identity(process)))
    results=[]
    for index in range(3):
        results.append(exercise(output/f'round-{index+1}'))
        if results[-1]['errors']: break
    for item in code: verify(item)
    freeze(output/'RESULT.json',dict(status='DIAGNOSTIC_COMPLETE',utc=datetime.now(timezone.utc).isoformat(),
        source=bind(__file__),readme=bind(HERE/'README_LEASE_OPEN_RACE_V1.md'),gate=bind(gate.__file__),
        prior_code_count=len(code),precheck=bind(output/'PRECHECK.json'),rounds=results,
        N4_accepted=False,actual_application_failure_callsite_known=False))
    print(json.dumps(results))


if __name__ == '__main__': main()
