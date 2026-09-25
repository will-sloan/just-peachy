"""Prepare one bounded A3 CPU-budget contrast; see README_GUI_TWOCORE.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from reuse_results import bound, load

HERE = Path(__file__).resolve().parent
GUI_CHANGES = {
    "MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui_finalaudit'":
        "MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui_twocore'",
    "'runner','cpu','io_helper'": "'runner','cpu','cpu_affinity','io_helper'",
    "process.cpu_affinity([admission['cpu']])": "process.cpu_affinity(admission['cpu_affinity'])",
    "choices=[4,14],default=4": "choices=[4],default=4",
    'job_count=len(jobs),cpu=args.cpu,threads=1':
        'job_count=len(jobs),cpu=args.cpu,cpu_affinity=[4,14],threads=1',
}
OLD_EXECUTION = "execution='sequential; one numerical child; CPU4 or CPU14; at most one GPU owner'"
NEW_EXECUTION = "execution='sequential; one private GUI candidate; CPU affinity [4,14]; no GPU; explicit two-core resource contrast'"
OLD_WAIT_VERIFY = '        verify(document)\n        try:\n            while True:'
NEW_WAIT_VERIFY = ('        # Full immutable binding verification remains inside the free-owner lock\n'
                  '        # below; do not hash models while another paced candidate is active.\n'
                  '        try:\n            while True:')


def transformed(text, changes):
    for old, new in changes.items():
        if text.count(old) != 1:
            raise ValueError('Derivative anchor changed: '+old)
        text = text.replace(old, new)
    return text


def verify_derivatives():
    pairs = [('gui_finalaudit.py', 'gui_twocore.py', GUI_CHANGES),
             ('supervise_n3.py', 'supervise_n3_twocore.py',
              {OLD_EXECUTION: NEW_EXECUTION, OLD_WAIT_VERIFY: NEW_WAIT_VERIFY})]
    for old, new, changes in pairs:
        expected = transformed((HERE/old).read_text(encoding='utf-8'), changes)
        if (HERE/new).read_text(encoding='utf-8') != expected:
            raise ValueError('Only declared CPU allocation/metadata changes are admitted: '+new)


def make_job(old, output):
    if old['id'] != 'actual-gui-A3' or old.get('gpu'):
        raise ValueError('Only the failed CPU A3 GUI panel is admitted')
    argv = list(old['argv'])
    if Path(argv[2]).name != 'gui_finalaudit.py':
        raise ValueError('Need the existing final-state audit')
    requested = [argv[i+1] for i, value in enumerate(argv[:-1]) if value == '--cell']
    if requested != ['A3_boundary', 'A3_short', 'A3_returning']:
        raise ValueError('Preserve the same three fixed GUI cells')
    argv[2] = str(HERE/'gui_twocore.py')
    argv[argv.index('--output')+1] = str(output/'gui-A3')
    return dict(old, id='actual-gui-A3-two-core', argv=argv,
        result=str(output/'gui-A3/GUI_PANEL_REPORT.json'), depends_on=[],
        cpu_affinity=[4,14], resource_scope='separate two-core host screening; not single-core parity or CM5')


def validate_failure(failure, diagnosis, binding):
    if (failure.get('status') != 'FAILED'
            or 'session lane edge-asr did not finish within 60 seconds' not in failure.get('cleanup_error', '')
            or diagnosis.get('status') != 'DIAGNOSED_NOT_REPAIRED'
            or diagnosis.get('equal_application_runtime_audio_and_cpu_contract') is not True
            or diagnosis.get('failed', {}).get('lane_drain_timeout_seconds') != 60.0
            or binding not in diagnosis.get('failed', {}).get('evidence', [])):
        raise ValueError('Expected the exact diagnosed fixed-join failure')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-plan', type=Path, required=True)
    parser.add_argument('--diagnosis', type=Path, required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not args.version.isalnum():
        raise ValueError('Alphanumeric version required')
    verify_derivatives()
    parent = load(args.parent_plan)
    terminal = Path(parent['output'])/'RESULT.json'
    prior = load(terminal)
    if prior['status'] != 'READY_FOR_REVIEW' or prior['plan_sha256'] != bound(args.parent_plan)['sha256']:
        raise ValueError('Exact parent GUI plan must be terminal')
    import psutil
    try:
        if psutil.Process(prior['owner']['pid']).create_time() == prior['owner']['create_time']:
            raise ValueError('Prior coordinator still owns the run')
    except psutil.NoSuchProcess:
        pass
    old = next(row for row in parent['jobs'] if row['id'] == 'actual-gui-A3')
    panel_binding = prior['jobs']['actual-gui-A3']['result']
    if (prior['jobs']['actual-gui-A3']['status'] != 'FAILED'
            or panel_binding['sha256'] != bound(old['result'])['sha256']):
        raise ValueError('Prior A3 failure binding changed')
    failure_path = Path(old['result']).parent/'private_cells/A3_boundary/cells/A3_boundary/RESULT.json'
    failure = load(failure_path)
    diagnosis = load(args.diagnosis)
    validate_failure(failure, diagnosis, bound(failure_path))
    policy = load(Path(parent['state'])/'campaign.json')['resource_policy']
    if policy['max_cpu_cores'] < 2:
        raise ValueError('Current admitted resource policy does not permit two cores')
    root = args.parent_plan.resolve().parent
    output = root/('numerical-'+args.version)
    plan, worker = root/('plan-'+args.version+'.json'), root/('worker-'+args.version+'.json')
    if any(path.exists() for path in [output, plan, worker]):
        raise ValueError('Use fresh paths; preserve all earlier attempts')
    worker_document = load(parent['worker_spec'])
    worker_document['argv'] = [worker_document['argv'][0], '-B', str(HERE/'supervise_n3_twocore.py'),
                               'run', '--plan', str(plan)]
    with worker.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(worker_document, stream, indent=2); stream.write('\n')
    bindings = {row['path']:row for row in parent['bindings']}
    additions = [args.parent_plan, terminal, Path(old['result']), failure_path, args.diagnosis, worker,
        *[HERE/name for name in ['gui_twocore.py','supervise_n3_twocore.py','prepare_gui_twocore.py',
                                 'test_gui_twocore.py','README_GUI_TWOCORE.md']]]
    for path in additions:
        item = bound(path); bindings[item['path']] = item
    document = dict(parent, created_utc=datetime.now(timezone.utc).isoformat(), output=str(output),
        worker_spec=str(worker), jobs=[make_job(old, output)], bindings=list(bindings.values()),
        purpose='One A3/D1/E0 two-core resource contrast after diagnosed one-core queue backlog',
        resource_contrast=dict(parent_affinity=[4], new_affinity=[4,14], threads_per_model=1,
            admitted_max_cpu_cores=policy['max_cpu_cores'], gpu=False, inference_workers=1),
        application_source_changed=False, model_changed=False, lane_timeout_changed=False,
        interpretation='A completed drain is not real-time qualification; retain original failure and actual timings')
    with plan.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(status='PREPARED_NOT_STARTED', plan=bound(plan), gui_cells=3,
                          cpu_affinity=[4,14], lane_timeout_changed=False)))


if __name__ == '__main__':
    main()
