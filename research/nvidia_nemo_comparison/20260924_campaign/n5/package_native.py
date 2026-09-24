"""Package verified ELF files with native bin/lib layout and notices. README_ARM64.md."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main(a):
    if a.stage.exists() or a.archive.exists():
        raise ValueError('Fresh native stage/archive required')
    receipt = json.loads((a.build/'BUILD_RECEIPT.json').read_text())
    if receipt['status'] != 'CROSS_BUILD_SUCCEEDED_NOT_EXECUTED':
        raise ValueError('A completed cross-build receipt is required')
    a.stage.mkdir(parents=True)
    for folder in ['bin','lib','licenses']:
        (a.stage/folder).mkdir()
    for row in receipt['binaries']:
        p = a.build/row['path']
        if sha(p) != row['sha256']:
            raise ValueError('Binary differs from build receipt')
        target = a.stage/('bin' if p.name=='nemo-speech' else 'lib')/p.name
        shutil.copy2(p, target)
    for p in (a.build/'build/bin').iterdir():
        if p.is_symlink():
            target = p.readlink()
            if target.is_absolute() or len(target.parts)!=1:
                raise ValueError('Native links must be relative sibling names')
            if not (a.build/'build/bin'/target).is_file() or not p.resolve().is_relative_to(a.build/'build/bin'):
                raise ValueError('Unsafe or missing native link')
            (a.stage/'lib'/p.name).symlink_to(target)
    source = a.build/'source'
    notice_files = []
    for p in sorted(source.rglob('*')):
        if p.is_file() and any(term in p.name.lower() for term in ['license','copying','copyright','notice']):
            relative = p.relative_to(source)
            dest = a.stage/'licenses'/relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
            notice_files.append(str(relative))
    (a.stage/'BUILD_RECEIPT.json').write_text(json.dumps(receipt, indent=2)+'\n')
    (a.stage/'README.md').write_text('''# Native ARM64 runtime engineering artifact

Contains the pinned NeMo-Speech.cpp ASR/diarization C ABI and CLI, ggml,
statically linked SentencePiece, source hashes, the one-thread patch record,
and notices. Runtime layout is bin/nemo-speech plus lib/*.so*. Keep symlinks.
Target: Linux aarch64 armv8-a, Bookworm-compatible symbol requirements.
Requires OS glibc, libstdc++6, libgcc-s1; no CUDA or training Python environment.
No models or personal data are included. Download exact model assets through
the campaign model manifests, after candidate acceptance. Do not use runtime
defaults to choose a model. Native model/WAV parity and full-GUI integration
remain untested; this is not a selected N4 deployment profile or a 2GB claim.

On Linux, extract with `tar -xzf ARCHIVE.tar.gz` and run
`./nemo-arm64/bin/nemo-speech --version` or `--help` for a no-model loader check.
Do not invoke microphone, doctor, or hardware discovery during this campaign.
PowerShell and CMD: `wsl.exe -d Ubuntu -- tar -xzf /mnt/g/PATH/ARCHIVE.tar.gz`;
that extracts only. An x86_64 WSL host requires explicit QEMU to execute ARM64.
Rebuild commands and emulator checks are in the campaign n5/README_ARM64.md.
''')
    files = []
    for p in sorted(a.stage.rglob('*')):
        if p.is_symlink():
            files.append(dict(path=p.relative_to(a.stage).as_posix(), symlink=str(p.readlink())))
        elif p.is_file():
            files.append(dict(path=p.relative_to(a.stage).as_posix(), bytes=p.stat().st_size, sha256=sha(p)))
    (a.stage/'NATIVE_MANIFEST.json').write_text(json.dumps(dict(status='ARM64_BUILD_VERIFIED',
        model_smoke='NOT_TESTED', CM5_HARDWARE_NOT_TESTED=True, files=files), indent=2)+'\n')
    a.archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(a.archive, 'x:gz') as t:
        t.add(a.stage, arcname='nemo-arm64')
    result = dict(status='NATIVE_ENGINEERING_PACKAGE_CREATED', archive=str(a.archive),
        bytes=a.archive.stat().st_size, sha256=sha(a.archive), binary_count=len(receipt['binaries']),
        notice_files=len(notice_files), model_assets=0, private_data=False, N4_selected=False)
    a.archive.with_suffix('.receipt.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['build','stage','archive']:
        p.add_argument('--'+key, type=Path, required=True)
    main(p.parse_args())
