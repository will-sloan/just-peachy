"""S4.5 official noise intake; see README_S45_NOISE.md. No hardware or models."""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, shutil, time, urllib.request, uuid
from pathlib import Path, PurePosixPath
import tarfile

SIM=Path(__file__).resolve().parents[1]
STAGE=SIM/'staging/s45_noise'
PAYLOAD=Path(r'G:\Just_Peachy_S4_5\20260909T031300Z\noise')
NETWORK_CAP=16*1024**3
ACTIVE_CAP_S=90*60
MUSAN_URL='https://openslr.trmal.net/resources/17/musan.tar.gz'
MUSAN_BYTES=11086114085
MUSAN_MD5='0c472d4fc0c5141eca47ad1ffeb2a7df'

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def save(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    # Windows readers may briefly omit delete sharing. Retry publication,
    # never truncate the previous valid manifest or redownload its payload.
    for attempt in range(40):
        try:
            os.replace(temp,path);break
        except PermissionError:
            if attempt==39:raise
            time.sleep(.05)

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def digest(path):
    path=Path(path);h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return {'path':str(path),'sha256':h.hexdigest(),'bytes':path.stat().st_size}

def free_check():
    if shutil.disk_usage('C:/').free < 50*1024**3:raise RuntimeError('C free-space floor 50 GiB')
    if shutil.disk_usage(PAYLOAD.anchor).free < 75*1024**3:raise RuntimeError('Payload free-space floor 75 GiB')

def ledger():
    p=STAGE/'DOWNLOAD_LEDGER.json'
    if p.exists():return read(p)
    return {'schema':'s45_noise_download_ledger_v1','created_utc':now(),'new_response_body_bytes':0,
            'active_transfer_wait_s':27.0,'preflight_requests':[
              {'url':MUSAN_URL,'method':'HEAD','status':200,'body_bytes':0,'elapsed_s':.703},
              {'url':'https://www.openslr.org/resources/17/md5sum.txt','status':404,'body_bytes':0,'elapsed_s':.437},
              {'url':'https://zenodo.org/api/records/1227121','status':'TIMEOUT','body_bytes':0,'elapsed_s':25.36}],
            'byte_cap':NETWORK_CAP,'active_wait_cap_s':ACTIVE_CAP_S,'attempts':[],'notes':
            'Body payload bytes counted; HTTP header overhead and browser search-page traffic are not measured. Preflight elapsed rounded up. No external archive digest found at the tried md5sum URL.'}

def download(url, target, expected_bytes=None, expected_md5=None, attempts=3):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True);STAGE.mkdir(parents=True,exist_ok=True)
    book=ledger();part=target.with_name(target.name+'.part')
    if target.exists():
        if expected_bytes is not None and target.stat().st_size!=expected_bytes:raise ValueError('Existing target size mismatch')
        if expected_md5:
            check=hashlib.md5()
            with target.open('rb') as f:
                for data in iter(lambda:f.read(8*1024*1024),b''):check.update(data)
            if check.hexdigest()!=expected_md5:raise ValueError('Existing target official MD5 mismatch')
        result=digest(target);result.update(status='REUSED_LOCAL_VERIFIED',url=url)
        return result
    for attempt in range(attempts):
        free_check();before=part.stat().st_size if part.exists() else 0
        if expected_bytes is not None and expected_bytes-before > NETWORK_CAP-book['new_response_body_bytes']:
            raise RuntimeError('Transfer would exceed remaining 16 GiB response-body budget')
        if book['active_transfer_wait_s']>=ACTIVE_CAP_S:raise RuntimeError('Active network waiting cap reached')
        started=time.monotonic();base_wait=book['active_transfer_wait_s'];received=0;last=time.monotonic()
        entry={'url':url,'target':str(target),'attempt':attempt+1,'started_utc':now(),'resume_offset':before}
        book['attempts'].append(entry);headers={'User-Agent':'JustPeachyResearch/1.0'}
        if before:
            headers['Range']=f'bytes={before}-'
            previous=[a for a in book['attempts'][:-1] if a['url']==url and a.get('headers',{}).get('ETag')]
            if previous:headers['If-Range']=previous[-1]['headers']['ETag']
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as response:
                entry.update(status_code=response.status,final_url=response.url,headers=dict(response.headers))
                if before and (response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {before}-')):
                    raise RuntimeError('Server did not honor exact resume; refusing duplicate full transfer')
                total=expected_bytes or (before+int(response.headers.get('Content-Length','0')) or None)
                with part.open('ab' if before else 'wb') as output:
                    while True:
                        if time.monotonic()-started+base_wait>=ACTIVE_CAP_S:raise TimeoutError('90 minute active network wait cap')
                        remaining=NETWORK_CAP-book['new_response_body_bytes']
                        if remaining<=0:raise RuntimeError('Network byte cap reached')
                        data=response.read(min(1024*1024,remaining))
                        if not data:break
                        received+=len(data);book['new_response_body_bytes']+=len(data)
                        if book['new_response_body_bytes']>NETWORK_CAP:raise RuntimeError('Network byte cap reached')
                        output.write(data)
                        if time.monotonic()-last>=15:
                            output.flush();free_check();elapsed=time.monotonic()-started
                            book['active_transfer_wait_s']=base_wait+elapsed
                            entry.update(new_bytes=received,partial_bytes=before+received,status='DOWNLOADING')
                            save(STAGE/'DOWNLOAD_LEDGER.json',book)
                            progress={'phase':'noise_download','file':target.name,'downloaded_bytes':before+received,
                                      'expected_bytes':total,'MiB_per_s':received/max(elapsed,1)/1024**2,
                                      'total_new_GiB':book['new_response_body_bytes']/1024**3,
                                      'active_wait_s':book['active_transfer_wait_s'],'updated_utc':now(),
                                      'payload_free_GiB':shutil.disk_usage(PAYLOAD.anchor).free/1024**3}
                            save(STAGE/'status.json',progress);print(json.dumps(progress),flush=True);last=time.monotonic()
                    output.flush();os.fsync(output.fileno())
            if expected_bytes is not None and part.stat().st_size!=expected_bytes:raise ValueError('Downloaded size mismatch')
            if expected_md5:
                md5=hashlib.md5()
                with part.open('rb') as f:
                    for data in iter(lambda:f.read(8*1024*1024),b''):md5.update(data)
                if md5.hexdigest()!=expected_md5:raise ValueError('Official MD5 mismatch')
            os.replace(part,target)
            result=digest(target);result.update(status='DOWNLOADED',url=url,official_md5=expected_md5,
                digest_scope='SHA256 computed locally; official expected MD5 checked when supplied. No upstream SHA is invented.')
            entry.update(status='COMPLETE',new_bytes=received,result=result)
            return result
        except Exception as exc:
            entry.update(status='FAILED',new_bytes=received,error=repr(exc))
            print(json.dumps({'phase':'noise_download','attempt':attempt+1,'error':repr(exc)}),flush=True)
            if isinstance(exc,ValueError) or 'cap' in str(exc).lower():raise
            if attempt+1==attempts:raise
        finally:
            book['active_transfer_wait_s']=base_wait+time.monotonic()-started
            entry['finished_utc']=now();save(STAGE/'DOWNLOAD_LEDGER.json',book)
    raise RuntimeError('Download attempts exhausted')

def safe_member(name, root):
    item=PurePosixPath(name)
    if item.is_absolute() or '..' in item.parts or any(':' in p or '\\' in p for p in item.parts):
        raise ValueError('Unsafe archive member '+name)
    target=(Path(root)/Path(*item.parts)).resolve();base=Path(root).resolve()
    if not target.is_relative_to(base):raise ValueError('Archive escape')
    return target

def initialize():
    STAGE.mkdir(parents=True,exist_ok=True);PAYLOAD.mkdir(parents=True,exist_ok=True);free_check()
    spec={'schema':'s45_noise_catalog_v1','status':'INTAKE_IN_PROGRESS','created_utc':now(),
          'parents':[],'prepared_segments':[],
          'split_policy':'Freeze parent and segment assignments before waveform QC; derivatives inherit parent split; no reserve task scoring.',
          'expected_segment_fields':['noise_id','parent_id','split','dataset','category','category_evidence',
          'speech_content','strict_nonspeech_eligible','rights','attribution','prepared_path',
          'prepared_sha256','rate_hz','channels','samples','duration_s','crop_native_samples',
          'native_rate_hz','resampler','scalar','quality'],
          'speech_content_values':['absent_documented','present','unknown'],
          'format':'16 kHz mono FLOAT32 WAV; original mono or documented single original channel; antialiased resample once if needed',
          'level_policy':'Preserve numerical noise source level; no RMS normalization. Scene renderer uses one four-microphone-domain SNR scalar after RIR convolution.',
          'payload_root':str(PAYLOAD),'L2_speech_used':False,
          'local_discovery':{'root':r'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets',
          'matching_MUSAN_DEMAND_files_found':0,'scope':'Dataset-root inventory and repository rg filename search, no guessed duplicate copies.'}}
    if not (STAGE/'NOISE_CATALOG.json').exists():save(STAGE/'NOISE_CATALOG.json',spec)
    save(STAGE/'CATALOG_SCHEMA.json',{k:v for k,v in spec.items() if k not in ['parents','prepared_segments','local_discovery']})
    if not (STAGE/'DOWNLOAD_LEDGER.json').exists():save(STAGE/'DOWNLOAD_LEDGER.json',ledger())


def index_musan():
    """Verify the official archive and copy metadata only, never execute members."""
    import gzip
    archive=PAYLOAD/'downloads/musan.tar.gz'
    if archive.stat().st_size!=MUSAN_BYTES:raise ValueError('MUSAN archive incomplete')
    expected=(STAGE/'MUSAN_checksum.txt').read_text(encoding='utf-8')
    if f'{MUSAN_MD5}  musan.tar.gz' not in expected:raise ValueError('Official checksum document mismatch')
    md5=hashlib.md5();sha=hashlib.sha256()
    with archive.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):md5.update(block);sha.update(block)
    if md5.hexdigest()!=MUSAN_MD5:raise ValueError('MUSAN official MD5 verification failed')
    members=[];metadata=[];seen=set();started=time.monotonic();last=started
    with gzip.open(archive,'rb') as decoded:
        with tarfile.open(fileobj=decoded,mode='r|') as tar:
            for member in tar:
                target=safe_member(member.name,STAGE/'official_metadata')
                if member.name in seen:raise ValueError('Duplicate archive path: '+member.name)
                seen.add(member.name)
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise ValueError('Nonregular archive member: '+member.name)
                if member.isfile():
                    members.append({'name':member.name,'bytes':member.size})
                    if Path(member.name).name.upper() in {'README','LICENSE','ANNOTATIONS'}:
                        if member.size>2*1024**2:raise ValueError('Unexpectedly large metadata member')
                        target.parent.mkdir(parents=True,exist_ok=True);data=tar.extractfile(member).read()
                        if len(data)!=member.size:raise ValueError('Truncated metadata')
                        if target.exists() and target.read_bytes()!=data:raise ValueError('Metadata replacement forbidden')
                        if not target.exists():target.write_bytes(data)
                        metadata.append(digest(target))
                if time.monotonic()-last>=15:
                    status={'phase':'noise_archive_index','members':len(members),'elapsed_s':time.monotonic()-started,'updated_utc':now()}
                    save(STAGE/'status.json',status);print(json.dumps(status),flush=True);last=time.monotonic()
        # Consume the gzip trailer even if tar stopped at its end-of-archive blocks.
        while decoded.read(8*1024*1024):pass
    receipt={'schema':'s45_musan_archive_index_v1','status':'VERIFIED','created_utc':now(),
             'archive':{'path':str(archive),'sha256':sha.hexdigest(),'bytes':archive.stat().st_size,
                        'official_md5':MUSAN_MD5,'gzip_crc_checked':True},
             'official_checksum_document':digest(STAGE/'MUSAN_checksum.txt'),
             'metadata':metadata,'members':members,'speech_audio_extracted':False}
    save(STAGE/'MUSAN_INDEX.json',receipt);print(json.dumps({'status':'VERIFIED','members':len(members),'metadata':len(metadata)}),flush=True)
    return receipt

