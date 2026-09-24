"""Compare identical audio across CPU/CUDA/reference routes without word truth."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
load=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def cells(folder):
    path=folder/'RESULT.json'
    if not path.exists():return {}
    rows={}
    for item in load(path).get('cells',[]):
        if sha(item['path'])!=item['sha256']:raise ValueError('Changed route evidence')
        value=load(item['path'])
        if value['status']=='COMPLETE':rows[value['audio_sha256']]=value
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    source=HERE.parent/'n2/evaluation/scoring.py'
    spec=importlib.util.spec_from_file_location('n3_route_words',source);scoring=importlib.util.module_from_spec(spec);spec.loader.exec_module(scoring)
    rows=[]
    for variant in ('A2','A3'):
        cpu=cells(args.root/('cpu-panel-'+variant))
        for other,prefix,scope in [('cuda','screen-','same Q8 weights, primary context; CPU/CUDA lexical output parity'),
                ('reference','reference-','Q8 native versus FP32 NeMo; quantization, decoder and endpoint routes differ'),
                ('lower_buffer','lower-buffer-','right-context 1 versus 0; deliberate configuration contrast')]:
            comparison=cells(args.root/(prefix+variant));common=sorted(cpu.keys()&comparison.keys());differences=[]
            for digest in common:
                left,right=cpu[digest],comparison[digest];a,b=map(scoring.words,(left['raw_final_text'],right['raw_final_text']))
                if left['input_samples']!=right['input_samples']:raise ValueError('Route input denominators differ')
                differences.append(dict(audio_sha256=digest,input_samples=left['input_samples'],
                    identical_lexical_output=a==b,lexical_edit_distance=scoring.edit_distance(a,b),
                    native_words=len(a),other_words=len(b),raw_output_equal=left['raw_final_text']==right['raw_final_text'],
                    native_compute_ms=left['compute_ms'],other_compute_ms=right['compute_ms']))
            rows.append(dict(variant=variant,comparison=other,scope=scope,status='COMPLETE' if len(common)==4 else 'PARTIAL_OR_UNAVAILABLE',
                required_pairs=4,observed_pairs=len(common),identical_lexical_pairs=sum(x['identical_lexical_output'] for x in differences),cells=differences))
    result=dict(schema='just-peachy.n3.route-comparison.v1',status='COMPLETE' if all(r['status']=='COMPLETE' for r in rows) else 'PARTIAL',
        comparisons=rows,limits=['Four fixed preselected rows; not full numerical tensor/state parity',
        'Different routes can have different precision/endpoint behavior; disagreements are retained, not rescore-aligned',
        'No truth, fitted word alignment or arbitrary equality threshold is used'])
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'ROUTE_COMPARISON.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    lines=['# N3 route comparison','','| Variant | Contrast | Paired files | Identical lexical outputs |','|---|---|---:|---:|']
    lines += [f'| {r["variant"]} | {r["comparison"]} | {r["observed_pairs"]}/4 | {r["identical_lexical_pairs"]} |' for r in rows]
    lines+=['','This small lexical comparison is not full tensor/state parity or a CM5 performance measurement.','']
    (args.output/'ROUTE_COMPARISON.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':main()
