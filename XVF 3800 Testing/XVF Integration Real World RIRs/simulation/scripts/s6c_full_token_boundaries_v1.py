"""Score-table token boundaries only; see README_S6C_FULL_TOKEN_BOUNDARIES_V1.md."""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import string

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S6C/20260910T123540Z'
ROOT = REPORT / 'full_token_boundaries_v1'
SCHEMA = 's6c-full-score-token-boundaries.v1'
ENDPOINT_SHA = '4e0665a21eb916e8697d312ee5f660818b10d040e26aae61e7162e509c16a6f2'
NORMALIZE_SHA = '0b5d8a227ca87c4dcee48db8118de35444fb32217291bf022feb458f0982d1a0'
LAYOUT_SHA = 'c7614c33c04cba1f47660c10235198c8cd697963eb42b12a3656b503a8c884cd'
BANK_SHA = '69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18'
INPUT_SHA = '97b20d821c671794b24b1f8a4a9d4049fd192767bd0a093309887c279b48e70d'
COMPARE_SPEC_SHA = 'f20b1ed2286d08b76ee45cba84a5d9e8aea77cae0f3acfbca3f60407e61dd6e9'
SEAL_SHA = '2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e'
HIST_SHA = '12ee9ccd91a2a924ba2f54b51f622c39c73ed15325073cac5439bad4298dda0f'
SLOTS = {
    'historical': [('B00', 'O0', 'O0'), ('B00', 'O1', 'O1'), ('B01', 'O0', 'O0'), ('B01', 'O1', 'O1'), ('B36', 'O0', 'O0'), ('B36', 'O1', 'O1')],
    'n01': [('C065', 'O0', 'O0'), ('C065', 'O1', 'O1')],
    'n03': [('C067', 'O0', 'O0'), ('C067', 'O1', 'O1')],
    'n08_n10': [('C072', 'O0', 'O0'), ('C072', 'O1', 'O1'), ('C074', 'O0', 'O0'), ('C074', 'O1', 'O1')],
    'n12': [('C076', 'O0', 'O0'), ('C076', 'O1', 'O1')],
    'cross': [('C085', 'O0', 'O1'), ('C086', 'O1', 'O0')],
}
POPULATIONS = {'PRIMARY_NONOVERLAP': 156, 'COMPLETE_OVERLAP': 47, 'STRICT_EMPTY_REFERENCE': 11, 'INCOMPLETE_REFERENCE': 26}
SCOPE = ('Original scored normalized_final_text, not new native-log verification. Deterministic unit-cost token-position alignment; '
         'backtrace equal/substitution/deletion/insertion. Incomplete full-reference edits are null. Complete overlap uses the '
         'canonical source-start utterance serialization, not MIMO/cp scoring. No token timing, phonetic clipping, reset or causal claim.')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def bind(path, raw=None):
    path = Path(path).resolve()
    raw = path.read_bytes() if raw is None else raw
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def exact(b, cap=100 * 2**20):
    require(type(b.get('bytes', 0)) is int and 0 <= b.get('bytes', 0) <= cap, 'Invalid declared byte count')
    with Path(b['path']).open('rb') as f:
        raw = f.read(cap + 1)
    require(len(raw) <= cap, 'Input byte cap exceeded')
    require(hashlib.sha256(raw).hexdigest() == b['sha256'] and ('bytes' not in b or len(raw) == b['bytes']), 'Changed exact source: ' + b['path'])
    return raw


def document(b):
    return json.loads(exact(b), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON: ' + value)))


def pinned(path, sha):
    raw = exact(dict(path=str(path), sha256=sha))
    return bind(path, raw), json.loads(raw)


def save(path, value):
    raw = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    return bind(path, raw)


def safe_folder(name):
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', name) is not None, 'Simple output name required')
    path = ROOT / name
    require(not path.exists(), 'Fresh output namespace required')
    return path


def quiet():
    require(not (REPORT / 'PACED_QUIET_OWNER.json').exists(), 'Active quiet lease: defer score-table streaming')


def api():
    namespace = dict(Counter=Counter, defaultdict=defaultdict, string=string, require=require)
    bindings = []
    for name, sha, function in [('s4_h2_analysis.py', NORMALIZE_SHA, 'normalize'),
                                 ('s6a_text_metrics.py', LAYOUT_SHA, 'reference_layout'),
                                 ('s6c_endpoint_audit_v1.py', ENDPOINT_SHA, 'positional_edits')]:
        path = Path(__file__).with_name(name)
        raw = exact(dict(path=str(path), sha256=sha))
        nodes = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == function]
        require(len(nodes) == 1, 'Exact inherited pure function required')
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        bindings.append(bind(path, raw))
    return namespace['normalize'], namespace['reference_layout'], namespace['positional_edits'], bindings


