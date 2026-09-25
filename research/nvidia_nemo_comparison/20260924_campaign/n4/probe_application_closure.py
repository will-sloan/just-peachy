"""Bounded closure qualification without source/model launch. README_APPLICATION_CLOSURE.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import unittest
from common import bind, freeze, load, verify
from metric_process import pin, identity
from asr_full_bank import payload_inventory
from probe_integrated_scoring import guard


def run(args):
    process=pin(); here=Path(__file__).resolve().parent; started=time.monotonic()
    public=load(here/'PACED_ADAPTERS_CHECK_V3.json'); source_binding=public['source_receipt']; verify(source_binding)
    source=load(source_binding['path']); root=Path(source['prototype']); local=Path(source_binding['path']).parents[2]
    for rel,b in source['files'].items():verify(dict(path=str((root/rel).resolve()),**b))
    acceptance=load(here.parent/'n3/N3_ACCEPTANCE.json')
    if acceptance['status']!='ACCEPTED_N3_OFFLINE_COMPONENT_SCOPE':raise ValueError('Accepted historical N3 evidence required')
    metrics_binding=dict(path=str((here.parent/'n3/N3_FINAL_METRICS.json').resolve()),**acceptance['analysis_files']['N3_FINAL_METRICS.json'])
    verify(metrics_binding);metrics=load(metrics_binding['path']);cases=[];parents=[]
    for b in metrics['receipts']:
        if Path(b['path']).name!='GUI_PANEL_REPORT.json' or 'private_cells' in Path(b['path']).parts:continue
        verify(b);report=load(b['path']);parents.append(b)
        for c in report['cells']:
            if c['status']!='COMPLETE' or c['archive_integrity_passed'] is not True:raise ValueError('Historical GUI cell not accepted')
            archive=next(v for v in c['evidence'] if Path(v['path']).name=='ARCHIVE_INTEGRITY.json');verify(archive)
            session=Path(c['session'])
            # These terminal files are freshly bound through their accepted
            # report session paths; no earlier terminal-file hash is invented.
            cases.append(dict(cell_id=c['cell_id'],audio=c['audio'],session=str(session),archive=archive,
                finalization=bind(session/'session_finalization_v3.json'),consumer=bind(session/'s6d_consumer_closure.json')))
    if len(parents)!=3 or len(cases)!=9 or len({c['cell_id'] for c in cases})!=9:raise ValueError('Exact accepted historical GUI population required')
    policy=load(local/'supervision/campaign.json')
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):raise ValueError('Fresh private N4 output required')
    guard(args.output,policy,started);inventory=payload_inventory(local);size=inventory['total_logical_bytes']
    if size+6*1024**3+128*1024**2>min(50,policy['resource_policy']['new_payload_allowance_gib'])*1024**3:raise ValueError('Shared allowance unavailable')
    code=[bind(here/n) for n in ('application_closure.py','test_application_closure.py','probe_application_closure.py',
        'README_APPLICATION_CLOSURE.md','common.py','metric_process.py','controller_projection.py','asr_full_bank.py','probe_integrated_scoring.py')]
    code += [bind(here.parent/n) for n in ('n3/gui_a1.py','n2/io_utils.py')]
    args.output.mkdir(parents=True,exist_ok=False)
    freeze(args.output/'ADMISSION.json',dict(owner=identity(process),source=source_binding,code=code,
        accepted_metrics=metrics_binding,historical_reports=parents,cases=cases,private_inventory=inventory,expected_tests=7,
        scope='Historical persisted receipt review plus owner-state fixtures and actual model-free partial startup cancellation'))
    sys.path[:0]=[str(root),str(root/'vendor'),str(here.parents[3])]
    import test_application_closure as tests
    from controller_projection import forbid_inference
    tests.CONTEXT.update(output=args.output,cases=cases)
    with (args.output/'unittest.txt').open('x',encoding='utf-8') as stream, forbid_inference():
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    for b in code:verify(b)
    guard(args.output,policy,started)
    checks=dict(historical=tests.CONTEXT.get('historical_checks',[]),partial_startup=tests.CONTEXT.get('partial_startup'))
    freeze(args.output/'CHECKS.json',checks)
    passed=result.wasSuccessful() and result.testsRun==7 and not result.skipped
    freeze(args.output/'RESULT.json',dict(status='PASS_APPLICATION_CLOSURE_HELPER' if passed else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(),admission=bind(args.output/'ADMISSION.json'),tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),log=bind(args.output/'unittest.txt'),
        checks=bind(args.output/'CHECKS.json'),historical_sessions=len(checks['historical']),elapsed_sec=time.monotonic()-started,
        models_loaded=0,new_source_execution=False,new_GUI_execution=False,complete_application_run=False,integrated_N4_cells=0))
    print(json.dumps(dict(result=bind(args.output/'RESULT.json'),passed=passed)))
    if not passed:raise RuntimeError('Closure qualification failed; preserve attempt')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args())
