"""Independent closed native recipe reader. See README_GEOMETRY_PACED_V1.md."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import psutil
from dispatch_geometry_v2 import remote, REMOTE, PRIVATE


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'd1-geometry-[a-z0-9-]+', args.run_id)
    psutil.Process().cpu_affinity([14])
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    out = PRIVATE/(args.run_id+'-evidence')
    assert json.loads((out/'LAUNCH_RESULT.json').read_text())['exit_code'] == 0
    code = '''
import base64,hashlib,json,os,subprocess
from pathlib import Path
os.sched_setaffinity(0,{3})
root=Path(ROOT)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
owner=json.loads((root/'OWNER.json').read_text());boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
p=Path('/proc',str(owner['pid']),'stat')
ticks=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
assert not(boot==owner['boot_id'] and ticks==owner['start_ticks'])
units=subprocess.run(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],capture_output=True,text=True,check=True).stdout
assert not units.strip(),units
inputs=json.loads((root/'INPUTS.json').read_text())
for row in inputs['files']:assert sha(root/row['name'])==row['sha256']
data={}
for p in root.iterdir():
 if p.is_file() and p.suffix in ('.json','.jsonl','.npy'):
  assert p.stat().st_size<2*1024**2
  data[p.name]=dict(sha256=sha(p),base64=base64.b64encode(p.read_bytes()).decode())
assert sum(p.stat().st_size for p in root.iterdir() if p.is_file() and p.name not in ('D1.gguf','source.wav'))<16*1024**2
print(json.dumps(dict(files=data,closure=dict(boot_id=boot,owner=owner,observed_ticks=ticks,exact_alive=False,all_inputs_rehashed=True,active_units=units))))
'''
    collected = remote('ROOT='+repr(REMOTE+'/'+args.run_id)+'\n'+code)
    for name,row in collected['files'].items():
        assert Path(name).name == name
        raw = base64.b64decode(row['base64'])
        assert hashlib.sha256(raw).hexdigest() == row['sha256']
        path = out/name
        if path.exists(): assert path.read_bytes() == raw
        else: path.write_bytes(raw)
    (out/'CLOSURE_REVIEW.json').write_text(json.dumps(collected['closure'],indent=2),encoding='utf-8')
    import numpy as np
    result = json.loads((out/'RESULT.json').read_text())
    admission = json.loads((out/'ADMISSION.json').read_text())
    config = json.loads((out/'CONFIG.json').read_text())
    assert result['status'] == 'NATIVE_GEOMETRY_COLLECTED_REQUIRES_REVIEW'
    assert admission['inputs_sha256'] == sha(out/'INPUTS.json')
    assert result['admission_sha256'] == sha(out/'ADMISSION.json')
    assert result['config'] == config and result['observed_c_abi_geometry'] == config['c_abi_geometry']
    expected = dict(chunk_frames=13, right_context_frames=1, left_context_frames=0,
                    fifo_frames=80, spkcache_frames=264, update_period_frames=40, preset='v3-streaming', gpu=-1)
    if config['profile'] == 'native_v3_delayed':
        expected.update(chunk_frames=264,left_context_frames=1,fifo_frames=0,update_period_frames=188,preset='v3-offline')
    else: assert config['profile'] == 'native_v3_streaming'
    assert result['observed_c_abi_geometry'] == expected
    assert result['address_space_limit_bytes'] == 768*1024**2
    for key in ('model_closed','reset_empty_passed','post_finish_push_rejected','repeated_finish_empty'):
        assert result[key] is True
    arrays = []
    metrics = []
    for index,case in enumerate(('saved_full','resident_repeat')):
        array = np.load(out/(case+'.npy'), allow_pickle=False)
        assert array.shape == (4470,8) and np.isfinite(array).all()
        assert np.min(array) >= 0 and np.max(array) <= 1
        arrays.append(array)
        rows = [json.loads(x) for x in (out/(case+'_calls.jsonl')).read_text().splitlines()]
        assert len(rows) == 448 and rows[-1]['kind'] == 'finish'
        cursor = 0; wall = 0; first = None
        for i,row in enumerate(rows):
            samples = min((i+1)*1600,715127)
            assert row['source_samples'] == samples
            assert row['kind'] == ('finish' if i == 447 else 'push')
            assert row['frame_start'] == cursor and row['frame_end'] >= cursor
            assert row['frame_end'] <= samples//160+1
            assert row['available_elapsed_seconds'] >= wall and row['compute_seconds'] >= 0
            if first is None and row['frame_end'] > cursor: first = row
            cursor = row['frame_end'];wall = row['available_elapsed_seconds']
        assert cursor == 4470
        metric = result['cases'][index]
        assert metric['case'] == case and metric['samples'] == 715127 and metric['frames'] == 4470
        assert abs(metric['audio_seconds']-715127/16000) < 1e-10
        assert abs(metric['call_sequence_rtf']-metric['elapsed_seconds']/metric['audio_seconds']) < 1e-10
        assert metric['first_emission_source_seconds'] == first['source_samples']/16000
        assert abs(sum(x['compute_seconds'] for x in rows)-metric['call_compute_seconds']) < 1e-8
        source = json.loads((out/(case+'_source.json')).read_text())
        assert source['producer_closed'] and not source['errors'] and len(source['arrivals']) == 447
        assert metric['producer_closed'] and result['paced'] and config['paced']
        assert 1 <= source['maximum_queue_chunks'] <= 200
        previous = 0
        waits = []
        for i,arrival in enumerate(source['arrivals']):
            assert arrival['source_samples'] == min((i+1)*1600,715127)
            assert abs(arrival['scheduled_elapsed_seconds']-arrival['source_samples']/16000) < 1e-10
            assert arrival['actual_elapsed_seconds'] >= arrival['scheduled_elapsed_seconds']-.001
            assert arrival['actual_elapsed_seconds'] >= previous
            previous = arrival['actual_elapsed_seconds']
            assert abs(rows[i]['source_arrival_elapsed_seconds']-arrival['actual_elapsed_seconds']) < 1e-10
            wait = rows[i]['consume_begin_elapsed_seconds']-arrival['actual_elapsed_seconds']
            assert wait >= 0
            waits.append(wait)
        assert abs(max(waits)-metric['max_queue_wait_seconds']) < 1e-9
        assert abs(metric['drain_elapsed_seconds']-(metric['elapsed_seconds']-715127/16000)) < 1e-9
        assert metric['first_emission_elapsed_seconds'] >= metric['first_emission_source_seconds']
        metrics.append(metric)
    repeat_error = float(np.max(np.abs(arrays[0]-arrays[1])))
    assert repeat_error <= 1e-5 and repeat_error == result['repeat_max_abs_probability_error']
    generic_error = None
    if config['kernel'] == 'a76':
        reference = np.load(out/'same_geometry_generic.npy', allow_pickle=False)
        assert reference.shape == arrays[0].shape
        generic_error = float(np.max(np.abs(reference-arrays[0])))
        assert generic_error <= 1e-5 and generic_error == result['generic_reference_max_abs_probability_error']
    else: assert config['kernel'] == 'generic'
    review = dict(status='PASS_NATIVE_RECIPE_FUNCTIONAL_RESOURCE_ONLY',run_id=args.run_id,
                  profile=config['profile'],kernel=config['kernel'],result_sha256=sha(out/'RESULT.json'),
                  inputs_sha256=sha(out/'INPUTS.json'),admission_sha256=sha(out/'ADMISSION.json'),
                  independent_repeat_max_abs=repeat_error,independent_generic_max_abs=generic_error,
                  tolerance=1e-5,all_samples_and_frames_passed=True,owner_closed=True,model_closed=True,
                  observed_c_abi_geometry=expected,metrics=metrics,peak_process_rss_bytes=result['peak_process_rss_bytes'],
                  paced=True,producer_closed=True,integrated_acceptance=False,accuracy_claim=False,real_world_validation=False,uncontended_benchmark=False)
    path = out/'REVIEW.json'
    with path.open('x',encoding='utf-8',newline='\n') as stream: json.dump(review,stream,indent=2)
    # Stage receipt only; never mutates the campaign's closed shared ledger.
    response = remote('ROOT='+repr(REMOTE+'/'+args.run_id)+'\nDATA='+repr(base64.b64encode(path.read_bytes()).decode())+'''
import base64,hashlib,json
from pathlib import Path
p=Path(ROOT)/'REVIEW.json'
with p.open('xb') as f:f.write(base64.b64decode(DATA))
print(json.dumps(dict(review_sha256=hashlib.sha256(p.read_bytes()).hexdigest())))
''')
    assert response['review_sha256'] == sha(path)
    print(json.dumps(review))


if __name__ == '__main__':
    main()