def bank_metadata():
    b, bank = pinned(SIM / 'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json', BANK_SHA)
    scenes = {s['case_id']: s for s in bank['scenes']}
    require(len(scenes) == len(bank['scenes']) == 240, 'Canonical unique 240-scene bank required')
    _, layout, _, _ = api()
    populations = Counter(layout(s)['population'] for s in scenes.values())
    require(dict(populations) == POPULATIONS, 'Canonical population counts differ')
    require(sum(len(layout(s)['reference'].split()) for s in scenes.values() if layout(s)['population'] in ('PRIMARY_NONOVERLAP', 'COMPLETE_OVERLAP')) == 6016, 'Complete reference word denominator differs')
    return b, scenes


def table_binding(receipt):
    found = [b for b in receipt['tables'] if Path(b['path']).name == 'SCENE_RESULTS.csv']
    require(len(found) == 1, 'One original SCENE_RESULTS.csv required')
    return found[0]


def admit_receipt(slot, b, receipt, case_ids):
    require(slot in SLOTS, 'Unknown source slot')
    require(receipt.get('status') == 'COMPLETE_REQUESTED_INDEX', 'Only completed core authority allowed')
    require(all(type(receipt[k]) is int for k in ('requested', 'scored', 'unscored')) and receipt['requested'] > 0 and receipt['requested'] == receipt['scored'] and receipt['unscored'] == 0, 'Incomplete score authority')
    require(receipt['input_index']['sha256'] == INPUT_SHA, 'Canonical input authority differs')
    codes = {Path(x['path']).name: x['sha256'] for x in receipt['codes']}
    require(codes.get('s4_h2_analysis.py') == NORMALIZE_SHA and codes.get('s6a_text_metrics.py') == LAYOUT_SHA, 'Exact normalizer/reference layout provenance required')
    wanted = set(SLOTS[slot])
    if slot == 'historical':
        require(receipt['schema'] == 'jp_s6b_analysis_v1' and b['sha256'] == HIST_SHA and receipt['scored'] == 13920, 'Exact historical full scorer required')
        require({p for p, _, _ in wanted} <= set(receipt['all240_two_tap_confirmed_profiles']), 'Historical full-bank profiles absent')
    else:
        require(receipt['schema'] == 'jp_s6c_core_analysis.v3', 'Held V3 core schema required')
        require(receipt['bank']['sha256'] == BANK_SHA and set(receipt['case_ids']) == set(case_ids) and len(receipt['case_ids']) == 240, 'Full canonical bank required')
        found = {(r['profile_id'], r['stream'], r['identity_tap']) for r in receipt['full240_confirmed_routes'] if r['scenes'] == 240}
        require(wanted <= found, 'Requested full-bank route not confirmed')
    tb = table_binding(receipt)
    require(Path(tb['path']).resolve().parent == Path(b['path']).resolve().parent, 'Original local core table required')
    return dict(slot=slot, status='COMPLETE_AUTHORITY_BOUND_TABLE_NOT_READ', receipt=b, scene_table=tb,
                score_schema=receipt['schema'], declared_table_rows=receipt['scored'], routes=[list(x) for x in SLOTS[slot]],
                input_index=receipt['input_index'], prediction_index_provenance_only=receipt['index'])


def authority(slot, b, case_ids):
    return admit_receipt(slot, b, document(b), case_ids)