def freeze_selection(selection_path):
    selection=read(selection_path);index=read(STAGE/'MUSAN_INDEX.json')
    if index['status']!='VERIFIED':raise ValueError('Verified archive index required')
    parents=selection['parents'];allowed={v['name'] for v in index['members']}
    ids=set();groups={}
    for parent in parents:
        pid=parent['parent_id']
        if pid in ids:raise ValueError('Duplicate noise parent')
        ids.add(pid)
        if parent['split'] not in {'development','reserve'}:raise ValueError('Invalid split')
        if parent['member_name'] not in allowed or parent['member_name'].startswith('musan/speech/'):
            raise ValueError('Unavailable or speech-branch parent')
        if parent['group_id'] in groups and groups[parent['group_id']]!=parent['split']:
            raise ValueError('Noise source group leaks between splits')
        groups[parent['group_id']]=parent['split']
        if parent['strict_nonspeech_eligible'] and parent['speech_content']!='absent_documented':
            raise ValueError('Unknown/present speech cannot become strict non-speech')
        if parent.get('rights',{}).get('status') not in {'PERMITTED','PERMITTED_WITH_ATTRIBUTION','PERMITTED_WITH_ATTRIBUTION_SHAREALIKE','PUBLIC_DOMAIN_SOURCE_ASSERTION'}:
            raise ValueError('Unresolved/restricted noise rights cannot enter the prepared pool')
        for key in ['category_evidence','speech_content_evidence','rights','attribution','crop_policy']:
            if not parent.get(key):raise ValueError('Missing parent evidence '+key)
        for b in parent['metadata_bindings']:
            if digest(b['path'])['sha256']!=b['sha256']:raise ValueError('Changed license/annotation evidence')
    encoded=json.dumps(selection,sort_keys=True,separators=(',',':')).encode()
    plan_sha=hashlib.sha256(encoded).hexdigest();path=STAGE/'NOISE_SELECTION_FROZEN.json'
    if path.exists():
        old=read(path)
        if old['plan_sha256']!=plan_sha:raise ValueError('Frozen parent plan cannot be overwritten')
        return old
    frozen={'schema':'s45_noise_selection_frozen_v1','status':'FROZEN_BEFORE_WAVEFORM_QC','frozen_utc':now(),
            'selection_source':digest(selection_path),'archive_index':digest(STAGE/'MUSAN_INDEX.json'),
            'plan_sha256':plan_sha,'plan':selection,'code':digest(Path(__file__)),
            'no_reserve_task_scoring':True,'waveform_qc_performed_before_freeze':False}
    save(path,frozen);return frozen

