"""One-time, hash-checked migration. See README.md; never modifies S7."""
import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seed', type=Path, required=True)
    p.add_argument('--models', type=Path, required=True)
    a = p.parse_args()
    dest = Path(__file__).resolve().parents[1]
    seed = json.loads(a.seed.read_text(encoding='utf-8-sig'))
    config_path = Path(seed['public_config']['path'])
    assert digest(config_path) == seed['public_config']['sha256']
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    copied = []
    for row in seed['source_files']:
        src = Path(seed['source_root']) / row['relative_path']
        assert digest(src) == row['sha256'], str(src)
        out = dest / 'vendor' / row['relative_path']
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            shutil.copy2(src, out)
        copied.append(row)
    assets = []
    for row in config['assets']:
        src = Path(row['path'])
        assert digest(src) == row['sha256'], str(src)
        out = a.models / row['sha256'] / src.name
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            shutil.copy2(src, out)
        assert digest(out) == row['sha256']
        assets.append({k: row[k] for k in ('component_id', 'sha256', 'deployment_relative_path')} |
                      {'filename': src.name, 'bytes': src.stat().st_size})
    for sub in ('app', 'config', 'evidence', 'tests', 'docs'):
        (dest/sub).mkdir(exist_ok=True)
    (dest/'app'/'__init__.py').touch(exist_ok=True)
    def write(rel, doc):
        (dest/rel).write_text(json.dumps(doc, indent=2)+'\n', encoding='utf-8')
    write('config/assets.json', assets)
    write('config/s7_profiles.json', config['profiles'])
    write('evidence/SOURCE_MIGRATION.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_seed': str(a.seed.resolve()), 'seed_sha256': digest(a.seed),
        'source_root': seed['source_root'], 'source_files': copied,
        'source_configuration_sha256': digest(config_path), 'assets': assets,
        'research_gallery_copied': False, 'historical_source_modified': False,
        'git_head': subprocess.check_output(['git', '-C', str(dest.parent), 'rev-parse', 'HEAD'], text=True).strip(),
        'initial_git_status': subprocess.check_output(['git', '-C', str(dest.parent), 'status', '--short'], text=True)})
    print(json.dumps({'vendor_files': len(copied), 'assets':len(assets), 'models':str(a.models)}))


if __name__ == '__main__':
    main()
