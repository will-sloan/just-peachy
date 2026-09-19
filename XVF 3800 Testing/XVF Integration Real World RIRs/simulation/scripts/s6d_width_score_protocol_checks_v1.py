"""Tiny fake-scorer protocol fixtures on G; README_S6D_WIDTH_SCORE_PROTOCOL.md."""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import time
from unittest.mock import patch
import psutil
import s6d_width_score_protocol_v1 as P


def setup(root):
    root.mkdir(parents=True)
    helper = root / 'fake_scorer.txt'; helper.write_text('Synthetic fixture, no executable model/scorer code.\n', encoding='utf-8')
    auth = root / 'fake_admission.json'; P.save(auth, dict(scope='SYNTHETIC_FIXTURE_ONLY_NO_EXPERIMENT_AUTHORITY'), exclusive=True)
    support = root / 'fake_support.json'; P.save(support, dict(synthetic=True), exclusive=True)
    helper_binding, support_binding = P.bind(helper), P.bind(support)
    rows, cells = [], []
    for case in ('X', 'Y'):
        path = root / (case + '_fake_prediction.json'); P.save(path, dict(synthetic_case=case), exclusive=True)
        rows.append(dict(candidate_id='S6D_C079_W02', stream='O0', identity_tap='O0', case_id=case, result=P.bind(path), status='COMPLETE'))
        cells.append(dict(candidate_id='S6D_C079_W02', stream='O0', identity_tap='O0', case_id=case, population='SYNTHETIC_POPULATION',
                          expected_prediction_path=str(path), support=support_binding))
    control = root / 'fake_control_score.json'; P.save(control, dict(synthetic_control=True), exclusive=True)
    index = root / 'fake_prediction_index.json'; P.save(index, dict(rows=rows, jobs=['SYNTHETIC_JOB']), exclusive=True)
    plan = dict(new_cells=cells, controls=[dict(candidate_id='C079', case_id='X', stream='O0', population='SYNTHETIC_POPULATION', score=P.bind(control))],
                adapter_sources=[helper_binding], scorer_codes=[], packages={}, bank=support_binding, diagnostics_context=support_binding,
                populations_per_route={'SYNTHETIC_POPULATION': 2}, analysis_report_root=str(root / 'report'), bulk_score_payload_root=str(root / 'scores'))
    plan_path = root / 'fake_plan.json'; P.save(plan_path, plan, exclusive=True)
    contract = P.make_contract(plan, P.bind(plan_path), [P.bind(index)]); contract['admission'] = P.bind(auth)
    owner = dict(run_id='synthetic_run', job_id='synthetic_job', child_run_id='synthetic_child', pid=os.getpid(), creation_time=psutil.Process().create_time())
    paths = {name: root / 'protocol' / (name + '.json') for name in ('heartbeat', 'completion', 'stop')}
    return contract, owner, paths


def score_value(expected):
    cell = expected['cell']
    return dict(schema='jp_s6c_core_analysis.v3', profile_id=cell['candidate_id'], case_id=cell['case_id'], stream=cell['stream'], identity_tap=cell['identity_tap'],
        population=cell['population'], analysis_identity=expected['identity'], analysis_key=expected['analysis_key'],
        text_metrics={name: {'synthetic': True} for name in ('first_final', 'latest_revised', 'first_display_label_final_words')}, turns=[], regions=[], lifecycle={})


def write_csv(path, rows):
    with path.open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, list(dict.fromkeys(k for row in rows for k in row)))
        writer.writeheader(); writer.writerows(rows)