def historical_authority(case_ids):
    cb, spec = pinned(REPORT / 'design/full_n01_anonymous_compare_v2_inputs_V3.json', COMPARE_SPEC_SHA)
    requests = [x for x in spec['historical_sources'] if set(x['candidate_ids']) == {'B00', 'B01', 'B36'}]
    require(len(requests) == 1 and requests[0]['case_ids'] == case_ids, 'Exact full-anonymous historical selector required')
    rb = requests[0]['receipt']
    receipt = document(rb)
    sb, seal = pinned(Path(receipt['input_index']['path']).parent / 'LOCAL_ARTIFACT_INDEX.json', SEAL_SHA)
    matches = [x for x in seal['artifacts'] if Path(x['path']).resolve() == Path(rb['path']).resolve()]
    require(len(matches) == 1 and all(matches[0][k] == rb[k] for k in ('path', 'bytes', 'sha256')), 'Historical receipt not in sealed authority')
    return authority('historical', rb, case_ids), [cb, sb]


def draft(name):
    quiet()
    folder = safe_folder(name)
    bb, scenes = bank_metadata()
    ids = sorted(scenes)
    historical, lineage = historical_authority(ids)
    sources = [historical]
    for slot, directory, sha in [('n01', 'full_n01_anonymous_core_v3', '72af65710f4bbc45733bd6f145fbd4eb67ce558b8c3bbdad01b9c2c807c4e094'),
                                  ('n03', 'full_n03_native_core_v3', '10d38193dfa630bc06dd15d582f1d9086493ce104cc5b45535be01844e238517')]:
        b, _ = pinned(REPORT / directory / 'ANALYSIS_RECEIPT.json', sha)
        sources.append(authority(slot, b, ids))
    for slot, label in [('n08_n10', 'full_n08_n10_native_core_v3'), ('n12', 'full_n12_native_core_v3'), ('cross', 'full_cross_native_core_v3')]:
        sources.append(dict(slot=slot, status='PENDING_EXPLICIT_COMPLETE_AUTHORITY', intended_label_not_binding=label, receipt=None,
                            scene_table=None, routes=[list(x) for x in SLOTS[slot]]))
    return save(folder / 'SPEC.json', dict(schema=SCHEMA, status='DRAFT_FINITE_UNRESOLVED_AUTHORITIES', utc=datetime.now(timezone.utc).isoformat(),
        helper=bind(__file__), readme=bind(Path(__file__).with_name('README_S6C_FULL_TOKEN_BOUNDARIES_V1.md')), pure_dependencies=api()[3],
        bank=bb, case_ids=ids, historical_authority_chain=lineage, sources=sources, requested_routes=18, requested_cells=4320,
        population_scenes_per_route=POPULATIONS, pairs=pair_routes(), scope=SCOPE,
        source_tables_read=False, new_models=0, run_requires_fully_resolved_plan=True))


def pair_routes():
    rows = []
    for pid in ('C067', 'C072', 'C074', 'C076', 'B00', 'B01', 'B36'):
        for tap in ('O0', 'O1'):
            rows.append(dict(left=['C065', tap, tap], right=[pid, tap, tap]))
    rows.extend([dict(left=['C065', 'O0', 'O0'], right=['C085', 'O0', 'O1']), dict(left=['C065', 'O1', 'O1'], right=['C086', 'O1', 'O0'])])
    return rows


def validate_spec(spec):
    require(spec['schema'] == SCHEMA and spec['requested_routes'] == 18 and spec['requested_cells'] == 4320, 'Fixed finite specification required')
    require(spec['pairs'] == pair_routes() and spec['population_scenes_per_route'] == POPULATIONS, 'Comparison/population specification differs')
    require(spec['helper'] == bind(__file__) and spec['readme'] == bind(Path(__file__).with_name('README_S6C_FULL_TOKEN_BOUNDARIES_V1.md')), 'Held helper/README changed')
    require(spec['pure_dependencies'] == api()[3], 'Held pure dependency bindings differ')
    bb, scenes = bank_metadata()
    require(spec['bank'] == bb and spec['case_ids'] == sorted(scenes), 'Canonical bank/case order differs')
    require(len(spec['sources']) == len(SLOTS) and {s['slot'] for s in spec['sources']} == set(SLOTS), 'Exactly six source slots required')
    for source in spec['sources']:
        require(source['routes'] == [list(x) for x in SLOTS[source['slot']]], 'Declared registered routes differ')
    hist, chain = historical_authority(spec['case_ids'])
    require(next(s for s in spec['sources'] if s['slot'] == 'historical') == hist and spec['historical_authority_chain'] == chain, 'Historical authority chain differs')
    return scenes


