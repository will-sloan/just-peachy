"""CM5 metadata-only preparation and inspection; README_S6D_CM5_PREPARATION.md."""
from __future__ import annotations
import argparse, hashlib, json, platform, shutil, wave
from pathlib import Path
MANIFEST_SHA='395dab640489f9e91545584fe17af60eb1b4e4332458c14ea1997da340769c8b'
PINS={'numpy':'2.2.6','scipy':'1.15.3','PyYAML':'6.0.3','soundfile':'0.13.1','sounddevice':'0.5.5','psutil':'7.2.2','onnxruntime':'1.29.0','sherpa-onnx':'1.13.4'}
CASES=[('S45_03_03','six metadata-declared subsecond whole replies'),('S45_02_10','three-person sequential switches and returns'),('S45_11_03','instrumental music-fma-0060_s00 at nominal 0 dB SNR')]

def bind(path,expected=None):
    path=Path(path).resolve();before=path.stat();h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Changed file')
    v=dict(path=str(path),bytes=after.st_size,sha256=h.hexdigest())
    if expected is not None and v['sha256']!=expected:raise ValueError('Hash mismatch: '+str(path))
    return v

def verify(v,path=None):
    a=bind(path or v['path'],v['sha256'])
    if a['bytes']!=v['bytes']:raise ValueError('Byte count differs')
    return a
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
    return bind(p)

