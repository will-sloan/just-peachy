"""Independent timing/event audit; README_REVIEW_SERIALIZATION_PROBE_V1.md."""
import json
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    run='serialization-probe-v1'
    v=remote('RUN='+repr(run)+'\n'+r'''
import os,json,hashlib,sys,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3});d=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN
sys.path.insert(0,str(d));from review_live_artifacts_v1 import decode
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
a=json.loads((d/'ADMISSION.json').read_text());r=json.loads((d/'RESULT.json').read_text());dispatch=json.loads((d/'DISPATCH_RESULT.json').read_text());e=json.loads((d/'LIVE_ENVELOPE.json').read_text())
assert r['status']=='COLLECTED_SERIALIZATION_SCHEDULING_DIAGNOSTIC_ONLY' and dispatch['exit_code']==0 and not dispatch['memory_guard'] and not dispatch['log_overflow']
assert e['address_space']==[768*1024**2]*2 and e['stack']==[1048576]*2 and e['affinity']==[2,3]
assert int(e['cpu_max'][0])/int(e['cpu_max'][1])==2 and e['properties']['TasksMax']=='64' and e['properties']['RuntimeMaxUSec']=='5min'
assert e['properties']['TimeoutStopUSec']=='10s' and int(e['properties']['LimitFSIZE'])==8*1024**2
for row in a['files']:assert sha(row['path'])==row['sha256']
for name in ['OWNER.json','DISPATCH_OWNER.json','PROBE_OWNER.json']:
 o=json.loads((d/name).read_text());assert not(o['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip() and ticks(o['pid'])==o['start_ticks'])
assert not subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True).strip()
original=next(v for v in decode(Path(a['event_journal'])) if v['event_type']=='n2_diarization_frames')
assert len(original['payload']['probabilities'])==2112
assert hashlib.sha256(json.dumps(original,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==r['event_sha256']
times={label:json.loads((d/file).read_text()) for label,file in [('python_thread_intervals','THREAD_TIMES.json'),('separate_process_intervals','PEER_TIMES.json')]}
for values in times.values():assert 1<len(values)<20000 and all(b>a for a,b in zip(values,values[1:]))
for phase in r['phases']:
 assert phase['start_ns']<phase['end_ns']
 for label,values in times.items():
  gaps=[b-a for a,b in zip(values,values[1:]) if phase['start_ns']<=a and b<=phase['end_ns']]
  measured=dict(count=len(gaps),max_ns=max(gaps),above_10ms=sum(v>10000000 for v in gaps),above_32ms=sum(v>32000000 for v in gaps),above_90ms=sum(v>90000000 for v in gaps))
  assert measured==phase[label]
 assert phase['cpu_delta']=={k:phase['cpu_after'][k]-v for k,v in phase['cpu_before'].items()}
for item in r['artifacts']:
 assert list(decode(d/item['variant']/'events.jsonl'))==[original]*3
 archive=Path(item['archive_path']);assert archive.is_relative_to(d)
 rows=list(decode(archive/'events.jsonl'));assert len(rows)==3 and all(v['payload']==original['payload'] and v['kind']==original['event_type'] for v in rows)
 m=json.loads((archive/'epoch.json').read_text());assert m['closed'] and not m['archive_error'] and m['queue_items']==m['queue_bytes']==0 and m['accepted_items']==m['completed_items']
 assert not m['audio_enabled'] and not (archive/'model_input.wav').exists()
 assert item['engine_metrics']['events']==3 and item['engine_metrics']['closed'] and item['engine_metrics']['status']=='COMPLETE'
assert r['peer_closed'] and r['thread_closed'] and not r['capture'] and not r['models_loaded'] and not r['live_fault_cause_proven'] and not r['application_candidate_integrated']
assert ticks(1013)==569 and ticks(1130)==607 and Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed'
assert sha(Path.home()/'JustPeachy/install/current.json')==a['install_sha256'] and sha(Path.home()/'JustPeachy/data/live_config.json')==a['live_config_sha256']
size=sum(p.stat().st_size for p in d.rglob('*') if p.is_file());assert size<a['target_output_max_bytes']
print(json.dumps(dict(status='PASS_NATIVE_RETAINED_PACKET_EXACT_TIMING_DIAGNOSTIC_ONLY',phases=r['phases'],artifacts=r['artifacts'],peak_rss_bytes=r['peak_rss_bytes'],elapsed_seconds=r['elapsed_seconds'],output_bytes=size,owners_closed=True,capture=False,models_loaded=False,baseline_unchanged=True,causal_live_repair_qualified=False,bindings={n:sha(d/n) for n in ['RESULT.json','ADMISSION.json','LIVE_ENVELOPE.json','DISPATCH_RESULT.json','THREAD_TIMES.json','PEER_TIMES.json']})))
''')
    assert json.loads((PRIVATE/(run+'-evidence')/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    with (PRIVATE/(run+'-evidence')/'REVIEW.json').open('x') as f:json.dump(v,f,indent=2)
    remote('RUN='+repr(run)+'\nV='+repr(v)+'\n'+"import json\nfrom pathlib import Path\np=Path.home()/'JustPeachy/research/nemotron-20260928'/RUN/'REVIEW.json'\nwith p.open('x') as f:json.dump(V,f,indent=2)\nprint(json.dumps({'written':True}))")
    print(json.dumps(dict(status=v['status'],phases=[dict(name=p['name'],thread_max_ms=p['python_thread_intervals']['max_ns']/1e6,peer_max_ms=p['separate_process_intervals']['max_ns']/1e6,throttled=p['cpu_delta']['nr_throttled']) for p in v['phases']])))


if __name__=='__main__':main()
