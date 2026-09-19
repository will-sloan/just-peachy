"""One paired mono O0/O1 interoperability smoke through unchanged H2."""
import argparse,collections,dataclasses,json,os,subprocess,sys,time
from pathlib import Path
from s0_common import ROOT,SIM,H2,EDGE_PYTHON,HashCache,Progress,read,save,now

def run(report,hardware):
    report=Path(report);hardware=Path(hardware)
    restoration=read(hardware/'restoration.json');summary=read(hardware/'hardware_summary.json')
    assert restoration['status']=='PASS' and restoration['hardware_lease_released']
    assert restoration['audio_handles_closed'] and restoration['telemetry_process_closed']
    assert summary['status']=='BOUNDED_CASES_CAPTURED'
    target=report/'h2_smoke';target.mkdir(exist_ok=False);cache=HashCache()
    baseline=read(SIM/'reports/S0/20260908T181703Z/baseline_manifest.json')
    bindings=[cache.bind(Path(b['path']),b['sha256']) for b in baseline['source_bindings']]
    assert all(b['status']=='BOUND' for b in bindings),'H2 implementation changed since S0'
    sys.path.insert(0,str(H2));from app.edge_speech_pipeline.config import PipelineConfig
    import soundfile as sf
    config=PipelineConfig();assets=[dataclasses.asdict(a) for a in config.assets]
    before={str(a.path):[a.path.stat().st_size,a.path.stat().st_mtime_ns] for a in config.assets}
    results=[]
    with Progress(report,'S3_H2_paired_file_smoke',2) as progress:
        for stream in ['O0','O1']:
            source=(hardware/'T3_ABA_repeat1'/f'{stream}.wav').resolve();info=sf.info(source)
            assert info.channels==1 and info.samplerate==16000,'Explicit mono only: never average six channels'
            data_root=target/(stream+'_empty_data');data_root.mkdir();assert not list(data_root.iterdir())
            env=dict(os.environ);env['EDGE_SPEECH_DATA_ROOT']=str(data_root.resolve());env['PYTHONDONTWRITEBYTECODE']='1'
            argv=[str(EDGE_PYTHON),'-m','app.edge_speech_pipeline','file',str(source),'--accelerated']
            progress.detail=stream;started=time.monotonic();error=None;code=None
            with (target/(stream+'_stdout.jsonl')).open('wb') as out,(target/(stream+'_stderr.txt')).open('wb') as err:
                try:code=subprocess.run(argv,cwd=H2,env=env,stdout=out,stderr=err,timeout=240,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).returncode
                except Exception as e:error=repr(e)
            summaries=list(data_root.glob('edge_speech_sessions/*/session_summary.json'))
            session=read(summaries[0]) if len(summaries)==1 else None
            events=[json.loads(l) for l in (summaries[0].parent/'events.jsonl').read_text().splitlines()] if session else []
            counts=dict(collections.Counter(e.get('event_type') for e in events))
            result={'stream':stream,'input':cache.bind(source),'channels':info.channels,'sample_rate_hz':info.samplerate,'duration_s':info.duration,
                'argv':argv,'cwd':str(H2),'isolated_data_root':str(data_root.resolve()),'initial_profile_files':0,
                'exit_code':code,'exception':error,'elapsed_s':time.monotonic()-started,'event_counts':counts,
                'final_transcript_payloads':[e['payload'] for e in events if e.get('event_type')=='transcript_final'],
                'error_events':[e for e in events if any(t in str(e.get('event_type','')).lower() for t in ['error','drop','exception'])],
                'session_summary':session,'status':'PASS' if code==0 and session and session.get('state')=='COMPLETED' else 'FAIL'}
            save(target/(stream+'_result.json'),result);results.append(result);progress.done+=1
    unchanged=all(before[str(a.path)]==[a.path.stat().st_size,a.path.stat().st_mtime_ns] for a in config.assets)
    result={'schema_version':'jp_s3_h2_smoke_v1','created_utc':now(),'status':'PASS' if all(r['status']=='PASS' for r in results) and unchanged else 'FAIL',
        'results':results,'source_bindings':bindings,'config':dataclasses.asdict(config),'assets':assets,'assets_stat_unchanged':unchanged,
        'asset_hash_validation':'Each unmodified H2 invocation validates all eight assets internally; completed runtime receipts reused, no redundant external weight hashing.',
        'scope':'Two explicit mono streams from the same physical conversation pass; interoperability only. Empty isolated profiles, no enrollment/naming evaluation, no ASR winner.'}
    save(report/'h2_smoke.json',result);cache.flush();print(json.dumps({'status':result['status'],'cases':[{'stream':r['stream'],'status':r['status'],'elapsed_s':r['elapsed_s'],'events':r['event_counts']} for r in results]},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--hardware',required=True);a=p.parse_args();run(a.report,a.hardware)
