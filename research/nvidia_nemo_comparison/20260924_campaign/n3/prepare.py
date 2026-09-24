"""Freeze reviewed N3 source and prepare a bound, nonlaunching run plan."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
WORKTREE=HERE.parents[3]
CAMPAIGN=WORKTREE.parent
LOCAL=CAMPAIGN/'local'
PRIVATE=LOCAL/'n3'
PYTHON=Path('C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe')
NEMO_PY=LOCAL/'n2/nemo-py312/Scripts/python.exe'
NEMO_SOURCE=LOCAL/'n2/source/Speech-cf724ac337d1ebc7d0dda1e23fb80916f52927a5'
MODELS=Path('C:/Users/amiri/JustPeachy/shared/models')
load=lambda path:json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Existing preparation must be preserved: '+str(path))
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def bound(path):
    path=Path(path).resolve(strict=True)
    return dict(path=str(path),sha256=sha(path),bytes=path.stat().st_size)


def freeze(release):
    if release.exists():raise ValueError('Use a fresh frozen release')
    prototype=release/'prototype';prototype.mkdir(parents=True)
    previous=load(LOCAL/'releases/n2-common-v7/SOURCE_RECEIPT.json')
    names={name for name in previous['files']
        if '__pycache__' not in Path(name).parts and Path(name).suffix not in ('.pyc','.pyo')}
    names.update(str(p.relative_to(WORKTREE/'prototype')).replace('\\','/') for p in (WORKTREE/'prototype').rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')
        and (p.name.startswith('n3_') or p.name.startswith('README_N3') or p.name=='test_n3_components.py'))
    for name in sorted(names):
        origin=WORKTREE/'prototype'/name
        target=prototype/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(origin,target)
    auxiliary={}
    for name in previous['auxiliary_files']:
        target=release/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(WORKTREE/name,target)
        auxiliary[name]={k:v for k,v in bound(target).items() if k!='path'}
    files={name:{k:v for k,v in bound(prototype/name).items() if k!='path'} for name in sorted(names)}
    ui=previous['common_ui_files']
    if any(files[name]['sha256']!=digest for name,digest in ui.items()):raise ValueError('Frozen shared UI changed')
    if files['config/ui.json']!=previous['files']['config/ui.json']:raise ValueError('Common layout changed')
    runtime={k:v['sha256'] for k,v in files.items() if k.startswith(('app/','vendor/','config/','release_tools/'))
        or k=='main.py' or '/' not in k and Path(k).suffix.lower() in {'.cmd','.bat','.ps1','.sh'}}
    receipt=dict(schema='just-peachy.n1.frozen-source.v1',prototype=str(prototype),
        frontend_runtime_sha256=canonical(runtime),frontend_hash_scope=previous['frontend_hash_scope'],
        common_ui_source_sha256=canonical(ui),common_ui_files=ui,files=files,file_count=len(files),auxiliary_files=auxiliary)
    save(release/'SOURCE_RECEIPT.json',receipt)
    return prototype


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',required=True)
    args=p.parse_args()
    if not args.version.isalnum():raise ValueError('Simple alphanumeric version required')
    release=LOCAL/'releases'/('n3-common-'+args.version)
    output=PRIVATE/('numerical-'+args.version)
    if output.exists():raise ValueError('Fresh numerical output required')
    prototype=freeze(release)
    assets=load(PRIVATE/'assets/FETCH_RESULT.json')['assets']
    payload={(r['variant'],Path(r['filename']).suffix):r for r in assets}
    for row in assets:
        if sha(row['path'])!=row['sha256']:raise ValueError('Changed official model asset')
    bindings={}
    for device,gpu in [('cpu',-1),('cuda',0)]:
        n2=load(LOCAL/('n2/runtime/'+device+'/n2_runtime.json'))
        variants={}
        for variant in ('A2','A3'):
            model=payload[(variant,'.gguf')]
            for right in (1,0):
                binding=dict(schema='just-peachy.n3.native-asr.v1',variant=variant,model_path=model['path'],
                    model_sha256=model['sha256'],model_revision=model['revision'],precision='Q8_0',
                    runtime_revision='97a15afa5caa9bce5baaa86c1184103877af4101',
                    library_path=n2['nemotron_library'],runtime_files=n2['native_runtime_files'],
                    gpu=gpu,right_context=right,language='en-US',stop_history_eou_ms=800,decoder='greedy')
                path=PRIVATE/'runtime'/args.version/device/(variant+'-rc'+str(right)+'.json');save(path,binding)
                bindings[(variant,device,right)]=path
                if right==1:variants[variant]=binding
        save(PRIVATE/'runtime'/args.version/device/'n3_runtime.json',dict(schema='just-peachy.n3.runtime.v1',variants=variants))
    screen=LOCAL/'n2/evaluation/AUDIO_ONLY.json';regression=LOCAL/'n2/evaluation/REGRESSION_AUDIO_ONLY.json'
    # Four fixed manifest rows for reference/native comparisons, not accuracy-selected.
    panel=PRIVATE/('FIXED_PANEL_'+args.version+'.json')
    panel_jobs=load(screen)['jobs'][:4]
    save(panel,dict(schema='n3-audio-only-panel-v1',selection='first four pre-frozen screen manifest rows',jobs=panel_jobs))
    jobs=[]
    def add(identifier,argv,result,*,deps=(),cells=None,gpu=False,timeout=7200,status=None):
        row=dict(id=identifier,argv=[str(x) for x in argv],result=str(result),depends_on=list(deps),
            gpu=gpu,timeout_seconds=timeout)
        if cells is not None:row['expected_cells']=cells
        if status is not None:row['accepted_status']=status
        jobs.append(row)
    add('prototype-suite',[PYTHON,'-B',HERE.parent/'n2/check_suite.py','--source',prototype,'--output',output/'suite','--cpu',4],output/'suite/RESULT.json')
    def asr(identifier,variant,runtime,manifest,*,device='cpu',right=1,deps=(),paced=False,limit=None,timeout=43200):
        py=NEMO_PY if runtime=='reference' else PYTHON
        argv=[py,'-B',HERE/'run_asr.py','--prototype',prototype,'--audio-manifest',manifest,'--models-root',MODELS,
            '--output',output/identifier,'--variant',variant,'--runtime',runtime,'--right-context',right,'--cpu',14 if device=='cuda' else 4]
        if runtime=='native':argv+=['--binding',bindings[(variant,device,right)]]
        if runtime=='reference':argv+=['--reference-model',payload[(variant,'.nemo')]['path'],'--reference-source',NEMO_SOURCE]
        if paced:argv+=['--paced']
        if limit:argv+=['--limit',limit]
        count=min(len(load(manifest)['jobs']),limit) if limit else len(load(manifest)['jobs'])
        add(identifier,argv,output/identifier/'RESULT.json',deps=deps,cells=count,gpu=device=='cuda',timeout=timeout)
    # All models receive an early smoke before the larger, amortized screens.
    asr('smoke-A0','A0','sherpa',panel,deps=['prototype-suite'],limit=1,timeout=1800)
    asr('smoke-A1','A1','reference',panel,deps=['prototype-suite'],limit=1,timeout=3600)
    add('probe-A1',[NEMO_PY,'-B',HERE/'probe_native.py','--prototype',prototype,
        '--reference-model',payload[('A1','.nemo')]['path'],'--reference-source',NEMO_SOURCE,
        '--audio-manifest',regression,'--output',output/'probe-A1'],output/'probe-A1/RESULT.json',deps=['smoke-A1'],timeout=7200)
    for variant in ('A2','A3'):
        asr('smoke-'+variant,variant,'native',panel,device='cuda',deps=['prototype-suite'],limit=1,timeout=1800)
    add('A1-export',[NEMO_PY,'-B',HERE/'export_a1.py','--model',payload[('A1','.nemo')]['path'],'--source',NEMO_SOURCE,'--output',output/'A1-export'],
        output/'A1-export/EXPORT_RESULT.json',deps=['prototype-suite'],timeout=7200,
        status=['EXPORTED_ENCODER_DYNAMIC_STATE_PARITY_PASSED'])
    for variant in ('A2','A3'):
        dependency=['smoke-'+variant]
        add('probe-'+variant,[PYTHON,'-B',HERE/'probe_native.py','--prototype',prototype,'--binding',bindings[(variant,'cpu',1)],
            '--audio-manifest',regression,'--output',output/('probe-'+variant)],output/('probe-'+variant)/'RESULT.json',deps=dependency,timeout=7200)
        asr('reference-'+variant,variant,'reference',panel,deps=['prototype-suite'],timeout=10800)
        asr('cpu-panel-'+variant,variant,'native',panel,deps=['probe-'+variant],timeout=7200)
        asr('paced-'+variant,variant,'native',regression,deps=['probe-'+variant],paced=True,limit=4,timeout=7200)
        asr('lower-buffer-'+variant,variant,'native',panel,device='cuda',right=0,deps=dependency,timeout=3600)
    for variant in ('A0','A1','A2','A3'):
        runtime='sherpa' if variant=='A0' else 'reference' if variant=='A1' else 'native'
        device='cuda' if variant in ('A2','A3') else 'cpu'
        asr('screen-'+variant,variant,runtime,screen,device=device,deps=['smoke-'+variant])
        asr('regression-'+variant,variant,runtime,regression,device=device,deps=['smoke-'+variant],timeout=10800)
        if variant in ('A0','A1'):asr('paced-'+variant,variant,runtime,regression,deps=['smoke-'+variant],paced=True,limit=4,timeout=7200)
    gallery=LOCAL/'n2/evaluation/component'
    gui=[PYTHON,'-B',HERE/'gui.py','--source',prototype,'--common-source',LOCAL/'releases/n1-common-v1/prototype',
        '--models-root',MODELS,'--runtime-config',LOCAL/'n2/runtime/cpu/n2_runtime.json',
        '--n3-runtime-config',PRIVATE/'runtime'/args.version/'cpu/n3_runtime.json','--regression-manifest',regression,'--screen-manifest',screen,
        '--e0-gallery',gallery/'E0/runtime_galleries/gallery_69c1a03b24b0c86e7998.json',
        '--e1-gallery',gallery/'E1/runtime_galleries/gallery_69c1a03b24b0c86e7998.json','--output',output/'gui','--timeout-seconds',7200]
    for variant in ('A2','A3'):
        argv=list(gui);argv[argv.index('--output')+1]=output/('gui-'+variant)
        for example in ('boundary','short','returning'):argv+=['--cell',variant+'_'+example]
        add('actual-gui-'+variant,argv,output/('gui-'+variant)/'GUI_PANEL_REPORT.json',deps=['probe-'+variant],timeout=7500)
    runs=[output/('screen-'+a) for a in ('A0','A1','A2','A3')]
    truth=LOCAL/'n2/evaluation/EVALUATOR_TRUTH.json'
    scoring=[PYTHON,'-B',HERE/'score_asr.py','--truth',truth,'--output',output/'analysis']
    text=[PYTHON,'-B',HERE/'compare_text.py','--prototype',prototype,'--models-root',MODELS,'--truth',truth,
        '--grammar',PRIVATE/'itn/export/itn_subset.json','--output',output/'text']
    for run in runs:scoring+=['--run',run];text+=['--run',run]
    add('lexical-comparison',scoring,output/'analysis/LEXICAL_COMPARISON.json',status=['COMPLETE','PARTIAL'],timeout=3600)
    add('text-comparison',text,output/'text/TEXT_COMPARISON.json',timeout=7200)
    add('route-comparison',[PYTHON,'-B',HERE/'compare_routes.py','--root',output,'--output',output/'routes'],
        output/'routes/ROUTE_COMPARISON.json',status=['COMPLETE','PARTIAL'],timeout=1800)
    worker=PRIVATE/('worker-'+args.version+'.json');plan=PRIVATE/('plan-'+args.version+'.json')
    save(worker,dict(argv=[str(PYTHON),'-B',str(HERE/'supervise_n3.py'),'run','--plan',str(plan)],cwd=str(WORKTREE)))
    paths={PYTHON,NEMO_PY,worker,release/'SOURCE_RECEIPT.json',screen,regression,panel,truth,PRIVATE/'itn/export/itn_subset.json'}
    paths.update(p for p in prototype.rglob('*') if p.is_file())
    paths.update(p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.py','.cpp','.json') and '__pycache__' not in p.parts)
    paths.update(p for p in (HERE.parent/'n2').rglob('*.py'))
    paths.add(HERE.parent/'supervision/supervisor.py')
    paths.update(p for p in (PRIVATE/'runtime'/args.version).rglob('*.json'))
    paths.update(Path(row['path']) for row in assets)
    # Pin the complete reviewed NeMo Python/config tree used by both references.
    paths.update(p for p in NEMO_SOURCE.rglob('*') if p.is_file() and p.suffix in ('.py','.yaml','.yml') and '__pycache__' not in p.parts)
    n2dir=LOCAL/'n2/numerical-v2'
    document=dict(schema='just-peachy.n3.queue-plan.v1',created_utc=datetime.now(timezone.utc).isoformat(),
        cwd=str(WORKTREE),output=str(output),state=str(LOCAL/'supervision'),worker_spec=str(worker),
        thread_id='01a0d3df-f647-75f1-bd82-aab88c1f570b',packaging_cutoff_utc='2026-09-28T02:48:19.949192+00:00',
        n2=dict(numerical_result=str(n2dir/'RESULT.json'),chain_result=str(n2dir/'CHAIN_RESULT.json'),
            numerical_contract=load(n2dir/'RESULT.json')['contract_sha256'],chain_contract=load(n2dir/'CHAIN_RESULT.json')['contract_sha256']),
        jobs=jobs,bindings=[bound(p) for p in sorted(paths)])
    save(plan,document)
    print(json.dumps(dict(status='PREPARED_NOT_STARTED',plan=str(plan),plan_sha256=sha(plan),jobs=len(jobs),source_receipt=str(release/'SOURCE_RECEIPT.json'))))


if __name__=='__main__':main()
