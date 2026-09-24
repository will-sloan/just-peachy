"""Prepare all implemented A0/A2/A3 combinations in a separate release. README.md."""
from copy import deepcopy
from itertools import product
from pathlib import Path
import argparse
import json
import shutil
from common import load, sha, bind, freeze, fingerprint


def expand(document):
    result = deepcopy(document)
    by_key = {r['key']:r for r in result['backends']}
    for a,d,e in product(('A2','A3'),('D0','D1'),('E0','E1')):
        if (d,e) == ('D1','E0'):
            continue
        row = deepcopy(by_key['nemotron_600m' if a == 'A2' else 'nemotron_35_600m'])
        donor = by_key[{('D0','E0'):'baseline',('D0','E1'):'titanet',('D1','E1'):'nemotron_titanet'}[(d,e)]]
        row.update(key='n4_'+a.lower()+'_'+d.lower()+'_'+e.lower(),
            label=f'{a} / {d} / {e} · validation pending',
            reason='N4 composition wiring implemented; numerical and resource admission pending')
        composition = row['composition']
        for component in ('diarization','enrollment'):
            composition['components'][component] = deepcopy(donor['composition']['components'][component])
        composition['n2'] = dict(diarization=d,embedding=e,streaming_profile='low_latency')
        row['capacity'] = deepcopy(donor['capacity'])
        row['manifest_id'] = 'sha256:'+fingerprint(composition)
        result['backends'].append(row)
    if len({r['manifest_id'] for r in result['backends']}) != len(result['backends']):
        raise ValueError('Duplicate composition')
    return result


def main(args):
    receipt = load(args.source_receipt)
    source = Path(receipt['prototype']).resolve()
    for rel,row in receipt['files'].items():
        file = source/rel
        if file.stat().st_size != row['bytes'] or sha(file) != row['sha256']:
            raise ValueError('Parent frozen source differs: '+rel)
    if args.output.exists():
        raise ValueError('Fresh derivative release required; preserve previous evidence')
    args.output.mkdir(parents=True)
    destination = args.output/'prototype'
    destination.mkdir()
    # Copy only receipt-bound files. No unrecorded caches, tests, assets or symlinks.
    for rel in receipt['files']:
        target = destination/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/rel,target)
    document = expand(load(source/'config/backends.json'))
    (destination/'config/backends.json').write_text(json.dumps(document,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
    test_path=destination/'tests/test_backend_catalog.py'
    old="{'baseline','nemotron_hybrid','titanet','nemotron_titanet','nemotron_600m','nemotron_35_600m'}"
    # Deterministic fixture update; model behavior and shared front end stay exact.
    updated='{'+','.join(repr(k) for k in sorted(r['key'] for r in document['backends'] if r['implemented']))+'}'
    test_source=test_path.read_text(encoding='utf-8')
    if test_source.count(old)!=1:
        raise ValueError('Parent catalog test changed; review before generating')
    test_path.write_text(test_source.replace(old,updated),encoding='utf-8')
    changed = [rel for rel,row in receipt['files'].items() if sha(destination/rel) != row['sha256']]
    if set(changed) != {'config/backends.json','tests/test_backend_catalog.py'}:
        raise ValueError('Derivative changed more than the composition catalog and its expected-set test: '+str(changed))
    files = {str(p.relative_to(destination)).replace('\\','/'):dict(sha256=sha(p),bytes=p.stat().st_size)
             for p in sorted(destination.rglob('*')) if p.is_file()}
    result = dict(schema='n4-catalog-derivative-v1',status='IMPLEMENTED_NOT_NUMERICALLY_ADMITTED',
        prototype=str(destination.resolve()),parent=bind(args.source_receipt),changed_files=changed,
        files=files,files_sha256=fingerprint(files),
        common_ui_source_sha256=receipt['common_ui_source_sha256'],
        common_ui_files=receipt['common_ui_files'],
        implemented_compositions=12,actual_N4_inference_cells=0,
        N3_bound_source_modified=False,personal_data_accessed=False,
        gates=['N2 final checks','N3 numerical review','D0/E1 C-only association profile',
               'real smoke/regression for each added composition'])
    freeze(args.output/'SOURCE_RECEIPT.json',result)
    freeze(args.output/'BACKEND_CATALOG.json',document)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','common_ui_files')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-receipt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