def prepare(spec_path, spec_sha, overrides, name):
    quiet()
    sb, spec = pinned(Path(spec_path), spec_sha)
    validate_spec(spec)
    supplied = {}
    for slot, path, sha in overrides:
        require(slot in ('n08_n10', 'n12', 'cross') and slot not in supplied, 'Explicit unique pending slot required')
        b, _ = pinned(Path(path), sha)
        supplied[slot] = b
    resolved = []
    for source in spec['sources']:
        slot = source['slot']
        if source['receipt'] is None:
            require(slot in supplied, 'Missing completed authority: ' + slot)
            resolved.append(authority(slot, supplied[slot], spec['case_ids']))
        else:
            require(slot not in supplied, 'Bound authority replacement forbidden')
            resolved.append(authority(slot, source['receipt'], spec['case_ids']))
    plan = dict(spec, status='READY_COMPLETE_AUTHORITIES_TABLES_NOT_READ', sources=resolved, original_spec=sb, utc=datetime.now(timezone.utc).isoformat())
    return save(safe_folder(name) / 'PLAN.json', plan)


def selected_rows(raw, source, case_ids, normalize):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    needed = {'profile_id', 'stream', 'case_id', 'population', 'normalized_final_text', 'duration_sec', 'family_id'}
    require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)) and needed <= set(reader.fieldnames), 'Original score-table fields required')
    if source['slot'] != 'historical':
        require('identity_tap' in reader.fieldnames, 'Explicit S6C identity route required')
    routes = {tuple(x) for x in source['routes']}
    expected = {(p, a, i, c) for p, a, i in routes for c in case_ids}
    seen = set(); selected = {}; count = 0
    for ordinal, row in enumerate(reader, 1):
        require(None not in row and all(v is not None for v in row.values()), 'Malformed or truncated CSV record')
        identity = row['stream'] if source['slot'] == 'historical' else row['identity_tap']
        key = (row['profile_id'], row['stream'], identity, row['case_id'])
        require(key not in seen, 'Duplicate source-table key')
        seen.add(key); count += 1
        if key[:3] not in routes:
            continue
        require(key in expected, 'Unexpected selected route/case')
        text = row['normalized_final_text']
        require(len(text.encode('utf-8')) <= 1024 * 1024 and normalize(text) == text, 'Normalized source text required, including exact empty string')
        duration = float(row['duration_sec'])
        require(math.isfinite(duration) and duration > 0, 'Finite actual source duration required')
        selected[key] = dict(source_row=row, csv_record_ordinal=ordinal, source_row_sha256=digest(row), normalized_text_sha256=hashlib.sha256(text.encode()).hexdigest())
    require(count == source['declared_table_rows'], 'Complete table row denominator differs')
    require(set(selected) == expected, 'Selected source grid incomplete')
    return selected


def cell_result(key, item, source, scene, layout, edits):
    row = item['source_row']; reference = layout(scene)
    require(row['population'] == reference['population'] and row['family_id'] == scene['family_id'], 'Score/reference population or scene family differs')
    ref = reference['reference'].split(); hyp = row['normalized_final_text'].split()
    result = edits(ref, hyp) if reference['complete'] else None
    return dict(profile_id=key[0], asr_tap=key[1], identity_tap=key[2], case_id=key[3], family_id=scene['family_id'],
        population=reference['population'], reference_complete=reference['complete'], duration_sec=float(row['duration_sec']),
        available_reference_words=len(ref), hypothesis_words=len(hyp), normalized_final_text_sha256=item['normalized_text_sha256'],
        first_reference_token=ref[0] if ref and reference['complete'] else None, last_reference_token=ref[-1] if ref and reference['complete'] else None,
        token_alignment=result, first_reference_token_deleted=result['first_reference_token_operation'] == 'deletion' if result and ref else None,
        last_reference_token_deleted=result['last_reference_token_operation'] == 'deletion' if result and ref else None,
        provenance=dict(authority_slot=source['slot'], receipt=source['receipt'], scene_table=source['scene_table'], csv_record_ordinal=item['csv_record_ordinal'], source_row_sha256=item['source_row_sha256']), scope=SCOPE)


