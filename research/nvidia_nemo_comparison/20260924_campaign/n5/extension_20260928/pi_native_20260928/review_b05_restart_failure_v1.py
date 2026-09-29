"""Inspect failed B05 restart without promoting it. See README_B05_RESTART_FAILURE_V1.md."""
import hashlib
import json
from pathlib import Path
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    code=r'''
import json,os,hashlib
from pathlib import Path
os.sched_setaffinity(0,{3})
d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-stop-restart-v2')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256']
o=json.loads((d/'OWNER.json').read_text());p=Path('/proc',str(o['pid']),'stat')
ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
assert not(ticks==o['start_ticks'] and o['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip())
r=json.loads((d/'RESULT.json').read_text());sessions=[]
bindings={n:sha(d/n) for n in ['RESULT.json','ADMISSION.json','STOP_SNAPSHOT.json','EARLY_STOP.json']}
for item in r['sessions']:
 s=Path(item['session_dir']);assert s.parent==d/'data/sessions'
 docs={n:json.loads((s/n).read_text()) for n in ['session_summary.json','session_finalization_v3.json','s6d_consumer_closure.json']}
 events=[json.loads(line) for line in (s/'events.jsonl').read_text().splitlines()]
 sessions.append(dict(item=item,documents=docs,failures=[e['payload'] for e in events if e['event_type']=='failure'],probability_frames=sum(len(e['payload']['probabilities']) for e in events if e['event_type']=='n2_diarization_frames')))
 for p in [s/'events.jsonl',*[s/n for n in docs]]:bindings[str(p.relative_to(d))]=sha(p)
print(json.dumps(dict(result=r,sessions=sessions,stop_snapshot=json.loads((d/'STOP_SNAPSHOT.json').read_text()),bindings=bindings,owner_closed=True)))
'''
    x=remote(code);r=x['result'];out=PRIVATE/'b05-stop-restart-v2-evidence'
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==1
    assert r['status']=='FAILED_PRESERVED' and r['controller_closed']
    assert r['harness_retains_early_engine'] is False
    assert len(x['sessions'])==2
    a,b=x['sessions'];n=a['item']['source_samples']
    assert 128000<=n<715127
    for s in x['sessions']:
        f=s['documents']['session_finalization_v3.json']
        assert not f['live_lanes_at_finalization'] and not f['finalization_error']
        assert f['event_and_transcript_handles_closed'] and not f['resident_bundle_lease_retained']
        c=s['documents']['s6d_consumer_closure.json'];assert c['full_event_consumer_drained']
        assert c['queues']['event_consumer']['depth']==0
        for name in ('journal','punctuation','policy'):
            q=c['queues'][name]
            assert q['closed'] and not q['thread_alive'] and not q['error'] and q['depth']==0 and q['accepted']==q['completed']
    assert a['documents']['session_finalization_v3.json']['state']=='COMPLETED' and not a['failures']
    t=a['documents']['session_summary.json']['telemetry']
    assert t['identity_audio_samples']==t['paired_audio_samples']==n and t['audio_frames_dropped']==0
    for name in ('asr_accept','diarizer_push'):assert t['component_costs']['rows'][name]['successful_samples']==n
    for row in t['component_costs']['rows'].values():assert row['errors']==row['in_flight']==0 and row['started']==row['completed']
    assert t['n2_embedding_calls']==0 and x['stop_snapshot']['metrics']['last_worker_cleanup']['owned_threads_joined']
    arc=x['stop_snapshot']['sessions']['last_archive']
    assert arc['closed'] and not arc['worker_alive'] and not arc['loss'] and not arc['archive_error'] and arc['source_samples']==n
    assert b['documents']['session_finalization_v3.json']['state']=='FAILED'
    assert b['failures'] and 'std::bad_alloc' in b['failures'][0]['reason']
    review=dict(status='FAIL_FULL_RESTART_WITH_SCOPED_EARLY_STOP_PASS',bindings=x['bindings'],early_stop_samples=n,
                early_stop_probability_frames=a['probability_frames'],early_stop_worker_and_archive_drain=True,
                stop_request_to_return_seconds=a['item']['stop_completed_monotonic']-a['item']['stop_requested_monotonic'],
                restart_samples=b['item']['source_samples'],restart_failure=b['failures'],
                application_failure_finalized=True,natural_exit_code=1,owner_closed=True,stage_accepted=False,
                harness_retains_early_engine=False,early_engine_alive_after_release=r['early_engine_alive_after_release'],
                cause_exclusively_harness=False)
    for name,value in [('FAILURE_AUDIT_INPUTS.json',x),('REVIEW.json',review)]:
        with (out/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    remote("import json\nfrom pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b05-stop-restart-v2/REVIEW.json')\nassert not p.exists()\np.write_text("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k not in ('bindings','restart_failure')},indent=2))


if __name__=='__main__':main()
