"""Package retained native source/objects for a bounded on-Pi rebuild. README_SCHEDULER.md."""
import hashlib
import json
from pathlib import Path
import tarfile
import sys

BASE = Path('/home/amiri/jp-n5-native-v1')
SOURCE = BASE/'source/NeMo-Speech.cpp-97a15afa5caa9bce5baaa86c1184103877af4101'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    out = Path(sys.argv[1])
    if out.exists():
        raise FileExistsError(out)
    session = SOURCE/'src/runtime/ggml/session.cpp'
    if sha(session) != '9583306947a8a0cb92d68da94c1803cb5caa064e112face5123e1f94e959251a':
        raise RuntimeError('Retained source differs')
    files = {str(Path('source')/p.relative_to(SOURCE)): p for p in SOURCE.rglob('*') if p.is_file()}
    for p in (BASE/'build/src/asr/CMakeFiles/nemo_speech_asr.dir').rglob('*.o'):
        files[str(Path('objects')/p.relative_to(BASE/'build/src/asr/CMakeFiles/nemo_speech_asr.dir'))] = p
    for name, path in {
        'runtime.a': 'build/src/runtime/ggml/libnemo_speech_runtime_ggml.a',
        'common.a': 'build/src/common/libnemo_speech_common.a',
        'libsentencepiece.a': 'sentencepiece-build/src/libsentencepiece.a',
        'libggml.so.0.12.0': 'build/bin/libggml.so.0.12.0',
        'libggml-base.so.0.12.0': 'build/bin/libggml-base.so.0.12.0',
        'libggml-cpu.so.0.12.0': 'build/bin/libggml-cpu.so.0.12.0',
    }.items():
        files['prebuilt/'+name] = BASE/path
    if any(p.is_symlink() for p in files.values()):
        raise RuntimeError('Unexpected symlink')
    manifest = dict(schema='scheduler-native-bundle.v1', source_session_sha256=sha(session),
                    provenance='Retained original cross-build source and ARM64 objects; no download',
                    files=[dict(name=n, bytes=p.stat().st_size, sha256=sha(p)) for n,p in sorted(files.items())])
    if sum(x['bytes'] for x in manifest['files']) > 96*1024**2:
        raise RuntimeError('Input expansion cap exceeded')
    with tarfile.open(out, 'x:gz') as archive:
        for name,path in sorted(files.items()):
            archive.add(path, arcname=name, recursive=False)
    manifest['archive_sha256'] = sha(out)
    with out.with_suffix('.json').open('x') as stream:
        json.dump(manifest,stream,indent=2)
    print(json.dumps(dict(archive_bytes=out.stat().st_size, expanded_bytes=sum(x['bytes'] for x in manifest['files']), archive_sha256=manifest['archive_sha256'])))


if __name__ == '__main__':
    main()
