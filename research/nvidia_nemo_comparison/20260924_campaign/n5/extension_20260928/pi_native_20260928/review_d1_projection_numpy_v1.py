"""Independent array/closure review and backup; README_D1_PROJECTION_NUMPY_V1.md."""
import hashlib,io,json,subprocess,tarfile
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE
from dispatch_b01_stack_v2 import SSH


def main():
    psutil.Process().cpu_affinity([14])
    out=PRIVATE/'d1-projection-numpy-v1-evidence'
    assert not (out/'REVIEW.json').exists() and not (out/'target').exists()
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import hashlib,json,subprocess,fcntl,ast,zipfile,struct,math,os,resource,signal
from pathlib import Path
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(256*1024**2,)*2);signal.alarm(110)
r=Path(ROOT);d=r/'d1-projection-numpy-v1'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def array(z,name):
 raw=z.read(name+'.npy');assert raw[:6]==b'\x93NUMPY' and raw[6] in (1,2)
 size=2 if raw[6]==1 else 4;n=int.from_bytes(raw[8:8+size],'little');offset=8+size+n
 h=ast.literal_eval(raw[8+size:offset].decode('latin1'));assert not h['fortran_order'] and h['descr'] in ('<f4','<f8','<i8')
 count=math.prod(h['shape']);fmt={'<f4':'f','<f8':'d','<i8':'q'}[h['descr']];assert len(raw)-offset==count*struct.calcsize(fmt)
 v=struct.unpack('<'+str(count)+fmt,raw[offset:]);assert all(math.isfinite(t) for t in v)
 return h,v,raw
