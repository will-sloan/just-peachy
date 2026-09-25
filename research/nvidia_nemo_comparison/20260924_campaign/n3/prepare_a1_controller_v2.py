"""Freeze the A1 Controller derivative and admit suite/GUI checks; README_A1_CONTROLLER.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from reuse_results import bound, load
from prepare import canonical, save

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[3]
CHANGED = {'app/n3_models.py', 'app/README_N3.md', 'config/backends.json', 'tests/test_backend_catalog.py'}
ADDED = {'vendor/edge_speech_pipeline/n3_a1_service.py',
         'vendor/edge_speech_pipeline/n3_a1_stream.py',
         'vendor/edge_speech_pipeline/n3_a1_adapter.py',
         'vendor/edge_speech_pipeline/README_N3_A1.md',
         'vendor/edge_speech_pipeline/LICENSE_NVIDIA_NEMO_A1.txt',
         'vendor/edge_speech_pipeline/NOTICE_NVIDIA_NEMO_A1.md', 'tests/test_n3_a1.py'}


def freeze(previous_source, release):
    old = load(previous_source.parent / 'SOURCE_RECEIPT.json')
    if release.exists(): raise ValueError('Preserve every existing source release')
    for name, row in old['files'].items():
        actual = bound(previous_source / name)
        if any(actual[k] != row[k] for k in ('sha256', 'bytes')):
            raise ValueError('Original frozen source changed: ' + name)
        if name not in CHANGED and bound(WORKTREE / 'prototype' / name)['sha256'] != row['sha256']:
            raise ValueError('Unreviewed source change: ' + name)
    source = release / 'prototype'; source.mkdir(parents=True)
    names = set(old['files']) | ADDED
    files = {}
    for name in sorted(names):
        origin = WORKTREE / 'prototype' / name
        target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
        files[name] = {k: v for k, v in bound(target).items() if k != 'path'}
    for name, expected in old['common_ui_files'].items():
        if files[name]['sha256'] != expected: raise ValueError('Frozen UI changed')
    if files['config/ui.json'] != old['files']['config/ui.json']: raise ValueError('Frozen layout changed')
    for name, expected in old['auxiliary_files'].items():
        origin = previous_source.parent / name
        if bound(origin)['sha256'] != expected['sha256']: raise ValueError('Auxiliary source changed')
        target = release / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    runtime = {k: v['sha256'] for k, v in files.items() if k.startswith(('app/', 'vendor/', 'config/', 'release_tools/'))
        or k == 'main.py' or '/' not in k and Path(k).suffix.lower() in {'.cmd', '.bat', '.ps1', '.sh'}}
    receipt = dict(old, prototype=str(source), files=files, file_count=len(files),
        frontend_runtime_sha256=canonical(runtime),
        derivative=dict(parent=bound(previous_source.parent / 'SOURCE_RECEIPT.json'),
                        changed=sorted(CHANGED), added=sorted(ADDED)))
    save(release / 'SOURCE_RECEIPT.json', receipt)
    return source


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('gui-plan', 'service-plan', 'nominal-plan'): p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--version', required=True); args = p.parse_args()
    if not args.version.isalnum(): raise ValueError('Alphanumeric fresh version required')
    gui, service, nominal = [load(x) for x in (args.gui_plan, args.service_plan, args.nominal_plan)]
    root = args.gui_plan.resolve().parent
    output = root / ('numerical-' + args.version); plan = root / ('plan-' + args.version + '.json')
    worker = root / ('worker-' + args.version + '.json')
    runtime_path = root / 'runtime' / args.version / 'cpu/n3_runtime.json'
    release = root.parent / 'releases' / ('n3-common-' + args.version)
    if any(x.exists() for x in (output, plan, worker, runtime_path, release)): raise ValueError('Use fresh outputs')
    parity_path = Path(service['output']) / 'parity/RESULT.json'; parity = load(parity_path)
    complete = load(Path(service['output']) / 'RESULT.json')
    if (complete['plan_sha256'] != bound(args.service_plan)['sha256'] or not complete.get('numerical_jobs_passed') or
        parity.get('status') != 'PASS_SERVICE_PARITY' or not parity.get('host_service_qualified') or
        complete['jobs']['A1-service-parity']['result']['sha256'] != bound(parity_path)['sha256']):
        raise ValueError('Exact complete host parity is required')
    smoke_path = Path(nominal['output']) / 'smoke-A1-onnx/RESULT.json'; smoke = load(smoke_path)
    if smoke.get('status') != 'COMPLETE' or smoke.get('completed') != 2 or smoke.get('total') != 2:
        raise ValueError('Independent application-runtime smoke must pass')
    gui_job = next(j for j in gui['jobs'] if j['id'] == 'actual-gui-A2')
    argv = list(gui_job['argv']); original_source = Path(argv[argv.index('--source') + 1])
    source = freeze(original_source, release)
    bundle = Path(service['output']) / 'bundle'
    if bound(bundle / 'BUNDLE.json')['sha256'] != parity['bundle_sha256']: raise ValueError('Export changed')
    runtime = load(argv[argv.index('--n3-runtime-config') + 1])
    runtime['variants']['A1'] = dict(schema='just-peachy.n3.a1-onnx.v1', variant='A1',
        model_sha256='6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893',
        bundle_sha256=parity['bundle_sha256'], bundle_path=str(bundle), precision='FP32',
        provider='CPUExecutionProvider', gpu=-1, decoder='greedy', right_context=1,
        language='en-US', chunk_samples=1280, frontend_policy='eval_no_dither', max_symbols_per_step=10)
    save(runtime_path, runtime)
    argv[2] = str(HERE / 'gui_a1.py')
    for key, value in (('--source', source), ('--n3-runtime-config', runtime_path), ('--output', output / 'gui-A1')):
        argv[argv.index(key) + 1] = str(value)
    argv = [a.replace('A2_', 'A1_') if a.startswith('A2_') else a for a in argv]
    python = argv[0]
    jobs = [dict(id='prototype-suite-A1', argv=[python, '-B', str(HERE.parent / 'n2/check_suite.py'),
        '--source', str(source), '--output', str(output / 'suite'), '--cpu', '4'],
        result=str(output / 'suite/RESULT.json'), depends_on=[], gpu=False, timeout_seconds=1800),
        dict(gui_job, id='actual-gui-A1', argv=argv, result=str(output / 'gui-A1/GUI_PANEL_REPORT.json'),
             depends_on=['prototype-suite-A1'])]
    spec = load(gui['worker_spec'])
    spec['argv'] = [python, '-B', str(HERE / 'supervise_n3.py'), 'run', '--plan', str(plan)]
    save(worker, spec)
    bindings = {r['path']: r for r in nominal['bindings']}
    for b in gui['bindings']: bindings[b['path']] = b
    paths = [args.gui_plan, args.service_plan, args.nominal_plan, parity_path, smoke_path, worker, runtime_path,
        *[p for p in release.rglob('*') if p.is_file()],
        *[HERE / name for name in ('prepare_a1_controller_v2.py', 'gui_a1.py')]]
    for path in paths:
        b = bound(path); bindings[b['path']] = b
    document = dict(gui, created_utc=datetime.now(timezone.utc).isoformat(), output=str(output),
        worker_spec=str(worker), jobs=jobs, bindings=list(bindings.values()),
        purpose='A1/P0 actual shared Controller, exact frozen UI, D0/E0, three saved-audio GUI cells',
        dependencies='Host service parity and app-runtime smoke passed; nominal screen remains independently required',
        stage_complete=False)
    save(plan, document)
    print(json.dumps(dict(status='PREPARED_NOT_STARTED', plan=bound(plan), source=str(source), gui_cells=3)))


if __name__ == '__main__': main()
