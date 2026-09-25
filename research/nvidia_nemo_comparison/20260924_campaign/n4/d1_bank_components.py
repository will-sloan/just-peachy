"""Admit/supervise a four-cell D1 smoke. See README_D1_COMPONENTS.md."""
import argparse
from datetime import datetime, timezone, timedelta
import gzip
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from asr_bank_components import verify_admission as verify_asr, require_owner
from common import audio_only, bind, verify, freeze, load, fingerprint
from d0_bank_components import verify_contract as verify_d0, event_digest
from d0_calibration_windows import supervisor, ROOT
from d1_lane_components import capture_type

HERE = Path(__file__).resolve().parent
ALLOCATION = 2*1024**3
CODE_NAMES = ('d1_bank_components.py', 'd1_lane_components.py',
              'test_d1_lane_components.py', 'test_d1_bank_components.py', 'README_D1_COMPONENTS.md')


def resource_guard(root, state):
    policy = load(state/'campaign.json')
    if datetime.now(timezone.utc) >= datetime.fromisoformat(policy['target_utc'])-timedelta(hours=12):
        raise TimeoutError('Packaging reserve reached')
    _, low = supervisor.disk_reserves(policy)
    if low:
        raise RuntimeError('Disk reserve breached: '+str(low))
    if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+32*1024**2 > ALLOCATION:
        raise RuntimeError('D1 component allocation exhausted')


def component_key(contract, job, encoder, profile):
    audio_only(job)
    if encoder not in ('E0', 'E1'):
        raise ValueError('Unsupported encoder')
    return fingerprint(dict(component=contract['component_contract'], job=job, encoder=encoder,
        profile=profile, history='one fresh native D1 stream per independent scene; no turn reset',
        delivery='unchanged application D1 loop; 100ms journal reads plus exact tail and one finish',
        queries='actual ActivityTimeline.exclusive_windows; contiguous already delivered support',
        clock='modeled serial source plus actual compute; raw native monotonic times preserved'))


def prepare(args):
    import soundfile as sf
    asr = verify_asr(args.asr_admission)
    base = verify_d0(Path(asr['d0_admission']['path']))
    if base['runtime'] not in load(HERE/'ACCEPTED_SOURCE_CATALOG_CHECK.json')['inputs']:
        raise ValueError('D1 runtime is not the accepted catalog runtime')
    runtime = load(base['runtime']['path'])
    if (runtime['native_device'] != dict(kind='cpu', gpu_index=-1)
            or runtime['streaming_profile'] != 'low_latency'):
        raise ValueError('Only the accepted nominal CPU D1 profile is admitted')
    assets = {b['path']: b for b in base['model_bindings']}
    for row in runtime['native_runtime_files']:
        verify(row)
        assets[row['path']] = row
    model = bind(runtime['nemotron_model'])
    if model['sha256'] != '08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1':
        raise ValueError('Wrong official D1 model')
    assets[model['path']] = model
    source = Path(base['source'])
    sys.path[:0] = [str(source), str(source/'vendor')]
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    profiles = {tap: effective_profile('balanced', 'anonymous_conversation', tap) for tap in ('O0', 'O1')}
    for profile in profiles.values():
        config = profile.apply(pipeline_config(args.output/'unused-private-root', Path(base['models_root'])))
        if config.input_gain != 1 or config.speaker_threads != 1:
            raise ValueError('Unexpected gain or native thread count')
    jobs = load(base['manifest']['path'])['jobs']
    if len(jobs) != 480 or len({j['job_id'] for j in jobs}) != 480:
        raise ValueError('Complete input bank binding required')
    selected = jobs[:2]
    if {j['tap'] for j in selected} != {'O0', 'O1'}:
        raise ValueError('Initial smoke must include both taps')
    for job in selected:
        audio_only(job)
        info = sf.info(job['audio_path'])
        if (bind(job['audio_path'])['sha256'] != job['audio_sha256'] or info.frames != job['frames']
                or info.samplerate != 16000 or info.channels != 1 or info.subtype != 'PCM_16'):
            raise ValueError('Prepared audio differs')
    inventory = load(args.payload_inventory)
    # Reserve D0's full 4GiB, ASR's full 2GiB, D1's 2GiB, then 1GiB contingency.
    if (inventory['errors'] or asr['allocation_bytes'] != 2*1024**3
            or inventory['total_logical_bytes']+4*1024**3+asr['allocation_bytes']+ALLOCATION+1024**3 > 50*1024**3):
        raise ValueError('Shared 50-GiB payload allowance exceeded')
    if args.output.exists():
        raise ValueError('Preserve previous attempts; use a fresh D1 output')
    dependencies = {b['path']: b for b in asr['component_contract']['dependencies']}
    dependencies[str((HERE/'asr_bank_components.py').resolve())] = bind(HERE/'asr_bank_components.py')
    dependencies[str((HERE/'asr_lane_components.py').resolve())] = bind(HERE/'asr_lane_components.py')
    component = dict(source_receipt=base['source_receipt'], runtime=base['runtime'],
        assets=list(assets.values()), code=[bind(HERE/name) for name in CODE_NAMES],
        dependencies=list(dependencies.values()), versions={k:importlib.metadata.version(k)
        for k in ('numpy', 'onnxruntime', 'soundfile', 'psutil')}, python=sys.version,
        cpu_affinity=[4], threads=1, gpu=False)
    contract = dict(schema='n4-d1-components-v1', scope='SMOKE_FOUR_COMPONENT_CELLS',
        component_contract=component, source=base['source'], models_root=base['models_root'],
        d0_admission=asr['d0_admission'], asr_admission=bind(args.asr_admission),
        catalog_check=bind(HERE/'ACCEPTED_SOURCE_CATALOG_CHECK.json'), manifest=base['manifest'],
        preparation=base['preparation'], jobs=selected, encoders=['E0', 'E1'], total=4,
        profiles={k:v.to_dict() for k,v in profiles.items()}, output=str(args.output.resolve()),
        state=str(args.state.resolve()), allocation_bytes=ALLOCATION,
        payload_inventory=bind(args.payload_inventory), other_component_reservations_bytes=6*1024**3,
        remaining_contingency_bytes=1024**3, integrated_N4_cells=0,
        gui_or_paced_qualification=False, inference_started=False)
    args.output.mkdir(parents=True)
    resource_guard(args.output, args.state)
    freeze(args.output/'ADMISSION.json', contract)
    freeze(args.output/'worker.json', dict(argv=[sys.executable, '-B', str(Path(__file__).resolve()),
        'run', '--admission', str(args.output.resolve()/'ADMISSION.json')], cwd=str(ROOT)))
    print(json.dumps(dict(status='PREPARED_NOT_STARTED', total=4, admission=bind(args.output/'ADMISSION.json'))))