names=['ADMISSION.json','OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','RESULT.json','DISPATCH_RESULT.json']
docs={n:json.loads((d/n).read_text()) for n in names};a=docs['ADMISSION.json'];e=docs['LIVE_ENVELOPE.json'];v=docs['RESULT.json'];di=docs['DISPATCH_RESULT.json']
assert v['status']=='NATIVE_NUMPY_PROJECTION_OBSERVATIONS_REVIEW_REQUIRED' and di['exit_code']==0
assert not any(di[k] for k in ['log_overflow','memory_guard','output_guard'])
assert v['session_released'] and v['absolute_tolerance']==a['absolute_tolerance']==1e-5 and not v['gate_relaxed']
assert v['kernel']=='numpy_float32_matmul_original_weight_transpose' and v['numpy_version']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=docs[n];assert o['boot_id']==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert e['owner']==docs['OWNER.json']==v['owner'] and int(e['properties']['MainPID'])==v['owner']['pid']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and e['properties']['RuntimeMaxUSec']=='5min'
assert e['properties']['TasksMax']=='64' and e['properties']['CPUQuotaPerSecUSec']=='2s'
assert int(e['properties']['LimitAS'])==a['address_space_max_bytes']==768*1024**2 and int(e['properties']['LimitSTACK'])==1024**2
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1024**2]*2 and e['affinity']==[2,3]
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2 and di['seconds']<300
for row in a['files']:assert sha(row['path'])==row['sha256']
assert sha(d/'projection_weight.npy')==a['projection_weight_sha256']
assert e['properties']['TimeoutStopUSec']=='10s' and int(e['properties']['LimitFSIZE'])==4*1024**2
assert sha(d/'HOST_REVIEW.json')==a['host_reference_review_sha256']
checks=[]
for name,frames in [('tail',8),('full_first',2120),('full_middle',2128),('full_tail',253)]:
 assert sha(Path(a['reference_directory'])/(name+'.npz'))==a['reference_files'][name+'.npz']
 rows=[row for row in v['cases'] if row['case']==name];assert [row['repeat'] for row in rows]==[0,1]
 with zipfile.ZipFile(Path(a['reference_directory'])/(name+'.npz')) as ref,zipfile.ZipFile(d/(name+'-native-0.npz')) as first,zipfile.ZipFile(d/(name+'-native-1.npz')) as second:
  hr,vr,_=array(ref,'pytorch');hh,vh,_=array(ref,'basic');h0,v0,raw0=array(first,'embedding');h1,v1,raw1=array(second,'embedding')
  assert hr==hh==h0==h1 and raw0==raw1 and h0['shape']==(1,(frames+7)//8,512)
  delta=max(abs(a-b) for a,b in zip(vr,v0));host_delta=max(abs(a-b) for a,b in zip(vh,v0))
  _,v64,_=array(ref,'float64_accumulation');diagnostic_delta=max(abs(a-b) for a,b in zip(v64,v0))
  for row in rows:assert row['float64_diagnostic_maxabs']==diagnostic_delta and row['reference_maxabs']==delta and row['host_ort_maxabs']==host_delta and row['within_unchanged_gate']==(delta<=1e-5)
  for field in ['stack','lengths']:
   h,_,raw=array(ref,field);hf,_,rf=array(first,field);hs,_,rs=array(second,field);assert h==hf==hs and raw==rf==rs
  checks.append(dict(case=name,feature_frames=frames,reference_maxabs=delta,host_ort_maxabs=host_delta,within_unchanged_gate=delta<=1e-5,float64_diagnostic_maxabs=diagnostic_delta,repeat_exact=True,stack_lengths_exact=True,seconds=[row['seconds'] for row in rows]))
assert len(v['cases'])==8 and v['all_reference_cases_within_gate']==all(row['within_unchanged_gate'] for row in checks)
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for path in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with path.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in d.iterdir() if p.is_file()}
assert len(files)==len(list(d.iterdir()));total=sum(row['bytes'] for row in files.values());assert total<a['output_max_bytes']==16*1024**2
review=dict(status='PASS_NATIVE_NUMPY_PROJECTION_CASES_ONLY' if all(c['within_unchanged_gate'] for c in checks) else 'REVIEWED_NATIVE_NUMPY_PROJECTION_MISMATCH_ONLY',cases=checks,
 absolute_tolerance=1e-5,gate_relaxed=False,numpy_version=v['numpy_version'],kernel=v['kernel'],kernel_protocol_seconds=v['kernel_protocol_seconds'],protocol_seconds=v['seconds'],kernel_peak_rss_kib=v['ru_maxrss_kib'],
 sampled_peaks={k:max((s.get(k,0) for s in di['samples']),default=None) for k in ['VmSize','VmPeak','VmRSS','Threads']},
 actual_live_envelope_verified=True,exact_owners_closed=True,natural_exit_code=0,baseline_unchanged=True,capture_closed=True,leases_free=True,
 output_bytes=total,output_bound_bytes=a['output_max_bytes'],full_waveform_qualified=False,speedup_qualified=False,stage_acceptance=False)
print(json.dumps(dict(review=review,files=files)))
''')
    reference=PRIVATE/'d1-onnx-projection-v1'
    for name in ['projection_weight.npy']:
        with (reference/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==x['files'][name]['sha256']
    with (reference/'REVIEW.json').open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==x['files']['HOST_REVIEW.json']['sha256']
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    # Read only this flat owned directory; refuse traversal, links or unexpected names.
    data=subprocess.check_output(SSH+['tar -C '+REMOTE+'/d1-projection-numpy-v1 -cf - .'],timeout=90)
    backup=out/'target';backup.mkdir();seen=set()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tar:
        for member in tar:
            if member.isdir():assert member.name=='.';continue
            assert member.isfile() and member.name.startswith('./')
            name=member.name[2:];assert '/' not in name and '\\' not in name and name in x['files'] and name not in seen
            raw=tar.extractfile(member).read();expected=x['files'][name]
            assert len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']
            with (backup/name).open('xb') as f:f.write(raw)
            assert hashlib.sha256((backup/name).read_bytes()).hexdigest()==expected['sha256'];seen.add(name)
    assert seen==set(x['files'])
    combined=x['review']['output_bytes']+sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    assert combined+128*1024<32*1024**2
    x['review'].update(backup_verified=True,backup_files=len(seen),combined_stage_backup_bytes=combined)
    for name,doc in [('BACKUP.json',x['files']),('REVIEW.json',x['review'])]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(doc,f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':main()
