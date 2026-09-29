"""Read the closed B01 native-stack failure; see README_B01_NATIVE_STACK_FAILURE_V1.md."""
import hashlib
import json
import psutil
from dispatch_geometry_v2 import remote, PRIVATE


def main():
    psutil.Process().cpu_affinity([14])
    out = PRIVATE / 'b01-native-stack-v2-evidence'
    launch = json.loads((out/'LAUNCH_RESULT.json').read_text(encoding='utf-8'))
    log = (out/'launch.log').read_text(encoding='utf-8')
    assert launch['exit_code'] != 0
    assert 'attempted to allocate   2.00 MB' in log and 'status=ABRT' in log
    x = remote(r'''
import os,json,hashlib,subprocess
from pathlib import Path
from collections import Counter
os.sched_setaffinity(0,{3})
d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-native-stack-v2')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['address_space_max_bytes']==768*1024**2 and a['startup_stack_limit_bytes']==1048576
assert a['mode']=='open_with_names' and a['empty_new_gallery']
o=json.loads((d/'OWNER.json').read_text());assert o['admission_sha256']==sha(d/'ADMISSION.json')
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
p=Path('/proc',str(o['pid']),'stat')
ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
assert not (boot==o['boot_id'] and ticks==o['start_ticks'])
unit=subprocess.run(['systemctl','--user','show','jp-b01-native-stack-v2','-p','ActiveState','-p','SubState','-p','Result','-p','MainPID','-p','ExecMainCode','-p','ExecMainStatus'],capture_output=True,text=True,check=True).stdout
fields=dict(line.split('=',1) for line in unit.splitlines())
assert fields['MainPID']=='0' and fields['ActiveState']=='failed' and fields['Result']=='signal' and fields['ExecMainStatus']=='6'
assert not (d/'RESULT.json').exists()
events=[];bindings={n:sha(d/n) for n in ('OWNER.json','ADMISSION.json','MEMORY.jsonl')}
sessions=list((d/'data/sessions').iterdir());assert len(sessions)==1
s=sessions[0];assert not (s/'session_finalization_v3.json').exists()
ep=s/'events.jsonl';events=[json.loads(line) for line in ep.read_text().splitlines()]
bindings[str(ep.relative_to(d))]=sha(ep)
memory=[json.loads(line) for line in (d/'MEMORY.jsonl').read_text().splitlines()]
observations={key:max(int(v.split()[1])*1024 for r in memory for v in r['values'] if v.startswith(key+':')) for key in ('VmSize','VmRSS','VmPeak')}
counts=dict(Counter(e['event_type'] for e in events))
assert counts.get('n2_diarization_frames',0)==0 and counts.get('s6d_text_ready',0)>0
print(json.dumps(dict(owner=o,observed_start_ticks=ticks,unit=fields,bindings=bindings,event_counts=counts,failures=[e['payload'] for e in events if e['event_type']=='failure'],memory=observations,admission_mode=a['mode'],source_samples_claimed_complete=False)))
''')
    review = dict(status='FAILED_B01_NATIVE_STACK_ALLOCATION_PRESERVED', run_id='b01-native-stack-v2',
                  owner=x['owner'], owner_closed=True, unit=x['unit'], bindings=x['bindings'],
                  launch_log_sha256=hashlib.sha256((out/'launch.log').read_bytes()).hexdigest(),
                  launch_exit_code=launch['exit_code'], result_present=False,
                  clean_application_finalization=False, observed_failure=x['failures'],
                  terminal_native_allocation_mb=2.0, hard_virtual_cap_bytes=768*1024**2,
                  startup_stack_bytes=1048576, sampled_memory_bytes=x['memory'],
                  text_publications=x['event_counts']['s6d_text_ready'], probability_frames=0,
                  retained_E0_mode_requested=True, combined_model_lifecycle_qualified=False,
                  source_coverage_qualified=False, integrated_acceptance=False)
    for name, value in [('FAILURE_AUDIT_INPUTS.json', x), ('REVIEW.json', review)]:
        with (out/name).open('x', encoding='utf-8') as f: json.dump(value, f, indent=2)
    remote("from pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-native-stack-v2/REVIEW.json')\nwith p.open('x') as f:f.write("+repr(json.dumps(review,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in review.items() if k not in ('bindings','observed_failure')}, indent=2))


if __name__ == '__main__':
    main()
