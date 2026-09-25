"""Prepare 16 wired combinations from accepted N3 source; README_COMPOSITIONS.md."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import argparse
import json
import shutil
from common import load, sha, bind, freeze, fingerprint

DONORS = {('D0', 'E0'): 'baseline', ('D0', 'E1'): 'titanet',
          ('D1', 'E0'): 'nemotron_hybrid', ('D1', 'E1'): 'nemotron_titanet'}
ASR_BASES = {'A1': ('compact_eou', 'D0', 'E0'),
            'A2': ('nemotron_600m', 'D1', 'E0'),
            'A3': ('nemotron_35_600m', 'D1', 'E0')}


def inventory(document):
    rows = {}
    for row in document['backends']:
        if not row['implemented']: continue
        composition = row['composition']
        if set(composition) & {'mode', 'recipe', 'tap', 'roster', 'seat_truth', 'selected_ids'}:
            raise ValueError('Composition cannot contain user intent or evaluator truth')
        if row['manifest_id'] != 'sha256:' + fingerprint(composition):
            raise ValueError('Composition hash mismatch')
        a = composition.get('n3', {}).get('variant', 'A0')
        identity = composition.get('n2', dict(diarization='D0', embedding='E0'))
        key = (a, identity['diarization'], identity['embedding'])
        if key in rows: raise ValueError('Duplicate factorial composition')
        if a not in ('A0', 'A1', 'A2', 'A3') or key[1] not in ('D0', 'D1') or key[2] not in ('E0', 'E1'):
            raise ValueError('Unreviewed component in core factorial matrix')
        rows[key] = row
    return rows


def expand(document):
    result = deepcopy(document)
    by_key = {r['key']: r for r in result['backends']}
    if len(by_key) != len(result['backends']): raise ValueError('Duplicate backend key')
    present = inventory(result)
    for identity, key in DONORS.items():
        if ('A0', *identity) not in present or present[('A0', *identity)]['key'] != key:
            raise ValueError('Exact implemented A0 identity donor missing')
    for a, (base, initial_d, initial_e) in ASR_BASES.items():
        if (a, initial_d, initial_e) not in present or present[(a, initial_d, initial_e)]['key'] != base:
            raise ValueError('Missing implemented N3 adapter: ' + a)
        template = by_key[base]
        if a == 'A1':
            asr = template['composition']['n3']
            if not isinstance(asr.get('bundle_sha256'), str) or len(asr['bundle_sha256']) != 64 or asr.get('frontend_policy') != 'eval_no_dither':
                raise ValueError('A1 requires its explicit qualified portable bundle')
        for d, e in product(('D0', 'D1'), ('E0', 'E1')):
            if (a, d, e) in present: continue
            row = deepcopy(template); donor = by_key[DONORS[(d, e)]]
            row.update(key='n4_' + '_'.join((a, d, e)).lower(),
                label=f'{a} / {d} / {e} · validation pending',
                reason='N4 composition wiring implemented; numerical, calibration and resource admission pending')
            composition = row['composition']
            for component in ('diarization', 'enrollment'):
                composition['components'][component] = deepcopy(donor['composition']['components'][component])
            composition['n2'] = dict(diarization=d, embedding=e, streaming_profile='low_latency')
            row['capacity'] = deepcopy(donor['capacity'])
            row['manifest_id'] = 'sha256:' + fingerprint(composition)
            result['backends'].append(row)
    actual = inventory(result)
    if set(actual) != set(product(('A0', 'A1', 'A2', 'A3'), ('D0', 'D1'), ('E0', 'E1'))):
        raise ValueError('Incomplete intended factorial matrix')
    return result


def contained(root, relative):
    original = root / relative
    path = original.resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or not path.is_file() or original.is_symlink():
        raise ValueError('Source inventory must contain ordinary internal files')
    return path


def main(args):
    receipt = load(args.source_receipt); source = Path(receipt['prototype']).resolve(strict=True)
    for rel, row in receipt['files'].items():
        file = contained(source, rel)
        if file.stat().st_size != row['bytes'] or sha(file) != row['sha256']:
            raise ValueError('Parent frozen source differs: ' + rel)
    document = expand(load(source / 'config/backends.json'))
    if args.output.exists(): raise ValueError('Fresh derivative release required')
    destination = args.output / 'prototype'; destination.mkdir(parents=True)
    for rel in receipt['files']:
        target = destination / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / rel, target)
    auxiliary = {}
    for rel, row in receipt.get('auxiliary_files', {}).items():
        original = contained(source.parent, rel)
        if sha(original) != row['sha256'] or original.stat().st_size != row['bytes']:
            raise ValueError('Parent auxiliary file differs')
        target = args.output / rel; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target); auxiliary[rel] = row
    (destination / 'config/backends.json').write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    test_path = destination / 'tests/test_backend_catalog.py'
    old = "{'baseline','nemotron_hybrid','titanet','nemotron_titanet','compact_eou','nemotron_600m','nemotron_35_600m'}"
    test_source = test_path.read_text(encoding='utf-8')
    if test_source.count(old) != 1: raise ValueError('Parent catalog expectation changed; review it')
    updated = '{' + ','.join(repr(k) for k in sorted(r['key'] for r in document['backends'] if r['implemented'])) + '}'
    test_path.write_text(test_source.replace(old, updated), encoding='utf-8')
    changed = [rel for rel, row in receipt['files'].items() if sha(destination / rel) != row['sha256']]
    if set(changed) != {'config/backends.json', 'tests/test_backend_catalog.py'}:
        raise ValueError('Only the catalog and its expected-set fixture may change')
    for rel, digest in receipt['common_ui_files'].items():
        if sha(destination / rel) != digest: raise ValueError('Frozen UI changed')
    files = {str(p.relative_to(destination)).replace('\\', '/'): dict(sha256=sha(p), bytes=p.stat().st_size)
             for p in sorted(destination.rglob('*')) if p.is_file()}
    result = dict(schema='n4-catalog-derivative-v2', status='IMPLEMENTED_NOT_NUMERICALLY_ADMITTED',
        prototype=str(destination.resolve()), parent=bind(args.source_receipt), changed_files=changed,
        files=files, files_sha256=fingerprint(files), auxiliary_files=auxiliary,
        common_ui_source_sha256=receipt['common_ui_source_sha256'], common_ui_files=receipt['common_ui_files'],
        implemented_compositions=16, actual_N4_inference_cells=0,
        N3_bound_source_modified=False, personal_data_accessed=False,
        gates=['Accepted N3 source and final numerical review', 'D0/E1 C-only association profile',
               'Actual smoke/regression for all added compositions', 'Full D0 activity and evidence lifecycle'])
    freeze(args.output / 'SOURCE_RECEIPT.json', result); freeze(args.output / 'BACKEND_CATALOG.json', document)
    print(json.dumps({k: v for k, v in result.items() if k not in ('files', 'common_ui_files', 'auxiliary_files')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