def prepare(repo,report,output):
    repo,report,output=repo.resolve(),report.resolve(),output.resolve()
    if output.exists():raise ValueError('Fresh output required')
    sim=report.parent.parent.parent
    ab=bind(report/'application/native_confirmation_predecl_v1/REPAIRED_GUIV3_MANIFEST.json',MANIFEST_SHA);a=read(ab['path'])
    bp=sim/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json';ip=sim/'reports/S6B/20260909T230840Z/INPUT_INDEX.json'
    bank=read(bp);scenes={s['case_id']:s for s in bank['scenes']};inputs={(s['case_id'],s['stream']):s for s in read(ip)['rows']}
    h2=repo/'Software Validation from Datasets/Evaluation Tool';req=h2/'deployment/h2_arm64/requirements-linux-arm64.txt'
    pins=dict(x.split('==') for x in req.read_text().splitlines() if x and not x.startswith('#'))
    if pins!=PINS:raise ValueError('Inherited pins changed')
    root=Path(a['source_root'])
    sources=[dict(role='source',binding=verify(v),target_relative='app/'+Path(v['path']).relative_to(root).as_posix()) for v in a['execution_files']]
    assets=[dict(role='asset',component_id=v['component_id'],binding=verify(v['binding']),target_relative=v['deployment_relative_path']) for v in a['assets']]
    if len(sources)!=45 or len(assets)!=8:raise ValueError('Exact source/asset count differs')
    base={c:next(j for j in a['jobs'] if j['candidate']==c and j['asr_tap']=='O0' and j['repeat_index']==1) for c in ('C065','C088')}
    settings=dict(schema_version='edge-s6d.v1',text_delivery=True,boundary_repair=True,transcript_mode='T0',direction_mode='V0')
    if any(j['settings']!=settings for j in base.values()):raise ValueError('Candidate settings differ')
    authorities=[ab,bind(bp),bind(ip),verify(a['source_review'])]
    historical=[bind(h2/'docs/full_pipeline'/n) for n in ('H2_ARM64_LINUX_HANDOFF.md','H2_ONNX_ARM64_PORTABILITY.md')]
    historical += [bind(p) for p in sorted((h2/'deployment/h2_arm64').iterdir()) if p.is_file()]
    workload=[]
    for case,reason in CASES:
        s=scenes[case];inp=inputs[case,'O0'];audio=verify(inp['audio'])
        with wave.open(audio['path'],'rb') as f:
            if (f.getnchannels(),f.getsampwidth(),f.getframerate())!=(1,2,16000):raise ValueError('Wrong PCM')
            frames=f.getnframes();pcm=f.readframes(frames)
        if hashlib.sha256(pcm).hexdigest()!=inp['audio_pcm_sha256']:raise ValueError('PCM differs')
        metadata={k:s.get(k) for k in ('case_id','family_id','family','title','cast','short_turn_durations_s','noise_policy','coverage_limitations')}
        metadata['noise_source_ids']=[x['source_id'] for x in s['segments'] if x.get('kind')=='real_noise']
        if case=='S45_03_03' and not all(0<x<1 for x in metadata['short_turn_durations_s']):raise ValueError('Short metadata differs')
        if case=='S45_11_03' and 'music-fma-0060_s00' not in metadata['noise_source_ids']:raise ValueError('Music absent')
        workload.append(dict(case_id=case,selection_reason=reason,metadata=metadata,audio=dict(role='workload_pcm',binding=audio,target_relative=f'workload/{case}/O0.wav'),
            frames=frames,sample_rate=16000,channels=1,pcm_sha256=inp['audio_pcm_sha256'],source_seconds=frames/16000,
            historical_gain_applied_once=inp['historical_gain_applied_once'],runtime_gain=1.0,already_gained=True,identity_tap_same_as_asr=True))
    gb=verify(base['C088']['gallery']);gallery=read(gb['path'])
    gi=[dict(role='gallery_manifest_original',binding=gb,target_relative='gallery/GALLERY_ORIGINAL.json')]
    for person in gallery['profiles']:
        for kind in ('metadata','vector'):
            b=verify(person[kind]);gi.append(dict(role='gallery_'+kind,binding=b,target_relative='gallery/profiles/'+Path(b['path']).name))
    if len(gallery['profiles'])!=15:raise ValueError('Exact A15 required')
    output.mkdir(parents=True);(output/'configs').mkdir()
    configs=[]
    for c,j in base.items():
        b=verify(j['profile_binding']);authorities.append(b);dest=output/'configs'/f'{c}_O0_PROFILE.json';shutil.copyfile(b['path'],dest)
        if bind(dest)['sha256']!=b['sha256']:raise ValueError('Profile copy differs')
        configs.append(dict(role='candidate_profile',candidate=c,binding=bind(dest),target_relative='configs/'+dest.name,original_binding=b))
    sb=save(output/'configs/S6D_SETTINGS.json',settings)
    configs.append(dict(role='s6d_settings',binding=sb,target_relative='configs/S6D_SETTINGS.json',semantic_source=ab))
    shutil.copyfile(req,output/'requirements-linux-arm64.txt')
    configs.append(dict(role='requirements',binding=bind(output/'requirements-linux-arm64.txt'),target_relative='requirements-linux-arm64.txt',original_binding=bind(req)))
    helper=Path(__file__).resolve();readme=helper.with_name('README_S6D_CM5_PREPARATION.md')
    shutil.copyfile(helper,output/helper.name);shutil.copyfile(readme,output/'README.md')
    transfers=sources+assets+gi+configs+[w['audio'] for w in workload];jobs=[]
    for w in workload:
        for c in ('C065','C088'):
            jid=c+'_'+w['case_id']+'_O0_CM5_PROPOSAL'
            argv=['python3.12','-m','edge_speech_pipeline','file','@STAGE@/'+w['audio']['target_relative'],'--research-profile','@STAGE@/configs/'+c+'_O0_PROFILE.json','--s6d-settings','@STAGE@/configs/S6D_SETTINGS.json']
            if c=='C088':argv+=['--research-gallery','@STAGE@/gallery/GALLERY_RELOCATED.json']
            jobs.append(dict(job_id=jid,candidate=c,case_id=w['case_id'],argv_template=argv,source_seconds=w['source_seconds'],
                mode='source-paced file (no --accelerated)',independent_process=True,serial_only=True,threads_per_model=1,
                output_root_template='@DATA@/'+jid,timeout_sec_proposed=300,cooperative_grace_sec_proposed=60))
    v=dict(schema='s6d-cm5-deployment-preparation.v1',status='PORT_REQUIRES_WORK_PROPOSAL_NOT_SUPPORTED_PROFILE',
        target=dict(platform='Compute Module 5',ram_gib_nominal=2,emmc_gb_nominal=32,cpu_only=True,wireless_used=False,exact_board_os_kernel_glibc_wheels_unverified=True),
        authority=ab,source_bindings=authorities,historical_h2=historical,
        historical_claim_boundary='August27 wheel availability and predecessor Windows parity only; no current wheel availability, S6D parity or target qualification.',
        source_root=str(root),source_file_count=45,asset_file_count=8,asset_graph_count=6,
        asset_count_note='Six ONNX graphs and two vocabulary/token files, including punctuation model and bpe.vocab.',
        model_bytes=sum(x['binding']['bytes'] for x in assets),assets=assets,source_files=sources,configs=configs,pins=PINS,python_required='3.12',
        wheel_availability_current='NOT_VERIFIED_NO_NETWORK_QUERY',gallery_original=gb,gallery_items=gi,workload=workload,jobs=jobs,
        selection_scope='Fixed short/switch/music metadata subset for reproducibility/resources, not a representative or held-out efficacy sample. No score-based choice.',
        unique_pcm_bytes=sum(w['audio']['binding']['bytes'] for w in workload),unique_source_seconds=sum(w['source_seconds'] for w in workload),
        scheduled_source_seconds=sum(j['source_seconds'] for j in jobs),transfer_map=transfers,preparation_sources=[bind(helper),bind(readme)],
        capability_flags=dict(manifest_and_local_bytes_verified=True,source_accepted_gui_v3=True,cm5_tested=False,linux_arm64_ready=False,current_arm64_wheels_resolved=False,
            s6d_arm64_parity=False,sustained_2gib_no_swap_fit=False,emmc_retention_enforced=False,live_audio_qualified=False,xvf_expanded_capture_qualified=False,
            physical_direction_association=False,tk_callback_latency_measured=False,physical_display_scanout_measured=False,cm5_native_jobs_run=False,six_resident_stacks_supported=False),
        runtime_architecture='One serial app/engine; ASR+punctuation and shared ReDim/Pyannote sessions, original one-thread profile; no Torch or per-speaker/per-beam stacks.',
        retention_proposal=dict(model_tree_read_only=True,session_limit_bytes=512*1024**2,stdout_stderr_limit_each_bytes=32*1024**2,
            closed_workload_total_limit_bytes=3*1024**3,min_target_free_bytes=4*1024**3,operational_log_ring_bytes=128*1024**2,operational_log_chunk_bytes=16*1024**2,
            scientific_receipts_rotate=False,delete_active_or_unreviewed_sessions=False,enforcement_status='DESIGN_ONLY_REQUIRES_TARGET_SUPERVISOR_AND_QUOTA_REVIEW'),
        new_model_calls=0,hardware_calls=0,downloads=0,installs=0,pcm_or_asset_payload_copies=0,execution_authorization_created=False)
    result=save(output/'CM5_MANIFEST.json',v)
    print(json.dumps(dict(status=v['status'],manifest=result,model_bytes=v['model_bytes'],assets=len(assets),source_files=len(sources),
        jobs=len(jobs),unique_pcm_bytes=v['unique_pcm_bytes'],unique_source_seconds=v['unique_source_seconds'],scheduled_source_seconds=v['scheduled_source_seconds']),indent=2),flush=True)

