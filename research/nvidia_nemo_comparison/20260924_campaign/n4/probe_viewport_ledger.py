"""Model-free saved-viewport ledger qualification. README_VIEWPORT_LEDGER.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import unittest
from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_integrated_scoring import guard, private_bytes


def run(args):
    process = pin(); here = Path(__file__).resolve().parent; started = time.monotonic()
    public = load(here/'WIDGET_VISIBILITY_CHECK_V2.json'); verify(public['private_receipt'])
    parent = load(public['private_receipt']['path']); verify(parent['saved_checks'])
    saved = load(parent['saved_checks']['path'])
    if len(saved['cases']) != 160 or saved['status'] != 'PASS_SAVED_OUTPUT_TK_VIEWPORT_OBSERVATIONS':
        raise ValueError('Complete qualified saved viewport population required')
    for b in saved['cases']: verify(b)
    source = public['source_receipt']; verify(source); local = Path(source['path']).parents[2]
    policy = load(local/'supervision/campaign.json')
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):
        raise ValueError('Fresh private N4 output required')
    guard(args.output, policy, started); size = private_bytes(local)
    if size+6*1024**3+128*1024**2 > min(50, policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared allowance unavailable')
    code = [bind(here/n) for n in ('viewport_ledger.py','test_viewport_ledger.py','probe_viewport_ledger.py',
        'README_VIEWPORT_LEDGER.md','widget_visibility.py','common.py','metric_process.py','probe_integrated_scoring.py')]
    args.output.mkdir(parents=True, exist_ok=False)
    freeze(args.output/'ADMISSION.json', dict(owner=identity(process), code=code, parent=public['private_receipt'],
        saved_checks=parent['saved_checks'], expected_tests=8, private_bytes_at_start=size,
        scope='Saved viewport point observations and synthetic ledger fixtures; no app/model/audio/GUI launch'))
    import test_viewport_ledger as tests
    tests.CONTEXT.update(output=args.output, saved_cases=saved['cases'])
    with (args.output/'unittest.txt').open('x', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    for b in code: verify(b)
    guard(args.output, policy, started)
    passed = result.wasSuccessful() and result.testsRun == 8 and not result.skipped
    checks = dict(saved=tests.CONTEXT.get('saved_checks', []), large_history=tests.CONTEXT.get('large_history'))
    freeze(args.output/'CHECKS.json', checks)
    freeze(args.output/'RESULT.json', dict(status='PASS_BOUNDED_VIEWPORT_LEDGER' if passed else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(), admission=bind(args.output/'ADMISSION.json'),
        tests=result.testsRun, errors=len(result.errors), failures=len(result.failures), skipped=len(result.skipped),
        log=bind(args.output/'unittest.txt'), checks=bind(args.output/'CHECKS.json'), saved_histories=len(checks['saved']),
        elapsed_sec=time.monotonic()-started, models_loaded=0, actual_GUI_execution=False,
        actual_source_execution=False, actual_continuity_test=False, integrated_N4_cells=0))
    print(json.dumps(dict(result=bind(args.output/'RESULT.json'), passed=passed)))
    if not passed: raise RuntimeError('Viewport ledger qualification failed; preserve this attempt')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
