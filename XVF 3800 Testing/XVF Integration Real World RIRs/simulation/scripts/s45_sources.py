"""S4.5 bounded speech inventory, pre-QC split freeze and source adapter. README_S45_SOURCES.md."""
from __future__ import annotations
import argparse, collections, json, math, re, sqlite3, sys, urllib.parse
from pathlib import Path
import numpy as np
import scipy
from scipy.signal import resample_poly
import soundfile as sf
from s4_sources import SIM, DATA, EN, RELEASE, RATE, active_stats, identity, bind, digest, row_hash, save, utc, file_hash
from s4_h2_analysis import normalize

OUT=SIM/'staging/s45_sources'
PAYLOAD=Path(r'G:\Just_Peachy_S4_5\20260909T031300Z\sources')
RAW=DATA/'Raw Datasets (Not formatted)'
CMU=RAW/'CMU Arctic'; HIFI=RAW/'Hi Fi TTS/hi_fi_tts_v0'
SEED='s45-speech-source-v1-20260909T031300Z'
S4=SIM/'staging/s4_sources'
MANIFEST=OUT/'SOURCE_AND_SPLIT_MANIFEST.json'
FREEZE=OUT/'ROSTER_AND_SELECTION_BEFORE_QC.json'
CMU_META={
 'aew':('male','US English'),'ahw':('male','German-accented English'),'aup':('male','Indian-accented English'),
 'awb':('male','Scottish English'),'axb':('female','Indian-accented English'),'bdl':('male','US English'),
 'clb':('female','US English'),'eey':('female','US English'),'fem':('male','German-accented English'),
 'gka':('male','Indian-accented English'),'jmk':('male','Canadian English'),'ksp':('male','Indian-accented English'),
 'ljm':('female','US English'),'lnh':('female','US English'),'rms':('male','US English'),
 'rxr':('male','Israeli-accented English'),'slp':('male','Indian-accented English'),'slt':('female','US English')}
HIFI_META={'92':'female','6097':'male','9017':'male','6670':'male','6671':'male','8051':'female',
           '9136':'female','11614':'female','11697':'female','12787':'female'}
CMU_RESERVE={'slt','axb','awb','rxr'}; HIFI_RESERVE={'9017','8051'}
ALLOWED_DATASETS={'CMU ARCTIC','HiFiTTS','Common Voice'}

def key(value):return digest((SEED+'|'+str(value)).encode())
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def report(value):print(json.dumps(value,ensure_ascii=True),flush=True)
def text_group(text):return 'TEXT_'+digest(normalize(text).encode())
def planned_text_split(text):return 'downstream_reserve' if int(key(text_group(text))[:8],16)%4==0 else 'development'
def planned_text_usage(text):return 'enrollment_reference' if int(key('role|'+text_group(text))[:8],16)%6==0 else 'probe'

def whole_short_candidate(text):
    stripped=text.strip().rstrip('"\u201d\u2019\'')
    words=normalize(text).split()
    return bool(words) and stripped.endswith(('.', '!', '?')) and words not in [['mr'],['mrs'],['ms'],['dr'],['st']]

def fetch_metadata():
    """Only small official project pages/notices; never download a speech archive."""
    import requests
    (OUT/'metadata').mkdir(parents=True,exist_ok=True)
    items=[('cmu_official_index.html','http://festvox.org/cmu_arctic/'),
           ('cmu_bdl_COPYING.txt','http://festvox.org/cmu_arctic/cmu_arctic/cmu_us_bdl_arctic/COPYING')]
    items += [(f'cmu_{sid}_COPYING.txt',f'http://festvox.org/cmu_arctic/cmu_arctic/cmu_us_{sid}_arctic/COPYING')
              for sid in ['awb','clb','jmk','ksp','rms','slt']]
    receipt_path=OUT/'OFFICIAL_METADATA_ACCESS.json'
    if receipt_path.exists():
        result=read(receipt_path)
        for b in result['files']:assert file_hash(b['path'])==b['sha256']
        return result
    rows=[]
    for name,url in items:
        dest=OUT/'metadata'/name
        response=requests.get(url,timeout=(10,20));response.raise_for_status()
        if len(response.content)>100000:raise ValueError('Unexpectedly large metadata download')
        dest.write_bytes(response.content)
        rows.append({**bind(dest),'url':url,'accessed_utc':utc(),'http_status':response.status_code})
    receipt={'status':'PASS','files':rows,'download_bytes':sum(r['bytes'] for r in rows),
        'scope':'Official HTTP Festvox project metadata/notices. HTTPS endpoint unavailable. No audio archives downloaded.',
        'missing_installed_cmu_licenses':True,'additional_11_separate_notices':'Not present in the installed minimal wav/etc subsets; family permission evidence retained separately.',
        'author_paper_url':'https://www.cs.cmu.edu/~awb/papers/ssw5/arctic.pdf',
        'author_paper_permission':'Primary author paper describes entire CMU ARCTIC package as free software without commercial/noncommercial restriction; no claim that an absent local per-voice notice was found.'}
    save(receipt_path,receipt);return receipt