def aggregate(cells):
    groups = defaultdict(list)
    for c in cells:
        groups[c['profile_id'], c['asr_tap'], c['identity_tap'], c['population']].append(c)
    rows = []
    for key, group in sorted(groups.items()):
        scored = [c for c in group if c['token_alignment'] is not None]
        nonempty = [c for c in scored if c['available_reference_words'] > 0]
        rows.append(dict(profile_id=key[0], asr_tap=key[1], identity_tap=key[2], population=key[3],
            requested_scenes=len(group), alignment_available_scenes=len(scored), alignment_unavailable_scenes=len(group)-len(scored),
            boundary_eligible_scenes=len(nonempty), hypothesis_words_all_scenes=sum(c['hypothesis_words'] for c in group),
            reference_words=sum(c['token_alignment']['reference_words'] for c in scored) if scored else None,
            **{k: sum(c['token_alignment'][k] for c in scored) if scored else None for k in ('errors', 'substitutions', 'deletions', 'insertions')},
            first_token_deletion_scenes=sum(c['first_reference_token_deleted'] for c in nonempty) if nonempty else None,
            last_token_deletion_scenes=sum(c['last_reference_token_deleted'] for c in nonempty) if nonempty else None,
            first_token_operation_counts=dict(Counter(c['token_alignment']['first_reference_token_operation'] for c in nonempty)),
            last_token_operation_counts=dict(Counter(c['token_alignment']['last_reference_token_operation'] for c in nonempty))))
    return rows


def compare_cells(cells, comparisons, case_ids):
    bykey = {(c['profile_id'], c['asr_tap'], c['identity_tap'], c['case_id']): c for c in cells}
    rows = []
    for pair in comparisons:
        for cid in case_ids:
            a, b = [bykey[(*route, cid)] for route in (pair['left'], pair['right'])]
            require(a['population'] == b['population'] and a['available_reference_words'] == b['available_reference_words'] and a['duration_sec'] == b['duration_sec'], 'Paired source/reference differs')
            aa, bb = a['token_alignment'], b['token_alignment']
            rows.append(dict(left=pair['left'], right=pair['right'], case_id=cid, population=a['population'],
                normalized_final_text_changed=a['normalized_final_text_sha256'] != b['normalized_final_text_sha256'],
                alignment_available=aa is not None and bb is not None,
                right_minus_left={k: bb[k]-aa[k] for k in ('errors', 'substitutions', 'deletions', 'insertions', 'hypothesis_words')} if aa is not None and bb is not None else None,
                first_reference_token_operation=dict(left=aa['first_reference_token_operation'], right=bb['first_reference_token_operation']) if aa is not None and bb is not None else None,
                last_reference_token_operation=dict(left=aa['last_reference_token_operation'], right=bb['last_reference_token_operation']) if aa is not None and bb is not None else None))
    return rows


