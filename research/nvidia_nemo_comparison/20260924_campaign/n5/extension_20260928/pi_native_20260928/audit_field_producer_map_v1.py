"""Static retained-writer audit only. See README_FIELD_PRODUCER_MAP_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
assert psutil.Process().cpu_affinity() == [14]
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import time
import field_host_finite_v1 as h

HERE = Path(__file__).resolve().parent
BASE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928')
INSTALLED = BASE/'field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12'
sys.path.insert(0, str(HERE.parent))
from window_guard_v5 import budget, window


def binding(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=h.digest(raw))


def identities(value):
    if isinstance(value, dict):
        if 'pid' in value and 'create_time' in value:
            yield (value['pid'], value['create_time'])
        for item in value.values():
            yield from identities(item)
    elif isinstance(value, list):
        for item in value:
            yield from identities(item)


def main(census, version, destination):
    now = datetime.now(timezone.utc)
    w = window()
    c = json.loads(census.read_bytes())
    cp = BASE/f'NATIVE_CLOSURE_V{version}.json'
    rp = BASE/f'NATIVE_RESOURCES_V{version}.json'
    closure = json.loads(cp.read_bytes()); resources = json.loads(rp.read_bytes())
    assert 0 <= time.time()-census.stat().st_mtime < 900
    assert 0 <= (now-datetime.fromisoformat(closure['checked_utc'])).total_seconds() < 900
    assert not c['active_allocations'] and not closure['units']
    assert all(not row['exact_alive'] for row in closure['owners'])
    assert closure['capture'] == 'closed' and closure['hardware_lease_free'] and closure['research_lease_free']
    observed = set()
    for owner in BASE.glob('*-evidence/host/metadata/REGISTERED_OWNER.json'):
        files = [owner]
        lifetime = owner.parents[2]/'lifetime/LIFETIME.json'
        if lifetime.exists(): files.append(lifetime)
        for path in files:
            for pid, created in identities(json.loads(path.read_bytes())):
                try: actual = psutil.Process(pid).create_time()
                except psutil.NoSuchProcess: actual = None
                assert actual is None or abs(actual-created) > .001, 'Recorded host identity active'
                observed.add((pid, created))
    requested = 2*h.MIB
    calculation = budget(c['calculation']['existing_bytes'] + resources['host_window_bytes']
                         - c['calculation']['window_used_bytes'] + resources['target_bytes'],
                         resources['combined_bytes'], requested,
                         {d: shutil.disk_usage(d+'/').free for d in ('C:', 'G:')}, 52)
    assert psutil.virtual_memory().available >= 8*1024**3
    mp = HERE/'FIELD_PRODUCER_MAP_V1.json'
    mapping = json.loads(mp.read_bytes())
    plan = json.loads((HERE/'FIELD_WHOLE_RUN_ALLOCATION_V3.json').read_bytes())
    assert h.digest((HERE/'FIELD_WHOLE_RUN_ALLOCATION_V3.json').read_bytes()) == mapping['allocation_sha256']
    source_rows = []
    for source in mapping['sources']:
        path = (HERE if source['root'] == 'reports' else INSTALLED)/source['path']
        raw = path.read_bytes()
        assert h.digest(raw) == source['sha256'] and len(raw) == source['bytes'], source['path']
        ast.parse(raw, filename=str(path))
        text = raw.decode('utf-8-sig')
        anchors = []
        for anchor in source['anchors']:
            lines = [n for n, line in enumerate(text.splitlines(), 1) if anchor in line]
            assert lines, (source['path'], anchor)
            anchors.append(dict(text=anchor, lines=lines))
        source_rows.append(dict(root=source['root'], path=source['path'], bytes=len(raw),
                                sha256=source['sha256'], anchors=anchors))
    reservations = {}
    for group in ('closure_reserve', 'failure', 'telemetry'):
        limits = plan['sidecar_groups'][group]
        names = [name for producer in mapping['producers'] for name in producer.get('independent_reservations', {}).get(group, [])]
        maximum = len(names)*limits['maximum_file_bytes']
        reservations[group] = dict(slots=len(names), bytes_at_independent_file_ceilings=maximum,
            shared_group_bytes=limits['maximum_bytes'], shared_file_slots=limits['maximum_files'],
            byte_shortfall=max(0, maximum-limits['maximum_bytes']),
            slot_shortfall=max(0, len(names)-limits['maximum_files']))
    assert reservations['closure_reserve']['slots'] == 6
    assert reservations['failure']['slots'] == 10
    assert reservations['telemetry']['slots'] == 2
    result = dict(schema='field-producer-audit.v1', checked_utc=now.isoformat(), audit_completed=True,
        live_composition_accepted=False, capture_admitted=False, policy_changed=False,
        execution_scope='CPU14 static hashes, AST parsing and arithmetic; no source imports or workers',
        sources=source_rows, producers=mapping['producers'], independent_reservations=reservations,
        blockers=mapping['blockers'], observed_closed_field_host_identities=len(observed),
        limitations=mapping['limitations'], source_census_not_transitive=True,
        process_affinity=psutil.Process().cpu_affinity())
    limits = {'metadata': (512*1024, 256*1024, 12), 'failure': (256*1024, 128*1024, 4),
              'closure': (128*1024, 64*1024, 4)}
    admission = dict(schema='STATIC_PRODUCER_REVIEW_V1', admitted_utc=now.isoformat(),
        checkpoint_utc=w['checkpoint_utc'], worker_execution_authorized=False,
        maximum_new_output_bytes=requested, budget=calculation, host_limits=limits,
        bindings=[binding(p) for p in (mp, Path(__file__), HERE/'README_FIELD_PRODUCER_MAP_V1.md',
                  HERE/'field_host_finite_v1.py', HERE/'field_host_budget_v1.py', cp, rp, census)])
    initial = {'ADMISSION.json': h.encoded(admission), 'PREFLIGHT.json': h.encoded(dict(closure=binding(cp),
               resources=binding(rp), census=binding(census), field_identities=sorted(observed)))}
    store = h.HostStore(destination/'host', limits=limits)
    for name, raw in initial.items(): store.preflight(name, raw)
    store.preflight('RESULT.json', h.encoded(result))
    assert destination.parent == BASE and not destination.exists()
    destination.mkdir()
    store.create(initial)
    store.json('RESULT.json', result)
    for source in source_rows:
        path = (HERE if source['root'] == 'reports' else INSTALLED)/source['path']
        assert h.digest(path.read_bytes()) == source['sha256']
    store.json('REVIEW.json', dict(audit_completed=True, sources_verified=len(source_rows),
        result_sha256=h.digest((store.root/'metadata/RESULT.json').read_bytes()), live_composition_accepted=False))
    batch = {name:(store.root/'metadata'/name).read_bytes() for name in ('ADMISSION.json','PREFLIGHT.json','RESULT.json','REVIEW.json')}
    h.publish_backup(store, destination/'verified-audit-backup', batch)
    store.json('review-closure.json', dict(review_complete=True, source_worker_started=False,
        live_composition_accepted=False, process_affinity=psutil.Process().cpu_affinity()))
    assert sum(p.stat().st_size for p in destination.rglob('*') if p.is_file()) < requested
    print(json.dumps(dict(audit_completed=True, live_composition_accepted=False, sources=len(source_rows),
                          producer_families=len(mapping['producers']), reservations=reservations)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--census', type=Path, required=True)
    p.add_argument('--closure-version', type=int, required=True)
    p.add_argument('--destination', type=Path, required=True)
    a = p.parse_args()
    main(a.census, a.closure_version, a.destination)