def verify_admission(path):
    contract = load(path)
    component = contract['component_contract']
    if contract['schema'] != 'n4-d1-components-v1' or contract['scope'] != 'SMOKE_FOUR_COMPONENT_CELLS':
        raise ValueError('Unsupported D1 scope; full bank needs a separate reviewed admission')
    for row in [component['source_receipt'], component['runtime'], contract['d0_admission'],
                contract['asr_admission'], contract['catalog_check'], contract['manifest'],
                contract['preparation'], *component['assets'], *component['code'], *component['dependencies']]:
        verify(row)
    for rel, row in load(component['source_receipt']['path'])['files'].items():
        actual = bind(Path(contract['source'])/rel)
        if any(actual[k] != row[k] for k in ('sha256', 'bytes')):
            raise ValueError('Frozen source differs')
    if (component['python'] != sys.version or component['versions'] !=
            {k:importlib.metadata.version(k) for k in component['versions']}):
        raise ValueError('Numerical runtime differs')
    return contract


def extract(args):
    import psutil
    import soundfile as sf
    import numpy as np
    process = psutil.Process()
    process.cpu_affinity([4])
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract = verify_admission(args.admission)
    root, state = Path(contract['output']), Path(contract['state'])
    parent = process.parent()
    require_owner(state, parent)
    if load(root/'RESULT.json')['owner'] != dict(pid=parent.pid, create_time=parent.create_time()):
        raise RuntimeError('Wrong numerical parent')
    source = Path(contract['source'])
    sys.path[:0] = [str(source), str(source/'vendor')]
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    from app.n2_models import N2ResidentModels, N2SpeakerModels, load_runtime
    from app.n2_pipeline import N2Engine, ActivityTimeline
    from app.n2_identity import N2NameMap
    runtime = load_runtime(Path(contract['component_contract']['runtime']['path']).parent)
    Capture = capture_type(N2Engine, ActivityTimeline, N2NameMap)
    destination = root/args.encoder
    destination.mkdir(exist_ok=False)
    cells = {}
    owner = N2ResidentModels('D1', args.encoder, runtime)
    try:
        resource_guard(root, state)
        profile = effective_profile('balanced', 'anonymous_conversation', 'O0')
        config = profile.apply(pipeline_config(root/'unused-private-root', Path(contract['models_root'])))
        start = time.perf_counter()
        encoder = N2SpeakerModels(config, args.encoder, runtime, pyannote=False)
        embedding_load_sec = time.perf_counter()-start
        for job in contract['jobs']:
            require_owner(state, parent)
            resource_guard(root, state)
            audio_only(job)
            if bind(job['audio_path'])['sha256'] != job['audio_sha256']:
                raise ValueError('Actual audio changed')
            wave, rate = sf.read(job['audio_path'], dtype='float32')
            if rate != 16000 or wave.ndim != 1 or len(wave) != job['frames'] or not np.isfinite(wave).all():
                raise ValueError('Invalid actual audio')
            profile = effective_profile('balanced', 'anonymous_conversation', job['tap'])
            if profile.to_dict() != contract['profiles'][job['tap']]:
                raise ValueError('Profile changed')
            cell = destination/job['job_id']
            cell.mkdir()
            start = time.perf_counter()
            try:
                with gzip.open(cell/'D1_EVENTS.jsonl.gz', 'xt', encoding='utf-8', newline='\n', compresslevel=3) as log:
                    capture = Capture(wave, log, owner, job['job_id'])
                    summary = capture.run_capture(encoder)
                result = dict(schema='n4-d1-component-cell-v1', status='COMPLETE', job=job,
                    encoder=args.encoder, admission_sha256=bind(args.admission)['sha256'],
                    cache_key=component_key(contract, job, args.encoder, profile.to_dict()),
                    profile_sha256=fingerprint(profile.to_dict()), namespace=encoder.namespace, summary=summary,
                    events=bind(cell/'D1_EVENTS.jsonl.gz'), events_expanded=event_digest(cell/'D1_EVENTS.jsonl.gz'),
                    elapsed_seconds=time.perf_counter()-start, process_rss_bytes=process.memory_info().rss,
                    embedding_load_sec=embedding_load_sec if not cells else None,
                    first_scene_includes_native_load=not bool(cells), actual_neural_inference=True,
                    cpu_affinity=process.cpu_affinity(), integrated_N4_cells=0)
                freeze(cell/'RESULT.json', result)
            except BaseException as exc:
                freeze(cell/'FAILED.json', dict(status='FAILED_PRESERVED', error=repr(exc), job=job))
                raise
            cells[job['job_id']] = bind(cell/'RESULT.json')
            supervisor.atomic(destination/'RESULT_INDEX.json', dict(cells=cells, completed=len(cells), total=len(contract['jobs'])))
            supervisor.atomic(state/'panel_progress.json', dict(stage='N4_D1_COMPONENT_SMOKE', encoder=args.encoder,
                completed=contract['encoders'].index(args.encoder)*len(contract['jobs'])+len(cells), total=contract['total']))
        freeze(destination/'RESULT.json', dict(status='COMPLETE', encoder=args.encoder,
            completed=len(cells), total=len(contract['jobs']), cells=cells, cpu_affinity=process.cpu_affinity()))
    finally:
        owner.close()


