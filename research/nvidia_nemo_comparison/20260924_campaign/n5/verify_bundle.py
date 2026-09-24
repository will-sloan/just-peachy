"""Check an extracted offline bundle before any installation. See INSTALL_CM5.md."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def verify(root):
    root = root.resolve()
    manifest = json.loads((root/'BUNDLE_MANIFEST.json').read_text())
    rows = manifest['files']
    if not rows or len(rows) > 1000 or len({r['path'] for r in rows}) != len(rows):
        raise ValueError('Invalid member inventory')
    for row in rows:
        rel = PurePosixPath(row['path'])
        if rel.is_absolute() or '\\' in row['path'] or ':' in row['path'] or '..' in rel.parts:
            raise ValueError('Unsafe member path')
        path = root.joinpath(*rel.parts)
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path,*path.parents] if p != root.parent):
            raise ValueError('Symlinks are not supported in the offline bundle')
        with path.open('rb') as f:
            digest = hashlib.file_digest(f, 'sha256').hexdigest()
        if path.stat().st_size != row['bytes'] or digest != row['sha256']:
            raise ValueError('Bundle member differs: ' + row['path'])
    return dict(status='BUNDLE_HASHES_PASS', files=len(rows), installation=False, hardware=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    print(json.dumps(verify(p.parse_args().root)))