def fake_scorer(contract, corrupt=None):
    report, plan = contract['report'], contract['plan']
    report.mkdir(); Path(plan['bulk_score_payload_root']).mkdir()
    for expected in contract['new'].values():
        value = score_value(expected)
        if corrupt == 'score_identity':
            value['analysis_key'] = 'wrong'
        P.save(expected['path'], value, exclusive=True)
        if corrupt == 'partial_raise':
            raise RuntimeError('Synthetic scorer interrupted after one score')
    coverage, scenes = [], []
    for row_key, expected in contract['new'].items():
        cell = expected['cell']
        coverage.append(dict(candidate_id=row_key[0], stream=row_key[1], case_id=row_key[2], status='SCORED', raw_words_invariant=True, result=json.dumps(P.bind(expected['path']))))
        scenes.append(dict(profile_id=row_key[0], stream=row_key[1], identity_tap=row_key[1], case_id=row_key[2], population=cell['population']))
    for row_key, control in contract['controls'].items():
        if corrupt != 'missing_control':
            coverage.append(dict(candidate_id=row_key[0], stream=row_key[1], case_id=row_key[2], status='REUSED_EXACT_BOUND_SCORER_RESULT', raw_words_invariant='', result=json.dumps(control['score'])))
        scenes.append(dict(profile_id=row_key[0], stream=row_key[1], identity_tap=row_key[1], case_id=row_key[2], population=control['population']))
    if corrupt == 'duplicate_coverage':
        coverage.append(coverage[0])
    write_csv(report / 'COVERAGE.csv', coverage)
    write_csv(report / 'SCENE_RESULTS.csv', scenes)
    for name in P.TABLES:
        if name not in ('COVERAGE.csv', 'SCENE_RESULTS.csv'):
            write_csv(report / name, [{'fixture': True}])
    for name in P.AGGREGATES:
        P.save(report / name, [dict(fixture=True)], exclusive=True)
    receipt = dict(schema='s6d-width-scoring-receipt.v1', status='COMPLETE_BOUNDED_MATRIX_SCORING', adapter_plan=contract['plan_binding'], prediction_indices=contract['indices'],
        scored_new_cells=len(contract['new']), reused_exact_control_cells=len(contract['controls']), total_scored_cells=len(contract['new']) + len(contract['controls']),
        raw_word_invariance_cells=len(contract['new']), population_counts_per_route=plan['populations_per_route'], scorer_codes=plan['scorer_codes'], diagnostic_context=plan['diagnostics_context'],
        diagnostics_are_only_width25=True, model_calls=0, hardware_calls=0, native_confirmation_required_before_retention=True,
        tables=[P.bind(report / name) for name in P.TABLES], other_artifacts=[P.bind(report / name) for name in P.AGGREGATES])
    if corrupt == 'receipt_count':
        receipt['total_scored_cells'] = 999
    P.save(report / 'SCORING_RECEIPT.json', receipt, exclusive=True)
    if corrupt == 'artifact_changed':
        (report / P.AGGREGATES[0]).write_text('[]', encoding='utf-8')


