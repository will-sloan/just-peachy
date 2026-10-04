"""Actual descriptor namespace regression; README_CURRENT_BACKUP_SCOPE_V4.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import copy
import hashlib
import json
from pathlib import Path
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, required=True)
    args = parser.parse_args()
    output = args.private/'live-runtime-20261003'/('current-scope-v4-'+uuid.uuid4().hex)
    output.mkdir()
    process = psutil.Process()
    (output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=process.pid,
        create_time=process.create_time(), affinity=process.cpu_affinity())))
    root = Path(__file__).parent
    sources = []
    for name in ('discover_production_backup_action_v4.py', 'check_current_scope_v4.py',
                 'README_CURRENT_BACKUP_SCOPE_V4.md'):
        raw = (root/name).read_bytes()
        for folder in ('backup', 'independent-restore'):
            destination = output/folder/name
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(raw)
            assert destination.read_bytes() == raw
        if name.endswith('.py'): compile(raw, name, 'exec')
        sources.append(dict(name=name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    (output/'SOURCE_CLOSED.json').write_text(json.dumps(dict(files=sources, independent_restore=True)))
    from discover_production_backup_action_v4 import validate_gallery_namespaces
    rows = []; titan = None
    for version in (27, 28):
        folder = args.private/('field-runtime-v%d-install'%version)/'stage-backup'/('field-runtime-v%d-profiles'%version)
        for path in sorted(folder.glob('*.json')):
            if path.name == 'COMMON_BUNDLE.json': continue
            raw = path.read_bytes(); value = json.loads(raw)
            keys = validate_gallery_namespaces(value)
            rows.append(dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), namespaces=keys))
            if value['runtime_profile']['definition']['selection']['embedding'] == 'E1': titan = value
    assert len(rows) == 20 and titan is not None
    rejected = []
    for label in ('missing_titanet', 'unknown_namespace', 'bad_schema', 'bad_type'):
        value = copy.deepcopy(titan)
        if label == 'missing_titanet': del value['runtime_profile']['galleries']['E1']
        elif label == 'unknown_namespace': value['runtime_profile']['galleries']['E2'] = {}
        elif label == 'bad_schema': value['schema'] = 'unknown'
        else: value['runtime_profile']['galleries'] = []
        try: validate_gallery_namespaces(value)
        except ValueError: rejected.append(label)
        else: raise AssertionError('Accepted '+label)
    result = dict(passed=True, actual_descriptors=rows, rejected=rejected,
        native_actions=False, galleries_modified=False)
    (output/'RESULT.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(dict(output=str(output), passed=True, actual_descriptors=len(rows), rejects=len(rejected))))


if __name__ == '__main__': main()