def choose_rows(rows,role,limit=18):
    """Only text/native duration metadata; roles are fixed before decoded-waveform QC."""
    eligible=[r for r in rows if r['usage']==role and .25<=r['metadata_duration_sec']<=10]
    chosen=[];seen=set()
    bins=[('subsecond',lambda r:r['metadata_duration_sec']<1 and whole_short_candidate(r['transcript']),4),
          ('one_to_two',lambda r:1<=r['metadata_duration_sec']<2 and whole_short_candidate(r['transcript']),4),
          ('ordinary',lambda r:2<=r['metadata_duration_sec']<=8,limit)] if role=='probe' else [('enrollment',lambda r:2<=r['metadata_duration_sec']<=10,4)]
    for label,predicate,n in bins:
        for row in sorted([r for r in eligible if predicate(r)],key=lambda r:key(r['source_id'])):
            if len([r for r in chosen if r['selection_bin']==label])>=n:break
            if row['prompt_group'] in seen:continue
            chosen.append({**row,'selection_bin':label});seen.add(row['prompt_group'])
            if len(chosen)>=limit:break
        if len(chosen)>=limit:break
    return chosen

def cmu_inventory(access):
    people=[];selected=[];all_prompt_groups={};metadata=[]
    for directory in sorted(CMU.glob('cmu_us_*_arctic')):
        sid=directory.name.split('_')[2]
        if sid not in CMU_META:raise ValueError('Undocumented CMU speaker directory')
        gender,accent=CMU_META[sid];split='downstream_reserve' if sid in CMU_RESERVE else 'development'
        person={'identity':'CMU_ARCTIC_'+sid,'dataset':'CMU ARCTIC','split':split,'gender':gender,'accent':accent,
                'L1':None,'age_band':None,'metadata_provenance':'Official CMU ARCTIC index page; accent is not asserted L1.',
                'known_aliases':[],'cross_corpus_human_uniqueness':'UNRESOLVED; no voice re-identification',
                'quality_partitions':['studio_recorded_project_design_not_anechoic'],'role_frozen_before_QC':True}
        people.append(person)
        transcripts=directory/'etc/txt.done.data';metadata.append(bind(transcripts));rows=[]
        parsed=[]
        for line in transcripts.read_text(encoding='utf-8-sig').splitlines():
            match=re.fullmatch(r'\(\s*(\S+)\s+"(.*)"\s*\)',line.strip())
            if match:parsed.append(match.groups())
        # Header reads are native duration/format inventory, not waveform-based quality selection.
        candidates=sorted(parsed,key=lambda pair:key(pair[0]))[:240]+[pair for pair in parsed if len(normalize(pair[1]).split())<=4]
        seen=set()
        for prompt,text in candidates:
            if prompt in seen:continue
            seen.add(prompt);group=text_group(text);group_split=planned_text_split(text)
            all_prompt_groups[group]={'split':group_split,'usage':planned_text_usage(text),'native_prompt_id':prompt}
            if group_split!=split:continue
            path=directory/'wav'/(prompt+'.wav')
            if not path.is_file():continue
            info=sf.info(path)
            rows.append({'source_id':'CMU_'+sid+'_'+prompt,'identity':person['identity'],'split':split,'usage':planned_text_usage(text),
                'dataset':'CMU ARCTIC','release':'installed_18_speaker_cmu_arctic','source_path':str(path),
                'metadata_duration_sec':info.duration,'transcript':text,'sentence_id':prompt,'prompt_group':group,
                'parent_book':None,'parent_group':'CMU_PROMPT_'+prompt,'quality_partition':'studio_project_design',
                'gender':gender,'accent':accent,'L1':None,'age_band':None,'native_metadata_binding':metadata[-1],
                'native_row_sha256':row_hash({'prompt_id':prompt,'text':text}),'upstream_split':None,
                'timestamp_provenance':'Whole original ARCTIC prompt recording; no supplied word alignment in local subset.',
                'rights':{'license_id':'CMU_ARCTIC_PERMISSIVE','attribution':'Carnegie Mellon University; original CMU ARCTIC authors; retain notices and mark modifications.',
                    'project_permission_supported':True,'separate_voice_notice_available':sid in {'awb','bdl','clb','jmk','ksp','rms','slt'},
                    'notice_binding':next((b for b in access['files'] if Path(b['path']).name==f'cmu_{sid}_COPYING.txt'),None),
                    'permission_scope':'Official family permission and project listing; absent local notices disclosed; downstream training requires notice review.',
                    'future_training_automatic_clearance':False}})
        selected+=choose_rows(rows,'probe',18)+choose_rows(rows,'enrollment_reference',4)
    return people,selected,{'metadata_bindings':metadata,'prompt_groups':all_prompt_groups,
            'scope':'Metadata/header inventory over at most 240 seeded prompts plus <=4-word prompts per person; no full CMU waveform scan.'}

