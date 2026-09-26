"""Review sealed modeled scores without rerunning metrics. README_SCORING_CLOCK_V2.md."""
import argparse
from datetime import datetime, timezone, timedelta
import math
from pathlib import Path
import shutil
import time

from common import bind, fingerprint, freeze, load, verify
from metric_process import exact_process, identity, pin
from metrics import canonical
from scoring_bank_v2 import admit, code_bindings as scoring_code, prediction, verify_bindings, writer_lock
from scoring_report import report

HERE = Path(__file__).resolve().parent
GIB = 1024**3
OUTPUT_LIMIT = 8*1024**2
COUNT_KEYS = ('errors', 'words', 'substitutions', 'deletions', 'insertions')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value):
    return type(value) is int and value >= 0


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def edit_counts(value, words, hypothesis_words=None):
    require(isinstance(value, dict) and all(integer(value.get(k)) for k in COUNT_KEYS), 'Invalid edit counts')
    require(value['words'] == words and value['errors'] == sum(value[k] for k in COUNT_KEYS[2:]), 'Edit denominator/sum differs')
    require(value['substitutions'] + value['deletions'] <= words, 'Edits exceed reference words')
    require(value.get('rate') == (value['errors']/words if words else None), 'Edit rate differs')
    if hypothesis_words is not None:
        require(words - value['deletions'] + value['insertions'] == hypothesis_words, 'Hypothesis word census differs')


def speaker_counts(value, words, hypothesis_words, reference_streams, hypothesis_streams):
    edit_counts(value['cpwer'], words, hypothesis_words)
    mimo = value['mimo']
    if max(reference_streams, hypothesis_streams) > 10:
        require(mimo == dict(status='UNAVAILABLE_ESTABLISHED_IMPLEMENTATION_SPEAKER_LIMIT', value=None), 'MIMO unavailable scope differs')
    elif not reference_streams or not hypothesis_streams:
        require(mimo == dict(status='EXACT_EMPTY_STREAM_COUNTS', value=value['cpwer']), 'Empty-stream MIMO differs')
    else:
        require(mimo['status'] == 'SCORED', 'MIMO status differs')
        edit_counts(mimo['value'], words, hypothesis_words)


def validate_activity(value, truth, pred):
    if pred['activity'] is None:
        require(value == dict(status='UNAVAILABLE_FULL_TRACK_ACTIVITY_NOT_RECORDED', DER=None, JER=None), 'Missing activity became a score')
        return
    if not truth['complete_reference']:
        require(value == dict(status='UNAVAILABLE_INCOMPLETE_REFERENCE', DER=None, JER=None), 'Incomplete reference became activity accuracy')
        return
    has_refs = any(t['activity_ranges_samples_estimated'] for t in truth['turns'])
    require(value['status'] == ('APPROXIMATE_ACTIVITY_ONLY' if has_refs else 'EMPTY_REFERENCE_FALSE_ALARMS'), 'Activity status differs')
    der, jer = value['DER_components'], value['JER_components']
    require(set(der) == {'total', 'correct', 'confusion', 'missed detection', 'false alarm'}
            and set(jer) == {'speaker count', 'speaker error'}, 'Activity component census differs')
    require(all(finite(x) for x in [*der.values(), *jer.values()]), 'Invalid activity components')
    require(math.isclose(der['total'], der['correct'] + der['confusion'] + der['missed detection'], rel_tol=1e-9, abs_tol=1e-9), 'DER total differs')
    require(jer['speaker error'] <= jer['speaker count'] and float(jer['speaker count']).is_integer(), 'JER component bounds differ')
    require(value['DER'] == (sum(der[k] for k in ('missed detection', 'false alarm', 'confusion'))/der['total'] if der['total'] else None), 'DER rate differs')
    require(value['JER'] == (jer['speaker error']/jer['speaker count'] if jer['speaker count'] else None), 'JER rate differs')
    require(value['collar_parameter_seconds'] == .25 and value['collar_halfwidth_seconds'] == .125
            and value['overlap'] == 'include' and value['mapping'] == 'per-scene Hungarian'
            and value['uem_seconds'] == [0, truth['frames']/16000]
            and value['timing'] == 'existing mapped estimated activity, not phonetic gold', 'Activity evaluation scope differs')


