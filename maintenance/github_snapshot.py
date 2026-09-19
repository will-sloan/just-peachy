"""Preserve compact project handoffs for GitHub. See maintenance/README.md."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ALLOWED = {'.md', '.json', '.jsonl', '.csv', '.txt', '.py', '.ps1', '.cmd',
           '.c', '.cs', '.h', '.js', '.html', '.css', '.sh', '.yaml', '.yml',
           '.toml', '.lock', '.in', '.diff', '.patch', '.sha256', '.png', '.svg'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_bytes(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError(f'Refusing to replace different snapshot: {path}')
    else:
        path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoffs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in sorted(args.handoffs.glob('*.zip')):
        with zipfile.ZipFile(source) as archive:
            members = [m for m in archive.infolist() if not m.is_dir()]
            excluded = [m.filename for m in members if Path(m.filename).suffix.lower() not in ALLOWED]
            if not excluded:
                target = args.output / source.name
                save_bytes(target, source.read_bytes())
            else:
                target = args.output / (source.stem + '_TEXT_ONLY.zip')
                if target.exists():
                    raise FileExistsError(f'Use a fresh output folder: {target}')
                with zipfile.ZipFile(target, 'x', zipfile.ZIP_DEFLATED) as filtered:
                    kept = {}
                    for member in members:
                        if member.filename in excluded:
                            continue
                        data = archive.read(member.filename)
                        filtered.writestr(member.filename, data)
                        kept[member.filename] = hashlib.sha256(data).hexdigest()
                    filtered.writestr('GITHUB_SNAPSHOT.json', json.dumps({
                        'scope': 'Text/figure/source snapshot, not the original complete handoff',
                        'source_name': source.name, 'source_sha256': digest(source),
                        'omitted_local_members': excluded, 'included_sha256': kept,
                        'note': 'Historical manifests inside retain their original scope; omitted audio/binaries are only available locally.'}, indent=2))
        with zipfile.ZipFile(target) as check:
            if check.testzip() is not None:
                raise ValueError(f'ZIP CRC failure: {target}')
        rows.append({'file': target.name, 'sha256': digest(target), 'bytes': target.stat().st_size,
                     'source_path': str(source.resolve()), 'source_sha256': digest(source),
                     'kind': 'TEXT_ONLY' if excluded else 'ORIGINAL_UNCHANGED',
                     'excluded_member_count': len(excluded)})
    target = args.output / args.release.name
    save_bytes(target, args.release.read_bytes())
    rows.append({'file': target.name, 'sha256': digest(target), 'bytes': target.stat().st_size,
                 'source_path': str(args.release.resolve()), 'kind': 'SOURCE_RELEASE_NO_MODELS_OR_PEOPLE'})
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'files': rows,
                'scope': 'Source, instructions and compact evidence; external recordings/models/voice profiles/environments are not Git backups.'}
    (args.output / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'archives': len(rows), 'bytes': sum(r['bytes'] for r in rows),
                      'filtered': [r['file'] for r in rows if r['kind'] == 'TEXT_ONLY']}))


if __name__ == '__main__':
    main()