def hifi_inventory():
    people=[];all_rows=[];metadata=[];book_readers=collections.defaultdict(set)
    license_binding=bind(HIFI/'LICENSE.txt')
    for path in sorted(HIFI.glob('*_manifest_*_train.json')):
        sid,_,quality,_=path.stem.split('_')
        if sid not in HIFI_META:raise ValueError('Unknown HiFi native reader')
        # Use clean material where available, retaining the native quality partition.
        if sid=='6097' and quality=='other':continue
        metadata.append(bind(path))
        for line_number,line in enumerate(path.open(encoding='utf-8-sig'),1):
            r=json.loads(line);parts=Path(r['audio_filepath']).parts;book=parts[2]
            book_readers[book].add(sid)
            if not .25<=r['duration']<=10:continue
            all_rows.append({'source_id':'HIFI_'+sid+'_'+Path(r['audio_filepath']).stem,
                'identity':'HIFITTS_'+sid,'dataset':'HiFiTTS','release':'hi_fi_tts_v0','source_path':str(HIFI/r['audio_filepath']),
                'metadata_duration_sec':r['duration'],'transcript':r['text_no_preprocessing'],
                'native_preprocessed_text':r['text'],'native_normalized_text':r['text_normalized'],
                'sentence_id':Path(r['audio_filepath']).stem,'prompt_group':text_group(r['text_no_preprocessing']),
                'parent_book':'LIBRIVOX_BOOK_'+book,'parent_group':'LIBRIVOX_BOOK_'+book,
                'parent_chapter':Path(r['audio_filepath']).stem.rsplit('_',1)[0],
                'quality_partition':quality,'gender':HIFI_META[sid],'accent':None,'L1':None,'age_band':None,
                'native_metadata_binding':metadata[-1],'native_line_number':line_number,'native_row_sha256':row_hash(r),
                'upstream_split':'train','timestamp_provenance':'Whole native released segment; source CTC segmentation estimated, no local per-word manual alignment.',
                'rights':{'license_id':'CC-BY-4.0','license_binding':license_binding,
                    'attribution':'NVIDIA CORPORATION; Bakhturina, Lavrukhin, Ginsburg and Zhang (2021), Hi-Fi Multi-Speaker English TTS Dataset; LibriVox/Gutenberg source IDs retained.',
                    'source_selection_ASR_based':True,'voice_synthesis_consent_not_claimed':True,'future_training_automatic_clearance':False}})
    book_splits={book:('downstream_reserve' if readers&HIFI_RESERVE else 'development') for book,readers in book_readers.items()}
    book_usage={book:'probe' for book in book_readers}
    for sid in sorted(HIFI_META):
        split='downstream_reserve' if sid in HIFI_RESERVE else 'development'
        books=sorted([b for b,ids in book_readers.items() if sid in ids and book_splits[b]==split],key=lambda b:key(sid+'|'+b))
        if len(books)<2:raise ValueError('Need disjoint HiFi probe/enrollment books')
        book_usage[books[0]]='enrollment_reference'
        people.append({'identity':'HIFITTS_'+sid,'dataset':'HiFiTTS','split':split,'gender':HIFI_META[sid],
            'accent':None,'L1':None,'age_band':None,'metadata_provenance':'Installed native README reader table',
            'known_aliases':['LIBRIVOX_READER_'+sid],'cross_corpus_human_uniqueness':'Only documented reader alias; no global human-identity claim',
            'quality_partitions':['clean' if sid in {'92','6097','9017'} else 'other'],'role_frozen_before_QC':True})
    selected=[]
    for person in people:
        rows=[]
        for r in all_rows:
            if r['identity']!=person['identity']:continue
            book=r['parent_book'].removeprefix('LIBRIVOX_BOOK_')
            if book_splits[book]!=person['split']:continue
            rows.append({**r,'split':person['split'],'usage':book_usage[book]})
        selected+=choose_rows(rows,'probe',18)+choose_rows(rows,'enrollment_reference',4)
    return people,selected,{'metadata_bindings':metadata,'book_groups':{b:{'split':book_splits[b],'usage':book_usage[b],'readers':sorted(ids)} for b,ids in book_readers.items()},
            'source_description_binding':bind(HIFI/'README.txt'),'license_binding':bind(HIFI/'LICENSE.txt')}

