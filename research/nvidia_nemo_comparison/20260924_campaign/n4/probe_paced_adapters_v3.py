"""Bounded saved-vector and source-clock qualification. README_PACED_ADAPTERS_V3.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import unittest
from common import bind, freeze, load, verify
from metric_process import identity, pin
from probe_integrated_scoring import guard, private_bytes


def run(args):
    process = pin(); here = Path(__file__).resolve().parent; started = time.monotonic()
    public = load(here/'APPLICATION_PUBLICATION_CHECK_V1.json')
    verify(public['source_receipt']); source = load(public['source_receipt']['path']); root = Path(source['prototype'])
    for rel, b in source['files'].items(): verify(dict(path=str((root/rel).resolve()), **b))
    preparation = public['gallery_preparation']; verify(preparation); prepared = load(preparation['path'])
    verify(prepared['catalog']); catalog = load(prepared['catalog']['path'])
    wiring = load(here/'ACCEPTED_SOURCE_CATALOG_CHECK.json')
    runtimes = [b for b in wiring['inputs'] if Path(b['path']).name in ('n2_runtime.json', 'n3_runtime.json')]
    if len(runtimes) != 2: raise ValueError('Exact two runtime manifests required')
    for b in runtimes: verify(b)
    local = Path(public['source_receipt']['path']).parents[2]; policy = load(local/'supervision/campaign.json')
    if args.output.exists() or not args.output.resolve().is_relative_to((local/'n4').resolve()):
        raise ValueError('Fresh private N4 output required')
    guard(args.output, policy, started); size = private_bytes(local)
    if size+6*1024**3+128*1024**2 > min(50, policy['resource_policy']['new_payload_allowance_gib'])*1024**3:
        raise ValueError('Shared allowance unavailable')
    code = [bind(here/n) for n in ('paced_adapters_v3.py', 'test_paced_adapters_v3.py', 'probe_paced_adapters_v3.py',
        'README_PACED_ADAPTERS_V3.md', 'mode_galleries.py', 'controller_projection.py', 'common.py',
        'metric_process.py', 'probe_integrated_scoring.py')]
    args.output.mkdir(parents=True, exist_ok=False)
    freeze(args.output/'ADMISSION.json', dict(owner=identity(process), source=public['source_receipt'], code=code,
        preparation=preparation, runtimes=runtimes, expected_tests=9, private_bytes_at_start=size,
        scope='No model/source execution or GUI. Existing research vectors and synthetic source events only.'))
    sys.path[:0] = [str(root), str(root/'vendor')]
    import test_paced_adapters_v3 as tests
    from controller_projection import forbid_inference
    tests.CONTEXT.update(output=args.output, preparation=preparation, catalog=catalog, runtimes=runtimes)
    with (args.output/'unittest.txt').open('x', encoding='utf-8') as stream, forbid_inference():
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    for b in code: verify(b)
    guard(args.output, policy, started)
    passed = result.wasSuccessful() and result.testsRun == 9 and not result.skipped
    checks = dict(galleries=tests.CONTEXT.get('gallery_checks', []), consumers=tests.CONTEXT.get('consumer_checks', []))
    freeze(args.output/'CHECKS.json', checks)
    freeze(args.output/'RESULT.json', dict(status='PASS_MODEL_FREE_PACED_ADAPTERS' if passed else 'FAILED_PRESERVED',
        utc=datetime.now(timezone.utc).isoformat(), admission=bind(args.output/'ADMISSION.json'),
        tests=result.testsRun, errors=len(result.errors), failures=len(result.failures), skipped=len(result.skipped),
        log=bind(args.output/'unittest.txt'), checks=bind(args.output/'CHECKS.json'),
        gallery_checks=len(checks['galleries']), consumer_checks=len(checks['consumers']),
        elapsed_sec=time.monotonic()-started, model_loads=0, integrated_N4_cells=0,
        actual_source_execution=False, source_to_widget_latency_qualified=False))
    print(json.dumps(dict(result=bind(args.output/'RESULT.json'), passed=passed)))
    if not passed: raise RuntimeError('Adapter qualification failed; preserve this attempt')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