def validate_score(score, truth, pred):
    """Check provenance-derived census and algebra, not optimal metric alignments."""
    fingerprint(score)  # Reject NaN/Infinity anywhere, including nested diagnostics.
    words = sum(len(canonical(t['transcript']).split()) for t in truth['turns'])
    hyps = len(canonical(pred['raw_text']).split())
    kind = truth['reference_class']
    require(pred['job_id'] == truth['job_id'] == score['job_id'] and pred['status'] == score['execution_status'] == 'COMPLETE', 'Metric job/status differs')
    require(score['reference_class'] == kind and score['reference_words'] == words
            and score['audio_seconds'] == truth['frames']/16000 and score['hypothesis_words'] == hyps, 'Metric audio/word denominator differs')
    require(score['integrated_N4_cells'] == 0 and score['tcpwer_status'] == 'UNAVAILABLE_NO_EXACT_REFERENCE_WORD_TIMES'
            and score['naming_metrics_status'] == 'UNAVAILABLE_ACTUAL_WIDGET_VISIBILITY_NOT_RECORDED'
            and score['first_widget_visibility'] == 'UNAVAILABLE_MODELED_METHOD_REPLAY_ONLY', 'Unsupported acceptance/visibility claim')
    require(score['scoring_status'] == ('TARGET_ONLY_NOT_ALL_SPEAKER_ACCURACY' if kind == 'incomplete_ambient_reference' else 'SCORED'), 'Scoring scope differs')
    if kind == 'complete_nonoverlap':
        edit_counts(score['primary_wer'], words, hyps)
        edit_counts(score['raw_wer'], len(' '.join(t['transcript'] for t in truth['turns']).split()), len(pred['raw_text'].split()))
    else:
        require(score['primary_wer'] is None and score['raw_wer'] is None, 'Ordinary WER applied outside nonoverlap scope')
    if kind in ('complete_nonoverlap', 'complete_overlap'):
        refs = len({str(t['identity']) for t in truth['turns']})
        tracks = len({str(s['track']) for s in pred['segments']})
        speaker_counts(score, words, hyps, refs, tracks)
        controls = score['constant_speaker_controls']
        require(controls['all_unknown'] == controls['all_one_name'] and controls['interpretation'] ==
                'Identical permutation-invariant scores; neither control supplies evidence of correctly recognized names', 'Constant-speaker controls differ')
        speaker_counts(controls['all_unknown'], words, hyps, refs, int(bool(pred['segments'])))
    else:
        require(score['cpwer'] is None and score['mimo'] is None and 'constant_speaker_controls' not in score, 'Incomplete reference acquired all-speaker scores')
    if kind == 'empty_control':
        require(words == 0 and score['inserted_words'] == hyps and score['inserted_words_per_minute'] == hyps/(truth['frames']/16000/60), 'Empty insertion denominator differs')
    else:
        require('inserted_words' not in score and 'inserted_words_per_minute' not in score, 'Foreign empty-control metric')
    if kind == 'incomplete_ambient_reference':
        edit_counts(score['target_only_diagnostic'], words, hyps)
    else:
        require('target_only_diagnostic' not in score, 'Foreign target-only metric')
    require(kind in ('complete_nonoverlap', 'complete_overlap', 'empty_control', 'incomplete_ambient_reference'), 'Unknown reference class')
    require(score['activity_support'] == pred['activity_support'], 'Activity provenance differs')
    validate_activity(score['activity'], truth, pred)
    formatting = score['formatting_lexical_preservation']
    require(formatting['status'] == 'ASR_WORD_PRESERVATION_DIAGNOSTIC_NOT_PUNCTUATION_ACCURACY', 'Formatting scope differs')
    total = formatting['totals']; source = {r['utterance_id']: r for r in pred['formatting']}
    require(len(source) == len(pred['formatting']) == total['utterances'] and integer(total['utterances']), 'Formatting utterance census differs')
    fw = sum(len(canonical(r['raw_text']).split()) for r in source.values())
    fh = sum(len(canonical(r['display_text']).split()) for r in source.values())
    edit_counts(dict(total, rate=total['errors']/fw if fw else None), fw, fh)
    changed = formatting['changed_utterances']; seen = set()
    for row in changed:
        uid = row['utterance_id']
        require(uid in source and uid not in seen and row['counts']['errors'] > 0, 'Changed-utterance census differs')
        seen.add(uid); original = source[uid]
        edit_counts(row['counts'], len(canonical(original['raw_text']).split()), len(canonical(original['display_text']).split()))
    require(all(total[k] == sum(r['counts'][k] for r in changed) for k in ('errors', 'substitutions', 'deletions', 'insertions')), 'Formatting diagnostic totals differ')
    # Unchanged rows must really have equal normalized content. This is not a scorer rerun.
    require(all(canonical(r['raw_text']) == canonical(r['display_text']) for uid, r in source.items() if uid not in seen), 'Unreported formatting change')