def check(output_root):
    output_root = Path(output_root).resolve()
    if output_root.drive.upper() != 'G:' or output_root.exists():
        raise ValueError('Fresh wholly-G fixture root required')
    output_root.mkdir(parents=True)
    checks = {}
    modes = ('success', 'score_identity', 'receipt_count', 'missing_control', 'duplicate_coverage', 'artifact_changed', 'partial_raise',
             'admission_changed', 'STOP_during_scorer', 'wrong_owner_STOP', 'STOP_after_join', 'STOP_before_publish')
    for mode in modes:
        contract, owner, paths = setup(output_root / mode)
        admission_binding = dict(contract['admission'])
        original_close, original_save = P.Observer.close, P.save
        def recheck(checkpoint):
            checkpoint(); P.verify(admission_binding, checkpoint)
        def invoke():
            if mode in ('STOP_during_scorer', 'wrong_owner_STOP'):
                request = dict(owner, reason=mode)
                if mode == 'wrong_owner_STOP':
                    request['child_run_id'] = 'another_child'
                original_save(paths['stop'], request, exclusive=True)
                if mode == 'STOP_during_scorer':
                    time.sleep(1.)  # Actual observer interrupt_main; no real scorer/model.
            fake_scorer(contract, mode)
            if mode == 'admission_changed':
                Path(admission_binding['path']).write_text('{}', encoding='utf-8')
        def close_hook(observer):
            original_close(observer)
            if mode == 'STOP_after_join':
                original_save(paths['stop'], dict(owner, reason=mode), exclusive=True)
        def save_hook(path, value, **kwargs):
            if mode == 'STOP_before_publish' and Path(path) == paths['completion']:
                original_save(paths['stop'], dict(owner, reason=mode), exclusive=True)
            return original_save(path, value, **kwargs)
        with patch.object(P.Observer, 'close', close_hook), patch.object(P, 'save', save_hook):
            result = P.run_protocol(contract, owner, paths, invoke, recheck)
        should_complete = mode in ('success', 'wrong_owner_STOP')
        checks[mode + '_completion_semantics'] = (result['status'] == 'COMPLETE') == should_complete and paths['completion'].exists() == should_complete
        checks[mode + '_observer_closed'] = result['protocol_observer_closed']
        if mode == 'success':
            proof = P.read(paths['completion'])
            checks['completion_binds_admission_and_scorer'] = proof['admission'] == admission_binding and proof['scorer'] == contract['plan']['adapter_sources'][0]
            checks['exact_scientific_coverage_and_aggregates'] = proof['semantic_checks']['exact_coverage_cells'] == 3 and proof['semantic_checks']['bound_aggregate_artifacts'] == 15
        if mode.startswith('STOP_'):
            checks[mode + '_matched_stop_recorded'] = result['stop_requested']
    contract, owner, paths = setup(output_root / 'observer_only')
    observer = P.Observer(owner, paths['heartbeat'], paths['stop'], contract)
    first = next(iter(contract['new'].values())); first['path'].parent.mkdir(parents=True)
    first['path'].write_text('{', encoding='utf-8'); observer.scan()
    checks['partial_score_is_not_progress'] = not observer.committed
    first['path'].write_text(json.dumps(score_value(first)), encoding='utf-8'); observer.scan()
    checks['complete_identity_bound_score_is_progress'] = len(observer.committed) == 1
    observer.publish(); observer.publish(); observer.scan()
    checks['heartbeat_and_repeat_scan_do_not_fake_progress'] = len(observer.committed) == 1
    for field in ('run_id', 'job_id', 'child_run_id', 'pid', 'creation_time'):
        bad = dict(owner); bad[field] = bad[field] + 1 if isinstance(bad[field], (float, int)) else 'wrong'
        checks['reject_stop_' + field] = not P.same_owner(bad, owner)
    checks['malformed_creation_time_not_owner'] = not P.same_owner(dict(owner, creation_time=None), owner)
    observer.committed.clear(); count = []
    real_read_score = P.read_score
    def closing_read(expected, checkpoint=None):
        value = real_read_score(expected, checkpoint); count.append(1); observer.closed.set(); return value
    with patch.object(P, 'read_score', closing_read):
        observer.scan()
    checks['scan_stops_between_declared_entries'] = len(count) == 1
    invalid_observer = P.Observer(owner, paths['heartbeat'], paths['stop'], contract)
    paths['stop'].parent.mkdir(exist_ok=True); paths['stop'].write_text('{', encoding='utf-8')
    invalid_observer.check_stop()
    checks['partial_STOP_waits_boundedly_during_run'] = not invalid_observer.stop_requested and invalid_observer.invalid_stop_since is not None
    try:
        invalid_observer.check_stop(final=True)
    except RuntimeError:
        checks['unresolved_final_STOP_fails_closed'] = True
    else:
        checks['unresolved_final_STOP_fails_closed'] = False
    atomic_root = output_root / 'atomic'; atomic_root.mkdir(); calls = []
    original_replace = P.os.replace
    def retry(src, dst):
        calls.append(str(src))
        if len(calls) <= 2:
            raise PermissionError('Synthetic sharing refusal')
        return original_replace(src, dst)
    with patch.object(P.os, 'replace', retry):
        P.save(atomic_root / 'transient.json', {'complete': True})
    checks['transient_atomic_replace_retried'] = len(calls) == 3 and P.read(atomic_root / 'transient.json')['complete']
    with patch.object(P.os, 'replace', side_effect=PermissionError('Persistent synthetic sharing refusal')) as operation:
        try:
            P.save(atomic_root / 'persistent.json', {'complete': True})
        except PermissionError:
            checks['persistent_atomic_replace_fails_closed'] = operation.call_count == 6 and not (atomic_root / 'persistent.json').exists()
        else:
            checks['persistent_atomic_replace_fails_closed'] = False
    checks['failed_publish_retains_named_temporary'] = len(list(atomic_root.glob('.persistent.json.*.tmp'))) == 1
    contract, owner, paths = setup(output_root / 'fake_clock_finalization')
    fake_scorer(contract)
    finalizer = P.Observer(owner, paths['heartbeat'], paths['stop'], contract)
    finalizer.scan(); initial_count = len(finalizer.committed); finalizer.closed.set()
    clock = {'now': 0.}
    with patch.object(P.time, 'monotonic', lambda: clock['now']):
        finalizer.begin_finalization(); first_heartbeat = P.bind(paths['heartbeat'])
        clock['now'] = 6.; finalizer.checkpoint(); second = P.read(paths['heartbeat'])
        checks['long_finalization_fake_clock_refreshes_heartbeat'] = P.bind(paths['heartbeat']) != first_heartbeat and second['status'] == 'FINALIZING' and second['phase'] == 'FINAL_VALIDATION'
        checks['finalization_liveness_does_not_fake_progress'] = second['progress_count'] == initial_count == 2
        original_admission = dict(contract['admission']); Path(original_admission['path']).write_text('{}', encoding='utf-8')
        clock['now'] = 12.
        try:
            P.verify(original_admission, finalizer.checkpoint)
        except ValueError:
            checks['long_finalization_still_rejects_source_change'] = True
        else:
            checks['long_finalization_still_rejects_source_change'] = False
        P.save(paths['stop'], dict(owner, reason='synthetic late stop'), exclusive=True); clock['now'] = 18.
        try:
            finalizer.checkpoint()
        except RuntimeError:
            checks['long_finalization_still_honors_STOP'] = finalizer.stop_requested
        else:
            checks['long_finalization_still_honors_STOP'] = False
    assert all(checks.values()), {key: value for key, value in checks.items() if not value}
    result = dict(status='PASS_SYNTHETIC_SCORER_PROTOCOL', checks=checks, passed=len(checks), fixture_root=str(output_root),
        fixture_scope='Tiny synthetic score/index/aggregate files only, two fake new cells and one fake control per run. Not a real scoring or matrix replay.',
        hardware_calls=0, real_scoring_calls=0, model_calls=0, sources=[P.bind(__file__), P.bind(P.__file__)])
    P.save(output_root / 'RESULT.json', result, exclusive=True)
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-root', type=Path, required=True)
    args = parser.parse_args()
    check(args.fixture_root)
