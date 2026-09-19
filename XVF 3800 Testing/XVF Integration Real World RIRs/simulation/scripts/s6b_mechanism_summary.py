"""Compact a completed mechanism audit; see README_S6B_MECHANISM_SUMMARY.md."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def binding(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def read_bound(value):
    observed = binding(value['path'])
    if observed != value:
        raise ValueError('Changed input binding: ' + value['path'])
    return json.loads(Path(value['path']).read_text(encoding='utf-8-sig'))


def key(row):
    return row['profile_id'], row['case_id'], row['stream']


def summarize_group(rows):
    instruments = [r['tracker'] for r in rows if r['tracker']['status'] == 'PASS']
    unknown = sum(r['unknown_decisions'] for r in instruments)
    decisions = sum(r['decision_count'] for r in instruments)
    operations = sum((Counter(r['all_actual_operations']) for r in instruments), Counter())
    return dict(
        outputs=len(rows), instrumented_outputs=len(instruments), decisions=decisions,
        unknown_decisions=unknown,
        unknown_observation_fraction=unknown / decisions if decisions else None,
        cap_rejections=operations['track_capacity_rejection'],
        cap_rejection_outputs=sum(r['operations']['track_capacity_rejection'] > 0 for r in instruments),
        maximum_final_tracks=max((r['final_track_count'] for r in instruments), default=None),
        cue_effective_positive_credit=sum(r['cue_effective_positive_credit'] for r in instruments),
        nonzero_spatial_score_decisions=sum(r['nonzero_spatial_score_decisions'] for r in instruments),
        cue_valid_but_zero_credit=sum(r['cue_valid_but_zero_credit'] for r in instruments),
        cue_unavailable_or_zero_credit=sum(r['cue_unavailable_or_zero_credit'] for r in instruments),
        cue_reasons=dict(sum((Counter(r['cue_reasons']) for r in instruments), Counter())),
        operations=dict(operations),
        revision_classes=dict(sum((Counter(r['revision_classes']) for r in instruments), Counter())),
        transcript_revision_scopes=dict(sum((Counter(r['transcript_revision_scopes']) for r in instruments), Counter())),
        activation_outputs=dict(sum((Counter(k for k, v in r['activated'].items() if v) for r in instruments), Counter())),
        instrumentation_scope='Actual frozen tracker counters; historical control without instrumentation remains unavailable, not zero activity.',
    )


def build(args):
    audit_binding = binding(args.audit)
    audit = read_bound(audit_binding)
    if audit['status'] != 'PASS' or not audit['index_population_complete']:
        raise ValueError('A passing complete-index audit is required')
    if audit['neural_calls'] != 0 or audit['hardware_invocations'] != 0:
        raise ValueError('Unexpected inference/hardware audit scope')
    index = read_bound(audit['prediction_or_native_index'])
    spec = read_bound(audit['execution_manifest'])
    if binding(audit['auditor_code']['path']) != audit['auditor_code']:
        raise ValueError('Auditor source changed; select its preserved exact source before exporting')
    native_inputs = read_bound(spec['input_index'])
    if index['status'] != 'COMPLETE':
        raise ValueError('Prediction index is not complete')
    profiles, cases = index['profiles'], index['case_ids']
    if len(profiles) != len(set(profiles)) or len(cases) != len(set(cases)):
        raise ValueError('Duplicate declared profile or scene')
    if len(profiles) != args.expect_profiles or len(cases) != args.expect_scenes:
        raise ValueError('Unexpected declared population')
    canonical_cases = {r['case_id'] for r in native_inputs['rows']}
    if not set(cases) <= canonical_cases:
        raise ValueError('Index contains a scene outside the canonical input bank')
    if args.expect_scenes == len(canonical_cases) and set(cases) != canonical_cases:
        raise ValueError('Full-bank claim does not preserve canonical cases')
    expected = {(p, c, t) for p in profiles for c in cases for t in ('O0', 'O1')}
    for label, rows in (('index', index['rows']), ('audit', audit['rows'])):
        observed = [key(r) for r in rows]
        if len(observed) != len(set(observed)) or set(observed) != expected:
            raise ValueError('Incomplete or duplicate exact ' + label + ' cell grid')
    if audit['audited_prediction_or_canonical_outputs'] != len(expected):
        raise ValueError('Audit output headline disagrees with exact cells')
    if len(audit['unique_upstream_jobs']) != args.expect_native_jobs:
        raise ValueError('Unexpected deduplicated native-job population')
    if any(r['tracker']['status'] not in ('PASS', 'NOT_INSTRUMENTED') for r in audit['rows']):
        raise ValueError('Unsuccessful tracker audit row')
    if any(r['status'] != 'PASS' for r in audit['unique_upstream_jobs'].values()):
        raise ValueError('Unsuccessful native audit row')
    by_profile = {}
    for pid in sorted(profiles):
        selected = [r for r in audit['rows'] if r['profile_id'] == pid]
        derived = summarize_group(selected)
        source = audit['summary']['by_profile'][pid]
        for field in ('outputs', 'instrumented_outputs', 'decisions', 'unknown_decisions', 'operations',
                      'cue_reasons', 'revision_classes', 'transcript_revision_scopes', 'activation_outputs'):
            if derived[field] != source[field]:
                raise ValueError('Derived aggregate differs from full audit: ' + pid + '/' + field)
        derived['by_tap'] = {t: summarize_group([r for r in selected if r['stream'] == t]) for t in ('O0', 'O1')}
        by_profile[pid] = derived
    compact = {k: deepcopy(v) for k, v in audit.items() if k not in ('rows', 'unique_upstream_jobs', 'summary')}
    compact.update(
        schema='jp_s6b_compact_mechanism_summary_v1', created_utc=datetime.now(timezone.utc).isoformat(),
        full_audit=audit_binding, exporter_code=binding(__file__),
        input_bank_binding=spec['input_index'],
        exact_grid_checks=dict(status='PASS', profiles=len(profiles), scenes=len(cases), taps=['O0', 'O1'],
                               predictions=len(expected), unique_native_jobs=args.expect_native_jobs),
        by_profile=by_profile,
        deduplicated_native_counts=audit['summary']['deduplicated_native_counts'],
        deduplicated_N04_endpoint_reasons=audit['summary']['deduplicated_N04_endpoint_reasons'],
        interpretation=[
            'Activity is not benefit. Score/reference metrics and finalist selection remain separate.',
            'Unknown fractions count decisions, not sole-speech samples, turns or words.',
            'Positive cue credit and nonzero location scores do not prove the final label changed.',
            'Track-capacity rejection is an observable bounded-gallery operation, not proof of a real additional speaker.',
            'Dormant reactivation is a tracker operation, not a reference-scored successful returning speaker.',
            'Tracker forward revisions and transcript revision scopes are different event populations.',
            'A current missing-cue comparison can retain earlier cue state; it is not a disabled-cue counterfactual.',
            'Native costs/calls are deduplicated by recipe job; shared trackers do not multiply native execution.',
        ],
    )
    output = Path(args.output).resolve()
    md = output.with_suffix('.md')
    if output == Path(args.audit).resolve() or output.exists() or md.exists():
        raise ValueError('Use fresh output names; preserve prior evidence')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as f:
        json.dump(compact, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    lines = [
        '# Full R0 mechanism audit', '',
        f"PASS: {len(expected):,} actual predictions, {len(profiles)} profiles, {len(cases)} scenes, both taps; {args.expect_native_jobs} unique native jobs.", '',
        'All exact scene/profile/tap cells and original audit counters match. This report is model-free and uses no reference identity or geometry. It reports activation, not measured benefit.', '',
        '| Profile | Decisions | Unknown observations | Capacity rejects / affected outputs | Positive cue observations | Nonzero location-score observations | Forward tracker revisions |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for pid, r in by_profile.items():
        if not r['instrumented_outputs']:
            lines.append(f'| {pid} | Uninstrumented | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable |')
        else:
            lines.append(f"| {pid} | {r['decisions']} | {r['unknown_decisions']} | {r['cap_rejections']} / {r['cap_rejection_outputs']} | {r['cue_effective_positive_credit']} | {r['nonzero_spatial_score_decisions']} | {r['operations'].get('label_revision', 0)} |")
    lines += ['', 'The JSON preserves separate O0/O1 counters, cue rejection reasons, individual mechanism operations and transcript revision scopes. A zero count means no observed activation in this population. It does not mean an absent implementation or demonstrated ineffectiveness.', '',
              'Structural track merge and split are absent; graph recomputation and forward association revision are distinct operations. N04 and N05 are disabled in the R0 recipe and require the full challenge audit for their actual activity.', '',
              'Source audit SHA-256: `' + audit_binding['sha256'] + '`. Compact JSON SHA-256: `' + binding(output)['sha256'] + '`.', '',
              'Reproduction commands and exact population arguments are in `simulation/scripts/README_S6B_MECHANISM_SUMMARY.md`.']
    with md.open('x', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return dict(status='PASS', grid=compact['exact_grid_checks'], outputs=[binding(output), binding(md)])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expect-profiles', required=True, type=int)
    parser.add_argument('--expect-scenes', required=True, type=int)
    parser.add_argument('--expect-native-jobs', required=True, type=int)
    print(json.dumps(build(parser.parse_args()), indent=2))