def run(plan_path, plan_sha, name):
    quiet()
    pb, plan = pinned(Path(plan_path), plan_sha)
    require(plan['status'] == 'READY_COMPLETE_AUTHORITIES_TABLES_NOT_READ', 'Explicit complete prepared plan required')
    scenes = validate_spec(plan)
    normalize, layout, edits, _ = api()
    folder = safe_folder(name)
    cells = []; sources = []
    for source in plan['sources']:
        quiet()
        require(authority(source['slot'], source['receipt'], plan['case_ids']) == source, 'Prepared authority metadata differs')
        raw = exact(source['scene_table'])
        selected = selected_rows(raw, source, plan['case_ids'], normalize)
        for key, item in sorted(selected.items()):
            cells.append(cell_result(key, item, source, scenes[key[3]], layout, edits))
        sources.append(dict(slot=source['slot'], receipt=source['receipt'], scene_table=source['scene_table'], selected_cells=len(selected)))
    require(len(cells) == 4320, 'Exact final 18-route grid required')
    aggregates = aggregate(cells)
    pairs = compare_cells(cells, plan['pairs'], plan['case_ids'])
    artifacts = [save(folder/'CELLS.json', cells), save(folder/'ROUTE_POPULATIONS.json', aggregates), save(folder/'PAIRED_SCENES.json', pairs)]
    return save(folder/'RESULT.json', dict(schema=SCHEMA, status='COMPLETE_SCORE_TABLE_DIAGNOSTIC', utc=datetime.now(timezone.utc).isoformat(), plan=pb,
        helper=bind(__file__), pure_dependencies=api()[3], sources=sources, artifacts=artifacts, cells=4320, routes=18,
        paired_scene_rows=len(pairs), population_scenes_per_route=POPULATIONS, scope=SCOPE,
        native_log_verification_performed=False, new_models=0, new_policy_replays=0, new_authoritative_core_scores=0))


