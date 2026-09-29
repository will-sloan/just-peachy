"""Read-only edge-run review; see README_REVIEW_A2_NATIVE_EDGES_V1.md."""
import json
from dispatch_geometry_v2 import remote, PRIVATE, REMOTE


def main():
    x = remote('ROOT='+repr(REMOTE)+'\n'+r'''
import hashlib,json,subprocess,fcntl,math
from pathlib import Path
r=Path(ROOT);d=r/'a2-native-edges-v1'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
names=['ADMISSION.json','BINDING.json','OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','RESULT.json','DISPATCH_RESULT.json','FORCE_RECEIPT.json']
docs={n:json.loads((d/n).read_text()) for n in names}
a=docs['ADMISSION.json'];e=docs['LIVE_ENVELOPE.json'];result=docs['RESULT.json'];dispatch=docs['DISPATCH_RESULT.json']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=docs[n];assert o['boot_id']==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert e['owner']==docs['OWNER.json']==result['owner'] and int(e['properties']['MainPID'])==e['owner']['pid']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active'
assert e['properties']['RuntimeMaxUSec']=='5min' and e['properties']['CPUQuotaPerSecUSec']=='2s'
assert e['properties']['TasksMax']=='64' and int(e['properties']['LimitAS'])==a['address_space_max_bytes']==1536*1024**2
assert e['address_space']==[a['address_space_max_bytes']]*2 and e['stack']==[1048576]*2
assert e['affinity']==[2,3] and int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
b=docs['BINDING.json'];assert sha(b['model_path'])==b['model_sha256']
assert b['variant']=='A2' and b['gpu']==-1 and b['right_context']==1
assert not dispatch['log_overflow'] and not dispatch['memory_guard'] and dispatch['exit_code']==0
assert result['status']=='EDGE_PROTOCOL_COLLECTED_REVIEW_REQUIRED' and result['model_closed']
assert len(result['sessions'])==4
expected=[('empty',0),('one_sample',1),('short_tail',1281),('saved_source_forced',715127)]
metrics=[]
for row,(name,count) in zip(result['sessions'],expected):
 assert row['case']==name and row['input_samples']==count
 assert all(row[k] for k in ['finish_idempotent','post_finish_rejected','post_finish_empty_drain','stream_closed'])
 assert math.isfinite(row['seconds']) and row['seconds']>=0
 en='EVENTS_'+name+'.json';cn='CASE_'+name+'_COMPLETED.json'
 ev=json.loads((d/en).read_text());assert sha(d/en)==row['event_sha256'] and json.loads((d/cn).read_text())==row
 assert len(ev)==row['events'] and sum(bool(v['final']) for v in ev)==row['finals']
 counts=[v['input_samples'] for v in ev];assert counts==sorted(counts) and min(counts)>=0 and max(counts)==count
 assert ev[-1]['final'] and all(v['input_end_sec']==v['input_samples']/16000 for v in ev)
 assert all(v['phase'] in ['push','forced_endpoint','finish'] for v in ev)
 forced=[v for v in ev if v['phase']=='forced_endpoint']
 if name=='saved_source_forced':
  assert row['forced_endpoint'] and row['force_at_samples']==197440
  assert len(forced)==1 and forced[0]['input_samples']==197440 and forced[0]['final']
  assert any(v['raw_text'].strip() for v in ev)
  assert any(v['input_samples']>197440 for v in ev)
 else:assert not row['forced_endpoint'] and row['force_at_samples'] is None and not forced
 docs[en]=ev;docs[cn]=row
 metrics.append(dict(case=name,input_samples=count,events=len(ev),finals=row['finals'],seconds=row['seconds']))
assert docs['FORCE_RECEIPT.json']==dict(case='saved_source_forced',input_samples=197440,events=1,native_call_returned=True)
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for p in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
size=sum(p.stat().st_size for p in d.rglob('*') if p.is_file());assert size<a['output_max_bytes']
review=dict(status='PASS_A2_EMPTY_TAIL_FORCED_ENDPOINT_LIFECYCLE_ONLY',cases=metrics,
 source_bindings_verified=True,live_unit_envelope_verified=True,exact_owners_closed=True,
 baseline_unchanged=True,capture_closed=True,leases_free=True,natural_exit_code=0,
 output_bytes=size,output_bound_bytes=a['output_max_bytes'],kernel_ru_maxrss_kib=result['ru_maxrss_kib'],
 forced_endpoint_at_samples=197440,forced_final_and_continued_passage=True,
 original_cpp_reader_executed=False,malformed_wav_qualified=False,independent_runtime_parity=False,
 accuracy_qualified=False,integrated_B02_qualified=False,stage_acceptance=False,
 hashes={n:sha(d/n) for n in docs})
print(json.dumps(dict(review=review,receipts=docs,log=(d/'service.log').read_text())))
''')
    out=PRIVATE/'a2-native-edges-v1-evidence'
    for n,v in x['receipts'].items():
        p=out/n
        if not p.exists():
            with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
    with (out/'service.log').open('x',encoding='utf-8') as f:f.write(x['log'])
    with (out/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(x['review'],f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':main()
