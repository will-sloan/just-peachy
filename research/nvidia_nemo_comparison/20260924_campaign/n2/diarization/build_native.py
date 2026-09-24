"""Build a CPU-one-thread copy of the pinned official standalone diarizer ABI."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local')

def sha(path):
    return hashlib.file_digest(Path(path).open('rb'), 'sha256').hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--cuda', action='store_true', help='Separate explicit desktop CUDA build; CPU graph threads remain1')
    ap.add_argument('--jobs', type=int, choices=(1,2), default=1)
    ap.add_argument('--cuda-compiler', type=Path, default=Path('C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.6/bin/nvcc.exe'))
    args = ap.parse_args()
    if args.output is None:
        args.output = LOCAL / ('n2/diarization/native-cuda-cpu1' if args.cuda else 'n2/diarization/native-cpu1')
    receipt_name = 'CUDA_BUILD_RECEIPT.json' if args.cuda else 'NATIVE_BUILD_RECEIPT.json'
    receipt = json.loads((CAMPAIGN / 'assets/runtime_receipt.json').read_text())
    configured = next(x['argv'] for x in receipt['commands'] if x['name'] == 'nemo-configure')
    original_source = Path(configured[configured.index('-S') + 1])
    source = args.output / 'source'
    build = args.output / 'build'
    logs = args.output / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(args.output).free < 75 * 1024**3:
        raise RuntimeError('Less than 75 GiB free: build allocation stopped')
    if not source.exists():
        shutil.copytree(original_source, source)
    relative = 'src/runtime/ggml/session.cpp'
    old = 'ggml_graph_compute_helper_async(sched.get(), cr.gf, 4)'
    new = 'ggml_graph_compute_helper_async(sched.get(), cr.gf, 1)'
    original = (original_source / relative).read_text(encoding='utf-8')
    if original.count(old) != 1:
        raise RuntimeError('Pinned reviewed thread-setting site changed')
    candidate = original.replace(old, new)
    current = (source / relative).read_text(encoding='utf-8')
    if current not in (original, candidate):
        raise RuntimeError('Refusing an unexpected pre-existing source modification')
    (source / relative).write_text(candidate, encoding='utf-8')
    configure = list(configured)
    configure[configure.index('-S') + 1] = str(source)
    configure[configure.index('-B') + 1] = str(build)
    if args.cuda:
        if not args.cuda_compiler.is_file():
            raise RuntimeError('Configured CUDA compiler unavailable; no toolkit install attempted')
        configure[configure.index('-DGGML_CUDA=OFF')] = '-DGGML_CUDA=ON'
        # Supported CMake custom-toolkit selection avoids requiring global VS
        # CUDA integration. It uses existing toolkit MSBuildExtensions only.
        configure.extend(['-T', 'cuda='+str(args.cuda_compiler.parent.parent),
                          '-DCMAKE_CUDA_ARCHITECTURES=86', '-DCMAKE_CUDA_COMPILER='+str(args.cuda_compiler)])
    commands = [configure, [configure[0], '--build', str(build), '--config', 'Release', '--target', 'nemo_speech_asr_c', '--parallel', str(args.jobs)]]
    result = {'source_revision': receipt['source_archives'][0]['revision'], 'status': 'BUILDING',
              'source': str(source), 'threads': 1, 'gpu': args.cuda, 'compiler_jobs':args.jobs,
              'cuda_compiler':str(args.cuda_compiler) if args.cuda else None,
              'cuda_architectures':[86] if args.cuda else [], 'asr_tts_models_loaded': False,
              'patch': {'path': relative, 'before_sha256': sha(original_source / relative),
                        'after_sha256': sha(source / relative), 'old': old, 'new': new}, 'commands': []}
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    for index, command in enumerate(commands):
        log = logs / f'{index}.log'
        start = time.time()
        with log.open('wb') as stream:
            run = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, env=env,
                                 creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name == 'nt' else 0)
        result['commands'].append({'argv': command, 'elapsed_sec': time.time()-start,
                                   'returncode': run.returncode, 'log': str(log), 'sha256': sha(log)})
        if run.returncode:
            result['status'] = 'FAILED'
            (HERE / receipt_name).write_text(json.dumps(result, indent=2)+'\n')
            raise RuntimeError(f'Build command failed; inspect {log}')
    binary = build / 'bin/Release/nemo_speech_asr_c.dll'
    result.update(status='ACTUALLY_BUILT', library_path=str(binary), library_sha256=sha(binary))
    result['runtime_files'] = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size}
                               for p in sorted(binary.parent.glob('*.dll'))]
    (HERE / receipt_name).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'library_path': str(binary)}))

if __name__ == '__main__':
    main()
