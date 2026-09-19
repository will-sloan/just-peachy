"""Independent compact family results audit; README_TEST_S6C_FAMILY_RESULTS_COMPONENT_REVIEW.md."""
from collections import Counter
import csv,hashlib,io,json,math
from pathlib import Path
import s6c_family_native_results as helper

REPORT=helper.core.REPORT

def bind(path,raw=None):
    p=Path(path).resolve();raw=p.read_bytes() if raw is None else raw
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(b):
    raw=Path(b['path']).read_bytes();assert bind(b['path'],raw)==b
    return json.loads(raw)
def table(b):
    raw=Path(b['path']).read_bytes();assert bind(b['path'],raw)==b
    return list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
def key(r):return r['profile_id'],r['stream'],r['identity_tap'],r['case_id']
def number(v):
    if v in ('',None):return None
    value=float(v);assert math.isfinite(value);return value
def same(a,b):return a is None and b is None or a is not None and b is not None and abs(a-b)<=1e-8

def main():
    rb=bind(REPORT/'family_gate6_native_results_v1/FAMILY_NATIVE_REVIEW_RECEIPT.json')
    assert rb['sha256']=='67d1205cd5af27a47c13f1bd0563b3fe7656ad733cd8ef41c456e3faf318ccbf'
    result=read(rb);assert bind(result['source']['path'])==result['source'] and bind(result['readme']['path'])==result['readme']
    assert helper.fixtures()==result['fixtures']==dict(status='PASS',checks=4)
    native=read(result['native_core']);cached=read(result['cached_panel_core'])
    assert native['status']==cached['status']=='COMPLETE_REQUESTED_INDEX' and native['unscored']==cached['unscored']==0
    nsb,nlb,csb=result['source_tables']
    assert nsb in native['tables'] and nlb in native['tables'] and csb in cached['tables']
    ns,nl,cs=table(nsb),table(nlb),table(csb);wanted={(p,t,t,c) for p in result['profiles'] for t in ('O0','O1') for c in result['cases']}
    selected=[r for r in cs if key(r) in wanted]
    assert len(ns)==len(nl)==len(selected)==len(wanted)==192
    assert all(len({key(r) for r in rows})==192 and {key(r) for r in rows}==wanted for rows in (ns,nl,selected))
    lookup={key(r):r for r in selected};checks=0
    cb=next(b for b in result['artifacts'] if Path(b['path']).name=='PAIRED_NATIVE_VS_CACHED_CELLS.csv');pairs=table(cb)
    assert len(pairs)==len({key(r) for r in pairs})==192
    pair_lookup={key(r):r for r in pairs}
    metrics=('word_errors','cp_first_final_errors','cp_latest_revised_errors','cp_first_display_label_final_words_errors','unknown_samples','false_merge_samples','return_consistent','return_inconsistent','return_unknown','embedding_calls','segmentation_calls')
    for a in ns:
        b=lookup[key(a)];out=pair_lookup[key(a)]
        for field in ('population','word_reference_words','cp_latest_revised_reference_words','source_turns','sole_active_samples','identity_tap'):
            assert a[field]==b[field];checks+=1
        assert out['normalized_final_text_equal']==str(a['normalized_final_text']==b['normalized_final_text']);checks+=1
        for metric in metrics:
            av,bv=number(a[metric]),number(b[metric]);delta=av-bv if av is not None and bv is not None else None
            assert same(number(out['native_'+metric]),av) and same(number(out['cached_'+metric]),bv) and same(number(out['native_minus_cached_'+metric]),delta);checks+=1
    assert len(result['summary'])==len({(r['profile_id'],r['stream']) for r in result['summary']})==32
    for row in result['summary']:
        pid,tap=row['profile_id'],row['stream'];life=[r for r in nl if r['profile_id']==pid and r['stream']==tap];scenes=[r for r in ns if r['profile_id']==pid and r['stream']==tap]
        assert len(life)==len(scenes)==row['cells']==6
        counts=Counter()
        for r in life:counts.update(json.loads(r['lineage_counts']))
        assert dict(counts)==row['lineage_counts'];checks+=1
        expected=dict(actual_decisions=sum(int(r['decisions']) for r in life),peak_live=max(int(r['peak_live']) for r in life),peak_archive=max(int(r['peak_archive']) for r in life),
            final_retirements_sum=sum(int(r['final_cumulative_retirements']) for r in life),final_lifetime_ids_sum=sum(int(r['final_lifetime_external_ids']) for r in life),
            blocked_unique_evidence_sec=sum(float(r['blocked_unique_evidence_sec']) for r in life),actual_embedding_calls=sum(int(r['embedding_calls']) for r in scenes),
            normalized_text_changed_cells=sum(r['normalized_final_text']!=lookup[key(r)]['normalized_final_text'] for r in scenes))
        for k,v in expected.items():assert same(row[k],v);checks+=1
        for metric in ('word_errors','cp_first_final_errors','cp_latest_revised_errors','cp_first_display_label_final_words_errors','unknown_samples','embedding_calls'):
            vals=[number(pair_lookup[key(r)]['native_minus_cached_'+metric]) for r in scenes];valid=[v for v in vals if v is not None]
            assert row[metric+'_paired_cells']==len(valid) and row[metric+'_changed_cells']==sum(v!=0 for v in valid) and same(row['native_minus_cached_'+metric],sum(valid));checks+=1
    for artifact in result['artifacts']:assert bind(artifact['path'])==artifact
    data=dict(status='PASS_192_COMPACT_TABLE_NUMERICAL_REVIEW',source_receipt=rb,source_tables=result['source_tables'],output_artifacts=result['artifacts'],
        compared_fields=checks,independent_cells=192,profile_tap_summaries=32,original_pure_fixtures=4,
        sources=[result['source'],result['readme'],bind(__file__),bind(Path(__file__).with_name('README_TEST_S6C_FAMILY_RESULTS_COMPONENT_REVIEW.md'))],
        findings=['Exact unique native/cached192 key grids and per-cell reference/support denominators match.',
            'All retained paired word/cp/Unknown/return/call deltas and32 lineage/lifecycle summaries reproduce from exact scorer CSV buffers.',
            'Retained pending/quarantine/shadow events establish only their logged branch activity; missing release/promotion cannot be claimed executed.',
            'These same six scenes are integration/reachability evidence and are not added to independent full-bank accuracy denominators.'],
        scope='No raw events, models, audio, vectors or score recalculation. Source CSV values are inherited from completed core scorers; this review checks the descriptive collector arithmetic and population semantics, not native clock/vector parity.')
    output=REPORT/'independent_review/FAMILY_RESULTS_COMPONENT_REVIEW_V1.json'
    with output.open('xb') as f:f.write((json.dumps(data,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps(bind(output)))

if __name__=='__main__':main()
