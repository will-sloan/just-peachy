"""Independent native E0 parity reader; see README_B01_E0_REFERENCE_REVIEW_V1.md."""
import hashlib,json,psutil
from dispatch_geometry_v2 import remote,PRIVATE

def main():
    psutil.Process().cpu_affinity([14]);out=PRIVATE/'b01-e0-reference-v1-evidence'
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code']==0
    x=remote(r"""
import os,json,hashlib,subprocess,struct,ast,math,wave,array,sys
from pathlib import Path
os.sched_setaffinity(0,{3});d=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-e0-reference-v1')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
a=json.loads((d/'ADMISSION.json').read_text());r=json.loads((d/'RESULT.json').read_text());plan=json.loads((d/'QUERY_PLAN.json').read_text())
for row in a['files']:assert sha(Path(row['path']))==row['sha256'],row['path']
assert a['address_space_max_bytes']==768*1024**2 and plan['tolerance_max_abs']==1e-5
assert r['status']=='B01_E0_REFERENCE_COLLECTED_REQUIRES_REVIEW' and r['session_released']
assert r['query_plan_sha256']==sha(d/'QUERY_PLAN.json') and len(plan['queries'])==r['query_count']==26 and len(r['cases'])==52
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for name in ['OWNER.json','DISPATCH_OWNER.json']:
 o=json.loads((d/name).read_text());p=Path('/proc',str(o['pid']),'stat');t=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
 assert not(boot==o['boot_id'] and t==o['start_ticks'])
u=dict(l.split('=',1) for l in subprocess.check_output(['systemctl','--user','show','jp-b01-e0-reference-v1','-p','MainPID','-p','Result','-p','ExecMainStatus'],text=True).splitlines())
assert u['MainPID']=='0' and u['Result']=='success' and u['ExecMainStatus']=='0'
max_error=0;max_repeat=0;rows=[];bindings={n:sha(d/n) for n in ['ADMISSION.json','RESULT.json','QUERY_PLAN.json','OWNER.json','DISPATCH_OWNER.json','DISPATCH_RESULT.json']}
assert sys.byteorder=='little'
for i,q in enumerate(plan['queries']):
 path=d/f'reference_{i:03d}.npy';b=path.read_bytes();assert b[:8]==b'\x93NUMPY\x01\x00'
 length=struct.unpack('<H',b[8:10])[0];header=ast.literal_eval(b[10:10+length].decode());assert header['shape']==(2,192) and header['descr']=='<f4' and not header['fortran_order']
 values=struct.unpack('<384f',b[10+length:]);v0=values[:192];v1=values[192:]
 assert all(math.isfinite(v) for v in values)
 difference=max(abs(v-q['expected'][j%192]) for j,v in enumerate(values));repeat=max(abs(x-y) for x,y in zip(v0,v1))
 assert difference<=1e-5 and repeat<=1e-5 and all(abs(sum(v*v for v in vec)-1)<1e-5 for vec in [v0,v1])
 with wave.open(q['source'],'rb') as f:
  assert f.getframerate()==16000 and f.getnchannels()==1 and f.getsampwidth()==2
  f.setpos(q['first_sample']);raw=f.readframes(q['last_sample']-q['first_sample'])
 samples=array.array('h');samples.frombytes(raw);floats=array.array('f',(v/32768 for v in samples));digest=hashlib.sha256(floats.tobytes()).hexdigest()
 cases=[x for x in r['cases'] if x['query']==i];assert len(cases)==2 and {x['repeat'] for x in cases}=={0,1}
 for case in cases:assert case['input_sha256']==digest and case['samples']==len(samples) and case['event_id']==q['event_id'] and case['max_abs_to_application']<=1e-5
 bindings[path.name]=sha(path);max_error=max(max_error,difference);max_repeat=max(max_repeat,repeat)
 rows.append(dict(query=i,run_id=q['run_id'],event_id=q['event_id'],source_first=q['first_sample'],source_last=q['last_sample'],input_sha256=digest,max_abs=difference,repeat_max_abs=repeat))
print(json.dumps(dict(status='PASS_NATIVE_E0_APPLICATION_WINDOW_PARITY_ONLY',queries=len(rows),calls=len(r['cases']),max_abs_application_reference=max_error,max_abs_repeat=max_repeat,owner_closed=True,natural_exit_code=0,unit=u,bindings=bindings,rows=rows,peak_rss_bytes=r['peak_rss_bytes'],accuracy_scored=False,enrollment=False,release_accepted=False)))
""")
    with (out/'REVIEW.json').open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
    remote("from pathlib import Path\np=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-e0-reference-v1/REVIEW.json')\nwith p.open('x') as f:f.write("+repr(json.dumps(x,indent=2))+")\nprint('{}')")
    print(json.dumps({k:v for k,v in x.items() if k not in ['bindings','rows']}))
if __name__=='__main__':main()
