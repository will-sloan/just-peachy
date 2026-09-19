"""Inventory current H2 and execute one existing offline fixture; no source edits."""
import argparse, collections, dataclasses, importlib.metadata, os, platform, subprocess, sys, time
from s0_common import *

def run(report):
    report=Path(report); cache=HashCache(); sys.path.insert(0,str(H2))
    from app.edge_speech_pipeline.config import PipelineConfig
    import onnxruntime as ort
    import soundfile as sf
    original=PipelineConfig()
    versions={}
    for name in ['numpy','scipy','soundfile','sounddevice','onnxruntime','sherpa-onnx','psutil','pytest']:
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]=None
    fixture=H2/'artifacts/realtime_test_audio/aew_rxr_eey_arctic_a0301_concat.wav'
    fixture_binding=cache.bind(fixture)
    source_paths=list((H2/'app/edge_speech_pipeline').glob('*.py'))+[
        H2/'scripts/run_edge_speech_pipeline.ps1',H2/'app/edge_speech_pipeline/README.md',
        H2/'app/edge_speech_pipeline/H2_PRE_XVF_HANDOFF.md',H2/'app/edge_speech_pipeline/BUILD_VALIDATION_REPORT.md']
    sources=[cache.bind(p) for p in source_paths]
    manifests=[]
    for asset in original.assets:
        p=asset.path.with_suffix(asset.path.suffix+'.manifest.json')
        if p.exists():
            d=read(p);manifests.append({'binding':cache.bind(p),'component_id':d.get('component_id'),
                'source_asset_checks_historical':d.get('source_asset_checks'),
                'source_asset_set_sha256':d.get('source_asset_set_sha256'),
                'status_at_export':d.get('status'),'active_onnx_sha256':d.get('onnx_sha256')})
    profiles=[]
    for p in original.profile_root.glob('*.json'):
        try:
            d=read(p);profiles.append({'backend_id':d.get('backend_id'),'backend_sha256':d.get('backend_sha256'),
                                    'vector_file_exists':p.with_suffix('.npy').is_file()})
        except Exception:profiles.append({'status':'UNREADABLE_METADATA'})
    root=report/'smoke_data'
    if root.exists() and list(root.rglob('session_summary.json')):
        raise FileExistsError('This report already contains a smoke; use a new report directory to rerun it')
    env=dict(os.environ);env['EDGE_SPEECH_DATA_ROOT']=str(root);env['PYTHONDONTWRITEBYTECODE']='1'
    argv=[str(EDGE_PYTHON),'-m','app.edge_speech_pipeline','file',str(fixture),'--accelerated']
    specs=[dataclasses.asdict(a) for a in original.assets]
    before={str(a.path):[a.path.stat().st_size,a.path.stat().st_mtime_ns] for a in original.assets if a.path.exists()}
    started=time.monotonic(); failure=None; code=None
    with Progress(report,'h2_offline_smoke',1) as progress:
        try:
            with (report/'h2_smoke_stdout.jsonl').open('wb') as out, (report/'h2_smoke_stderr.txt').open('wb') as err:
                completed=subprocess.run(argv,cwd=H2,env=env,stdout=out,stderr=err,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                code=completed.returncode
        except Exception as exc:failure=type(exc).__name__+': '+str(exc)
        progress.done=1
    wall=time.monotonic()-started
    summaries=list(root.glob('edge_speech_sessions/*/session_summary.json'))
    summary=read(summaries[0]) if len(summaries)==1 else None
    events=[]
    if summaries:
        events=[json.loads(l) for l in (summaries[0].parent/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        save(report/'h2_smoke_session_summary.json',summary)
    counts=dict(collections.Counter(e.get('event_type') for e in events))
    finals=[e['payload'] for e in events if e.get('event_type')=='transcript_final']
    complete=code==0 and summary and summary.get('state')=='COMPLETED'
    assets=[]
    for spec,a in zip(specs,original.assets):
        unchanged=a.path.exists() and before.get(str(a.path))==[a.path.stat().st_size,a.path.stat().st_mtime_ns]
        assets.append({**spec,'path':str(a.path),'bytes':a.path.stat().st_size if a.path.exists() else None,
            'status':'FRESH_RUNTIME_CHECKSUM_VALIDATED' if complete and unchanged else 'NOT_PROVEN_BY_COMPLETED_SMOKE',
            'validation_scope':'Unmodified models.py calls validate_assets for two speaker assets and six Sherpa/punctuation assets before inference; no duplicate external weight hashing',
            'observed_sha256':a.sha256 if complete and unchanged else None})
    info=sf.info(fixture) if fixture.exists() else None
    manifest={'schema_version':'jp_s0_h2_baseline_v1','observed_utc':now(),'python':sys.executable,
        'python_version':platform.python_version(),'versions':versions,'onnxruntime_available_providers':ort.get_available_providers(),
        'active_provider':'CPUExecutionProvider / Sherpa cpu','ambient_overrides':{k:os.environ.get(k) for k in ['EDGE_SPEECH_ASSET_ROOT','EDGE_SPEECH_DATA_ROOT']},
        'config':dataclasses.asdict(original),'assets':assets,'source_bindings':sources,'export_provenance':manifests,
        'checkpoint_training_ancestry':'Active hashes preserved. Export manifests identify b2-vox2-lm.pt and pyannote segmentation-3.0; no current resolver path identifies a newly fine-tuned checkpoint. Historical no-fine-tuning text does not authorize changing active weights.',
        'existing_profile_inventory':{'metadata_count':len(profiles),'profiles_without_names':profiles,'names_vectors_audio_not_exported':True},
        'preprocessing':{'mono':'float32 channel mean','sample_rate_hz':16000,'resampler':'existing _StreamingResampler; no resampling for this 16k fixture',
            'journal':'disk PCM16 lossless from journal append onward; independent consumer cursors','ASR':'80-dim features, greedy_search, max_active_paths=4; endpoint rules in config; 0.66s final padding',
            'embedding':'raw float32 mono waveform -> 192-dim L2-normalized ReDimNet2-B2 embedding','segmentation':'fixed 160000-sample window; powerset-to-speech/overlap; thresholds in config',
            'punctuation':'final only, learned INT8 model; raw hypothesis preserved'},
        'identity_memory':{'anonymous':'session-local normalized running centroid; cosine threshold 0.35; no cross-session anonymous memory persisted',
            'enrollment':'ReDimNet2-B2 shared with tracking, backend ID/hash and shape (192,) checked',
            'names':'score, margin and evidence gate; tentative name before minimum evidence; anonymous fallback',
            'evidence_limit':'elapsed source time since cluster first observation, not calibrated independent speech duration',
            'spatial':'inactive contract; no XVF result effects'},
        'smoke':{'argv':argv,'cwd':str(H2),'environment_overrides':{'EDGE_SPEECH_DATA_ROOT':str(root),'PYTHONDONTWRITEBYTECODE':'1'},
            'fixture':fixture_binding,'fixture_duration_sec':info.duration if info else None,'fixture_channels':info.channels if info else None,
            'fixture_subtype':info.subtype if info else None,'exit_code':code,'failure':failure,'wall_sec':wall,
            'status':'COMPLETED' if complete else 'FAILED','event_counts':counts,'final_payloads':finals,'session_summary':summary,
            'scope':'Existing accelerated file path (4x paced source), ASR, punctuation, segmentation, anonymous tracking, journaling. Empty isolated profile gallery; no enrollment identity accuracy, GUI, live microphone, XVF, CM5 or broad accuracy validation.'}}
    save(report/'baseline_manifest.json',manifest);cache.flush()
    print(json.dumps({'smoke_status':manifest['smoke']['status'],'wall_sec':wall,'events':counts,'assets_validated':sum(a['status']=='FRESH_RUNTIME_CHECKSUM_VALIDATED' for a in assets)},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(a.report)
