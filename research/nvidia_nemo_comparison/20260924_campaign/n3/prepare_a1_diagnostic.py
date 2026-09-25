"""Prepare a fresh supervised post-v4 A1 diagnostic; README_A1_DIAGNOSTIC.md."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import json
from reuse_results import bound, load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-plan', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not args.version.isalnum(): raise ValueError('Alphanumeric version required')
    prior = load(args.parent_plan)
    here = Path(__file__).resolve().parent
    private = args.parent_plan.resolve().parent
    output = private / ('numerical-' + args.version)
    plan = private / ('plan-' + args.version + '.json')
    worker = private / ('worker-' + args.version + '.json')
    if any(p.exists() for p in (output, plan, worker)):
        raise ValueError('Use fresh diagnostic paths')
    old_export = next(job for job in prior['jobs'] if job['id'] == 'A1-export')
    argv = old_export['argv']
    model = argv[argv.index('--model') + 1]
    source = argv[argv.index('--source') + 1]
    python = argv[0]
    worker_document = load(prior['worker_spec'])
    worker_document['argv'] = [worker_document['argv'][0], '-B', str(here/'supervise_n3.py'), 'run', '--plan', str(plan)]
    worker.write_text(json.dumps(worker_document, indent=2)+'\n', encoding='utf-8')
    job = dict(id='A1-parity-diagnostic', argv=[python, '-B', str(here/'diagnose_a1_parity.py'),
               '--parent-plan', str(args.parent_plan.resolve()), '--model', model, '--source', source,
               '--output', str(output/'diagnostic')], result=str(output/'diagnostic/RESULT.json'),
               depends_on=[], gpu=False, timeout_seconds=1200, accepted_status=['DIAGNOSTIC_COMPLETE'])
    bindings = {row['path']:row for row in prior['bindings']}
    # Parent RESULT is still mutable. The diagnostic verifies its terminal
    # status and exact plan identity only after supervisor ownership transfers.
    for path in [args.parent_plan, worker, Path(__file__), here/'diagnose_a1_parity.py', here/'test_a1_diagnostic.py']:
        row=bound(path);bindings[row['path']]=row
    export = load(old_export['result'])
    for path in [Path(old_export['result']), *[Path(row['path']) for row in export['files']]]:
        row=bound(path);bindings[row['path']]=row
    document = dict(prior, created_utc=datetime.now(timezone.utc).isoformat(), output=str(output),
                    worker_spec=str(worker), jobs=[job], bindings=list(bindings.values()),
                    purpose='Bounded A1 diagnostic after current N3 owner exits; no N3 acceptance implied')
    plan.write_text(json.dumps(document, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status='PREPARED_NOT_STARTED', plan=bound(plan), jobs=1)))


if __name__ == '__main__': main()
