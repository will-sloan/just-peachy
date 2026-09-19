"""Bind the nine previously requested N03 contrasts; see the matching README."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S6C/20260910T123540Z'

def read(path, expected=None):
    path = Path(path)
    raw = path.read_bytes()
    binding = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    if expected is not None and binding != expected:
        raise ValueError('Changed exact source: ' + str(path))
    return json.loads(raw), binding

def write_new(path, data):
    raw = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    with Path(path).open('xb') as handle:
        handle.write(raw)
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

def main():
    scope, scope_binding = read(REPORT / 'design/FULL_N03_COMPARISON_SCOPE_V1.json')
    if scope_binding['sha256'] != 'cf21af4c2dbadc564d6dfd87bee0d8abb9d436930140f26010543a3bbb3434bc':
        raise ValueError('The pre-scoring comparison request changed')
    base, base_binding = read(REPORT / 'design/full_n01_anonymous_compare_v2_inputs_V3.json')
    if base_binding['sha256'] != 'f20b1ed2286d08b76ee45cba84a5d9e8aea77cae0f3acfbca3f60407e61dd6e9':
        raise ValueError('Historical source/registry example changed')
    n03, n03_binding = read(REPORT / 'full_n03_native_core_v3/ANALYSIS_RECEIPT.json')
    if (n03['status'], n03['requested'], n03['scored'], n03['unscored']) != ('COMPLETE_REQUESTED_INDEX',480,480,0):
        raise ValueError('Full N03 core did not complete the requested population')
    n01_row = next(x for x in base['sources'] if 'C065' in x['candidate_ids'])
    _, n01_binding = read(n01_row['receipt']['path'], n01_row['receipt'])
    historical = base['historical_sources']
    if len(historical) != 1 or historical[0]['candidate_ids'] != ['B00','B01','B36']:
        raise ValueError('Unexpected historical control selection')
    read(historical[0]['receipt']['path'], historical[0]['receipt'])
    cases = historical[0]['case_ids']
    if len(cases) != 240 or len(set(cases)) != 240:
        raise ValueError('Historical complete grid required')
    contrasts = []
    for row in scope['comparisons']:
        left = dict(candidate_id=row['left'], asr_tap=row['left_asr_tap'], identity_tap=row['left_identity_tap'])
        right = dict(candidate_id=row['right'], asr_tap=row['right_asr_tap'], identity_tap=row['right_identity_tap'])
        comparison_id = f"{left['candidate_id']}_{left['asr_tap']}_to_{right['candidate_id']}_{right['asr_tap']}"
        contrasts.append(dict(comparison_id=comparison_id, label=row['label']+'; right minus left',
                               left=left, right=right, case_scope='REQUIRE_IDENTICAL_SCENES'))
    if len(contrasts) != 9 or len({x['comparison_id'] for x in contrasts}) != 9:
        raise ValueError('Nine unique requested contrasts required')
    for path, sha in base['registry_extensions']:
        _, binding = read(path)
        if binding['sha256'] != sha:
            raise ValueError('Changed registry extension')
    spec = dict(schema='jp_s6c_compare_inputs.v2',
                sources=[dict(receipt=n03_binding,candidate_ids=['C067'],case_ids=cases),
                         dict(receipt=n01_binding,candidate_ids=['C065'],case_ids=cases)],
                historical_sources=historical, registry_extensions=base['registry_extensions'],
                expected_candidates=234, comparisons=contrasts)
    output = write_new(REPORT / 'design/full_n03_compare_v2_inputs_V1.json',spec)
    codes = []
    for path in (Path(__file__), Path(__file__).with_name('README_S6C_FULL_N03_COMPARE_PLAN_V1.md')):
        raw=path.read_bytes()
        codes.append(dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    receipt = write_new(REPORT / 'design/FULL_N03_COMPARISON_BINDING_V1.json',dict(
        status='BOUND_REQUEST_ONLY', codes=codes, scope=scope_binding, inherited_source_selection=base_binding,
        score_receipts=[n03_binding,n01_binding,historical[0]['receipt']], output=output,
        comparisons=len(contrasts),matched_cases=240,
        limitation='No score computation or inference. Held compare V2 must independently admit all exact score/table/source chains before collecting results.'))
    print(json.dumps(receipt,indent=2))

if __name__ == '__main__':
    main()
