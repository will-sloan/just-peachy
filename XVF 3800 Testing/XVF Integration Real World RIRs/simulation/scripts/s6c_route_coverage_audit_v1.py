"""Metadata-only declared-route coverage audit. See README_S6C_ROUTE_COVERAGE_AUDIT_V1.md."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S6C/20260910T123540Z'

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def binding(path, raw):
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': digest(raw)}

def read(path):
    path = Path(path)
    last = None
    for _ in range(5):
        try:
            before = path.stat()
            raw = path.read_bytes()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(raw) != after.st_size:
                raise RuntimeError('Metadata changed during read')
            obj = json.loads(raw.decode('utf-8-sig'))
            return obj, binding(path, raw)
        except (PermissionError, json.JSONDecodeError, RuntimeError) as exc:
            last = exc
            time.sleep(.05)
    raise last

def route(row):
    return row['candidate_id'], row.get('asr_tap', row.get('stream')), row['identity_tap']

def route_obj(key):
    return dict(candidate_id=key[0], asr_tap=key[1], identity_tap=key[2])

def profile_without_id(row):
    value = copy.deepcopy(row['profile'])
    del value['profile_id']
    return value

def run(args):
    out = Path(args.output)
    if out.exists():
        raise ValueError('Output already exists; use a new named snapshot')
    registry, registry_binding = read(REPORT/'EFFECTIVE_PROFILE_REGISTRY_V5.json')
    epoch, epoch_binding = read(REPORT/'EPOCH2_EXECUTION_MANIFEST.json')
    panel, panel_binding = read(REPORT/'design/REGISTERED_PANEL_V1.json')
    old_aliases, alias_binding = read(REPORT/'design/EFFECTIVE_ROUTE_DEDUP_V1.json')
    current = {route(r): r for r in registry['profiles']}
    old = {route(r): r for r in epoch['profiles']}
    panel_cases = set(panel['case_ids'])
    if len(current) != 376 or len({r[0] for r in current}) != 190 or len(panel_cases) != 56:
        raise ValueError('Declared registry/panel count changed')
    index_bindings, index_rows, skipped = [], {}, []
    coverage = defaultdict(set)
    result_views = defaultdict(set)
    for directory in sorted(REPORT.glob('epoch[1-4]')):
        for path in sorted(directory.glob('*PREDICTION_INDEX.json')):
            if any(word in path.name.lower() for word in ('fixture', 'synthetic')):
                skipped.append({'path': str(path), 'reason': 'SYNTHETIC_FIXTURE_NAME'})
                continue
            value, b = read(path)
            rows = value.get('rows', [])
            requested = value.get('requested')
            complete = value.get('completed')
            if value.get('status') != 'COMPLETE' or not rows or requested != complete or complete != len(rows) or any(r.get('status') != 'COMPLETE' for r in rows):
                skipped.append({'source': b, 'reason': 'NOT_COMPLETE_DECLARED_INDEX'})
                continue
            seen = set()
            for row in rows:
                key = route(row)
                full = (*key, row['case_id'])
                if key not in current or full in seen:
                    raise ValueError('Unknown current route or duplicate tuple in '+str(path))
                seen.add(full)
                coverage[key].add(row['case_id'])
                result_views[full].add((row['result']['path'], row['result']['sha256']))
            index_bindings.append(b)
            index_rows[str(path.resolve())] = (value, b)
    core, names = defaultdict(set), defaultdict(set)
    analysis_bindings, incomplete_analyses = [], []
    # One-level completed analysis receipts only: no nested fixture trees, score payloads or CSV scans.
    for directory in sorted(REPORT.iterdir()):
        if not directory.is_dir() or any(x in directory.name.lower() for x in ('fixture','check','independent_review')):
            continue
        for filename, destination in (('ANALYSIS_RECEIPT.json', core), ('NAME_ANALYSIS_RECEIPT.json', names)):
            path = directory/filename
            if not path.exists():
                continue
            value, b = read(path)
            source = value.get('index', {})
            match = index_rows.get(str(Path(source.get('path', '')).resolve()))
            ok = str(value.get('status', '')).startswith('COMPLETE') and value.get('scored') == value.get('requested') and value.get('unscored', 0) == 0 and value.get('failed_or_missing', 0) == 0
            if not match or not ok:
                incomplete_analyses.append({'source': b, 'reason': 'NO_MATCHING_COMPLETE_INDEX_OR_ANALYSIS'})
                continue
            index, ib = match
            if source != ib or value['requested'] != len(index['rows']):
                raise ValueError('Analysis declared index binding/count changed: '+str(path))
            analysis_bindings.append(b)
            for row in index['rows']:
                destination[route(row)].add(row['case_id'])
    rows = []
    for key, row in sorted(current.items()):
        predicted = coverage[key] & panel_cases
        scored = core[key] & panel_cases
        named = names[key] & panel_cases
        rows.append({**route_obj(key), 'recipe_id': row['recipe_id'], 'family': row['family'],
            'cue_condition': row['cue_condition'], 'gallery_condition': row['gallery_condition'],
            'enrollment_tier': row['enrollment_tier'], 'declared_panel_cases': 56,
            'predicted_panel_cases': len(predicted), 'core_scored_panel_cases': len(scored),
            'name_scored_panel_cases': len(named), 'all_observed_prediction_cases': len(coverage[key]),
            'missing_prediction_panel_cases': sorted(panel_cases-predicted),
            'predicted_but_core_unscored_panel_cases': sorted(predicted-scored),
            'declared_naming_mode': row['profile']['identity']['mode']})
    aliases = []
    fields = ('recipe_id','cue_condition','gallery_condition','enrollment_tier','asr_tap','identity_tap')
    for alias_id, tap in (('C083','O0'), ('C084','O1')):
        ak, pk = (alias_id,tap,tap), ('C065',tap,tap)
        a, p = current[ak], current[pk]
        if profile_without_id(a) != profile_without_id(p) or any(a[f] != p[f] for f in fields):
            raise ValueError('Alias is not exact executable profile/condition parity')
        for key in (ak,pk):
            if current[key]['profile'] != old[key]['profile'] or any(current[key][f] != old[key][f] for f in fields):
                raise ValueError('Current alias profile differs from frozen epoch2')
        a_binding, p_binding = read(Path(a['profile_binding']['path']))[1], read(Path(p['profile_binding']['path']))[1]
        if a_binding != a['profile_binding'] or p_binding != p['profile_binding']:
            raise ValueError('Actual alias profile file binding changed')
        effective = profile_without_id(a)
        aliases.append({'alias': route_obj(ak), 'parent': route_obj(pk),
            'profile_id_only_removed': True, 'conditions_exact': True,
            'current_profiles_equal_epoch2_profiles': True,
            'alias_profile_binding': a_binding, 'parent_profile_binding': p_binding,
            'effective_profile_sha256': digest(json.dumps(effective, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()),
            'parent_exact_panel_cases': sorted(coverage[pk] & panel_cases),
            'scope': 'Same executable settings and current/frozen tap/condition declarations. Candidate IDs and route display labels remain separate; no alias-ID prediction or physical execution is invented.'})
    enrollment, enrollment_binding = read(REPORT/'jobs/epoch2/enrollment_v1.json')
    gallery_index, gallery_panel_binding = read(REPORT/'epoch2/N01_gallery_panel_v1_PREDICTION_INDEX.json')
    native_ids = sorted({j['candidate_id'] for j in enrollment['jobs']})
    policy_ids = sorted({r['candidate_id'] for r in gallery_index['rows']})
    policy_naming = sorted({cid for cid in policy_ids if current[next(k for k in current if k[0] == cid)]['profile']['identity']['mode'] == 'post_association'})
    extra = sorted(set(policy_ids)-set(native_ids))
    if native_ids != policy_naming or extra != ['C065','C079'] or len(enrollment['jobs']) != 336:
        raise ValueError('Unexpected native enrollment/policy candidate relationship')
    cells = {(*route(j), j['case_id']) for j in enrollment['jobs']}
    if len(cells) != 336 or len(enrollment['case_ids']) != 6 or len(native_ids) != 28:
        raise ValueError('Native enrollment manifest is not unique28×6×2')
    summary = {'schema': 's6c_route_coverage_audit.v1', 'status': 'METADATA_SNAPSHOT_COMPLETE',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'registry': registry_binding, 'epoch2': epoch_binding, 'panel': panel_binding, 'historical_alias_declaration': alias_binding,
        'sources': index_bindings, 'analysis_sources': analysis_bindings, 'excluded_indices': skipped,
        'analysis_not_admitted': incomplete_analyses, 'candidate_count': 190, 'route_count': 376,
        'complete_prediction_index_count': len(index_bindings),
        'unique_candidate_route_case_prediction_tuples': len(result_views),
        'prediction_artifact_reference_variants': sum(map(len,result_views.values())),
        'routes_full_panel_prediction': sum(r['predicted_panel_cases'] == 56 for r in rows),
        'routes_partial_panel_prediction': sum(0 < r['predicted_panel_cases'] < 56 for r in rows),
        'routes_zero_panel_prediction': sum(r['predicted_panel_cases'] == 0 for r in rows),
        'routes_full_panel_core_score': sum(r['core_scored_panel_cases'] == 56 for r in rows),
        'routes': rows, 'same_tap_aliases': aliases,
        'native_enrollment_reconciliation': {'manifest': enrollment_binding, 'policy_index': gallery_panel_binding,
            'native_jobs': 336, 'native_candidate_ids': native_ids, 'native_case_count': 6, 'native_taps': ['O0','O1'],
            'policy_candidate_count': len(policy_ids), 'policy_rows': len(gallery_index['rows']),
            'policy_extra_none_gallery_controls': extra, 'missing_native_naming_candidates_from_that_policy_panel': [],
            'scope': 'Prepared native job metadata, not execution completion. The30-policy set is28naming candidates plus2NONE controls.'},
        'scope': 'Coverage presence from exact read buffers of COMPLETE non-fixture prediction indices; score presence only from matching completed analysis-receipt declarations. No waveform/vector/model/prediction/score payload hash or metric recomputation. Multiple artifacts for a candidate/case/route are references, not extra coverage or physical attempts. Mutable study snapshot, not final completion. Raw labels and aliases remain separate.'}
    out.mkdir(parents=True)
    src = Path(__file__)
    summary['helper'] = binding(src, src.read_bytes())
    doc = src.with_name('README_S6C_ROUTE_COVERAGE_AUDIT_V1.md')
    summary['readme'] = binding(doc, doc.read_bytes())
    raw = (json.dumps(summary, indent=2, allow_nan=False)+'\n').encode()
    with (out/'ROUTE_COVERAGE.json').open('xb') as handle:
        handle.write(raw)
    missing = [r for r in rows if r['predicted_panel_cases'] < 56]
    lines = ['# Exact-route metadata coverage snapshot', '',
        f"190 candidates /376 declared routes; {summary['routes_full_panel_prediction']} have all56 panel cases in completed indices; {summary['routes_partial_panel_prediction']} partial and {summary['routes_zero_panel_prediction']} absent.",
        f"{summary['routes_full_panel_core_score']} routes have completed core-score declarations for all56 panel cases. This is not a physical-run count or a payload audit.", '',
        '| Candidate | ASR / identity | Recipe | Predicted /56 | Core scored /56 |', '|---|---|---|---:|---:|']
    lines.extend(f"| {r['candidate_id']} | {r['asr_tap']} / {r['identity_tap']} | {r['recipe_id']} | {r['predicted_panel_cases']} | {r['core_scored_panel_cases']} |" for r in missing)
    lines += ['', 'C083 O0/O0 and C084 O1/O1 exactly alias C065 on the corresponding same tap after removing only executable profile_id; actual condition settings and tap declarations match in currentV5 and frozenepoch2. Their raw candidate coverage remains separate above.', '',
        'The enrollment manifest has28 naming candidates ×6 cases ×2 taps =336 jobs. Its policy panel adds C065/C079 NONE-gallery controls:30 candidates ×56 ×2 =3360. No naming candidate from that panel is omitted from enrollment_v1.', '', summary['scope']]
    (out/'ROUTE_COVERAGE.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(json.dumps({'receipt': binding(out/'ROUTE_COVERAGE.json',raw), 'complete_routes': summary['routes_full_panel_prediction'], 'zero_routes': summary['routes_zero_panel_prediction'], 'missing_candidates': sorted({r['candidate_id'] for r in missing})}, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
