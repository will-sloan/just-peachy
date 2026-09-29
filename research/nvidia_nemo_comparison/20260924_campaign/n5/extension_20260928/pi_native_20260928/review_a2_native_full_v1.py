"""Independent A2 failure/lifecycle reader. See README_REVIEW_A2_NATIVE_FULL_V1.md."""
import argparse, json, sys
from pathlib import Path
from dispatch_geometry_v2 import remote, PRIVATE, REMOTE


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',choices=['a2-native-full-v1'],required=True);args=p.parse_args()
    x=remote('ROOT='+repr(REMOTE)+'\nRUN='+repr(args.run_id)+'\n'+r'''
import hashlib,json,subprocess,fcntl
from pathlib import Path
r=Path(ROOT);d=r/RUN
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
docs={n:json.loads((d/n).read_text()) for n in ['ADMISSION.json','BINDING.json','OWNER.json','DISPATCH_OWNER.json','LIVE_ENVELOPE.json','RESULT.json','DISPATCH_RESULT.json'] if (d/n).exists()}
a=docs['ADMISSION.json'];e=docs['LIVE_ENVELOPE.json'];result=docs.get('RESULT.json');dispatch=docs['DISPATCH_RESULT.json']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==a['boot_id']
for n in ['OWNER.json','DISPATCH_OWNER.json']:
 o=docs[n];assert o['boot_id']==a['boot_id'] and ticks(o['pid'])!=o['start_ticks']
assert e['owner']==docs['OWNER.json'] and int(e['properties']['MainPID'])==e['owner']['pid']
assert e['properties']['LoadState']=='loaded' and e['properties']['ActiveState']=='active'
assert e['properties']['RuntimeMaxUSec']=='10min' and e['properties']['CPUQuotaPerSecUSec']=='2s'
assert e['properties']['TasksMax']=='64' and int(e['properties']['LimitAS'])==a['address_space_max_bytes']
assert e['address_space']==[a['address_space_max_bytes']]*2 and e['stack']==[1048576]*2
assert e['affinity']==[2,3] and int(e['cpu_max'][0])/int(e['cpu_max'][1])==2
for row in a['files']:assert sha(row['path'])==row['sha256']
binding=docs['BINDING.json'];assert sha(binding['model_path'])==binding['model_sha256']
assert binding['variant']=='A2' and binding['gpu']==-1 and binding['right_context']==1
assert not dispatch['log_overflow'] and not dispatch.get('memory_guard',False)
size=sum(p.stat().st_size for p in d.rglob('*') if p.is_file());assert size<a['output_max_bytes']
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
assert ticks(1013)==569 and ticks(1130)==607
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256']
assert sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
for p in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with p.open('r+b') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
log=(d/'service.log').read_text()
if result is None:
 assert dispatch['exit_code']==255 and 'status=ABRT' in log and '157.81 MB' in log
 status='REVIEWED_A2_GRAPH_ALLOCATION_ABORT_OS_CLOSURE_ONLY'
elif result['status']=='FAILED_PRESERVED':
 assert result['sessions']==[] and result['load_seconds']>0 and result['model_closed']
 assert dispatch['exit_code']==1 and '930624512' in log and 'out of device memory?' in result['error']
 status='REVIEWED_A2_STREAM_ALLOCATION_FAILURE_AND_CLEAN_CLOSURE_ONLY'
else:
 assert dispatch['exit_code']==0 and result['model_closed'] and len(result['sessions'])==2
 events=[json.loads((d/('EVENTS_'+str(i)+'.json')).read_text()) for i in range(2)]
 assert events[0]==events[1]
 assert any(e['raw_text'].strip() for e in events[0])
 for rows in events:
  counts=[e['input_samples'] for e in rows];assert counts==sorted(counts) and max(counts)==715127 and min(counts)>=0
  assert rows[-1]['final'] and all(e['input_end_sec']==e['input_samples']/16000 for e in rows)
 for i,row in enumerate(result['sessions']):
  assert row['input_samples']==715127 and row['finish_idempotent'] and row['post_finish_rejected']
  assert sha(d/('EVENTS_'+str(i)+'.json'))==row['event_sha256']
 status='PASS_A2_FULL_SOURCE_RESIDENT_REPEAT_LIFECYCLE_ONLY'
samples=dispatch['samples'];peaks={k:max(s.get(k,0) for s in samples) for k in ['VmSize','VmPeak','VmRSS','Threads']}
review=dict(status=status,run=RUN,source_bindings_verified=True,live_unit_envelope_verified=True,
 address_space_max_bytes=a['address_space_max_bytes'],minimum_available_ram_bytes=a['minimum_available_ram_bytes'],
 input_samples_processed=None if result is None else (0 if not result['sessions'] else 1430254),model_buffer_request_bytes=None,
 transcript_nonempty_events=sum(bool(e['raw_text']) for e in events[0]) if result and result['sessions'] else None,
 natural_exit_code=dispatch['exit_code'],recognizer_closed=bool(result and result['model_closed']),exact_owners_closed=True,
 baseline_unchanged=True,capture_closed=True,leases_free=True,output_bytes=size,output_bound_bytes=a['output_max_bytes'],
 sampled_peaks=peaks,kernel_ru_maxrss_kib=result['ru_maxrss_kib'] if result else None,full_source_functional=bool(result and result['sessions']),forced_endpoint_qualified=False,independent_runtime_reference_parity=False,stage_acceptance=False,
 hashes={n:sha(d/n) for n in docs})
print(json.dumps({'review':review,'receipts':docs,'log':log}))
''')
    out=PRIVATE/(args.run_id+'-evidence')
    for n,v in x['receipts'].items():
        dest=out/n
        if not dest.exists():
            with dest.open('x') as f:json.dump(v,f,indent=2)
    with (out/'service.log').open('x') as f:f.write(x['log'])
    with (out/'REVIEW.json').open('x') as f:json.dump(x['review'],f,indent=2)
    print(json.dumps(x['review']))


if __name__=='__main__':main()
