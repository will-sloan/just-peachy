"""Changed selector boundaries only; README_D1_MODES_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
assert psutil.Process().cpu_affinity() == [14]
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
import d1_modes_v1 as modes
import field_host_finite_v1 as h

HERE = Path(__file__).resolve().parent
BASE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
sys.path.insert(0, str(HERE.parent))
from window_guard_v5 import budget, window
from audit_field_producer_map_v1 import identities


def main(census, version, destination):
    now = datetime.now(timezone.utc); window()
    c = json.loads(census.read_bytes()); cp = BASE/f'NATIVE_CLOSURE_V{version}.json'
    rp = BASE/f'NATIVE_RESOURCES_V{version}.json'
    closure = json.loads(cp.read_bytes()); resources = json.loads(rp.read_bytes())
    assert 0 <= time.time()-census.stat().st_mtime < 900
    assert 0 <= (now-datetime.fromisoformat(closure['checked_utc'])).total_seconds() < 900
    assert not c['active_allocations'] and not closure['units']
    assert all(not x['exact_alive'] for x in closure['owners'])
    assert closure['capture'] == 'closed' and closure['hardware_lease_free'] and closure['research_lease_free']
    checked_owners = set()
    for owner in BASE.glob('*-evidence/host/metadata/REGISTERED_OWNER.json'):
        files = [owner]; lifetime = owner.parents[2]/'lifetime/LIFETIME.json'
        if lifetime.exists(): files.append(lifetime)
        for path in files:
            for pid, created in identities(json.loads(path.read_bytes())):
                try: actual = psutil.Process(pid).create_time()
                except psutil.NoSuchProcess: actual = None
                assert actual is None or abs(actual-created) > .001
                checked_owners.add((pid, created))
    calculation = budget(c['calculation']['existing_bytes']+resources['host_window_bytes']
                         - c['calculation']['window_used_bytes']+resources['target_bytes'],
                         resources['combined_bytes'], 2*h.MIB,
                         {d:shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}, 52)
    assert psutil.virtual_memory().available >= 8*1024**3
    def pin(path):
        raw = path.read_bytes()
        return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    evidence = []
    for mode in modes.catalog()['modes']:
        root = BASE/(mode['retained_run']+'-evidence')
        for name, expected in mode['evidence'].items():
            actual = pin(root/name)
            assert actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256']
            evidence.append(actual)
    bindings = [pin(HERE/n) for n in ('d1_modes_v1.py','D1_MODE_CATALOG_V1.json','check_d1_modes_v1.py',
                'README_D1_MODES_V1.md','field_host_finite_v1.py','field_host_budget_v1.py','audit_field_producer_map_v1.py')]
    admission = dict(schema='D1_MODE_SELECTOR_CHECK_V1', admitted_utc=now.isoformat(),
        scope='Changed pure selection/inventory/geometry/runtime-path rejection checks; no native model or factory invocation',
        worker_execution_authorized=False, budget=calculation, bindings=bindings, evidence=evidence,
        census=pin(census), closure=pin(cp), resources=pin(rp), output_max_bytes=2*h.MIB, affinity=[14])
    assert destination.parent == BASE and not destination.exists()
    limits = {'metadata':(512*1024,256*1024,12),'failure':(256*1024,128*1024,4),'closure':(128*1024,64*1024,4)}
    store = h.HostStore(destination/'host', limits=limits)
    initial = {'ADMISSION.json':h.encoded(admission), 'PREFLIGHT.json':h.encoded(dict(field_owners_closed=sorted(checked_owners)))}
    for name, raw in initial.items(): store.preflight(name, raw)
    destination.mkdir(); store.create(initial)
    cases = []
    def reject(name, call):
        try: call()
        except (ValueError, RuntimeError) as exc:
            cases.append(dict(case=name,rejected=True,error=str(exc)))
        else: raise AssertionError(name+' was accepted')
    try:
        expected = {'delayed':(264,1,1,0,264,188,'v3-offline',1),
                    'streaming':(13,1,0,80,264,40,'v3-streaming',8),
                    'chunk52':(52,1,0,80,264,40,'v3-streaming',8)}
        for key, values in expected.items():
            selected = modes.select(key); geometry = selected['geometry']
            assert tuple(geometry[f] for f in modes.GEOMETRY_FIELDS)+(geometry['preset'],selected['compute_graph_lru']) == values
            assert modes.check_geometry(key, geometry)
            inventory = {x['name']:{'bytes':x['bytes'],'sha256':x['sha256']} for x in selected['assets']}
            assert modes.check_inventory(key, inventory)
            selected['geometry']['chunk_frames'] = -1
            assert modes.select(key)['geometry']['chunk_frames'] == values[0]
            cases.append(dict(case=key+'-exact-selection',passed=True,caller_mutation_isolated=True))
        reject('unsupported-onnx',lambda:modes.select('onnx-full-waveform'))
        reject('nonstring-mode',lambda:modes.select(True))
        geometry = modes.select('delayed')['geometry']; geometry['preset'] = 'v3-streaming'
        reject('delayed-zero-fifo-wrong-preset',lambda:modes.check_geometry('delayed',geometry))
        geometry = modes.select('streaming')['geometry']; geometry['right_context_frames'] = True
        reject('bool-context',lambda:modes.check_geometry('streaming',geometry))
        assets = {x['name']:{'bytes':x['bytes'],'sha256':x['sha256']} for x in modes.select('delayed')['assets']}
        other = {x['name']:x for x in modes.select('streaming')['assets']}
        wrapper = 'nemo-arm64/lib/libnemo_speech_asr_c.so.1'
        assert assets[wrapper]['sha256'] == other[wrapper]['sha256']
        assets['nemo-arm64/lib/libnemo_speech_asr.so']['sha256'] = other['nemo-arm64/lib/libnemo_speech_asr.so']['sha256']
        reject('same-wrapper-wrong-main-runtime',lambda:modes.check_inventory('delayed',assets))
        assets = {x['name']:{'bytes':x['bytes'],'sha256':x['sha256']} for x in modes.select('delayed')['assets']}
        assets.pop('nemo-arm64/lib/libggml-cpu.so')
        reject('missing-cpu-kernel',lambda:modes.check_inventory('delayed',assets))
        reject('hot-runtime-switch',lambda:modes.require_fresh_runtime(['/retained/libggml-cpu.so']))
        root = BASE/'not-created-path-fixture'
        selected = modes.select('delayed'); lib = root/selected['retained_run']/'nemo-arm64/lib'
        paths = [str(lib/'libnemo_speech_asr_c.so.1'),str(lib/'libnemo_speech_asr.so')]
        assert modes.check_loaded_paths('delayed',root,paths)
        cases.append(dict(case='declared-loaded-path-list',passed=True,actual_loader_exercised=False))
        reject('foreign-loaded-runtime',lambda:modes.check_loaded_paths('delayed',root,paths+['/other/libggml-cpu.so']))
        reject('missing-loaded-main',lambda:modes.check_loaded_paths('delayed',root,paths[:1]))
        for binding in bindings+evidence:
            assert pin(Path(binding['path'])) == binding
        for name in ('d1_modes_v1.py','check_d1_modes_v1.py'): ast.parse((HERE/name).read_bytes())
        result = dict(status='PASS_D1_MODE_SELECTION_BOUNDARIES_ONLY',checked_utc=now.isoformat(),cases=cases,
            evidence_receipts_verified=len(evidence),same_wrapper_different_main_detected=True,
            native_factory_executed=False,model_loaded=False,assets_rehashed_on_Pi=False,
            accuracy_claim=False,new_speedup_claim=False,affinity=psutil.Process().cpu_affinity())
        store.json('RESULT.json',result)
        store.json('REVIEW.json',dict(status=result['status'],case_count=len(cases),
            result_sha256=pin(store.root/'metadata/RESULT.json')['sha256'],native_factory_prepared_only=True))
        batch={n:(store.root/'metadata'/n).read_bytes() for n in ('ADMISSION.json','PREFLIGHT.json','RESULT.json','REVIEW.json')}
        h.publish_backup(store,destination/'verified-mode-backup',batch)
        store.json('review-closure.json',dict(review_complete=True,model_started=False,worker_started=False))
    except BaseException as exc:
        store.failure('review',repr(exc).encode(),exc)
        raise
    assert sum(p.stat().st_size for p in destination.rglob('*') if p.is_file()) < 2*h.MIB
    print(json.dumps(dict(status=result['status'],cases=len(cases),rejections=sum(x.get('rejected',False) for x in cases))))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--census',type=Path,required=True)
    p.add_argument('--closure-version',type=int,required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();main(a.census,a.closure_version,a.destination)