def owners_closed(workers, required, lookup=exact_process):
    require(isinstance(workers, list) and bool(workers), 'Missing metric worker closure')
    requests = 0; all_owners = set()
    for worker in workers:
        require(worker['all_exact_owners_exited'] is True and worker['pipe_threads_closed'] is True, 'Metric worker/pipe closure incomplete')
        require(integer(worker['requests']) and worker['requests'] > 0, 'Invalid metric request count')
        requests += worker['requests']
        require(worker['owners'] and integer(worker['stderr_bytes']) and integer(worker['stderr_retained_bytes'])
                and worker['stderr_retained_bytes'] <= min(worker['stderr_bytes'], 65536), 'Worker census/stderr bounds differ')
        for owner in worker['owners']:
            key = owner['pid'], owner['create_time']
            require(integer(key[0]) and key[0] > 0 and finite(key[1]) and key not in all_owners, 'Duplicate/invalid exact metric owner')
            all_owners.add(key)
            require(lookup(owner) is None, 'Exact metric worker remains active')
    require(requests == required, 'Metric request denominator differs')


def validate_terminal(result, plan):
    require(result['status'] == 'SCORED_MODELED_BANK_REQUIRES_REVIEW' and result['stop_reason'] is None, 'Only a complete scored bank can pass review')
    require(result['required'] == result['prediction_completed'] == len(result['scores']) == plan['required'], 'Scored bank count differs')
    require(all(type(result[k]) is int and result[k] == 0 for k in
                ('prediction_failed', 'prediction_not_tested', 'metrics_unavailable_for_complete_predictions', 'integrated_N4_cells')), 'Scoring denominators incomplete')
    require(len({b['path'] for b in result['scores']}) == len(result['scores']), 'Duplicate score binding')


def validate_row(value, row, job, truth, pred, method_binding):
    expected = dict(cell_id=row['cell_id'], job_id=job['job_id'], case_id=truth['case_id'], tap=job['tap'],
                    composition=row['composition'], mode=row['contract']['mode'], method_result=method_binding, integrated_N4_cells=0)
    require(all(value[k] == v for k, v in expected.items()), 'Score row/plan/method join differs')
    require(truth['job_id'] == job['job_id'] and truth['frames'] == job['frames'] and truth['tap'] == job['tap'], 'Reference/audio join differs')
    require(value['metric_input_sha256'] == fingerprint(dict(truth=truth, prediction=pred)), 'Metric input digest differs')
    require(finite(value['metric_seconds']) and value['score']['metric_status'] == 'SCORED', 'Unavailable/invalid metric result')
    validate_score(value['score'], truth, pred)


