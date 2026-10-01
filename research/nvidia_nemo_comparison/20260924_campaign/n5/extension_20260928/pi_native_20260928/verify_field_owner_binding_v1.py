"""One host owner-binding check; README_FIELD_OPERATOR_NATIVE_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,copy,hashlib,json,sys,time
from pathlib import Path
sys.dont_write_bytecode=True
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--native',type=Path,required=True);p.add_argument('--extra',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir()
    me=psutil.Process()
    (a.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    began=time.perf_counter()
    from field_owner_binding_v1 import pack,decode,encoded
    pins=[];values=[]
    for path in (a.native,a.extra):
        raw=path.read_bytes()
        if len(raw)>1048576:raise ValueError('Bounded owner evidence')
        values.append(json.loads(raw));pins.append(dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
    owners={}
    for row in values[0]['owners']+values[1]['pi']:
        v=row['owner'];owners[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    for v in (values[0]['utility_owner'],values[1]['utility_owner']):
        owners[(v['boot_id'],v['pid'],v['start_ticks'])]=v
    original=[{k:v[k] for k in ('boot_id','pid','start_ticks')} for v in owners.values()]
    packed=pack(original);decoded=decode(json.loads(encoded(packed)))
    assert {(v['boot_id'],v['pid'],v['start_ticks']) for v in decoded}==set(owners)
    rejects=[]
    def reject(name,fn):
        try:fn()
        except (ValueError,TypeError):rejects.append(name)
        else:raise AssertionError('Accepted invalid '+name)
    reject('duplicate-input',lambda:pack(original+[original[0]]))
    mutations=[]
    v=copy.deepcopy(packed);v['count']=True;mutations.append(('boolean-count',v))
    v=copy.deepcopy(packed);v['boots'][0]['members'][0][0]=True;mutations.append(('boolean-pid',v))
    v=copy.deepcopy(packed);v['boots'][0]['members'][0][1]=0;mutations.append(('zero-tick',v))
    v=copy.deepcopy(packed);v['sha256']='0'*64;mutations.append(('wrong-digest',v))
    v=copy.deepcopy(packed);v['boots'][0]['members'].reverse();mutations.append(('changed-order',v))
    v=copy.deepcopy(packed);v['boots'][0]['members'].append(v['boots'][0]['members'][0]);mutations.append(('duplicate-pair',v))
    v=copy.deepcopy(packed);v['count']+=1;mutations.append(('wrong-count',v))
    v=copy.deepcopy(packed);v['extra']='unbound';mutations.append(('extra-field',v))
    for name,v in mutations:reject(name,lambda v=v:decode(v))
    result=dict(status='PASS_HOST_LOSSLESS_OWNER_BINDING_ONLY',native_executed=False,pins=pins,unique_owners=len(owners),
        full_bytes=len(encoded(original)),compact_bytes=len(encoded(packed)),count=packed['count'],digest=packed['sha256'],
        rejected=rejects,seconds=time.perf_counter()-began)
    (a.output/'REVIEW.json').open('x').write(json.dumps(result))
    (a.output/'BINDING.json').open('xb').write(encoded(packed))
    print(json.dumps(result))
if __name__=='__main__':main()