def extract_selected():
    frozen=read(STAGE/'NOISE_SELECTION_FROZEN.json');wanted={p['member_name'] for p in frozen['plan']['parents']}
    index=read(STAGE/'MUSAN_INDEX.json')
    if digest(index['archive']['path'])['sha256']!=index['archive']['sha256']:raise ValueError('Changed official archive')
    extracted={};last=time.monotonic();count=0
    with tarfile.open(index['archive']['path'],'r|gz') as tar:
        for member in tar:
            count+=1
            if member.name not in wanted:continue
            if not member.isfile():raise ValueError('Selected member is not regular')
            target=safe_member(member.name,PAYLOAD/'selected_originals')
            target.parent.mkdir(parents=True,exist_ok=True)
            source=tar.extractfile(member);temp=target.with_name(target.name+'.extracting')
            with temp.open('wb') as dest:shutil.copyfileobj(source,dest,1024*1024)
            if temp.stat().st_size!=member.size:raise ValueError('Selected extraction incomplete')
            if target.exists():
                if digest(temp)['sha256']!=digest(target)['sha256']:raise ValueError('Existing original differs')
                temp.unlink()
            else:os.replace(temp,target)
            extracted[member.name]=digest(target)
            if time.monotonic()-last>=15:
                progress={'phase':'noise_extract_selected','parents_written':len(extracted),'total':len(wanted),'updated_utc':now()}
                save(STAGE/'status.json',progress);print(json.dumps(progress),flush=True);last=time.monotonic()
    if set(extracted)!=wanted:raise ValueError('Missing selected originals')
    hash_splits={}
    for parent in frozen['plan']['parents']:
        sha=extracted[parent['member_name']]['sha256']
        if sha in hash_splits and hash_splits[sha]!=parent['split']:
            raise ValueError('Identical original waveform bytes cross frozen parent splits')
        hash_splits[sha]=parent['split']
    save(STAGE/'SELECTED_ORIGINALS.json',{'status':'COMPLETE','parents':extracted,'frozen_selection':digest(STAGE/'NOISE_SELECTION_FROZEN.json')})
    return extracted