def inspect(manifest,staged_root=None):
    m=read(manifest);observed=[]
    for item in m['transfer_map']:
        path=(staged_root/item['target_relative']).resolve() if staged_root else Path(item['binding']['path'])
        observed.append(dict(target=item['target_relative'],actual=verify(item['binding'],path)))
    print(json.dumps(dict(status='PASS_FILE_BINDINGS_ONLY',manifest=bind(manifest),files=len(observed),source_or_target='staged' if staged_root else 'original',
        platform_observation=dict(system=platform.system(),machine=platform.machine(),python=platform.python_version()),cm5_qualified=False,models_loaded=0,hardware_calls=0,observed=observed),indent=2))

def relocate_gallery(manifest,staged_root,output):
    m=read(manifest);root=staged_root.resolve();original=root/'gallery/GALLERY_ORIGINAL.json';verify(m['gallery_original'],original);g=read(original)
    admitted={x['target_relative']:x['binding'] for x in m['gallery_items']}
    for person in g['profiles']:
        for kind in ('metadata','vector'):
            rel='gallery/profiles/'+Path(person[kind]['path'].replace('\\','/')).name;person[kind]=verify(admitted[rel],root/rel)
    g['profile_root']=str(root/'gallery/profiles');b=save(output,g)
    print(json.dumps(dict(status='PATH_RELOCATION_ONLY_NEW_GALLERY_HASH',original=m['gallery_original'],relocated=b,semantic_fields_and_template_bytes_unchanged=True,native_gallery_load_tested=False),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare')
    for n in ('repo','report','output'):a.add_argument('--'+n,type=Path,required=True)
    b=s.add_parser('inspect');b.add_argument('--manifest',type=Path,required=True);b.add_argument('--staged-root',type=Path)
    c=s.add_parser('relocate-gallery')
    for n in ('manifest','staged-root','output'):c.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.repo,a.report,a.output)
    elif a.action=='inspect':inspect(a.manifest,a.staged_root)
    else:relocate_gallery(a.manifest,a.staged_root,a.output)

