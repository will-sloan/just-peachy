"""Report existing lifecycle work/count observations and closed chronological bytes; no inference."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics
import tempfile
from datetime import datetime, timezone

INDEX_SHA = 'bae3ec7011eec5b53ab782c1813ca6107e456db7674fc2f709ca370e045038e5'
SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S6C/20260910T123540Z'
INDEX = REPORT / 'requirement_gap_review_v2/STRATA_AND_STATE_SOURCE_INDEX.json'
ID_FIELDS = ('profile_id', 'stream', 'identity_tap', 'route', 'case_id')
COUNT_NAMES = ('active', 'dormant', 'provisional', 'live', 'archive',
               'cumulative_retirements', 'lifetime_external_ids', 'prototypes')
METRICS = ('decisions', 'track_count', 'peak_live', 'peak_archive',
           'blocked_unique_evidence_sec', 'prototype_comparisons',
           'max_live_prototype_comparisons_per_observation') + tuple(
               prefix + name for prefix in ('final_', 'peak_observed_') for name in COUNT_NAMES)
ADDITIVE = {'decisions', 'prototype_comparisons', 'blocked_unique_evidence_sec'}
PREFIX = '__work_'
CHRONO_KIND = 'VERIFIED_NATIVE_CACHE_CHRONOLOGICAL_POLICY_DIAGNOSTIC_NOT_NATIVE_ENDURANCE'


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def binding(path, raw):
    return dict(path=str(Path(path).resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def read_bound(declaration, cap=32 * 1024 * 1024):
    path = Path(declaration['path'])
    if type(declaration['bytes']) is not int or not 0 <= declaration['bytes'] <= cap:
        raise ValueError('Invalid bounded metadata size')
    raw = path.read_bytes()
    if binding(path, raw) != declaration:
        raise ValueError('Exact source buffer differs')
    return raw


def document(raw):
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def bound_json(declaration):
    return document(read_bound(declaration))


def safe_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Simple source/output name required')
    return value


def numeric(cell, field):
    if cell == '':
        return None
    if field == 'blocked_unique_evidence_sec':
        value = float(cell)
        if not math.isfinite(value) or value < 0:
            raise ValueError('Finite nonnegative duration required')
        return value
    if not re.fullmatch(r'[0-9]+', cell):
        raise ValueError('Nonnegative integer count required')
    return int(cell)


def csv_rows(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    header = reader.fieldnames
    if not header or len(set(header)) != len(header) or any(x.startswith(PREFIX) for x in header):
        raise ValueError('Unique original headers required')
    if not set(ID_FIELDS).issubset(header):
        raise ValueError('Actual route/case columns required')
    if not {'prototype_comparisons', 'max_live_prototype_comparisons_per_observation'}.issubset(header):
        raise ValueError('Source work columns missing')
    rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError('Malformed CSV width')
    return header, rows


def metric_scope(field):
    if field == 'prototype_comparisons':
        return 'Recorded total prototype comparisons; may include archive work beyond live-bank maximum.'
    if field == 'max_live_prototype_comparisons_per_observation':
        return 'Maximum of each scene source field; not continuous CPU cost or total archive work.'
    if field.startswith('peak_observed_'):
        return 'Maximum count among source decision observations; sparse observation scope, no interpolation.'
    if field.startswith('final_') or field == 'track_count':
        return 'Final count per scene; group maximum is over final snapshots, not a within-session peak.'
    if field in ('peak_live', 'peak_archive'):
        return 'Source tracker-maintained peak field; preserved separately from observed-decision peaks.'
    if field == 'blocked_unique_evidence_sec':
        return 'Per-scene source blocked-evidence interval union; group sum over source rows only.'
    return 'Recorded source decision count; not an inference-call or physical-session count.'


def group_source(source_id, authority, header, rows):
    routes = [(x['candidate_id'], x['stream'], x['identity_tap']) for x in authority['profile_routes']]
    cases = authority['case_ids']
    if len(routes) != len(set(routes)) or len(cases) != len(set(cases)):
        raise ValueError('Repeated declared route/case')
    if any(a not in ('O0', 'O1') or b not in ('O0', 'O1') for _, a, b in routes):
        raise ValueError('Unexpected audio route')
    if authority['requested'] != len(routes) * len(cases):
        raise ValueError('Requested Cartesian route grid differs')
    groups = {route: [] for route in routes}
    seen = set()
    for row in rows:
        route = tuple(row[x] for x in ('profile_id', 'stream', 'identity_tap'))
        key = route + (row['case_id'],)
        if route not in groups or row['case_id'] not in cases or key in seen:
            raise ValueError('Unexpected/duplicate source row identity')
        if row['route'] != f'{route[1]}_ASR_{route[2]}_ID':
            raise ValueError('Route label contradicts actual taps')
        seen.add(key)
        for field in METRICS:
            if field in header:
                numeric(row[field], field)
        groups[route].append(row)
    if len(rows) != authority['scored'] or authority['scored'] + authority['unscored'] != authority['requested']:
        raise ValueError('Scored row count differs from exact authority')
    output = []
    for (profile, asr, identity), subset in sorted(groups.items()):
        for field in METRICS:
            observations = [(numeric(row[field], field), row['case_id']) for row in subset] if field in header else []
            present = [(value, case) for value, case in observations if value is not None]
            values = [value for value, _ in present]
            maximum = max(values) if values else None
            output.append(dict(source_id=source_id, profile_id=profile, stream=asr, identity_tap=identity,
                route=f'{asr}_ASR_{identity}_ID', metric=field, declared_case_count=len(cases),
                observed_source_rows=len(subset), missing_source_rows=len(cases)-len(subset),
                field_present=field in header, value_observed_rows=len(values),
                value_missing_rows=len(subset)-len(values),
                minimum=min(values) if values else None, median=statistics.median(values) if values else None,
                maximum=maximum, sum_observed=sum(values) if values and field in ADDITIVE else None,
                sum_scope='SUM_OF_OBSERVED_SOURCE_ROWS_ONLY' if field in ADDITIVE else 'NOT_ADDITIVE_NOT_SUMMED',
                maximum_case_ids=json.dumps(sorted(case for value, case in present if value == maximum)),
                missing_case_ids=json.dumps(sorted(set(cases)-{row['case_id'] for row in subset})),
                scope=metric_scope(field)))
    return output


def project_tracker_snapshot(snapshot, pointer):
    """Pure projection only; caller must separately admit closure, epoch, profile, owner and source."""
    tracker = snapshot
    if not pointer.startswith('/'):
        raise ValueError('Explicit tracker JSON pointer required')
    for key in pointer[1:].split('/'):
        tracker = tracker[key.replace('~1', '/').replace('~0', '~')]
    result = dict(state_bytes=tracker.get('state_bytes'), counts=tracker.get('counts'),
                  prototype_comparisons=tracker.get('prototype_comparisons'),
                  max_live_prototype_comparisons_per_observation=tracker.get('max_live_prototype_comparisons_per_observation'),
                  per_track_measured_heap_bytes=None, native_process_rss_bytes=None)
    for field in ('prototype_comparisons', 'max_live_prototype_comparisons_per_observation'):
        v=result[field]
        if v is not None and (type(v) is not int or v < 0):
            raise ValueError('Invalid snapshot work count')
    for parent, fields in [('counts', COUNT_NAMES), ('state_bytes', ('array_payload', 'shallow_object_estimate'))]:
        if result[parent] is not None:
            if not isinstance(result[parent], dict):
                raise ValueError('Snapshot count/byte object required')
            for field in fields:
                v=result[parent].get(field)
                if v is not None and (type(v) is not int or v < 0):
                    raise ValueError('Invalid snapshot count/byte estimate')
    return result


def write_json(path, value):
    raw=(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n').encode('utf-8')
    with path.open('xb') as handle:
        handle.write(raw)
    return binding(path, raw)


def write_csv(path, header, rows):
    with path.open('x', encoding='utf-8', newline='') as handle:
        writer=csv.DictWriter(handle, fieldnames=header, extrasaction='raise');writer.writeheader();writer.writerows(rows)
    return binding(path, path.read_bytes())


def require_quiet_absent():
    if (REPORT/'PACED_QUIET_OWNER.json').exists():
        raise ValueError('Active shared paced/continuous quiet lease; defer reporting')


def run(output):
    require_quiet_absent()
    output=output.resolve()
    if output.parent != REPORT/'work_state_reporting' or output.exists():
        raise ValueError('Fresh report/work_state_reporting child required')
    safe_name(output.name)
    raw=INDEX.read_bytes(); ib=binding(INDEX,raw)
    if ib['sha256'] != INDEX_SHA:
        raise ValueError('Held source index changed')
    index=document(raw); declarations=index['comparison_work_tables']
    if len(declarations)!=31 or len({x['source_id'] for x in declarations})!=31 or len(index['closed_state_snapshots'])!=2:
        raise ValueError('Exact31 lifecycle plus2 chronological source scope required')
    strata={x['source_id']:x for x in index['strata_tables']}
    output.mkdir(parents=True)
    summaries=[]; sources=[]; outputs=[]; all_cells=0
    for decl in declarations:
        require_quiet_absent()
        source_id=safe_name(decl['source_id']); authority=bound_json(decl['authority'])
        if authority['schema'] not in ('jp_s6c_core_analysis.v1','jp_s6c_core_analysis.v2','jp_s6c_core_analysis.v3') or authority['status']!='COMPLETE_REQUESTED_INDEX':
            raise ValueError('Completed core authority required')
        if decl['authority']!=strata[source_id]['authority'] or authority['profile_routes']!=strata[source_id]['declared_profile_routes']:
            raise ValueError('Pinned source authority or actual routes differ')
        pointers=[n for n,t in enumerate(authority['tables']) if t==decl['table']]
        if len(pointers)!=1 or Path(decl['table']['path']).name!='TRACK_LIFECYCLE_RESULTS.csv':
            raise ValueError('Exact lifecycle authority pointer required')
        raw=read_bound(decl['table']); header, rows=csv_rows(raw)
        summary=group_source(source_id,authority,header,rows);summaries.extend(summary)
        provenance=[PREFIX+'source_id',PREFIX+'authority_sha256',PREFIX+'table_sha256',PREFIX+'source_row',PREFIX+'cell_map_sha256']
        retained=[dict(row, **{provenance[0]:source_id,provenance[1]:decl['authority']['sha256'],provenance[2]:decl['table']['sha256'],provenance[3]:n,provenance[4]:hashlib.sha256(canonical(row)).hexdigest()}) for n,row in enumerate(rows,1)]
        folder=output/source_id;folder.mkdir()
        outputs.append(write_csv(folder/'SOURCE_CELLS.csv',header+provenance,retained));all_cells+=len(rows)
        sources.append(dict(**decl,binding_pointer=f'/tables/{pointers[0]}',source_header=header,
            rows=len(rows),declared_routes=authority['profile_routes'],case_ids=authority['case_ids'],
            requested=authority['requested'],scored=authority['scored'],unscored=authority['unscored'],
            scope=authority.get('scope'),row_preservation='Every original decoded CSV cell unchanged; original header order retained, provenance appended.'))
    outputs.append(write_csv(output/'GROUP_METRICS.csv',list(summaries[0]),summaries))
    chronological=[]
    for decl in index['closed_state_snapshots']:
        if decl['execution_kind']!=CHRONO_KIND:
            raise ValueError('This CLI admits only the two closed chronological snapshots')
        snapshot=bound_json(decl['binding']); projected=project_tracker_snapshot(snapshot,decl['json_pointer'])
        for field in ('state_bytes','counts','prototype_comparisons','max_live_prototype_comparisons_per_observation'):
            if projected[field]!=decl[field]:
                raise ValueError('Snapshot projection differs from prior review')
        chronological.append(dict(source=decl,projection=projected))
    outputs.append(write_json(output/'CHRONOLOGICAL_STATE_ONLY.json',dict(schema='s6c-work-state-chronological.v1',records=chronological,
        scope='Model-free chronological N00 policy diagnostics; not native endurance, paced RSS, recognition validation or finalist measurements. Array/shallow estimates exclude recursive heap/models/queues.')))
    outputs.append(write_json(output/'SOURCE_ADMISSION.json',dict(sources=sources,index=ib,chronological_review=index['chronological_snapshot_review'])))
    for d in declarations:
        read_bound(d['authority'])
    if binding(INDEX, INDEX.read_bytes())!=ib:
        raise ValueError('Source index changed during report')
    code=Path(__file__).resolve();readme=code.with_name('README_S6C_WORK_STATE_REPORT_V1.md')
    return write_json(output/'RESULT.json',dict(schema='s6c-work-state-report.v1',status='COMPLETE_EXPLICIT_WORKING_REPORT_NOT_FINAL',
        utc=datetime.now(timezone.utc).isoformat(),source_count=31,source_rows=all_cells,
        authority_route_groups=len(summaries)//len(METRICS),metric_rows=len(summaries),metrics=list(METRICS),
        source_index=ib,sources=[binding(p,p.read_bytes()) for p in (code,readme)],outputs=outputs,
        sums='Only decisions, prototype_comparisons and blocked_unique_evidence_sec are summed within one authority/candidate/actual route. No cross-authority sum, best-repetition selection or accuracy ranking.',
        maxima='All groups retained; tied maximum case IDs sorted lexically. Final counts, tracker-maintained peaks and observed-decision maxima remain separate.',
        missingness='Blank source values and absent fields remain unavailable. Missing source rows, value-missing rows and field presence have distinct columns. Empty aggregate values export as blank with explicit denominators.',
        state_memory='Only two already-bound chronological snapshots admitted. Per-track heap/native RSS unavailable. No pending native state source was discovered or read.',
        prospective_interface='project_tracker_snapshot is pure, not an admission API. Later paced/long callers must first verify the exact completed native cell/session closure, epoch/profile/gallery/owner/source and artifact binding with reviewed inventory/diagnostic admission; then explicitly bind a final tracker pointer. This CLI intentionally cannot accept those sources.',
        models=0,scoring=0,prediction_reads=0,native_event_reads=0,audio_reads=0))


def checks():
    passed=[]
    def check(name, fn):
        fn();passed.append(name)
    def fails(fn):
        try:fn()
        except (ValueError,KeyError,TypeError):return
        raise AssertionError('Expected rejection')
    authority=dict(profile_routes=[dict(candidate_id='C001',stream='O0',identity_tap='O1')],case_ids=['A','B'],requested=2,scored=2,unscored=0)
    header=list(ID_FIELDS)+['prototype_comparisons','max_live_prototype_comparisons_per_observation','peak_live','final_live']
    rows=[dict(zip(header,['C001','O0','O1','O0_ASR_O1_ID',c,w,'3','4',f])) for c,w,f in [('A','0','2'),('B','8','')]]
    def summary_test():
        g=group_source('s',authority,header,rows); w=next(x for x in g if x['metric']=='prototype_comparisons'); f=next(x for x in g if x['metric']=='final_live'); m=next(x for x in g if x['metric']=='final_archive')
        assert w['sum_observed']==8 and w['minimum']==0 and w['maximum_case_ids']=='["B"]'
        assert f['value_observed_rows']==1 and f['value_missing_rows']==1 and f['sum_observed'] is None
        assert not m['field_present'] and m['value_observed_rows']==0 and m['value_missing_rows']==2 and m['maximum'] is None
    check('zero_vs_missing_and_nonadditive_stocks',summary_test)
    check('duplicate_row_rejected',lambda:fails(lambda:group_source('s',authority,header,[rows[0],rows[0]])))
    check('wrong_actual_route_rejected',lambda:fails(lambda:group_source('s',authority,header,[dict(rows[0],route='O0_ASR_O0_ID'),rows[1]])))
    check('bad_numeric_rejected',lambda:fails(lambda:numeric('NaN','blocked_unique_evidence_sec')))
    check('boolean_count_rejected',lambda:fails(lambda:numeric('True','prototype_comparisons')))
    def missing_rows():
        a=dict(authority,scored=1,unscored=1);g=group_source('s',a,header,rows[:1]);assert all(x['missing_source_rows']==1 and x['missing_case_ids']=='["B"]' for x in g)
    check('missing_source_row_separate_from_blank_cell',missing_rows)
    def independent():
        a=group_source('a',authority,header,rows); b=group_source('b',authority,header,rows)
        assert all(x['source_id']=='a' for x in a) and all(x['source_id']=='b' for x in b)
    check('separate_authority_groups',independent)
    def ties():
        g=group_source('s',authority,header,[rows[1],dict(rows[0],prototype_comparisons='8')]);w=next(x for x in g if x['metric']=='prototype_comparisons');assert w['maximum_case_ids']=='["A", "B"]'
    check('all_maximum_ties_deterministically_retained',ties)
    def snapshot():
        z=project_tracker_snapshot({'tracker':{'counts':{'live':3},'state_bytes':{'array_payload':123,'shallow_object_estimate':456}}},'/tracker')
        assert z['per_track_measured_heap_bytes'] is None and z['native_process_rss_bytes'] is None and z['state_bytes']['array_payload']==123
    check('bytes_not_divided_or_renamed_native_memory',snapshot)
    check('snapshot_boolean_bytes_rejected',lambda:fails(lambda:project_tracker_snapshot({'tracker':{'state_bytes':{'array_payload':True}}},'/tracker')))
    def exact():
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'bound.json';p.write_bytes(b'{"a":1}');b=binding(p,p.read_bytes());assert bound_json(b)=={'a':1};p.write_bytes(b'{"a":2}');fails(lambda:read_bound(b))
    check('exact_buffer_change_rejected',exact)
    def cells():
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)/'rows.csv';z=dict(rows[0],note='false, "None"\n0');b=write_csv(p,header+['note'],[z]);h,q=csv_rows(read_bound(b));assert q==[z] and h==header+['note']
    check('source_cell_text_and_quoting_preserved',cells)
    return dict(status='PASS_MODEL_FREE',checks=len(passed),names=passed,models=0,actual_source_tables_read=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('action',choices=['checks','run']);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.output is None:parser.error('--output required')
    if args.action=='checks':
        result=checks();result['sources']=[binding(p,p.read_bytes()) for p in (Path(__file__).resolve(),Path(__file__).with_name('README_S6C_WORK_STATE_REPORT_V1.md'))]
        args.output.parent.mkdir(parents=True,exist_ok=True);result=write_json(args.output,result)
    else:result=run(args.output)
    print(json.dumps(result,indent=2))
