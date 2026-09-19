"""Bounded independent review; README_S6C_SCORE_TABLES_COMPONENT_REVIEW_V1.md."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from pathlib import Path
import s6c_score_tables as collector

SIM=Path(__file__).resolve().parents[1]
REPORT=SIM/'reports/S6C/20260910T123540Z'


def bind(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def main():
    original=REPORT/'compact_score_tables/COLLECTOR_CHECKS_V1.json'
    b=bind(original)
    assert b['sha256']=='53441ccf13ad5f78ec8b50f913340f557af3d499143554f4750c66d2f74dbc31'
    prior=json.loads(original.read_bytes())
    for row in prior['sources']:assert bind(row['path'])==row
    reproduced=collector.checks();assert reproduced==prior['checks']
    checks=['Held source/README match original31-fixture receipt','All31 original isolated fixtures reproduced with no actual score export']
    values=dict(profile_id='C_alias',case_id='case',population='incomplete_target_only',stream='O0',identity_tap='O1',
        zero='0.000000000000000000',false='False',missing='',nan_literal='NaN',inf_literal='Infinity',
        words='01',unicode='é, "quote"\nsecond line',lineage_counts='{"a": 1, "b":null}',
        recipe_costs='{"wall_sec":0.0000001,"calls":0}',strata='{"source": ["A", "B"]}',normalized_final_text='a, "quoted"\nword')
    table=dict(row_key=['profile_id','case_id','population','stream','identity_tap'],omit_fields=['recipe_costs','strata','normalized_final_text'])
    provenance=dict(source_id='separate',scope_kind='split',scope_label='explicit split input',authority_sha256='a'*64,table_sha256='b'*64)
    raw=io.StringIO(newline='');writer=csv.DictWriter(raw,fieldnames=list(values));writer.writeheader();writer.writerow(values)
    header,rows=collector.csv_rows(raw.getvalue().encode());out=io.StringIO(newline='');omitted=io.StringIO()
    result=collector.write_compact(header,rows,table,provenance,out,omitted)
    row=next(csv.DictReader(io.StringIO(out.getvalue(),newline='')))
    for key,value in values.items():
        if key not in table['omit_fields']:assert row[key]==value
    checks.append('Every retained numeric/boolean/empty/nonfinite-looking string, alias, split route, nested JSON, Unicode and newline cell is exact')
    details=[json.loads(v) for v in omitted.getvalue().splitlines()]
    for detail in details:
        text=values[detail['field']]
        assert detail['cell_utf8_bytes']==len(text.encode()) and detail['cell_sha256']==hashlib.sha256(text.encode()).hexdigest()
        assert detail['row_key']=={k:values[k] for k in table['row_key']}
        assert detail['schema_sha256'] in result['omitted_schemas']
    checks.append('Three omissions preserve exact decoded UTF8 hashes, row identities and resolvable schema IDs')
    assert len(row)==len(values)-3+7 and result['rows']==1 and result['omission_records']==3
    checks.append('No undeclared field loss or row expansion in the independent fixture')
    data=dict(status='PASS_BOUNDED_SOURCE_AND_MODEL_FREE_REVIEW',reviewer='s6_components',checks=checks,
        reproduced_original_checks=31,additional_fixture_cells=len(values),original_fixture_receipt=b,
        held_sources=prior['sources'],review_sources=[bind(__file__),bind(Path(__file__).with_name('README_S6C_SCORE_TABLES_COMPONENT_REVIEW_V1.md'))],
        actual_score_exports=0,models=0,scoring=0,
        conclusions=['Exact-buffer authority/CSV parsing and declared omission provenance are consistent.',
            'Separate namespaces preserve overlapping experiments and aliases; no implicit pooling, aggregation or score recomputation.',
            'copy_intact publishes original certified CSV bytes; compact_rows preserves every retained CSV cell string.',
            'Draft catalog cannot export; final scope/case coverage remains the caller-supplied explicit score authority scope.'],
        limitations=['No actual full table payloads or later approved export specification reviewed.',
            'Source size admission checks the declared bounded binding; a changed oversized on-disk file is rejected after read, not an enforced streaming allocation cap.',
            'Status/schema and pointer identity are caller-pinned; the collector is not an independent scientific scorer or a general schema allowlist.',
            'Source tables are not rescanned at closure because exported values came from their certified original buffers; small authorities/spec are rechecked.',
            'Partially written output is preserved on failure and cannot be reused as a completed collection.'])
    target=REPORT/'independent_review/SCORE_TABLES_COMPONENT_REVIEW_V1.json'
    with target.open('xb') as f:f.write((json.dumps(data,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps(bind(target)))


if __name__=='__main__':main()