def run(args):
    import psutil
    process = psutil.Process()
    process.cpu_affinity([14])
    process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    contract = verify_admission(args.admission)
    root, state = Path(contract['output']), Path(contract['state'])
    require_owner(state, process)
    with supervisor.lock(root/'owner.lock'):
        if (root/'RESULT.json').exists():
            raise ValueError('Preserve prior D1 attempt')
        result = dict(status='RUNNING', owner=dict(pid=process.pid, create_time=process.create_time()),
            child=None, admission=bind(args.admission), completed=0, total=contract['total'], integrated_N4_cells=0)
        supervisor.atomic(root/'RESULT.json', result)
        try:
            for encoder in contract['encoders']:
                resource_guard(root, state)
                require_owner(state, process)
                with (root/(encoder+'.log')).open('x', encoding='utf-8') as log:
                    child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()),
                        'extract', '--admission', str(args.admission), '--encoder', encoder], cwd=str(ROOT),
                        stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
                    result.update(encoder=encoder, child=dict(pid=child.pid, create_time=psutil.Process(child.pid).create_time()))
                    supervisor.atomic(root/'RESULT.json', result)
                    code = child.wait()
                if code:
                    raise RuntimeError(encoder+' D1 collection exit '+str(code))
                terminal = load(root/encoder/'RESULT.json')
                if terminal['status'] != 'COMPLETE' or terminal['completed'] != len(contract['jobs']):
                    raise ValueError('Incomplete D1 census')
                result['completed'] += len(contract['jobs'])
            result.update(status='SMOKE_COLLECTED_REQUIRES_REVIEW', child=None,
                encoders=[bind(root/e/'RESULT.json') for e in contract['encoders']], finished_utc=supervisor.now())
        except BaseException as exc:
            result.update(status='FAILED_PRESERVED', error=repr(exc), finished_utc=supervisor.now())
            raise
        finally:
            supervisor.atomic(root/'RESULT.json', result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    for name in ('asr-admission', 'payload-inventory', 'output', 'state'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('check', 'run', 'extract'):
        p = sub.add_parser(name)
        p.add_argument('--admission', type=Path, required=True)
        if name == 'extract':
            p.add_argument('--encoder', choices=['E0', 'E1'], required=True)
    args = parser.parse_args()
    import psutil
    psutil.Process().cpu_affinity([4] if args.command == 'extract' else [14])
    if args.command == 'check':
        contract = verify_admission(args.admission)
        print(json.dumps(dict(status='VERIFIED_NOT_STARTED', total=contract['total'])))
    else:
        {'prepare': prepare, 'run': run, 'extract': extract}[args.command](args)