def convert_mono(wave, rate, channel=0):
    import numpy as np
    from scipy.signal import resample_poly
    import math
    x=np.asarray(wave,dtype=np.float32)
    if x.ndim==2:
        if channel<0 or channel>=x.shape[1]:raise ValueError('Source channel unavailable')
        x=x[:,channel]
    if x.ndim!=1 or not np.isfinite(x).all():raise ValueError('Nonfinite or invalid source waveform')
    if rate!=16000:
        factor=math.gcd(int(rate),16000)
        x=resample_poly(x,16000//factor,int(rate)//factor,window=('kaiser',5.0)).astype(np.float32)
    return x

def prepare_sources():
    import numpy as np
    import soundfile as sf
    import scipy
    frozen=read(STAGE/'NOISE_SELECTION_FROZEN.json');originals=read(STAGE/'SELECTED_ORIGINALS.json')['parents']
    parents=[];segments=[];failures=[]
    for parent in frozen['plan']['parents']:
        p=dict(parent);original=originals[p['member_name']]
        if digest(original['path'])['sha256']!=original['sha256']:raise ValueError('Changed selected parent bytes')
        p['original']=original;parents.append(p)
        try:
            info=sf.info(original['path'])
            # This crop rule was fixed before waveform QC. No energy-seeking crop.
            limit_s=p['crop_policy']['maximum_seconds'];frames=min(info.frames,round(limit_s*info.samplerate))
            wave,rate=sf.read(original['path'],frames=frames,dtype='float32',always_2d=True)
            mono=convert_mono(wave,rate,0)
            if not len(mono) or not np.any(mono):raise ValueError('Empty or digital-silent noise source')
            rms=float(np.sqrt(np.mean(mono.astype(np.float64)**2)))
            peak=float(np.max(np.abs(mono)));dc=float(np.mean(mono,dtype=np.float64))
            quality={'decode':'PASS','finite':True,'peak_fs':peak,'rms_fs':rms,'rms_dbfs':20*float(np.log10(max(rms,1e-15))),
                     'dc_fs':dc,'near_rail_samples':int(np.sum(np.abs(mono)>=.9999)),
                     'zero_fraction':float(np.mean(mono==0)),'flags':[],
                     'waveform_quality_is_speech_absence_proof':False,'human_listening_certified':False}
            if peak>=.9999:quality['flags'].append('SOURCE_NEAR_RAIL_SAMPLES_RETAINED')
            if abs(dc)>.01:quality['flags'].append('SOURCE_DC_RETAINED')
            if rms<.0001:quality['flags'].append('FAINT_SOURCE_RETAINED')
            identity={'parent_sha256':original['sha256'],'crop_native_samples':[0,frames],
                      'native_rate_hz':rate,'channel':0,'output_rate_hz':16000,'scalar':1.0,
                      'resample':'scipy.signal.resample_poly_kaiser5' if rate!=16000 else 'none',
                      'scipy_version':scipy.__version__}
            ident=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
            target=PAYLOAD/'prepared'/f'{p["parent_id"]}_{ident[:12]}.wav';target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():sf.write(target,mono,16000,subtype='FLOAT')
            check,check_rate=sf.read(target,dtype='float32')
            if check_rate!=16000 or not np.array_equal(check,mono):raise ValueError('Prepared source byte-content verification failed')
            prepared=digest(target);entry={k:p[k] for k in ['parent_id','split','dataset','category','category_evidence',
                      'speech_content','strict_nonspeech_eligible','rights','attribution']}
            entry.update(noise_id=p['parent_id']+'_s00',prepared_path=str(target),prepared_sha256=prepared['sha256'],
                      prepared_bytes=prepared['bytes'],rate_hz=16000,channels=1,samples=len(mono),duration_s=len(mono)/16000,
                      crop_native_samples=[0,frames],native_rate_hz=rate,original_channels=info.channels,
                      selected_original_channel=0,resampler=identity['resample'],resampler_version=scipy.__version__,
                      scalar=1.0,quality=quality,source_binding=original,transform_identity=identity,
                      parent_group_id=p['group_id'],rights_status=p['rights']['status'])
            segments.append(entry);p['quality_status']='PREPARED'
        except Exception as exc:
            p['quality_status']='QC_FAILED';p['quality_error']=repr(exc)
            failures.append({'parent_id':p['parent_id'],'split':p['split'],'error':repr(exc)})
        progress={'phase':'noise_prepare','finished_parents':len(parents),'total':len(frozen['plan']['parents']),
                  'prepared_segments':len(segments),'failures':len(failures),'updated_utc':now()}
        save(STAGE/'status.json',progress);print(json.dumps(progress),flush=True)
    catalog=read(STAGE/'NOISE_CATALOG.json')
    catalog.update(status='COMPLETE' if not failures else 'COMPLETE_WITH_QC_GAPS',updated_utc=now(),
                   parents=parents,prepared_segments=segments,qc_failures=failures,
                   frozen_selection=digest(STAGE/'NOISE_SELECTION_FROZEN.json'),
                   archive_index=digest(STAGE/'MUSAN_INDEX.json'),adapter_code=digest(Path(__file__)),
                   reserve_task_scoring_performed=False)
    save(STAGE/'NOISE_CATALOG.json',catalog)
    return catalog



def transfer_time_status():
    book=ledger()
    status=read(STAGE/'status.json') if (STAGE/'status.json').exists() else {}
    asof=status.get('updated_utc',now())
    spent=book['active_transfer_wait_s'];remaining_wait=max(0,ACTIVE_CAP_S-spent)
    done=status.get('downloaded_bytes',0);remaining_bytes=max(0,MUSAN_BYTES-done)
    rate=status.get('MiB_per_s',0)*1024**2
    eta=remaining_bytes/rate if rate>0 else None
    complete=[a for a in book['attempts'] if a.get('status')=='COMPLETE' and a.get('url')==MUSAN_URL]
    transfer_complete=bool(complete and (STAGE/'MUSAN_ARCHIVE_RECEIPT.json').exists())
    if transfer_complete:
        # The general status file subsequently describes extraction/preparation.
        # A completed transfer must never appear to restart at zero bytes.
        done=MUSAN_BYTES;remaining_bytes=0;eta=0.0
        asof=complete[-1]['finished_utc']
    at=datetime.datetime.fromisoformat(asof)
    return {'schema':'s45_noise_transfer_time_ledger_v1','updated_utc':now(),
        'transfer_status':'COMPLETE' if transfer_complete else 'IN_PROGRESS_OR_INCOMPLETE',
        'measurement_asof_utc':asof,'downloaded_bytes':done,'remaining_download_bytes':remaining_bytes,
        'new_response_body_bytes':book['new_response_body_bytes'],
        'remaining_response_body_budget_bytes':NETWORK_CAP-book['new_response_body_bytes'],
        'active_transfer_wait_spent_s':spent,'active_transfer_wait_remaining_s':remaining_wait,
        'conditional_active_budget_exhaustion_utc_if_continuous':None if transfer_complete else (at+datetime.timedelta(seconds=remaining_wait)).isoformat(),
        'overall_run_deadline_utc':'2026-09-09T11:13:00+00:00',
        'closeout_reserve_begins_utc':'2026-09-09T10:43:00+00:00',
        'estimated_remaining_download_s':eta,
        'estimated_remaining_download_s_range':[eta*.75,eta*1.5] if eta is not None else None,
        'eta_scope':'Heuristic range from achieved average body throughput; excludes checksum/extraction work and is not a guaranteed completion time.',
        'download_attempt_count':len(book['attempts']),
        'download_ledger':digest(STAGE/'DOWNLOAD_LEDGER.json')}

def watch_download():
    """Read-only to downloader-owned files; publish an independent time ledger."""
    started=time.monotonic()
    while time.monotonic()-started<ACTIVE_CAP_S+60:
        time_status=transfer_time_status()
        save(STAGE/'TRANSFER_TIME_LEDGER.json',time_status)
        print(json.dumps(time_status),flush=True)
        if (PAYLOAD/'downloads/musan.tar.gz').exists():
            # Do not race the downloader's post-write hashing/receipt completion.
            if (STAGE/'MUSAN_ARCHIVE_RECEIPT.json').exists():
                index_musan();return
        if time_status['active_transfer_wait_remaining_s']<=0:raise RuntimeError('Download active budget exhausted')
        time.sleep(30)
    raise TimeoutError('Bounded download watcher ended without completion')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--initialize',action='store_true')
    p.add_argument('--download-musan',action='store_true');p.add_argument('--url');p.add_argument('--target')
    p.add_argument('--expected-bytes',type=int);p.add_argument('--expected-md5')
    p.add_argument('--index-musan',action='store_true');p.add_argument('--freeze-selection',type=Path)
    p.add_argument('--extract-selected',action='store_true');p.add_argument('--prepare',action='store_true')
    p.add_argument('--watch-download',action='store_true');p.add_argument('--time-status',action='store_true');a=p.parse_args()
    initialize()
    if a.watch_download:watch_download()
    elif a.time_status:save(STAGE/'TRANSFER_TIME_LEDGER.json',transfer_time_status())
    elif a.index_musan:index_musan()
    elif a.freeze_selection:freeze_selection(a.freeze_selection)
    elif a.extract_selected:extract_selected()
    elif a.prepare:prepare_sources()
    elif a.download_musan:
        result=download(MUSAN_URL,PAYLOAD/'downloads/musan.tar.gz',MUSAN_BYTES,MUSAN_MD5)
        save(STAGE/'MUSAN_ARCHIVE_RECEIPT.json',result);print(json.dumps(result),flush=True)
    elif a.url:
        if not a.target:p.error('--target required')
        if not Path(a.target).resolve().is_relative_to(PAYLOAD.resolve()):p.error('--target must remain within the approved noise payload root')
        print(json.dumps(download(a.url,a.target,a.expected_bytes,a.expected_md5)),flush=True)

if __name__=='__main__':main()