def verify_report(actual, rows, strata, scope):
    expected = report(rows, strata, scope=scope)
    require(fingerprint(actual) == fingerprint(expected), 'Recomputed aggregate/paired report differs')
    return fingerprint(expected)


def code_bindings():
    from review_scoring_bank import code_bindings as original_code
    values=original_code()+scoring_code()
    return list({b['path']:b for b in values}.values())


def guard(output, local, started, seconds):
    require(time.monotonic() - started < seconds, 'Scoring review time budget reached')
    policy = load(local / 'supervision/campaign.json')
    require(datetime.now(timezone.utc) < datetime.fromisoformat(policy['target_utc']) - timedelta(hours=12), 'Packaging reserve reached')
    for drive, floor in (('C:/', 50), ('G:/', 75)):
        require(shutil.disk_usage(drive).free >= floor*GIB + OUTPUT_LIMIT, 'Review drive floor unavailable')
    if output.exists():
        require(sum(p.stat().st_size for p in output.rglob('*') if p.is_file()) < OUTPUT_LIMIT, 'Review output bound reached')


def shared_allowance(local):
    from asr_full_bank import payload_inventory
    inventory = payload_inventory(local)
    policy = load(local / 'supervision/campaign.json')
    require(not inventory['errors'] and inventory['total_logical_bytes'] + 6*GIB + OUTPUT_LIMIT <=
            min(50, policy['resource_policy']['new_payload_allowance_gib'])*GIB, 'Shared review allowance unavailable')
    return inventory


