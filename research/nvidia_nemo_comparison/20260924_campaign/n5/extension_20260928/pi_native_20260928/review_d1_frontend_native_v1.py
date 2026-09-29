"""Independent stdlib NPY and exact native closure reader; README_REVIEW_D1_FRONTEND_NATIVE_V1.md."""
import json
from dispatch_geometry_v2 import remote,PRIVATE,REMOTE


def main():
    x=remote('ROOT='+repr(REMOTE)+'\n'+r'''
import hashlib,json,subprocess,fcntl,ast,zipfile,struct,math,os
from pathlib import Path
os.sched_setaffinity(0,{3});r=Path(ROOT);d=r/'d1-frontend-native-v1'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def array(z,name):
 raw=z.read(name+'.npy');assert raw[:6]==b'\x93NUMPY'
 v=raw[6];assert v in (1,2)
 hs=2 if v==1 else 4;length=int.from_bytes(raw[8:8+hs],'little');offset=8+hs+length
 h=ast.literal_eval(raw[8+hs:offset].decode('latin1'));assert not h['fortran_order']
 assert h['descr'] in ('<f4','<i8');count=math.prod(h['shape']);fmt='f' if h['descr']=='<f4' else 'q'
 assert len(raw)-offset==count*struct.calcsize(fmt)
 values=struct.unpack('<'+str(count)+fmt,raw[offset:]);assert all(math.isfinite(v) for v in values)
 return h,values,raw
names=['ADMISSION.json','OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','RESULT.json','DISPATCH_RESULT.json']
docs={n:json.loads((d/n).read_text()) for n in names};a=docs['ADMISSION.json'];e=docs['LIVE_ENVELOPE.json'];v=docs['RESULT.json'];di=docs['DISPATCH_RESULT.json']
assert v['status']=='NATIVE_FRONTEND_CASES_REVIEW_REQUIRED' and di['exit_code']==0 and not di['log_overflow'] and not di['memory_guard']
assert v['session_released'] and v['invalid_cases_rejected']==4 and v['absolute_tolerance']==a['absolute_tolerance']==1e-4
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=docs[n];assert o['boot_id']==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert e['owner']==docs['OWNER.json']==v['owner'] and int(e['properties']['MainPID'])==v['owner']['pid']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active' and e['properties']['RuntimeMaxUSec']=='5min'
assert e['properties']['TasksMax']=='64' and e['properties']['CPUQuotaPerSecUSec']=='2s'
assert int(e['properties']['LimitAS'])==768*1024**2==a['address_space_max_bytes'] and int(e['properties']['LimitSTACK'])==1024**2
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1024**2]*2 and e['affinity']==[2,3]
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
checks=[];extra_hashes={}
case_names=['empty','one','hop_minus','hop_exact','hop_plus','tail','full','zero','impulse']
for name,entry in zip(case_names,v['cases']):
 assert name==entry['case'] and entry['repeat_exact'] and entry['input_bytes_unchanged']
 with zipfile.ZipFile(d/(name+'.npz')) as reference:
  hr,vr,_=array(reference,'reference');hl,vl,_=array(reference,'length');ha,va,_=array(reference,'audio')
  n=ha['shape'][0];valid=n//160;width=((valid+1+15)//16)*16
  assert vl==(valid,) and hr['shape']==(1,128,width)
  differences=[];first_raw=None
  for mode in ['fixed','irregular','repeat']:
   with zipfile.ZipFile(d/(name+'-native-'+mode+'.npz')) as output:hg,vg,raw=array(output,'output')
   assert hr==hg
   delta=max((abs(x-y) for x,y in zip(vr,vg)),default=0.0);assert delta<=1e-4
   assert all(x==0 for i,x in enumerate(vg) if i%width>=valid)
   if mode=='fixed':first_raw=raw
   if mode=='repeat':assert raw==first_raw
   differences.append(delta)
  checks.append(dict(case=name,samples=n,valid_frames=valid,max_abs=differences,repeat_exact=True,seconds=entry['seconds'],maximum_buffer_samples=entry['maximum_buffer_samples']))
 for suffix in ['.npz','-native-fixed.npz','-native-irregular.npz','-native-repeat.npz']:extra_hashes[name+suffix]=sha(d/(name+suffix))
assert len(checks)==len(v['cases'])==9
assert [x['samples'] for x in checks]==[0,1,159,160,161,1281,715127,3201,1600]
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for p in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in d.rglob('*') if p.is_file());assert size<a['output_max_bytes']
peaks={k:max(x.get(k,0) for x in di['samples']) for k in ['VmSize','VmPeak','VmRSS','Threads']}
review=dict(status='PASS_NATIVE_FRONTEND_FULL_EDGE_IRREGULAR_ONLY',cases=checks,absolute_tolerance=1e-4,
 kernel_peak_rss_kib=v['ru_maxrss_kib'],sampled_peaks=peaks,actual_live_envelope_verified=True,exact_owners_closed=True,natural_exit_code=0,
 baseline_unchanged=True,capture_closed=True,leases_free=True,output_bytes=size,output_bound_bytes=a['output_max_bytes'],
 full_model_qualified=False,complete_driver=False,speedup_qualified=False,stage_acceptance=False,input_output_hashes=extra_hashes,hashes={n:sha(d/n) for n in docs})
print(json.dumps(dict(review=review,docs=docs,log=(d/'service.log').read_text())))
''')
    out=PRIVATE/'d1-frontend-native-v1-evidence'
    # Confirm copied inputs correspond to the previously reviewed host reference files.
    import hashlib
    for n in ['empty','one','hop_minus','hop_exact','hop_plus','tail','full','zero','impulse']:
        with (PRIVATE/'d1-onnx-frontend-v1'/(n+'.npz')).open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        assert h==x['review']['input_output_hashes'][n+'.npz']
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    for n,v in x['docs'].items():
        with (out/n).open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
    with (out/'service.log').open('x',encoding='utf-8') as f:f.write(x['log'])
    with (out/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(x['review'],f,indent=2)
    print(json.dumps({k:x['review'][k] for k in ['status','cases','kernel_peak_rss_kib','sampled_peaks','output_bytes']}))


if __name__=='__main__':main()