def checks():
    normalize, layout, edits, deps = api(); passed = []
    def check(label, ok):
        require(ok, label); passed.append(label)
    def rejects(label, fn):
        try:
            fn()
        except (ValueError, KeyError, UnicodeError):
            passed.append(label)
        else:
            raise AssertionError(label)
    check('normalization exact inherited punctuation/case', normalize(' A, B! ') == 'a b')
    for ref, hyp, first, last, d, i in [(['a','b','c'], ['b','c'], 'deletion','equal',1,0), (['a','b','c'], ['a','b'], 'equal','deletion',1,0),
                                      (['a'], ['x'], 'substitution','substitution',0,0), ([], ['x'], None,None,0,1), (['a'], [], 'deletion','deletion',1,0)]:
        e=edits(ref,hyp); check('endpoint tuple '+str((ref,hyp)), (e['first_reference_token_operation'],e['last_reference_token_operation'],e['deletions'],e['insertions'])==(first,last,d,i))
    e=edits(['a','a'],['a']);check('repeated-word inherited equal-first backtrace tie',e['deleted_reference_positions']==[0])
    rejects('alignment size bounded',lambda:edits(['a']*1500,['b']*1500))
    check('fixed asymmetric registered cross routes',SLOTS['cross']==[('C085','O0','O1'),('C086','O1','O0')])
    check('18 finite routes and 16 comparisons',sum(map(len,SLOTS.values()))==18 and len(pair_routes())==16)
    fields=['profile_id','stream','identity_tap','case_id','population','normalized_final_text','duration_sec','family_id']
    row=dict(zip(fields,['C085','O0','O1','x','PRIMARY_NONOVERLAP','a b','1','f']))
    source=dict(slot='cross',routes=[['C085','O0','O1']],declared_table_rows=1,receipt={},scene_table={})
    def buf(rows):
        f=io.StringIO();w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows);return f.getvalue().encode()
    check('explicit cross source route admitted',len(selected_rows(buf([row]),source,['x'],normalize))==1)
    for label, rows in [('duplicate row',[row,row]),('wrong identity route',[dict(row,identity_tap='O0')]),('unexpected case',[dict(row,case_id='z')]),('nonfinite duration',[dict(row,duration_sec='NaN')]),('non-normalized text',[dict(row,normalized_final_text='A!')])]:
        rejects(label,lambda rows=rows:selected_rows(buf(rows),source,['x'],normalize))
    rejects('missing normalized text header',lambda:selected_rows(b'profile_id,stream\nC085,O0\n',source,['x'],normalize))
    empty=dict(row,normalized_final_text='');check('empty text is observed value',len(selected_rows(buf([empty]),source,['x'],normalize))==1)
    word=dict(kind='utterance',speaker_key='p',transcript='a b',source_start_sample=0,source_stop_sample=16000)
    scene=dict(case_id='x',family_id='f',segments=[word],all_speaker_reference_complete=False,transcript_valid=False)
    item=next(iter(selected_rows(buf([dict(row,population='INCOMPLETE_REFERENCE')]),source,['x'],normalize).values()))
    c=cell_result(('C085','O0','O1','x'),item,source,scene,layout,edits)
    check('incomplete full edits and boundary loss null',c['token_alignment'] is None and c['first_reference_token_deleted'] is None)
    check('incomplete aggregate edits remain null',aggregate([c])[0]['errors'] is None and aggregate([c])[0]['boundary_eligible_scenes']==0)
    pair=compare_cells([c], [dict(left=['C085','O0','O1'],right=['C085','O0','O1'])], ['x'])[0]
    check('incomplete paired edit deltas null',pair['right_minus_left'] is None)
    scene.update(all_speaker_reference_complete=True,transcript_valid=True,overlap_intervals=[[0,1]])
    check('overlap serialization separate population',layout(scene)['population']=='COMPLETE_OVERLAP')
    rejects('source population contradiction',lambda:cell_result(('C085','O0','O1','x'),item,source,scene,layout,edits))
    rejects('output traversal rejected',lambda:safe_folder('../outside'))
    rejects('changed exact buffer rejected',lambda:exact({'path':str(Path(__file__)),'sha256':'0'*64}))
    fake_binding=dict(path=str(ROOT/'synthetic/ANALYSIS_RECEIPT.json'),bytes=1,sha256='0'*64)
    case_ids=['x'+str(i) for i in range(240)]
    fake=dict(schema='jp_s6c_core_analysis.v3',status='COMPLETE_REQUESTED_INDEX',requested=480,scored=480,unscored=0,
        input_index=dict(sha256=INPUT_SHA),bank=dict(sha256=BANK_SHA),case_ids=case_ids,index={},
        codes=[dict(path='s4_h2_analysis.py',sha256=NORMALIZE_SHA),dict(path='s6a_text_metrics.py',sha256=LAYOUT_SHA)],
        full240_confirmed_routes=[dict(profile_id=p,stream=a,identity_tap=i,scenes=240) for p,a,i in SLOTS['cross']],
        tables=[dict(path=str(ROOT/'synthetic/SCENE_RESULTS.csv'),bytes=1,sha256='1'*64)])
    check('complete source schema admitted without table read',admit_receipt('cross',fake_binding,fake,case_ids)['declared_table_rows']==480)
    for label,changed in [('partial status',dict(fake,status='PARTIAL')),('unscored failures',dict(fake,unscored=1)),('boolean count',dict(fake,requested=True)),
                          ('wrong canonical input',dict(fake,input_index=dict(sha256='0'*64))),('missing full route',dict(fake,full240_confirmed_routes=fake['full240_confirmed_routes'][:1])),
                          ('missing case',dict(fake,case_ids=case_ids[:-1])),('duplicate table',dict(fake,tables=fake['tables']*2))]:
        rejects(label,lambda changed=changed:admit_receipt('cross',fake_binding,changed,case_ids))
    return dict(status='PASS', checks=passed, count=len(passed), pure_dependencies=deps,
                helper=bind(__file__), readme=bind(Path(__file__).with_name('README_S6C_FULL_TOKEN_BOUNDARIES_V1.md')),
                model_calls=0, actual_score_tables_read=False)


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('checks');a.add_argument('--name',default='source_checks_v1')
    a=sub.add_parser('draft');a.add_argument('--name',default='draft_v1')
    a=sub.add_parser('prepare');a.add_argument('--spec',required=True);a.add_argument('--spec-sha',required=True);a.add_argument('--authority',nargs=3,action='append',default=[],metavar=('SLOT','RECEIPT','SHA'));a.add_argument('--name',required=True)
    a=sub.add_parser('run');a.add_argument('--plan',required=True);a.add_argument('--plan-sha',required=True);a.add_argument('--name',required=True)
    args=p.parse_args()
    if args.command=='checks': result=save(safe_folder(args.name)/'CHECKS.json',checks())
    elif args.command=='draft': result=draft(args.name)
    elif args.command=='prepare': result=prepare(args.spec,args.spec_sha,args.authority,args.name)
    else: result=run(args.plan,args.plan_sha,args.name)
    print(json.dumps(result))


if __name__=='__main__':
    main()
