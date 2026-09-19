"""Describe original-setting neural/legacy-label parity. README_S6B_R0_FEATURE_PARITY.md."""
from __future__ import annotations
import argparse
import json
import numpy as np
from s6b_common import *


def audit(epoch,panel,output):
    source_index=REPORT/'INPUT_INDEX.json';items=read(source_index)['rows']
    ids=set(read(REPORT/'design/CHALLENGE_PANEL.json')['case_ids']) if panel=='challenge' else {r['case_id'] for r in items}
    rows=[];missing=[]
    for r in items:
        if r['case_id'] not in ids:continue
        ep=PAYLOAD/epoch/'neural/R0'/r['case_id']/r['stream']/'evidence.json'
        pp=REPORT/epoch/'predictions/B36'/r['case_id']/(r['stream']+'.json')
        if not ep.exists() or not pp.exists():missing.append(dict(case_id=r['case_id'],stream=r['stream']));continue
        old=read(r['baseline_features']['path'])['features'];e=read(ep);new=e['features'];prediction=read(pp)
        bind(r['baseline_features']['path'],r['baseline_features']['sha256']);bind(r['baseline_vectors']['path'],r['baseline_vectors']['sha256'])
        bind(e['vectors']['path'],e['vectors']['sha256'])
        a=np.load(r['baseline_vectors']['path'],allow_pickle=False)['vectors'];b=np.load(e['vectors']['path'],allow_pickle=False)['vectors']
        finite=bool(np.isfinite(a).all() and np.isfinite(b).all())
        spans=len(old)==len(new) and all(all(o[k]==n[k] for k in ('source_start_sec','source_end_sec','speech','overlap')) for o,n in zip(old,new))
        expected=[f['native_anonymous_label'] for f in old];actual=[d['anonymous_label'] for d in prediction['decisions']]
        labels=len(expected)==len(actual) and expected==actual
        same_shape=a.shape==b.shape
        rows.append(dict(case_id=r['case_id'],stream=r['stream'],features=len(old),same_spans_and_flags=spans,
            finite=finite,same_shape=same_shape,vectors_bit_exact=bool(same_shape and np.array_equal(a,b)),
            maximum_absolute_vector_difference=float(np.max(np.abs(a-b))) if same_shape and a.size else 0. if same_shape else None,
            legacy_anonymous_labels_equal=labels,legacy_label_differences=sum(x!=y for x,y in zip(expected,actual))+abs(len(expected)-len(actual)),
            evidence=bind(ep),prediction=bind(pp)))
    semantic=all(r['same_spans_and_flags'] and r['finite'] and r['same_shape'] and r['legacy_anonymous_labels_equal'] for r in rows)
    result=dict(status=('PASS_SEMANTIC_WITH_NUMERICAL_DIFFERENCES' if semantic else 'DIFFERENCES_REQUIRE_REVIEW') if not missing else 'PARTIAL',
        panel=panel,outputs=len(rows),requested=len(ids)*2,features=sum(r['features'] for r in rows),missing=missing,
        same_spans_outputs=sum(r['same_spans_and_flags'] for r in rows),bit_exact_vector_outputs=sum(r['vectors_bit_exact'] for r in rows),
        legacy_label_equal_outputs=sum(r['legacy_anonymous_labels_equal'] for r in rows),
        legacy_label_differences=sum(r['legacy_label_differences'] for r in rows),
        maximum_absolute_vector_difference=max((r['maximum_absolute_vector_difference'] or 0 for r in rows),default=None),
        interpretation='Compare newly executed R0 vectors with accepted S6A journal-derived vectors. Floating-point values are not assumed bit-identical. Exact spans/flags and actual legacy anonymous decisions are checked separately. B00/B36 transcript attribution still differs by scheduler/expiry convention; lexical parity is separately scored.',
        source_index=bind(source_index),code=bind(__file__),rows=rows)
    target=REPORT/output
    if target.exists():raise ValueError('Preserve prior audit; choose a new output filename')
    save(target,result)
    return {k:v for k,v in result.items() if k not in ('rows','missing','source_index','code','interpretation')}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--epoch',default='epoch2');p.add_argument('--panel',choices=('challenge','all'),default='challenge');p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(audit(a.epoch,a.panel,a.output),indent=2))