def run(args):
    process = pin(); started = time.monotonic()
    run_root = args.run.resolve(strict=True)
    result_binding = bind(run_root / 'RESULT.json'); result = load(result_binding['path'])
    verify(result['admission']); admission = load(result['admission']['path'])
    require(Path(result['admission']['path']).resolve() == run_root / 'ADMISSION.json', 'Foreign scoring admission')
    require(exact_process(admission['owner']) is None, 'Exact scoring driver is still active')
    verify(admission['plan']); plan = load(admission['plan']['path'])
    local = Path(plan['context']['source_receipt']['path']).parents[2]
    require(not args.output.exists() and args.output.resolve().is_relative_to((local/'n4').resolve()), 'Fresh private N4 output required')
    with writer_lock(local/'n4/metric-scoring.owner.lock'):
        guard(args.output, local, started, args.max_seconds)
        qualification = load(HERE/'SCORING_CLOCK_CHECK_V2.json')
        code = code_bindings()
        require(qualification['status'] == 'PASS_SCORING_CLOCK_DERIVATIVE_DEVELOPMENT_ONLY' and qualification['review_code'] == code, 'Reviewer implementation is not qualified')
        verify_bindings(qualification)
        for binding in code: verify(binding)
        freeze(args.output/'ADMISSION.json', dict(owner=identity(process), result=result_binding, scoring_admission=result['admission'],
            code=code, qualification=bind(HERE/'SCORING_CLOCK_CHECK_V2.json'), max_seconds=args.max_seconds,
            maximum_output_bytes=OUTPUT_LIMIT, cpu_affinity=process.cpu_affinity(), models_loaded=0, integrated_N4_cells=0))
        checked = 0
        try:
            validate_terminal(result, plan); owners_closed(result['workers'], plan['required'])
            known = load(HERE/'SCORING_BANK_IMPLEMENTATION_V1.json')
            require(admission['code'] == scoring_code() == qualification['scoring_code']
                    and admission['qualification'] == bind(HERE/'SCORING_CLOCK_CHECK_V2.json'), 'Scorer implementation differs')
            for key in ('terminal', 'review', 'truth', 'strata', 'environment'): verify(admission[key])
            bundle = admit(Path(admission['terminal']['path']).parent, Path(admission['review']['path']))
            require(bundle['terminal_binding'] == admission['terminal'] and bundle['terminal']['plan'] == admission['plan'], 'Scorer/method plan binding differs')
            require(bundle['terminal']['status'] == 'COLLECTED_METHOD_BANK_REQUIRES_REVIEW', 'Incomplete predictions')
            require(admission['environment'] == known['environment'], 'Foreign metric environment')
            from probe_integrated_scoring import verify_environment
            files = verify_environment(admission['environment'])
            require(files == admission['environment_files_verified'] == known['environment_files_verified'], 'Metric environment file census differs')
            inventory = shared_allowance(local)
            prep_binding = load(HERE/'PREPARATION_V2_CHECK.json')['preparation']; verify(prep_binding); prep = load(prep_binding['path'])
            require(admission['truth'] == next(b for b in prep['inputs'] if Path(b['path']).name == 'EVALUATOR_TRUTH.json')
                    and admission['strata'] == next(b for b in prep['outputs'] if Path(b['path']).name == 'EVALUATOR_STRATA.json')
                    and plan['context']['manifest'] == next(b for b in prep['outputs'] if Path(b['path']).name == 'AUDIO_ONLY_480.json'), 'Evaluator preparation differs')
            truth_doc = load(admission['truth']['path']); strata_doc = load(admission['strata']['path'])
            truths = {r['job_id']: r for r in truth_doc['cells']}; strata = {r['case_id']: r for r in strata_doc['scenes']}
            require(truth_doc['NEVER_PASS_TO_RUNTIME'] is True and strata_doc['NEVER_PASS_TO_RUNTIME'] is True
                    and len(truth_doc['cells']) == len(truths) == 480 and len(strata_doc['scenes']) == len(strata) == 240, 'Evaluator population differs')
            rows = []
            for i, (row, binding) in enumerate(zip(plan['rows'], result['scores'])):
                guard(args.output, local, started, args.max_seconds)
                require(Path(binding['path']).resolve() == run_root/'cells'/f'{i:05d}.json', 'Score prefix/order differs')
                verify(binding); value = load(binding['path']); method = bundle['terminal']['cells'][i]
                job = bundle['jobs'][row['job_id']]; pred = prediction(load(method['path']), row, job)
                validate_row(value, row, job, truths[job['job_id']], pred, method)
                rows.append(value); checked += 1
                if checked % 128 == 0: print(f'Reviewed {checked}/{plan["required"]}', flush=True)
            verify(result['report']); require(Path(result['report']['path']).resolve() == run_root/'REPORT.json', 'Foreign score report')
            aggregate_digest = verify_report(load(result['report']['path']), rows, strata, plan['scope'])
            guard(args.output, local, started, args.max_seconds)
            for binding in code + [result_binding, result['admission'], *result['scores'], result['report']]: verify(binding)
            verify_bindings(admission); verify_bindings(plan['context'])
            require(exact_process(admission['owner']) is None, 'Scoring owner reappeared')
            owners_closed(result['workers'], plan['required'])
            freeze(args.output/'RESULT.json', dict(status='PASS_REVIEWED_MODELED_SCORING_ONLY', utc=datetime.now(timezone.utc).isoformat(),
                admission=bind(args.output/'ADMISSION.json'), scoring_result=result_binding, plan=admission['plan'],
                method_review=admission['review'], report=result['report'], report_content_sha256=aggregate_digest,
                reviewed=checked, required=plan['required'], scope=plan['scope'], all_metric_inputs_and_report_totals_verified=True,
                metric_alignment_recomputed=False, environment_files_verified=files, inventory=inventory,
                models_loaded=0, integrated_N4_cells=0, physical_widget_observed=False, N4_accepted=False))
        except BaseException as exc:
            freeze(args.output/'FAILED.json', dict(status='FAILED_REVIEW_PRESERVED', error_type=type(exc).__name__,
                reviewed=checked, admission=bind(args.output/'ADMISSION.json'), integrated_N4_cells=0))
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run', 'output'): parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--max-seconds', type=int, default=7200)
    args = parser.parse_args()
    if not 1 <= args.max_seconds <= 7200: parser.error('Maximum review budget is two hours')
    run(args)
