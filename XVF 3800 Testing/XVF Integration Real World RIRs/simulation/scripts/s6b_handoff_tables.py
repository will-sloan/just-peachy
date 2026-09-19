"""Export compact, source-bound S6B handoff tables; see README_S6B_HANDOFF_TABLES.md."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from s6b_common import REPORT, bind, read, save, utc


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def certified_rows(path, receipt, field='tables'):
    path = Path(path).resolve()
    binding = next(b for b in receipt[field] if Path(b['path']).resolve() == path)
    bind(path, binding['sha256'])
    data = rows(path)
    bind(path, binding['sha256'])
    return data


def unique_rows(data, fields):
    keys = [tuple(r[k] for k in fields) for r in data]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate rows: ' + ','.join(fields))
    return set(keys)


def write_csv(path, data, fields=None):
    fields = fields or list(dict.fromkeys(k for r in data for k in r))
    with Path(path).open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in data:
            writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items() if k in fields})


def build(a):
    report = a.report.resolve()
    out = report / a.output_subdir
    if out.exists():
        raise ValueError('Use a fresh handoff table output directory')
    decision_path = report / a.decision
    decision = read(decision_path)
    registry_path = report / 'EFFECTIVE_PROFILE_REGISTRY.json'
    epoch = read(report / 'EPOCH2_EXECUTION_MANIFEST.json')
    for name in ('effective_profile_registry', 'challenge_panel', 'scene_manifest'):
        bind(epoch[name]['path'], epoch[name]['sha256'])
    effective = read(registry_path)['profiles']
    if Path(epoch['effective_profile_registry']['path']).resolve() != registry_path.resolve():
        raise ValueError('Registry path is not frozen epoch registry')
    canonical_cases = {r['case_id'] for r in read(epoch['scene_manifest']['path'])['scenes']}
    challenge_cases = set(read(epoch['challenge_panel']['path'])['case_ids'])
    registry_ids = {r['profile_id'] for r in effective}
    admitted = read(report / 'FULL_CONFIRMATION_ADMISSION.json')
    full_ids = {r['profile_id'] for r in effective if r['recipe_id'] in ('R0', 'HISTORICAL_B0')} | set(admitted['profiles_to_add'])
    full_index_path = report / a.index
    challenge_index_path = report / 'CHALLENGE_PREDICTION_INDEX.json'
    index = read(full_index_path)
    challenge = read(challenge_index_path)
    if index['status'] != 'COMPLETE' or challenge['status'] != 'COMPLETE':
        raise ValueError('Both prediction indexes must be complete')
    # Count actual unique case/profile/tap cells rather than accepting a headline total.
    def cells(source, profiles, cases):
        result = [(r['profile_id'], r['case_id'], r['stream']) for r in source['rows']]
        expected = {(p, c, t) for p in profiles for c in cases for t in ('O0', 'O1')}
        if len(set(result)) != len(result) or set(result) != expected or set(source['profiles']) != profiles or set(source['case_ids']) != cases:
            raise ValueError('Duplicate, missing or unexpected prediction cell')
        if any(r.get('status', 'COMPLETE') != 'COMPLETE' for r in source['rows']):
            raise ValueError('Unsuccessful prediction row')
        return Counter(p for p, _, _ in result), Counter((p, t) for p, _, t in result)
    full_counts, full_taps = cells(index, full_ids, canonical_cases)
    challenge_counts, challenge_taps = cells(challenge, registry_ids, challenge_cases)
    if len(challenge_counts) != 44 or set(challenge_counts.values()) != {88} or set(challenge_taps.values()) != {44}:
        raise ValueError('Challenge is not 44 profiles x 44 scenes x both taps')
    if len(full_counts) != 29 or set(full_counts.values()) != {480} or set(full_taps.values()) != {240}:
        raise ValueError('Full confirmation is not 29 profiles x 240 scenes x both taps')
    if decision['status'] != 'FINAL_RESEARCH_SELECTION':
        raise ValueError('Selection decision is not finalized')
    dispositions = {r['profile_id']: r for r in decision['dispositions']}
    allowed_statuses = {'SHORTLIST_CONDITIONAL_RESEARCH', 'FULL_CONFIRMED_NOT_SHORTLISTED',
        'CHALLENGE_ONLY_REJECTED_AT_NOMINAL', 'DIAGNOSTIC_CONTROL', 'CHALLENGE_ONLY_DIAGNOSTIC'}
    if len(dispositions) != len(decision['dispositions']) or any(r['status'] not in allowed_statuses or not r.get('reason', '').strip() for r in dispositions.values()):
        raise ValueError('Disposition rows need unique IDs, explicit status and nonempty reasons')
    finalists = decision['shortlist_profile_ids']
    if not 3 <= len(finalists) <= 5 or len(set(finalists)) != len(finalists):
        raise ValueError('Require 3 to 5 unique shortlist families/profiles')
    if set(dispositions) != {r['profile_id'] for r in effective} or not set(finalists) <= set(full_counts):
        raise ValueError('Incomplete disposition map or unconfirmed finalist')
    if {pid for pid, r in dispositions.items() if r['status'] == 'SHORTLIST_CONDITIONAL_RESEARCH'} != set(finalists):
        raise ValueError('Shortlist and disposition statuses disagree')
    for pid, row in dispositions.items():
        if row['status'].startswith('CHALLENGE_ONLY') and pid in full_ids:
            raise ValueError('Fully confirmed profile mislabeled challenge-only')
        if row['status'] == 'FULL_CONFIRMED_NOT_SHORTLISTED' and pid not in full_ids:
            raise ValueError('Unconfirmed profile mislabeled full-bank')
    analysis = report / a.analysis_subdir
    component = report / a.component_subdir
    ar = read(analysis / 'ANALYSIS_RECEIPT.json')
    cr = read(component / 'COMPONENT_SCREEN_RECEIPT.json')
    car = read(report / 'challenge_analysis_v1/ANALYSIS_RECEIPT.json')
    ccr = read(report / 'component_screen_v1/COMPONENT_SCREEN_RECEIPT.json')
    expected_index = bind(full_index_path)
    for receipt in (ar, cr):
        if receipt['status'] != 'COMPLETE_REQUESTED_INDEX' or receipt['index']['sha256'] != expected_index['sha256']:
            raise ValueError('Table source does not bind the completed full index')
    for receipt in (car, ccr):
        if receipt['status'] != 'COMPLETE_REQUESTED_INDEX' or receipt['index']['sha256'] != bind(challenge_index_path)['sha256']:
            raise ValueError('Challenge table source/index mismatch')
    full_table = lambda name: certified_rows(analysis / name, ar)
    profile_rows = full_table('PROFILE_RESULTS.csv')
    profile_keys = unique_rows(profile_rows, ('profile_id', 'stream', 'population'))
    populations = {'PRIMARY_NONOVERLAP', 'COMPLETE_OVERLAP', 'INCOMPLETE_REFERENCE', 'STRICT_EMPTY_REFERENCE', 'ALL_COMPLETE_NONEMPTY'}
    if profile_keys != {(p, t, pop) for p in full_ids for t in ('O0', 'O1') for pop in populations}:
        raise ValueError('Unexpected profile/population grid')
    lookup = {(r['profile_id'], r['stream'], r['population']): r for r in profile_rows}
    checks = []
    for pid in sorted(full_counts):
        for tap in ('O0', 'O1'):
            for population, count, words in (
                ('PRIMARY_NONOVERLAP', 156, 4560), ('COMPLETE_OVERLAP', 47, 1456),
                ('INCOMPLETE_REFERENCE', 26, 683), ('STRICT_EMPTY_REFERENCE', 11, 0)):
                row = lookup[pid, tap, population]
                if int(row['scenes']) != count or int(row['word_reference_words']) != words:
                    raise ValueError(f'Population mismatch {pid}/{tap}/{population}')
            turns = sum(int(lookup[pid, tap, p]['source_turns']) for p in ('PRIMARY_NONOVERLAP', 'COMPLETE_OVERLAP', 'INCOMPLETE_REFERENCE'))
            complete = lookup[pid, tap, 'ALL_COMPLETE_NONEMPTY']
            if turns != 777 or int(complete['cp_first_final_reference_words']) != 6016:
                raise ValueError('Source-turn or cp denominator mismatch')
            checks.append(dict(profile_id=pid, stream=tap, all_source_turns=turns, complete_cp_words=6016))
    shorts = full_table('SHORT_REPLY_RESULTS.csv')
    unique_rows(shorts, ('profile_id', 'stream', 'population', 'duration_bin'))
    short40 = [r for r in shorts if r['population'] == 'ALL_COMPLETE_NONEMPTY' and r['duration_bin'] == '<1s']
    if unique_rows(short40, ('profile_id', 'stream')) != {(p, t) for p in full_ids for t in ('O0', 'O1')} or any(int(r['source_turns']) != 40 for r in short40):
        raise ValueError('Missing complete-reference subsecond cases')
    companions = set(decision.get('companion_profile_ids', []))
    cases = set(decision['diagnostic_case_ids'])
    if not companions <= full_ids or not cases or not cases <= canonical_cases or len(cases) != len(decision['diagnostic_case_ids']):
        raise ValueError('Invalid companion or diagnostic case selection')
    selected = set(finalists) | {'B00', 'B01', 'B36', 'B37', 'B38'} | companions
    screen_rows = certified_rows(component / 'COMPONENT_SCREEN.csv', cr, 'outputs')
    if unique_rows(screen_rows, ('profile_id', 'stream')) != {(p, t) for p in full_ids for t in ('O0', 'O1')}:
        raise ValueError('Missing profile summary cells')
    scene_rows = [r for r in full_table('SCENE_RESULTS.csv') if r['profile_id'] in selected and r['case_id'] in cases]
    if unique_rows(scene_rows, ('profile_id', 'case_id', 'stream')) != {(p, c, t) for p in selected for c in cases for t in ('O0', 'O1')}:
        raise ValueError('Missing diagnostic scene grid')
    out.mkdir(parents=True)
    candidates = []
    for row in effective:
        pid = row['profile_id']
        candidates.append(dict(**row, challenge_outputs=challenge_counts[pid], full_bank_outputs=full_counts.get(pid, 0),
            final_disposition=dispositions[pid], shortlist=pid in finalists,
            interpretation='Screen/full confirmation are exploratory on reused synthetic scenes; implementation and activation do not alone establish benefit.'))
    save(out / 'CANDIDATE_REGISTRY.json', dict(schema='s6b-final-candidate-registry.v1', status='COMPLETE',
        profiles=candidates, source_registry=bind(registry_path), decision=bind(decision_path),
        core_profiles=40, limited_challenge_diagnostics=4, full_bank_profiles=29,
        prospective_seed_idea_decisions=read(report / 'design/NEW_HYPOTHESIS_DECISIONS.json'),
        final_mechanism_coverage='Use METHOD_FAMILY_COVERAGE.csv and the final coverage receipt in this handoff for observed implementation/activation and adapted or unsupported N01–N08 ideas; the prospective map is retained as design history.'))
    diffs = []
    for r in read(report / 'EFFECTIVE_PROFILE_DIFFS.json')['rows']:
        for field, value in r['different_fields'].items():
            diffs.append(dict(profile_id=r['profile_id'], comparison_parent=r['parent'], field=field,
                parent_value=value['parent'], candidate_value=value['candidate'], same_neural_recipe=r['same_neural_recipe']))
    write_csv(out / 'EFFECTIVE_PROFILE_DIFFS.csv', diffs)
    write_csv(out / 'PER_PROFILE_SUMMARY.csv', screen_rows)
    write_csv(out / 'CHALLENGE_PER_PROFILE_SUMMARY.csv', certified_rows(report / 'component_screen_v1/COMPONENT_SCREEN.csv', ccr, 'outputs'))
    write_csv(out / 'FULL_PROFILE_POPULATIONS.csv', profile_rows)
    write_csv(out / 'FULL_PAIRED_COMPARISONS.csv', full_table('PAIRED_COMPARISONS.csv'))
    write_csv(out / 'CHALLENGE_FACTORIAL_COMPARISONS.csv', certified_rows(report / 'challenge_analysis_v1/PAIRED_COMPARISONS.csv', car))
    write_csv(out / 'SHORT_REPLY_RESULTS.csv', shorts)
    strata = [r for r in full_table('STRATA_RESULTS.csv') if r['profile_id'] in selected]
    fields = [k for k in strata[0] if k not in ('lineage_counts', 'transcript_event_counts')]
    write_csv(out / 'SELECTED_STRATA_RESULTS.csv', strata, fields)
    fields = [k for k in scene_rows[0] if k not in ('recipe_costs', 'lineage_counts', 'transcript_event_counts')]
    write_csv(out / 'DIAGNOSTIC_SCENE_RESULTS.csv', scene_rows, fields)
    sources = [bind(p) for p in (decision_path, registry_path, full_index_path, challenge_index_path,
        analysis / 'ANALYSIS_RECEIPT.json', component / 'COMPONENT_SCREEN_RECEIPT.json',
        analysis / 'PROFILE_RESULTS.csv', analysis / 'SHORT_REPLY_RESULTS.csv',
        analysis / 'STRATA_RESULTS.csv', analysis / 'SCENE_RESULTS.csv',
        analysis / 'PAIRED_COMPARISONS.csv', component / 'COMPONENT_SCREEN.csv',
        report / 'component_screen_v1/COMPONENT_SCREEN.csv', report / 'challenge_analysis_v1/PAIRED_COMPARISONS.csv',
        report / 'challenge_analysis_v1/ANALYSIS_RECEIPT.json', report / 'component_screen_v1/COMPONENT_SCREEN_RECEIPT.json',
        report / 'EFFECTIVE_PROFILE_DIFFS.json', report / 'design/NEW_HYPOTHESIS_DECISIONS.json',
        report / 'FULL_CONFIRMATION_ADMISSION.json', report / 'EPOCH2_EXECUTION_MANIFEST.json',
        Path(epoch['challenge_panel']['path']), Path(epoch['scene_manifest']['path']))]
    (out / 'TABLE_SCOPE.md').write_text(
        '# Compact table scope\n\nComplete cp totals use 203 complete scenes and 6,016 words per tap; primary words use 156 scenes and 4,560 words. Ambient targets, overlap MIMO and strict-empty controls remain separate.\n\n'
        'Native recipe costs repeat across profile reusers for comparison and must not be summed across those rows. Nested phases overlap; measured engine CPU, accelerated wall, replay cost and paced latency have different scopes.\n\n'
        'Short-turn wait quantiles include observed and missing counts. Contained waveform, known label support and duration-mapped correctness are different measures. Retained-row exposure is not word-aligned harm and needs its own observed-state denominator.\n\n'
        'First-display cp applies first labels to final words; it is not first-partial word accuracy. Strata may overlap. Conditional uncertainty belongs to its explicit eligible subset. Diagnostic scenes were selected after outcomes for explanation, not independent validation.\n\n'
        'Selected profile IDs: ' + ', '.join(sorted(selected)) + '.\n\nDiagnostic case IDs: ' + ', '.join(sorted(cases)) + '.\n', encoding='utf-8')
    outputs = [bind(p) for p in sorted(out.iterdir()) if p.is_file()]
    receipt = dict(status='PASS', created_utc=utc(), code=bind(__file__), inputs=sources,
        challenge_predictions=3872, full_predictions=13920, denominator_checks=checks,
        subsecond_groups=len(short40), outputs=outputs,
        interpretation='Extraction only; scores and outcome-based diagnostic selection are disclosed, no new inference or parameter fitting. No generic dominance claim. All strata are source-defined and may overlap.')
    save(out / 'HANDOFF_TABLES_RECEIPT.json', receipt)
    return dict(status=receipt['status'], outputs=len(outputs), full_predictions=13920, output=str(out))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, default=REPORT)
    p.add_argument('--decision', default='FINAL_SELECTION_DECISION.json')
    p.add_argument('--index', default='FULL_PREDICTION_INDEX.json')
    p.add_argument('--analysis-subdir', default='full_analysis_v1')
    p.add_argument('--component-subdir', default='full_component_screen_v1')
    p.add_argument('--output-subdir', default='final_tables_v1')
    print(json.dumps(build(p.parse_args()), indent=2))