def cv_inventory():
    import csv
    c=sqlite3.connect((EN/'state/common_voice_phase3.sqlite3').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    historical_path=DATA/'Evaluation Tool/benchmarks/speaker_breadth/commonvoice_60plus_v1/source_selection.tsv'
    excluded=set();historical_hashes=set()
    for r in csv.DictReader(historical_path.open(encoding='utf-8-sig'),delimiter='\t'):
        cid=c.execute('select client_id from candidates where path=?',(Path(r['logical_audio_path']).name,)).fetchone()
        assert cid is not None;excluded.add(cid[0]);historical_hashes.add(r['audio_sha256'].lower())
    assert len(excluded)==413
    old=read(S4/'SOURCE_AND_SPLIT_MANIFEST.json');old_ledger=read(S4/'SPLIT_FREEZE_BEFORE_AUDIO_QC.json')
    old_source_names={Path(s['source_binding']['path']).name for s in old['sources']}
    old_prompt_groups={text_group(s['transcript']) for s in old['sources']}
    old_source_names|={r['clip'] for r in read(S4/'SHORTLIST_QUALITY.json')['rejected'] if 'clip' in r}
    rows_by_id=collections.defaultdict(list)
    sql="""select c.*,d.duration_ms,a.audio_sha256,coalesce(u.split,'validated_unassigned') upstream_split
      from candidates c join durations d on d.path=c.path join audio_validation a on a.path=c.path
      left join upstream u on u.path=c.path where c.locale='en' and cast(c.down_votes as integer)=0
      and cast(c.up_votes as integer)>=2 and a.readable=1 and a.channels=1 and d.duration_ms between 250 and 10000"""
    for row in c.execute(sql):
        r=dict(row)
        if r['client_id'] in excluded or r['path'] in old_source_names or r['upstream_split'] not in ['train','validated_unassigned']:continue
        if not r['transcript'].strip() or text_group(r['transcript']) in old_prompt_groups:continue
        pseudonym=identity(r.pop('client_id'));rows_by_id[pseudonym].append(r)
    c.close()
    old_dev=[p['identity'] for p in old['people'] if p['split']=='development']
    old_reserve=[p['identity'] for p in old['people'] if p['split']=='downstream_reserve']
    def eligible(pid,split):
        rows=rows_by_id[pid]
        return sum(planned_text_usage(r['transcript'])=='probe' for r in rows)>=14 and sum(planned_text_usage(r['transcript'])=='enrollment_reference' for r in rows)>=3
    locked_dev=set(old_ledger['development_candidate_priority'])|set(old_dev)
    reserve_candidates=sorted((p for p in rows_by_id if p not in locked_dev and p not in old_reserve and eligible(p,'downstream_reserve')),key=key)
    reserves=old_reserve+reserve_candidates[:1]
    dev_candidates=[p for p in old_ledger['development_candidate_priority'] if p not in old_dev and eligible(p,'development')]
    dev_candidates += sorted((p for p in rows_by_id if p not in set(dev_candidates+old_dev+reserves) and eligible(p,'development')),key=key)
    devs=old_dev+dev_candidates[:6]
    assert len(set(devs))==12 and len(set(reserves))==4 and not set(devs)&set(reserves), {'dev_count':len(set(devs)),'reserve_count':len(set(reserves)),'overlap':sorted(set(devs)&set(reserves)),'new_reserve_candidates':len(reserve_candidates),'new_dev_candidates':len(dev_candidates)}
    # Preserve usable sparse contributors without randomly discarding three
    # quarters of their prompts. Assign shared text groups from the frozen
    # roster, with reserve precedence, before any waveform is decoded.
    cv_prompt_splits={text_group(r['transcript']):'development' for pid in devs for r in rows_by_id[pid]}
    cv_prompt_splits.update({text_group(r['transcript']):'downstream_reserve' for pid in reserves for r in rows_by_id[pid]})
    people=[];selected=[]
    for split,ids in [('development',devs),('downstream_reserve',reserves)]:
        for pid in ids:
            rows=[];metadata_rows=rows_by_id[pid]
            people.append({'identity':pid,'dataset':'Common Voice','split':split,'gender':sorted({r['gender'] for r in metadata_rows if r['gender']}),
                'accent':sorted({r['accents'] for r in metadata_rows if r['accents']}),'age_band':sorted({r['source_age_label'] for r in metadata_rows}),
                'L1':None,'metadata_provenance':'Native contributor self-reports through existing read-only verified release index',
                'known_aliases':[],'cross_corpus_human_uniqueness':'UNRESOLVED; contributor identity, not biometric identification',
                'quality_partitions':['self_reported_60plus_real_recording'],'role_frozen_before_QC':True,
                'preserved_S4_identity':pid in old_dev+old_reserve})
            for r in metadata_rows:
                if cv_prompt_splits[text_group(r['transcript'])]!=split:continue
                rows.append({'source_id':'CV26_'+Path(r['path']).stem,'identity':pid,'split':split,'usage':planned_text_usage(r['transcript']),
                    'dataset':'Common Voice','release':RELEASE,'source_path':str(EN/'clips'/r['path']),
                    'metadata_duration_sec':r['duration_ms']/1000,'transcript':r['transcript'],'sentence_id':r['sentence_id'],
                    'prompt_group':text_group(r['transcript']),'parent_book':None,'parent_group':text_group(r['transcript']),
                    'quality_partition':'self_reported_60plus_real_recording','gender':r['gender'] or None,'accent':r['accents'] or None,
                    'age_band':r['source_age_label'],'L1':None,'upstream_split':r['upstream_split'],
                    'prior_source_sha256':r['audio_sha256'].lower(),'native_row_sha256':row_hash(r),
                    'votes':{'up':int(r['up_votes']),'down':int(r['down_votes'])},
                    'timestamp_provenance':'Whole contributed clip; no supplied native/manual word timing.',
                    'rights':{'license_id':'CC0','license_binding':old['license_binding'],
                        'attribution':'Mozilla Common Voice English '+RELEASE+'; local self-reported older cohort.',
                        'no_contributor_identification':True,'pretraining_exposure_unknown':True,'future_training_automatic_clearance':False}})
            selected+=choose_rows(rows,'probe',18)+choose_rows(rows,'enrollment_reference',4)
    return people,selected,{'historical_exclusion_binding':bind(historical_path),'historical_contributors_excluded':len(excluded),
        'historical_source_hashes':sorted(historical_hashes),'S4_manifest_binding':bind(S4/'SOURCE_AND_SPLIT_MANIFEST.json'),
        'S4_split_freeze_binding':bind(S4/'SPLIT_FREEZE_BEFORE_AUDIO_QC.json'),'S4_sources_retained_in_old_version_only':old['sources'],
        'prompt_group_splits_before_QC':cv_prompt_splits,'S4_prompt_groups_excluded_from_new_selection':sorted(old_prompt_groups),
        'source_release_materialization':old['materialization_binding'],'native_metadata_path':str(EN/'metadata/original/validated.tsv')}

def freeze():
    OUT.mkdir(parents=True,exist_ok=True)
    if FREEZE.exists():report({'status':'FROZEN_SELECTION_EXISTS','path':str(FREEZE)});return
    access=fetch_metadata();people=[];sources=[];evidence={}
    for name,fn in [('cmu',lambda:cmu_inventory(access)),('hifi',hifi_inventory),('cv',cv_inventory)]:
        p,s,e=fn();people+=p;sources+=s;evidence[name]=e
        report({'phase':'metadata_freeze','dataset':name,'people':len(p),'candidate_clips':len(s)})
    assert len(people)==44 and len({p['identity'] for p in people})==44
    assert {p['dataset'] for p in people}==ALLOWED_DATASETS
    # CMU/CV lexical groups are preassigned globally. HiFi book partitions are
    # stronger source-parent groups; cross-corpus phrase coincidence is disclosed.
    result={'schema':'jp_s45_speech_selection_freeze_v1','frozen_utc':utc(),'seed':SEED,'role_frozen_before_QC':True,
        'adapter_binding':bind(Path(__file__)),'S4_adapter_binding':bind(SIM/'scripts/s4_sources.py'),
        'payload_root':str(PAYLOAD),'people':people,'candidates':sources,'evidence':evidence,
        'official_metadata_access_binding':bind(OUT/'OFFICIAL_METADATA_ACCESS.json'),
        'exclusions':['L2-ARCTIC excluded by explicit user request; not permission-blocked','413 historical Common Voice contributors',
                      'All prior S4 probe/enrollment/reserve clip bytes stay in S4 and are excluded from this new candidate pool'],
        'selection_policy':{'max_probe_candidates_per_identity':18,'max_enrollment_candidates_per_identity':4,
            'all_candidate_usage_roles_fixed_before_waveform_QC':True,'duration_source':'Native manifest duration or WAV header only',
            'short_candidates':'Whole source files with sentence-final punctuation for <2s priority; no arbitrary crop or ASR filtering',
            'lexical_independence':'CMU/CV prompt groups and HiFi parent books kept in one declared role/split; cross-corpus text coincidence checked after selection and disclosed, not a universal unseen-language claim',
            'reserve_task_scoring':'FORBIDDEN; input waveform integrity/QC only'}}
    save(FREEZE,result);report({'status':'FROZEN_BEFORE_QC','identities':len(people),'candidate_clips':len(sources),'path':str(FREEZE)})

def qc_reasons(q,duration):
    hard=[];review=[]
    if not .25<=duration<=10:hard.append('duration_outside_frozen_preparation_limits')
    if q['active_seconds_estimated']<min(.25,duration*.20):hard.append('insufficient_estimated_activity')
    if q['active_rms_dbfs'] < -36:hard.append('RMS_target_would_require_more_than_12dB_boost')
    if q['peak']>1 or q['max_run_abs_ge_0_999']>2 or q['samples_abs_ge_0_999']>3:hard.append('source_rail_or_overrange')
    if abs(q['dc_offset'])>.01:hard.append('large_source_DC')
    if q['frame_p95_to_p10_db']<12:review.append('weak_pause_contrast_not_noise_proof_or_short_clip_rejection')
    if q['active_ranges_samples_estimated'] and q['active_ranges_samples_estimated'][-1][1]>duration*RATE-.04*RATE:review.append('activity_near_source_end')
    return hard,review

def gain_for(q):
    target=10**(-24/20)
    if q['active_rms']<=0 or target/q['active_rms']>10**(12/20)+1e-10:raise ValueError('Excessive or undefined dry-source boost')
    return min(target/q['active_rms'],.5/q['peak'])

def prepare():
    if not FREEZE.exists():raise ValueError('Run freeze before waveform QC')
    if MANIFEST.exists():
        manifest=read(MANIFEST)
        for s in manifest['sources']:
            for field in ['source_binding','decoded_16k_binding']:assert file_hash(s[field]['path'])==s[field]['sha256']
        report({'status':'REUSED_VERIFIED','manifest':str(MANIFEST),'counts':manifest['counts']});return
    frozen=read(FREEZE);PAYLOAD.mkdir(parents=True,exist_ok=True);(PAYLOAD/'decoded_16k').mkdir(exist_ok=True)
    accepted=[];rejected=[];seen_bytes=set(frozen['evidence']['cv']['historical_source_hashes']);seen_pcm=set()
    for s in frozen['evidence']['cv']['S4_sources_retained_in_old_version_only']:
        seen_bytes.add(s['source_binding']['sha256']);seen_pcm.add(s['decoded_pcm_sha256'])
    for i,row in enumerate(frozen['candidates'],1):
        try:
            path=Path(row['source_path']);source_bind=bind(path)
            if row.get('prior_source_sha256') and source_bind['sha256']!=row['prior_source_sha256']:raise ValueError('Indexed source byte hash changed')
            if source_bind['sha256'] in seen_bytes:raise ValueError('Exact source duplicate of previous selection')
            x,sr=sf.read(path,dtype='float64',always_2d=True)
            if x.shape[1]!=1 or not len(x) or not np.isfinite(x).all():raise ValueError('Non-mono, empty or nonfinite source')
            divisor=math.gcd(int(sr),RATE)
            y=resample_poly(x[:,0],RATE//divisor,int(sr)//divisor,window=('kaiser',5.0),padtype='constant').astype('float32')
            pcm_hash=digest(y.astype('<f4').tobytes())
            if pcm_hash in seen_pcm:raise ValueError('Exact decoded duplicate of previous selection')
            q=active_stats(y);hard,review=qc_reasons(q,len(y)/RATE)
            if hard:
                rejected.append({'source_id':row['source_id'],'identity':row['identity'],'split':row['split'],'usage':row['usage'],
                                 'reasons':hard,'source_binding':source_bind,'quality':q});continue
            gain=gain_for(q);dest=PAYLOAD/'decoded_16k'/(row['source_id']+'_'+pcm_hash[:12]+'.wav')
            if dest.exists():
                old,rate=sf.read(dest,dtype='float32');assert rate==RATE and np.array_equal(old,y)
            else:sf.write(dest,y,RATE,subtype='FLOAT')
            result={**{k:v for k,v in row.items() if k not in ['source_path','prior_source_sha256']},
                'source_binding':source_bind,'decoded_16k_binding':bind(dest),'decoded_pcm_sha256':pcm_hash,
                'native_decoded':{'sample_rate_hz':int(sr),'channels':1,'samples':len(x),'duration_sec':len(x)/sr,
                    'float64_pcm_sha256':digest(x.astype('<f8').tobytes())},
                'sample_rate_hz':RATE,'samples':len(y),'duration_sec':len(y)/RATE,
                'transcript_sha256':digest(row['transcript'].encode()),'transcript_normalized':normalize(row['transcript']),
                'whole_clip':True,'source_crop_native_samples':[0,len(x)],'source_crop_seconds':[0,len(x)/sr],
                'quality':q,'quality_review_flags':review,'quality_disposition':'REVIEW' if review else 'PASS',
                'source_gain_applied':1.0,'preparation_gain':gain,'postgain_peak_fs':q['peak']*gain,
                'preparation_gain_db':20*math.log10(gain),'role_frozen_before_QC':True,
                'short_turn_evidence':'Whole native source file; sentence-final text candidate, estimated release boundaries, not a spontaneous reply' if len(y)<2*RATE else None,
                'source_quality_caveats':['No auditory/anechoic certification; inherited source room/microphone conditions',
                    'Numerical activity is not phonetic boundary ground truth; no denoising or ASR-based shortlist filtering']}
            accepted.append(result);seen_bytes.add(source_bind['sha256']);seen_pcm.add(pcm_hash)
        except (ValueError,RuntimeError,FileNotFoundError,sf.LibsndfileError) as e:
            rejected.append({'source_id':row['source_id'],'identity':row['identity'],'split':row['split'],'usage':row['usage'],'reasons':[str(e)]})
        if i%40==0:report({'phase':'source_QC','done':i,'total':len(frozen['candidates']),'accepted':len(accepted),'rejected':len(rejected)})
    people=[];gaps=[]
    for p in frozen['people']:
        clips=[s for s in accepted if s['identity']==p['identity']]
        counts=collections.Counter(s['usage'] for s in clips)
        if counts['probe']<10 or counts['enrollment_reference']<2:gaps.append({'identity':p['identity'],'split':p['split'],'counts':dict(counts),'target':'10 probes +2 enrollment references; no role reassignment after QC'})
        people.append({**p,'source_ids':[s['source_id'] for s in clips],'accepted_counts':dict(counts)})
    counts={'identities':len(people),'identities_with_usable_probe':sum(p['accepted_counts'].get('probe',0)>0 for p in people),
            'source_clips':len(accepted),'candidate_clips':len(frozen['candidates']),'rejected_clips':len(rejected),
            'decoded_seconds':sum(s['duration_sec'] for s in accepted),
            'corpora':dict(collections.Counter(p['dataset'] for p in people)),
            'identity_splits':dict(collections.Counter(p['split'] for p in people)),
            'whole_subsecond_probe_clips':sum(s['usage']=='probe' and s['duration_sec']<1 for s in accepted),
            'whole_1_to_2_second_probe_clips':sum(s['usage']=='probe' and 1<=s['duration_sec']<2 for s in accepted)}
    manifest={'schema':'jp_s45_speech_sources_v1','created_utc':utc(),'status':'COMPLETE_WITH_SOURCE_GAPS' if gaps else 'COMPLETE',
        'split_freeze_binding':bind(FREEZE),'adapter_binding':bind(Path(__file__)),'S4_adapter_binding':bind(SIM/'scripts/s4_sources.py'),
        'people':people,'sources':accepted,'counts':counts,'gaps':gaps,'historical_identities_excluded':413,
        'resampler':{'implementation':'scipy.signal.resample_poly','scipy_version':scipy.__version__,'window':['kaiser',5.0],
            'padtype':'constant','output_rate':RATE,'decoded_gain':1.0},
        'source_level_policy':{'target_active_rms_dbfs':-24,'maximum_requested_boost_db':12,'dry_peak_cap_fs':.5,
            'formula':'min(10**(-24/20)/active_rms,0.5/peak), reject requested boost above12dB',
            'renderer_must_apply_preparation_gain_once':True,'estimator':'S4 active_stats unchanged,20ms nonoverlap frames',
            'not_SPL_or_equal_perceived_effort':True},
        'reserve_policy':'Prepared input integrity/QC only. No reserve task score inspection or recipe tuning. Enrollment references remain separate from probe.',
        'exclusions':frozen['exclusions'],'metadata_and_rights_evidence':frozen['evidence'],
        'limitations':['44 metadata-qualified source identities are not proven44 globally distinct humans. Cross-corpus simultaneous casts require known identity resolution.',
            'HiFi is curated/CTC-segmented, includes source ASR-agreement selection; only3 clean-capable speakers,7other-only.',
            'CV is this release self-reported older English cohort, not population-random older speech; pretraining exposure unknown.',
            'CMU local minimal distribution omits notices; official notices/project family permission retained, future automatic training clearance withheld.',
            'Cross-corpus text coincidences and original CMU prompt repetition prevent a universal independent lexical-diversity claim.',
            'Subsecond inputs are complete released files with original native transcript evidence; timing is estimated and no spontaneous response claim is made.']}
    validate_manifest(manifest)
    save(OUT/'SOURCE_QC.json',{'status':'PASS','created_utc':utc(),'candidate_count':len(frozen['candidates']),'accepted_count':len(accepted),'rejected':rejected,'gaps':gaps,'selection_changed_after_QC':False})
    save(MANIFEST,manifest);report({'status':manifest['status'],'counts':counts,'gaps':gaps,'manifest':str(MANIFEST)})

def validate_manifest(m):
    people={p['identity']:p for p in m['people']};assert len(people)==44
    assert {p['dataset'] for p in people.values()}==ALLOWED_DATASETS
    source_ids=set();source_hashes=set();pcm_hashes=set();group_roles=collections.defaultdict(set)
    for s in m['sources']:
        assert s['source_id'] not in source_ids;source_ids.add(s['source_id'])
        assert s['source_binding']['sha256'] not in source_hashes;source_hashes.add(s['source_binding']['sha256'])
        assert s['decoded_pcm_sha256'] not in pcm_hashes;pcm_hashes.add(s['decoded_pcm_sha256'])
        assert s['split']==people[s['identity']]['split'] and s['dataset']==people[s['identity']]['dataset']
        assert s['usage'] in ['probe','enrollment_reference'] and s['role_frozen_before_QC'] and s['source_gain_applied']==1
        assert s['samples']>0 and s['whole_clip'] and s['source_crop_seconds'][0]==0 and s['postgain_peak_fs']<=.5000001
        assert s['transcript_normalized']==normalize(s['transcript'])
        group=s['parent_book'] if s['dataset']=='HiFiTTS' else s['prompt_group']
        group_roles[(s['dataset'],group)].add((s['split'],s['usage']))
    assert all(len(roles)==1 for roles in group_roles.values()),'Parent/prompt split or enrollment/probe leakage'
    old=read(S4/'SOURCE_AND_SPLIT_MANIFEST.json')
    for p in old['people']:assert people[p['identity']]['split']==p['split']

def verify():
    """Selected native transcript rows only, source/decoded hashes and frozen role joins."""
    import csv
    m=read(MANIFEST);frozen=read(FREEZE);frozen_by_id={r['source_id']:r for r in frozen['candidates']}
    wanted={Path(s['source_binding']['path']).name:s for s in m['sources'] if s['dataset']=='Common Voice'}
    count=0
    with (EN/'metadata/original/validated.tsv').open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream,delimiter='\t'):
            if row['path'] not in wanted:continue
            s=wanted.pop(row['path']);assert s['identity']==identity(row['client_id']) and s['transcript']==row['sentence']
            assert s['sentence_id']==row['sentence_id'] and s['age_band']==row['age'] and s['gender']==(row['gender'] or None)
            count+=1
            if not wanted:break
    assert not wanted,'Missing selected native CV metadata'
    for s in m['sources']:
        original=frozen_by_id[s['source_id']]
        for field in ['identity','split','usage','transcript','parent_book','prompt_group']:assert s[field]==original[field]
        for field in ['source_binding','decoded_16k_binding']:assert file_hash(s[field]['path'])==s[field]['sha256']
    validate_manifest(m)
    receipt={'status':'PASS','created_utc':utc(),'native_CV_rows_verified':count,'all_source_rows':len(m['sources']),
        'checks':['Exact accepted source/decoded byte hashes','All role/group joins to pre-QC freeze','Native CV contributor/transcript/age/gender rows',
                  'CMU parsed native prompt rows and HiFi native manifest row/hash/path/line provenance','No enrollment/probe or within-corpus parent group split leakage'],
        'manifest_binding':bind(MANIFEST),'scope':'Input integrity only; no H2/XVF results or reserve task metrics'}
    save(OUT/'SOURCE_VERIFICATION.json',receipt);report(receipt)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['freeze','prepare','verify'])
    {'freeze':freeze,'prepare':prepare,'verify':verify}[parser.parse_args().action]()
