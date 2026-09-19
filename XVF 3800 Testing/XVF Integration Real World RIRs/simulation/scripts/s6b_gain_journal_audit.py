"""Read-only gain-variant native PCM audit; README_S6B_GAIN_JOURNAL_AUDIT.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import os
import uuid
import importlib.util
import tempfile
import sys

os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[_key]='1'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def binding(p,expected=None):
    p=Path(p);before=p.stat();h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''):h.update(block)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('File changed while read: '+str(p))
    if expected and h.hexdigest()!=expected:raise RuntimeError('Binding mismatch: '+str(p))
    return dict(path=str(p),bytes=before.st_size,sha256=h.hexdigest())
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.tmp')
    with t.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(t,p)
def pcm(path):
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(path) as w:
        if (w.channels,w.samplerate)!=(1,16000):raise ValueError('Audit only supports prepared mono16k inputs; no resampling')
        h=hashlib.sha256();observed=0;n=w.frames;subtype=w.subtype
        while True:
            data=w.read(1600,dtype='float32',always_2d=True)
            if not data.size:break
            mono=np.mean(data,axis=1,dtype=np.float32)
            if not np.isfinite(mono).all():raise ValueError('Nonfinite source audio')
            b=np.round(np.clip(mono,-1.0,0.999969)*32768.0).astype('<i2').tobytes()
            h.update(b);observed+=len(b)
    if observed!=2*n:raise ValueError('Truncated gain WAV PCM')
    return dict(sha256=h.hexdigest(),bytes=observed,samples=n,duration_sec=n/16000,source_subtype=subtype)


def verify_conversion(spec):
    import numpy as np
    import soundfile as sf
    audio_path=Path(spec['root'])/'app/edge_speech_pipeline/audio.py'
    declared=next(row for row in spec['execution_files'] if Path(row['path'])==audio_path)
    audio_binding=binding(audio_path,declared['sha256'])
    module_spec=importlib.util.spec_from_file_location('s6b_audit_frozen_audio',audio_path)
    module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='s6b_audio_conversion_') as directory:
        for subtype in ('PCM_16','FLOAT'):
            path=Path(directory)/(subtype+'.wav');journal_path=Path(directory)/(subtype+'.pcm')
            values=np.resize(np.array([-1.2,-1.,-.5,-.5/32768,0.,.5/32768,.5,.999969,1.,1.2],dtype=np.float32),1707)
            sf.write(path,values,16000,subtype=subtype)
            expected=pcm(path);journal=module.AudioJournal(journal_path)
            source=module.WavSource(journal,path,target_rate=16000,realtime=False,accelerated_factor=0)
            source.start();source.thread.join(timeout=10)
            if source.thread.is_alive():source.stop();raise RuntimeError('Model-free source fixture timeout')
            assert journal.finished and journal.fatal_error is None
            actual=binding(journal_path)
            assert expected['sha256']==actual['sha256'] and expected['bytes']==actual['bytes'] and journal.committed_samples==1707
            rows.append(dict(source_subtype=subtype,samples=1707,exact_frozen_entrypoint_equal=True))
    return dict(status='PASS',tests=len(rows),rows=rows,frozen_audio=audio_binding,numpy=np.__version__,soundfile=sf.__version__)


def audit(args):
    spec_path=args.report/(args.epoch.upper()+'_EXECUTION_MANIFEST.json');spec=read(spec_path)
    source_index=binding(spec['gain_index']['path'],spec['gain_index']['sha256'])
    out=args.report/'independent_review';out.mkdir(exist_ok=True)
    conversion=verify_conversion(spec)
    ep=out/'R6_EXPECTED_PCM_INDEX.json';bp=out/'R6_EXPECTED_PCM_INDEX_BINDING.json'
    if ep.exists():
        prior=read(bp);binding(ep,prior['sha256']);expected=read(ep)
        if expected['source_gain_index']!=source_index:raise ValueError('Expected PCM source index changed')
    else:
        rows=[]
        for row in read(source_index['path'])['rows']:
            audio=binding(row['audio']['path'],row['audio']['sha256']);body=pcm(audio['path'])
            if abs(body['duration_sec']-row['duration_sec'])>1e-8:raise ValueError('Prepared PCM/index duration differs')
            rows.append(dict(case_id=row['case_id'],stream=row['stream'],audio=audio,pcm=body,
                gain_once=row['raw_gain_applied_once'],input_gain=row['input_gain']))
        expected=dict(schema='s6b-gain-expected-pcm.v2',source_gain_index=source_index,rows=rows,conversion_entrypoint_check=conversion,
            code=binding(__file__),scope='Gain WAV float32 decode and exact frozen AudioJournal clip/round PCM16 quantization derived once; no gain reapplied or inference')
        save(ep,expected);save(bp,binding(ep))
    mapping={(r['case_id'],r['stream']):r for r in expected['rows']}
    if args.panel=='challenge':
        binding(spec['challenge_panel']['path'],spec['challenge_panel']['sha256']);cases=set(read(spec['challenge_panel']['path'])['case_ids'])
    else:cases={k[0] for k in mapping}
    root=Path('G:/Just_Peachy_S6B')/args.report.name/args.epoch/'neural'
    results=[];missing=[]
    for recipe in args.recipes:
        if not recipe.startswith('R6'):raise ValueError('This audit is restricted to gain-variant R6 recipes')
        for case in sorted(cases):
            for stream in ('O0','O1'):
                receipt_path=root/recipe/case/stream/'run_receipt.json'
                if not receipt_path.exists():missing.append(dict(recipe_id=recipe,case_id=case,stream=stream));continue
                receipt_binding=binding(receipt_path);receipt=read(receipt_path)
                if receipt['status']!='COMPLETE':raise ValueError('Non-complete run_receipt encountered')
                source=mapping[case,stream]
                if receipt['identity']['audio']!=source['audio']:raise ValueError('Native receipt points to another gain input')
                journal=binding(receipt['full_journal']['path'],receipt['full_journal']['sha256'])
                equal=journal['sha256']==source['pcm']['sha256'] and journal['bytes']==source['pcm']['bytes']
                binding(receipt_path,receipt_binding['sha256'])
                results.append(dict(recipe_id=recipe,case_id=case,stream=stream,exact_pcm_equal=equal,
                    receipt=receipt_binding,journal=journal,expected_pcm=source['pcm'],gain_audio=source['audio']))
    mismatches=[r for r in results if not r['exact_pcm_equal']]
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    result=dict(schema='s6b-native-gain-pcm-audit.v1',status='FAIL' if mismatches else 'COMPLETE_PASS' if not missing else 'PARTIAL_PASS',
        created_utc=stamp,epoch=args.epoch,panel=args.panel,recipes=args.recipes,expected_jobs=len(cases)*2*len(args.recipes),
        checked_jobs=len(results),mismatch_count=len(mismatches),missing_count=len(missing),rows=results,missing=missing,
        expected_pcm_index=binding(ep),epoch_manifest=binding(spec_path),auditor=binding(__file__),conversion_entrypoint_check=conversion,
        inference_reruns=0,active_source_mutations=0,scope='Independent prepared-WAV float32 decode/AudioJournal quantization versus native PCM16 journal equality. Existing completion receipts only; missing work is not silently counted as validated.')
    path=out/'gain_pcm_audits'/('AUDIT_'+stamp+'.json');save(path,result)
    save(out/'R6_NATIVE_PCM_AUDIT_LATEST.json',dict(status=result['status'],audit=binding(path)))
    return {k:result[k] for k in ('status','expected_jobs','checked_jobs','mismatch_count','missing_count')}|{'report':str(path)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--report',type=Path,required=True);p.add_argument('--epoch',default='epoch2')
    p.add_argument('--panel',choices=('challenge','all'),default='challenge');p.add_argument('--recipes',nargs='+',default=['R6','R6_FULL_RMS'])
    a=p.parse_args();result=audit(a);print(json.dumps(result,indent=2));raise SystemExit(1 if result['status']=='FAIL' else 0)
