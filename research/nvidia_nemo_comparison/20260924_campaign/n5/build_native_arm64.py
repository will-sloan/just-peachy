"""Isolated, one-worker native ARM64 cross-build, without inference. README_ARM64.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
import zipfile


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main(a):
    if a.output.exists():
        raise ValueError('Fresh build root required')
    if shutil.disk_usage(a.output.parent).free < 50 * 1024**3:
        raise RuntimeError('Host disk reserve reached')
    a.output.mkdir()
    start = time.monotonic()
    os.nice(10)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    receipt = dict(status='BUILDING', started_utc=datetime.now(timezone.utc).isoformat(),
                   compiler_workers=1, linux_cpu_affinity=sorted(os.sched_getaffinity(0)),
                   note='WSL CPU index is not a verified Windows physical-core mapping',
                   target='Linux aarch64 armv8-a; Bookworm ABI ceilings audited separately',
                   inference=False, hardware='CM5_HARDWARE_NOT_TESTED', commands=[])
    record = a.output / 'BUILD_RECEIPT.json'

    def run(name, argv):
        log = a.output / (name + '.log')
        tick = time.monotonic()
        with log.open('wb') as f:
            completed = subprocess.run(list(map(str, argv)), stdout=f, stderr=subprocess.STDOUT,
                                       env=dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1'), timeout=1800)
        receipt['commands'].append(dict(name=name, argv=list(map(str, argv)), returncode=completed.returncode,
                                        elapsed_seconds=time.monotonic()-tick, log=log.name, sha256=sha(log)))
        dump(record, receipt)
        if completed.returncode:
            raise RuntimeError(name + ' failed; see ' + str(log))

    try:
        tools = json.loads((a.downloads / 'TOOLS.json').read_text())
        tool_dir = a.output / 'tools'
        tool_dir.mkdir()
        for row in tools['files']:
            archive = a.downloads / row['filename']
            if sha(archive) != row['sha256']:
                raise ValueError('Tool bytes changed')
            if archive.suffix == '.whl':
                with zipfile.ZipFile(archive) as z:
                    z.extractall(tool_dir)
            else:
                with tarfile.open(archive) as t:
                    t.extractall(tool_dir, filter='data')
        cmake = tool_dir / 'cmake/data/bin/cmake'
        ninja = tool_dir / 'ninja/data/bin/ninja'
        for p in (tool_dir / 'cmake/data/bin').iterdir():
            p.chmod(0o755)
        ninja.chmod(0o755)
        arm = tool_dir / 'arm-gnu-toolchain-12.3.rel1-x86_64-aarch64-none-linux-gnu'
        cc = arm / 'bin/aarch64-none-linux-gnu-gcc'
        run('compiler', [cc, '--version'])
        run('sysroot', [cc, '-print-sysroot'])
        src_receipt = json.loads(a.source_receipt.read_text())
        source = a.output / 'source'
        source.mkdir()
        receipt['source_archives'] = []
        for row in src_receipt['source_archives']:
            archive = a.assets / Path(row['path'].replace('\\', '/')).name
            if sha(archive) != row['sha256']:
                raise ValueError('Pinned source archive differs')
            with zipfile.ZipFile(archive) as z:
                z.extractall(source)
            receipt['source_archives'].append(dict(filename=archive.name, sha256=row['sha256'], revision=row['revision'], url=row['url']))
        nemo = source / ('NeMo-Speech.cpp-' + src_receipt['source_archives'][0]['revision'])
        ggml = source / ('ggml-' + src_receipt['source_archives'][1]['revision'])
        spm = source / ('sentencepiece-' + src_receipt['source_archives'][2]['revision'])
        shutil.copytree(ggml, nemo / 'ggml', dirs_exist_ok=True)
        session = nemo / 'src/runtime/ggml/session.cpp'
        original = session.read_text()
        old = 'ggml_graph_compute_helper_async(sched.get(), cr.gf, 4)'
        new = 'ggml_graph_compute_helper_async(sched.get(), cr.gf, 1)'
        if original.count(old) != 1:
            raise ValueError('Pinned thread-setting site changed')
        before = sha(session)
        session.write_text(original.replace(old, new))
        receipt['patch'] = dict(path='src/runtime/ggml/session.cpp', before_sha256=before,
                                after_sha256=sha(session), old=old, new=new)
        toolchain = a.output / 'toolchain.cmake'
        toolchain.write_text('\n'.join([
            'set(CMAKE_SYSTEM_NAME Linux)', 'set(CMAKE_SYSTEM_PROCESSOR aarch64)',
            f'set(CMAKE_C_COMPILER "{cc}")',
            f'set(CMAKE_CXX_COMPILER "{arm}/bin/aarch64-none-linux-gnu-g++")',
            f'set(CMAKE_SYSROOT "{arm}/aarch64-none-linux-gnu/libc")',
            'set(CMAKE_C_FLAGS_INIT "-march=armv8-a")',
            'set(CMAKE_CXX_FLAGS_INIT "-march=armv8-a")',
            'set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)',
            'set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)',
            'set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)',
            'set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)', '']))
        common = ['-G', 'Ninja', '-DCMAKE_MAKE_PROGRAM='+str(ninja), '-DCMAKE_TOOLCHAIN_FILE='+str(toolchain),
                  '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
                  '-DFETCHCONTENT_FULLY_DISCONNECTED=ON']
        spb = a.output / 'sentencepiece-build'
        run('sentencepiece-configure', [cmake, '-S', spm, '-B', spb, *common,
                                       '-DSPM_ENABLE_SHARED=OFF', '-DSPM_BUILD_TEST=OFF', '-DSPM_ENABLE_TCMALLOC=OFF'])
        run('sentencepiece-build', [cmake, '--build', spb, '--target', 'sentencepiece-static', '--parallel', '1'])
        build = a.output / 'build'
        disabled = ['GGML_CUDA', 'GGML_VULKAN', 'GGML_NATIVE', 'GGML_OPENMP', 'GGML_CPU_KLEIDIAI',
                    'NEMO_SPEECH_GGML_PATCHED', 'NEMO_SPEECH_BUILD_TTS', 'NEMO_SPEECH_BUILD_NMT',
                    'NEMO_SPEECH_BUILD_S2S', 'NEMO_SPEECH_BUILD_MIC_CAPTURE', 'NEMO_SPEECH_BUILD_HTTP',
                    'NEMO_SPEECH_BUILD_GRPC', 'NEMO_SPEECH_WITH_FLASHLIGHT', 'NEMO_SPEECH_WITH_NORM',
                    'NEMO_SPEECH_BUILD_TESTS', 'BUILD_TESTING', 'NEMO_SPEECH_BUILD_EXAMPLES', 'NEMO_SPEECH_BUILD_TOOLS']
        run('nemo-configure', [cmake, '-S', nemo, '-B', build, *common,
                              *['-D'+d+'=OFF' for d in disabled], '-DGGML_CPU_ARM_ARCH=armv8-a',
                              '-DSENTENCEPIECE_STATIC_LIB='+str(spb / 'src/libsentencepiece.a'),
                              '-DSENTENCEPIECE_INCLUDE_DIR='+str(spm / 'src'),
                              '-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON'])
        run('nemo-build', [cmake, '--build', build, '--target', 'nemo_speech_asr_c', 'nemo_speech_cli', '--parallel', '1'])
        receipt.update(status='CROSS_BUILD_SUCCEEDED_NOT_EXECUTED',
                       binaries=[dict(path=str(p.relative_to(a.output)), bytes=p.stat().st_size, sha256=sha(p))
                                 for p in sorted((build/'bin').iterdir()) if p.is_file() and not p.is_symlink()],
                       elapsed_seconds=time.monotonic()-start, tool_downloads=tools)
    except Exception as error:
        receipt.update(status='FAILED', error=str(error), elapsed_seconds=time.monotonic()-start)
        raise
    finally:
        dump(record, receipt)
    print(json.dumps(dict(status=receipt['status'], receipt=str(record))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ['downloads', 'assets', 'source-receipt', 'output']:
        p.add_argument('--'+key, type=Path, required=True)
    main(p.parse_args())
