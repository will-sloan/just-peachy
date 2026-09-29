"""Validate a fresh CM5 research stage and unpack its pinned runtime. See README.md."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(__file__).resolve().parent
    expected = Path.home()/'JustPeachy/research/nemotron-20260928/d1-generic-v1'
    if root != expected or any(x.is_symlink() for x in [root, *root.parents]):
        raise RuntimeError('Unexpected or linked stage root')
    if not Path('/proc/device-tree/model').read_text().startswith('Raspberry Pi Compute Module 5'):
        raise RuntimeError('Wrong hardware')
    if shutil.disk_usage(root).free < 5*1024**3:
        raise RuntimeError('Keep at least 5 GiB free on Pi')
    manifest = json.loads((root/'INPUTS.json').read_text())
    if manifest['schema'] != 'pi-d1-generic-inputs.v1':
        raise RuntimeError('Unknown manifest')
    for row in manifest['files']:
        path = root/row['name']
        if Path(row['name']).name != row['name'] or path.is_symlink():
            raise RuntimeError('Unexpected staged path')
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise RuntimeError('Input hash mismatch: '+row['name'])
    target = root/'nemo-arm64'
    if target.exists():
        raise FileExistsError('Preserve existing runtime stage')
    with tarfile.open(root/'runtime.tar.gz') as archive:
        entries = archive.getmembers()
        names = [x.name for x in entries]
        if len(entries) > 128 or len(names) != len(set(names)) or sum(x.size for x in entries) > 16*1024**2:
            raise RuntimeError('Archive count/size bound exceeded')
        for member in entries:
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or name.parts[0] != 'nemo-arm64':
                raise RuntimeError('Archive path escape')
            if not (member.isfile() or member.isdir() or member.issym()):
                raise RuntimeError('Unsupported archive member')
            if member.issym():
                link = PurePosixPath(member.linkname)
                if link.is_absolute() or '..' in link.parts or len(link.parts) != 1:
                    raise RuntimeError('Nonlocal runtime symlink')
        # Explicit extraction also works on the target's Python 3.11.2.
        # All paths and link destinations above are bounded to this fresh stage.
        for member in entries:
            path = root/member.name
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif member.issym():
                path.symlink_to(member.linkname)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, path.open('xb') as output:
                    shutil.copyfileobj(source, output)
                path.chmod(member.mode & 0o755)
    library = target/'lib/libnemo_speech_asr_c.so.1'
    if digest(library) != '9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f':
        raise RuntimeError('Runtime library differs')
    result = dict(status='STAGED_VERIFIED_NOT_INFERENCE', manifest_sha256=digest(root/'INPUTS.json'),
                  library_sha256=digest(library), target_root=str(root), installed_current_unchanged=True)
    with (root/'STAGED.json').open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
