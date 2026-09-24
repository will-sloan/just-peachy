"""Build the reviewed, pinned CPU runtime locally with microphone support disabled."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
BASE = Path('G:/Just_Peachy_N1/20260924_campaign/local/assets')
CPP = 'NeMo-Speech.cpp-97a15afa5caa9bce5baaa86c1184103877af4101'
GGML = 'ggml-c03b4e2bcece5134827881af90242086daf75be5'
SP = 'sentencepiece-17d7580d6407802f85855d2cc9190634e2c95624'
CMAKE = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe')
ARCHIVES = {
    CPP: ('NVIDIA/NeMo-Speech.cpp', 'f1fdefc70fc810f70f5cdf86eb31f27a990005506cb9c9938941b53bda53677c'),
    GGML: ('ggml-org/ggml', 'dd9bc340931eb7d12b3b8fd946cbf545c4430b1594835f36c3ac368a0a085c49'),
    SP: ('google/sentencepiece', '73b688b48130c2979d70215e571980ce64ee4b343878ade8f9104e779ec43d04'),
}


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=BASE)
    parser.add_argument('--cmake', type=Path, default=CMAKE)
    args = parser.parse_args()
    base = args.base
    logs = base / 'build_logs'
    logs.mkdir(parents=True, exist_ok=True)
    receipt = {'started_at_utc': now(), 'status': 'RUNNING', 'source_archives': [], 'commands': [],
               'jobs': 1, 'priority': 'BELOW_NORMAL', 'microphone_capture_compiled': False,
               'cuda_enabled': False, 'model_inference_executed': False,
               'review': 'Root/component CMake, optional-dependency conditions, native CLI entry/help paths, ggml CPU build, and SentencePiece bundled dependencies reviewed before execution. No installer scripts executed.'}
    output = ROOT / 'runtime_receipt.json'
    def save():
        output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    def run(name, command):
        if shutil.disk_usage('G:/').free < 75 * 1024**3:
            raise RuntimeError('Minimum G: reserve reached')
        path = logs / (name + '.log')
        started = now()
        with path.open('w', encoding='utf-8') as stream:
            process = subprocess.run([str(x) for x in command], stdout=stream, stderr=subprocess.STDOUT,
                creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW,
                timeout=1800)
        entry = {'name': name, 'argv': [str(x) for x in command], 'started_at_utc': started,
                 'finished_at_utc': now(), 'exit_code': process.returncode, 'log': str(path),
                 'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        receipt['commands'].append(entry)
        save()
        print(name, process.returncode, flush=True)
        if process.returncode:
            raise RuntimeError(f'{name} failed: {path}')
    try:
        for stem, (repo, expected) in ARCHIVES.items():
            path = base / (stem + '.zip')
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise RuntimeError(f'Source archive hash mismatch: {path}')
            receipt['source_archives'].append({'path': str(path), 'sha256': actual, 'revision': stem[-40:], 'url': f'https://codeload.github.com/{repo}/zip/{stem[-40:]}'})
        save()
        cpp = base / 'source' / CPP
        ggml = base / 'source' / GGML
        sp = base / 'source' / SP
        shutil.copytree(ggml, cpp / 'ggml', dirs_exist_ok=True)
        spbuild = base / 'build' / 'sentencepiece'
        build = base / 'build' / 'nemo-cpu'
        run('sentencepiece-configure', [args.cmake, '-S', sp, '-B', spbuild, '-G', 'Visual Studio 17 2022', '-A', 'x64', '-DSPM_ENABLE_SHARED=OFF', '-DSPM_BUILD_TEST=OFF', '-DSPM_ENABLE_TCMALLOC=OFF'])
        run('sentencepiece-build', [args.cmake, '--build', spbuild, '--config', 'Release', '--target', 'sentencepiece-static', '--parallel', '1'])
        run('nemo-configure', [args.cmake, '-S', cpp, '-B', build, '-G', 'Visual Studio 17 2022', '-A', 'x64',
            '-DGGML_CUDA=OFF', '-DGGML_VULKAN=OFF', '-DGGML_NATIVE=OFF', '-DGGML_OPENMP=OFF', '-DGGML_CPU_KLEIDIAI=OFF',
            '-DFETCHCONTENT_FULLY_DISCONNECTED=ON', '-DNEMO_SPEECH_GGML_PATCHED=OFF',
            '-DNEMO_SPEECH_BUILD_TTS=OFF', '-DNEMO_SPEECH_BUILD_NMT=OFF', '-DNEMO_SPEECH_BUILD_S2S=OFF',
            '-DNEMO_SPEECH_BUILD_MIC_CAPTURE=OFF', '-DNEMO_SPEECH_BUILD_HTTP=OFF', '-DNEMO_SPEECH_BUILD_GRPC=OFF',
            '-DNEMO_SPEECH_WITH_FLASHLIGHT=OFF', '-DNEMO_SPEECH_WITH_NORM=OFF', '-DNEMO_SPEECH_BUILD_TESTS=OFF',
            '-DBUILD_TESTING=OFF', '-DNEMO_SPEECH_BUILD_EXAMPLES=OFF', '-DNEMO_SPEECH_BUILD_TOOLS=OFF',
            f'-DSENTENCEPIECE_LIB={spbuild / "src/Release/sentencepiece.lib"}', f'-DSENTENCEPIECE_INCLUDE_DIR={sp / "src"}'])
        run('nemo-build', [args.cmake, '--build', build, '--config', 'Release', '--target', 'nemo_speech_cli', 'nemo_speech_asr_c', '--parallel', '1'])
        install = base / 'runtime_install'
        run('nemo-install', [args.cmake, '--install', build, '--config', 'Release', '--prefix', install])
        notices = install / 'share/licenses/nemo-speech/third_party/sentencepiece'
        notices.mkdir(parents=True, exist_ok=True)
        for source, name in [('LICENSE', 'LICENSE'), ('third_party/absl/LICENSE', 'absl-LICENSE'),
                             ('third_party/darts_clone/LICENSE', 'darts-clone-LICENSE'),
                             ('third_party/protobuf-lite/LICENSE', 'protobuf-lite-LICENSE')]:
            shutil.copy2(sp / source, notices / name)
        binary = build / 'bin/Release/nemo-speech.exe'
        run('nemo-version', [binary, '--version'])
        run('nemo-help', [binary, '--help'])
        run('nemo-diarize-help', [binary, 'diarize', '--help'])
        run('nemo-transcribe-help', [binary, 'transcribe', '--help'])
        receipt['binary'] = {'path': str(binary), 'sha256': hashlib.sha256(binary.read_bytes()).hexdigest()}
        receipt['installed_files'] = [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                      'bytes': path.stat().st_size} for path in sorted(install.rglob('*'))
                                     if path.is_file() and (path.suffix in ('.exe', '.dll') or 'licenses' in path.parts)]
        receipt['status'] = 'BUILT_AND_HELP_VERIFIED'
    except Exception as error:
        receipt['status'] = 'BUILD_FAILED'
        receipt['error'] = type(error).__name__ + ': ' + str(error)
    receipt['finished_at_utc'] = now()
    save()
    print(receipt['status'], flush=True)
    return 0 if receipt['status'] == 'BUILT_AND_HELP_VERIFIED' else 1


if __name__ == '__main__':
    sys.exit(main())
