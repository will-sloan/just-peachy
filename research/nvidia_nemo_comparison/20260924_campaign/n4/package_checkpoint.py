"""Publish redacted preparation receipts and an explicitly partial ZIP. README_PACKAGE.md."""
import argparse
from datetime import datetime,timezone
from itertools import product
from pathlib import Path
import csv
import json
import shutil
import zipfile
from common import bind,load,freeze,sha,fingerprint
from check_readiness import inspect

HERE=Path(__file__).resolve().parent


def main(args):
    local=args.local
    public=args.public
    for name in ('N4_METRICS.json','MATRIX.json','PREPARATION_TESTS.json','CHECKPOINT_CONTENTS.json'):
        if (public/name).exists():raise ValueError('Existing published checkpoint: use a fresh public directory')
    public.mkdir(parents=True,exist_ok=True)
    source=load(local/'releases/n4-catalog-v2/SOURCE_RECEIPT.json')
    catalog=load(local/'releases/n4-catalog-v2/BACKEND_CATALOG.json')
    base=next(r for r in catalog['backends'] if r['key']=='baseline')
    if base['manifest_id']!='sha256:1a6be7490786a81d971c19ad35572b8c13c30993f7b8a7c1903f4b0617b6b1b5':
        raise ValueError('Baseline changed')
    a1=next(r for r in load(HERE.parent/'n3/MODEL_REGISTRY.json')['candidates'] if r['variant']=='A1')
    rows=[]
    for a,d,e in product(('A0','A1','A2','A3'),('D0','D1'),('E0','E1')):
        backend=next((r for r in catalog['backends'] if r['implemented'] and
            r['composition'].get('n3',{}).get('variant','A0')==a and
            r['composition'].get('n2',{}).get('diarization','D0')==d and
            r['composition'].get('n2',{}).get('embedding','E0')==e),None)
        if backend:
            composition=backend['composition'];manifest=backend['manifest_id']
        else:
            donor=next(r for r in catalog['backends'] if r['implemented'] and not r['composition'].get('n3') and
                r['composition'].get('n2',{}).get('diarization','D0')==d and r['composition'].get('n2',{}).get('embedding','E0')==e)
            composition=dict(status='INTENDED_NOT_IMPLEMENTED',asr={k:a1[k] for k in ('repository','revision','filename','bytes','sha256','license')},
                diarization=donor['composition']['components']['diarization'],
                embedding=donor['composition']['components']['enrollment'],punctuation=donor['composition']['components']['punctuation'])
            manifest='intended-sha256:'+fingerprint(composition)
        gates=['N2/N3 reviewed numerical admission','real integrated smoke/regression','full-bank runner/storage admission']
        if a=='A1':gates.append('A1 integrated Controller adapter missing')
        if d=='D0' and e=='E1':gates.append('D0/E1 C-only anonymous association profile not validated')
        rows.append(dict(profile='_'.join((a,d,e)),asr=a,diarization=d,embedding=e,
            punctuation='P0' if a in ('A0','A1') else 'P1_native',
            implementation='WIRED_MODEL_FREE_CHECK_PASSED' if backend else 'NOT_IMPLEMENTED',
            backend_key=backend['key'] if backend else None,manifest_id=manifest,composition=composition,
            required=480,completed=0,failed=0,incompatible=0,not_tested=480,
            status='NOT_TESTED',gates=gates,deployment_tier='UNKNOWN',rescue_used=0))
    freeze(public/'MATRIX.json',dict(schema='n4-preparation-matrix-v1',rows=rows))
    columns=['profile','asr','diarization','embedding','punctuation','implementation','manifest_id',
             'required','completed','failed','incompatible','not_tested','status','deployment_tier']
    with (public/'MATRIX.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        writer.writerows({k:r[k] for k in columns} for r in rows)
    snapshots={
        'PREPARATION_RECEIPT.json':local/'n4/preparation-v1/PREPARATION_RECEIPT.json',
        'CATALOG_CHECK.json':local/'n4/catalog-check-v2/RESULT.json',
        'METRIC_ENVIRONMENT.json':local/'n4/metrics/environment-v1/SUMMARY.json',
        'METRIC_BUILD.json':local/'n4/metrics/msvc20-v1/BUILD_RECEIPT.json',
        'SCORING_SMOKE.json':local/'n4/metrics/scoring-smoke-v1.json',
        'STORAGE_PROBE.json':local/'n4/storage/d1e0-first-cell-v1.receipt.json',
        'PLOT_RECEIPT.json':local/'n4/plots-v1/PLOT_RECEIPT.json'}
    for name,path in snapshots.items():freeze(public/name,load(path))
    freeze(public/'SOURCE_DERIVATION.json',{k:v for k,v in source.items() if k!='files'})
    freeze(public/'READINESS.json',inspect(local))
    log=local/'n4/metrics/tests-v4.log'
    text=log.read_text(encoding='utf-8')
    if 'Ran 27 tests' not in text or not text.rstrip().endswith('OK'):
        raise ValueError('Missing actual passing test log')
    freeze(public/'PREPARATION_TESTS.json',dict(status='PASS_PREPARATION_ONLY',
        n4_tests=dict(run=27,passed=27,log=bind(log)),
        inherited_catalog_asr_text_tests=dict(run=15,passed=15,scope='N4 v2 derivative; tool execution receipt'),
        actual_controller_selection_cases=12,actual_models_loaded=0,
        existing_N2_cells_rescored=2,N4_inference_cells=0,
        source_code=[bind(p) for p in sorted(HERE.glob('*.py'))],
        previous_issues=['MSVC default build failed; C++20 unmodified source succeeds',
                         'Empty-reference JER denominator fixed; retains false alarms',
                         'V1 expected catalog test set superseded by V2 fixture']))
    freeze(public/'N4_METRICS.json',dict(schema='n4-stage-checkpoint-v1',stage_status='PARTIAL_PREPARATION_NOT_COMPLETE',
        generated_utc=datetime.now(timezone.utc).isoformat(),required_profiles=16,wired_profiles=12,
        actual_N4_neural_calls=0,required_cells=7680,completed_cells=0,failed_cells=0,incompatible_cells=0,not_tested_cells=7680,
        scenes=240,taps=['O0','O1'],shortlist=[],default_promoted=False,
        accuracy=None,naming=None,resource_tiers='UNKNOWN',paced_GUI_cells=0,continuity_candidates_tested=0,
        target_device='NOT_TESTED_PI_OFF',scope='Preparation evidence only',
        primary_remaining=['N2/N3 acceptance','A1 integrated adapter','D0/E1 association calibration',
            'full D0 activity timeline','integrated runner and bounded archive lifecycle','full matrix',
            'mode/gallery naming analysis','isolated resources','shortlist GUI and continuity'],
        automatic_N4_queue_registered=False,automatic_LLM_resume_verified=False))
    for name in ('BANK_COVERAGE.png','BANK_COVERAGE.svg'):
        shutil.copyfile(local/'n4/plots-v1'/name,public/name)
    env=local/'n4/metrics/environment-v1'
    shutil.copyfile(env/'THIRD_PARTY_NOTICES.md',public/'METRIC_THIRD_PARTY_NOTICES.md')
    shutil.copyfile(env/'requirements.txt',public/'metric-requirements.txt')
    requirements=(env/'requirements.txt').read_text(encoding='utf-8').splitlines()
    (public/'metric-dependency-requirements.txt').write_text('\n'.join(r for r in requirements if not r.lower().startswith('meeteval=='))+'\n',encoding='utf-8')
    freeze(public/'METRIC_DISTRIBUTIONS.json',dict(
        dependency_downloads=[dict(name=r['metadata']['name'],version=r['metadata']['version'],download=r['download_info'])
            for r in load(local/'n4/metrics/dependency-install.json')['install']],
        meeteval_source=load(local/'n4/metrics/msvc20-v1/install.json')['install'][0]['download_info']))
    allowed={'.md','.py','.json','.csv','.txt','.png','.svg'}
    paths=sorted(p for p in public.iterdir() if p.is_file() and p.suffix in allowed)
    if any(p.is_symlink() or p.resolve().parent!=public.resolve() for p in paths):
        raise ValueError('Only reviewed flat checkpoint files can enter the ZIP')
    freeze(public/'CHECKPOINT_CONTENTS.json',dict(status='PARTIAL_PREPARATION',files=[bind(p) for p in paths],
        excluded='All private audio, full transcripts, galleries/vectors, models, raw logs and full runtime source trees'))
    paths.append(public/'CHECKPOINT_CONTENTS.json')
    args.zip.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.zip,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in paths:archive.write(path,path.name)
    with zipfile.ZipFile(args.zip) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP CRC failure')
        if len(archive.namelist())!=len(paths):raise ValueError('ZIP entry count differs')
        import hashlib
        for path in paths:
            if hashlib.sha256(archive.read(path.name)).hexdigest()!=sha(path):raise ValueError('ZIP content changed')
    if args.zip.stat().st_size>20*1024**2:raise ValueError('Checkpoint exceeds hard 20 MiB limit')
    freeze(public/'ZIP_CHECKPOINT.json',dict(status='VERIFIED_PREPARATION_CHECKPOINT_NOT_FINAL_N4',
        artifact=bind(args.zip),files=len(paths),target_limit_bytes=10*1024**2,hard_limit_bytes=20*1024**2))
    print(json.dumps(dict(zip=bind(args.zip),files=len(paths),stage='PARTIAL_PREPARATION'),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--local',type=Path,default=Path('G:/Just_Peachy_N1/20260924_campaign/local'))
    p.add_argument('--public',type=Path,default=HERE);p.add_argument('--zip',type=Path,required=True)
    main(p.parse_args())
