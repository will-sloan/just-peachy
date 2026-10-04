"""Review a verified private native benchmark mirror. README_BENCHMARK_REVIEW.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import hashlib
import json
import math
import os
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''):h.update(block)
    return h.hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mirror',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--reference',type=Path)
    ap.add_argument('--reference-sha256')
    a=ap.parse_args();a.output.mkdir()
    def save(name,v):
        raw=json.dumps(v,sort_keys=True,allow_nan=False).encode()
        with (a.output/name).open('xb') as f:
            assert f.write(raw)==len(raw);f.flush();os.fsync(f.fileno())
    me=psutil.Process();save('REGISTERED_OWNER.json',dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    root=a.mirror/'benchmark'
    result=json.loads((root/'RESULT.json').read_bytes())
    plan=json.loads((root/'PLAN.json').read_bytes())
    # This review never substitutes for the transport's closure/mirror receipt.
    output=dict(schema='just-peachy.native-benchmark-review.v1',result=result,
                plan=plan,transport_closure_review_required=True,quality_evaluated=False,
                more_ram_benefit='UNMEASURED_4GB_8GB',reference_comparison=None)
    metrics={}
    count=0
    for path in sorted(root.glob('calls-jsonl-*.bin')):
        if path.stat().st_size>16*1024**2:raise ValueError('Segment extent')
        # Serialized call lines can cross part boundaries.
    pending=b''
    for path in sorted(root.glob('calls-jsonl-*.bin')):
        with path.open('rb') as f:
            for block in iter(lambda:f.read(65536),b''):
                pending+=block
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1)
                    if len(line)>4096:raise ValueError('Call record bound')
                    row=json.loads(line);count+=1
                    def visit(value,prefix=''):
                        if type(value) is dict:
                            for key,v in value.items():visit(v,prefix+'.'+key if prefix else key)
                        elif type(value) in (int,float) and math.isfinite(value):
                            m=metrics.setdefault(prefix,dict(min=value,max=value,first=value,last=value,count=0,total=0.))
                            m.update(min=min(m['min'],value),max=max(m['max'],value),last=value,count=m['count']+1,total=m['total']+value)
                    visit(row)
                if len(pending)>4096:raise ValueError('Unterminated call bound')
    if pending:raise ValueError('Truncated final call')
    for m in metrics.values():m['mean']=m.pop('total')/m['count']
    output.update(call_records=count,call_metric_summary=metrics)
    if a.reference:
        if not a.reference_sha256 or digest(a.reference)!=a.reference_sha256:raise ValueError('Reference pin')
        import numpy as np
        ref=np.load(a.reference,allow_pickle=False)
        if ref.ndim!=2 or ref.shape[1]!=8 or not np.isfinite(ref).all():raise ValueError('Reference shape')
        position=0;maximum=0.;mismatches=0
        for path in sorted(root.glob('probabilities-f32le-*.bin')):
            with path.open('rb') as f:
                for raw in iter(lambda:f.read(65536),b''):
                    if len(raw)%32:raise ValueError('Probability row alignment')
                    values=np.frombuffer(raw,dtype='<f4').reshape(-1,8)
                    if position+len(values)>len(ref) or not np.isfinite(values).all():raise ValueError('Output shape/nonfinite')
                    delta=np.abs(values-ref[position:position+len(values)])
                    maximum=max(maximum,float(delta.max(initial=0)))
                    mismatches+=int(np.count_nonzero(delta>1e-5));position+=len(values)
        if position!=len(ref):raise ValueError('Incomplete comparison')
        output['reference_comparison']=dict(reference_sha256=a.reference_sha256,rows=position,columns=8,
            max_abs=maximum,elements_exceeding_1e_minus5=mismatches,pass_tolerance_1e_minus5=mismatches==0,
            scope='same-geometry numerical comparison, not ground-truth diarization accuracy')
    save('REVIEW.json',output)
    print(json.dumps(dict(output=str(a.output),call_records=count,reference=output['reference_comparison'])))


if __name__=='__main__':main()
