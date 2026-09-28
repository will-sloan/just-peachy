"""Independent full-protocol retest audit; README_BASELINE_ARM64_CPU_REVIEW_V2.md."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin,exact_process
from review_baseline_asr_cpu_v5 import windows_binding
from baseline_arm64_asr_review_v1 import review as read_protocol,compare


def run(folder,output):
    pin()
    if output.exists():raise ValueError('Fresh audit output required')
    a=load(folder/'ADMISSION.json');t=load(folder/'RESULT.json');lt=load(folder/'linux/RESULT.json')
    assert a['scope']=='BASELINE_ARM64_CORTEX_A76_FULL_PROTOCOL_V2'
    assert t['status']==lt['status']=='PASS_EMULATED_BASELINE_ASR_COMPONENT_PARITY_ONLY'
    assert t['error'] is None and lt['error'] is None
    verify(t['admission']);verify(t['linux_result'])
    for b in a['code']+[a[k] for k in ('precheck','census','prior_admission','prior_linux_inputs','prior_model_command','prior_binary_record','prior_windows_events','audio','cpu_diagnostic_audit')]+[r['asset'] for r in a['models']+a['malformed_inputs']]:verify(b)
    owners=[t['owner'],t['wsl_owner'],{k:a['supervisor'][k] for k in ('pid','create_time')}]
    assert all(exact_process(o) is None for o in owners)
    commands=lt['commands'];assert len(commands)==10
    invalid=('empty','not_riff','truncated','stereo','wrong_rate','short','nonfinite','too_loud')
    assert [Path(c['stdout']['path']).name for c in commands]==[n+'.stdout' for n in ('cpu_help',*invalid,'model')]
    for c in commands:
        windows_binding(c['stdout']);windows_binding(c['stderr'])
        assert c['cancelled'] is None and not c['remaining_group_members']
    assert commands[0]['returncode'] in (0,1) and commands[-1]['returncode']==0
    for name,c in zip(invalid,commands[1:-1]):
        assert c['returncode']==1
        rows=windows_binding(c['stdout']).read_text(encoding='utf-8').splitlines();assert len(rows)==1
        row=json.loads(rows[0]);assert row['kind']=='failure' and any(k in row['error'] for k in ('WAV','sample','source'))
        assert c['argv'][-5:-1]==['INTENTIONALLY_ABSENT']*4
        asset=next(x['asset'] for x in a['malformed_inputs'] if x['name']==name)
        assert bind(windows_binding({**asset,'path':c['argv'][-1]}))==asset
    old=load(a['prior_model_command']['path']);model=commands[-1]
    assert model['argv'][1:3]==['-cpu','cortex-a76'] and model['argv'][:1]+model['argv'][3:]==old['argv']
    binary=load(a['prior_binary_record']['path'])['binary'];windows_binding(binary)
    assert load(folder/'linux/INPUTS.json')['reused_binary']==binary
    native=read_protocol(folder/'linux/model.stdout',a['frames']);reference=read_protocol(a['prior_windows_events']['path'],a['frames'])
    parity=compare(reference,native)
    assert parity==lt['parity']
    assert load(folder/'linux/COMPONENT_REVIEW.json')==dict(native=native,reference=reference,parity=parity)
    linux_owners=[lt['owner']]+[c['owner'] for c in commands]
    program='''import json,pathlib,sys
rows=[]
for o in json.loads(sys.argv[1]):
 p=pathlib.Path('/proc')/str(o['pid'])/'stat';s=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 members=[]
 for f in pathlib.Path('/proc').glob('[0-9]*/stat'):
  try:
   v=f.read_text().rsplit(')',1)[1].split()
   if int(v[2])==o['pid']:members.append(dict(pid=int(f.parent.name),start_ticks=int(v[19])))
  except FileNotFoundError:pass
 rows.append(dict(owner=o,exact_owner_exists=bool(s and int(s[19])==o['start_ticks']),group_members=members))
print(json.dumps(dict(boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),rows=rows)))
'''
    proc=subprocess.run(['wsl.exe','-d','Ubuntu','--','python3','-c',program,json.dumps(linux_owners)],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,stdin=subprocess.DEVNULL,timeout=20,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    assert not proc.stderr.strip();census=json.loads(proc.stdout)
    assert all(not row['exact_owner_exists'] and not row['group_members'] for row in census['rows'])
    output.mkdir();freeze(output/'LINUX_CLOSURE.json',census)
    result=dict(status='PASS_INDEPENDENT_EMULATED_BASELINE_ASR_PARITY_REVIEW',checked_utc=datetime.now(timezone.utc).isoformat(),
        parity=parity,malformed_cases_passed=8,model_elapsed_seconds=model['elapsed_seconds'],
        cases=[dict(name=c['case'],frames=c['frames'],finals=len(c['finals']),endpoint_resets=c['endpoint_resets'],stream_closed=c['stream_closed']) for c in native['cases']],
        exact_binary_reused=True,source_bindings_verified=len(a['code']),windows_owners_closed=owners,
        linux_closure=bind(output/'LINUX_CLOSURE.json'),admission=bind(folder/'ADMISSION.json'),terminal=bind(folder/'RESULT.json'),
        model_command=bind(folder/'linux/model.json'),component_review=bind(folder/'linux/COMPONENT_REVIEW.json'),
        review_code=[bind(__file__),bind(HERE/'README_BASELINE_ARM64_CPU_REVIEW_V2.md')],
        GUI_validated=False,CM5_tested=False,N4_accepted=False,N5_complete=False)
    freeze(output/'RESULT.json',result)
    print(json.dumps({k:result[k] for k in ('status','cases','malformed_cases_passed','model_elapsed_seconds')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.run,a.output)
