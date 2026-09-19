"""S5 analysis-first Markdown handoff and bounded ZIP. README_S5.md."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import difflib
import hashlib
import json
import re
from pathlib import Path
import zipfile
from s5_common import *
from s5_results import write_csv

def pct(value, digits=2):
    return 'unavailable' if value is None else f'{100 * value:.{digits}f}%'

def num(value, digits=2):
    return 'unavailable' if value is None else f'{value:.{digits}f}'

def table(headers, rows):
    clean = lambda x: str(x).replace('|', '/').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(clean, headers)) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(map(clean, r)) + ' |' for r in rows])

def atomic_bytes(path, data):
    temp = path.with_name(path.name + '.final.tmp')
    temp.write_bytes(data)
    os.replace(temp, path)

def readable_prose(text):
    # Formatting only; preserve model IDs, paths and hexadecimal hashes.
    prefixes = 'all|the|one|two|four|eight|with|over|across|from|per|of|and|on|in|has|uses|through|contains|used|is|ends|by|at|only|about|remain|supports|scalar|gain|hash|mono|English|are|to|or|versus|beyond|within|least|minimum|maximum|above|below|cover|covers|resamples|remains|have|adds|using|CER|MIMO|cpWER|Overlap|relocation|upright|obstructed|mixed|flags|support|speech|shared|peak|longest|wall|median|advantage|separation|deltas|interval|respect|MeetEval|segmentation|embedding|original|corrected|threshold|old|room'
    text = re.sub(r'\b(' + prefixes + r')(?=[+-]?\d)', r'\1 ', text, flags=re.IGNORECASE)
    units = 'dBFS|FS|IDs|dB|kHz|Hz|MiB|GiB|ms|s|ASR|speaker|punctuation|seconds|minutes|hours|cases|scenes|controls|jobs|outputs|assets|threads|frames|windows|disjoint|replicates'
    text = re.sub(r'(\d)(?=(?:' + units + r')\b)', r'\1 ', text)
    text = re.sub(r';(?=\S)', '; ', text)
    text = re.sub(r'(?<=[A-Za-z]):(?=\d)', ': ', text)
    text = re.sub(r'\b(O[01]):(?=\d)', r'\1: ', text)
    text = re.sub(r',(?=\d{1,2}(?:[/\s,]|$))', ', ', text)
    return text

def score_cell(value, stream):
    r = value[stream]
    return f"{pct(r['wer'])} ({r['errors']}/{r['reference_words']}; {r['substitutions']}S/{r['deletions']}D/{r['insertions']}I)"

def elapsed_through(utc):
    ended = dt.datetime.fromisoformat(utc.replace('Z', '+00:00'))
    assert ended.tzinfo is not None and ended >= START, 'Qualified S5 elapsed-time boundary required'
    return {'start_utc': START.isoformat(), 'through_utc': ended.isoformat(),
            'elapsed_wall_s': (ended - START).total_seconds()}

def resource_table(audit):
    """Display qualified audit observations without requerying hardware or inventing peaks."""
    r = audit['resources']
    assert r['status'] == 'PASS', 'Qualified final resource audit required'
    clock = elapsed_through(audit['ended_utc'])
    rows = [
        ['S5 wall time through final audit', f"{num(clock['elapsed_wall_s'])} s ({num(clock['elapsed_wall_s'] / 3600)} h)", clock['through_utc']],
        ['Sampled canonical model-tree peak RSS', f"{num(r['sampled_model_tree_peak_rss_bytes'] / 2**20)} MiB", f"{r['model_ram_samples']} samples; not a continuous absolute peak"],
        ['Minimum sampled available OS RAM', f"{num(r['sampled_available_ram_min_bytes'] / 2**30)} GiB", 'Recorded canonical-run samples'],
        ['Available OS RAM at audit', f"{num(r['current_ram']['available'] / 2**30)} GiB", 'Final audit snapshot'],
        ['New S5 logical storage at audit', f"{num(r['new_storage']['bounded_new_logical_bytes'] / 2**30)} GiB", 'Bounded new files; existing datasets excluded; later package bytes not yet included']]
    for origin, label in (('fresh_s5', 'Fresh native child wall sum'), ('reused_s45', 'Historical reused child wall sum')):
        native = audit['native_totals'][origin]
        rows.append([label, f"{num(native['model_child_wall_s'])} s / {native['jobs']} jobs", 'Child process elapsed sums; historical work is outside S5 elapsed wall time' if origin == 'reused_s45' else 'Offline child process elapsed sums, separate from end-to-end S5 wall time'])
    volumes = r['ssd']['volumes']
    assert {v['drive'] for v in volumes} == {'C:', 'G:'}, 'Both final SSD observations required'
    for volume in volumes:
        models = '; '.join(f"{m['model'].strip()}: {m['health_status']} / {', '.join(m['operational_status'])}" for m in volume['mapping'])
        rows.append([volume['drive'] + ' free space and mapped SSD', f"{num(volume['free_bytes'] / 2**30)} GiB free", models])
    return table(['Audited resource / runtime', 'Observed value', 'Scope'], rows)

def region_level_table(support):
    rows = []
    for region, label in (('speech_active', 'Estimated speech-active support'),
                          ('quiet_outside_all_convolution_envelopes', 'Quiet outside all convolution envelopes')):
        for out in ('O0', 'O1'):
            r = support[out]['regions'].get(region)
            if r is None:
                rows.append([label, out, 'unavailable', 'unavailable', 'unavailable', 'unavailable'])
                continue
            def level(key):
                v = r[key]['per_scene_rms_dbfs']
                return f"{num(v['median'])} [{num(v['p10'])}, {num(v['p90'])}]; n={v['n']}; zero RMS={r[key]['zero_rms_scenes']}"
            rows.append([label, out, f"{r['scenes_with_nonempty_support']}/{r['scenes']}",
                         num(r['support_samples'] / 16000), level('raw_levels'), level('adapter_pcm16_levels')])
    return table(['Region', 'Output', 'Nonempty / mapped scenes', 'Support seconds',
                  'Raw RMS dBFS median [p10, p90]', 'Native-adapter RMS dBFS median [p10, p90]'], rows)

def verify_binding(item, expected_path=None):
    path = Path(item['path'])
    if expected_path is not None:
        assert path.resolve() == Path(expected_path).resolve(), 'Evidence binding path differs'
    assert bind(path) == item, 'Evidence binding changed: ' + str(path)
    return path

def figure_bundle():
    folder = REPORT / 'figures'
    receipt = read(folder / 'FIGURE_RECEIPT.json')
    assert receipt['schema'] == 'jp_s5_figures_v1' and receipt['status'] == 'FINAL_COMPLETE_PANEL_FIGURES', 'Final figure receipt required'
    assert receipt['figure_count'] == 4 and len(receipt['figures']) == 4, 'Exactly four final figures required'
    assert not receipt['layout_warnings'] and receipt['reserve_task_audio_or_native_logs_opened'] == 0
    names = [Path(b['path']).name for b in receipt['figures']]
    assert len(set(names)) == 4 and all(n.endswith('.png') for n in names), 'Four unique PNGs required'
    assert {p.name for p in folder.glob('*.png')} == set(names), 'Only the four receipted figures may be packaged'
    for item in receipt['figures']:
        verify_binding(item, folder / Path(item['path']).name)
    verify_binding(receipt['plotdata'], folder / 'plotdata.csv')
    verify_binding(receipt['captions'], folder / 'CAPTIONS.md')
    verify_binding(receipt['code'], SIM / 'scripts/s5_figures.py')
    required = {str((REPORT / n).resolve()) for n in ('SUMMARY_METRICS.json', 'PAIRED_METRICS.json',
                 'SHORT_TURN_SUMMARY.csv', 'SCORING_PROTOCOL.json', 'JOB_MANIFEST.json', 'representation/SUMMARY_COMPACT.json')}
    actual = {str(verify_binding(b).resolve()) for b in receipt['input_bindings']}
    assert actual == required and len(receipt['input_bindings']) == len(required), 'Final figures must bind the current numeric panel and representation'
    text = (folder / 'CAPTIONS.md').read_text(encoding='utf-8')
    captions = dict(re.findall(r'\*\*([^\n*]+\.png)\*\*\s*\n(.*?)(?=\n\*\*[^\n*]+\.png\*\*|\Z)', text, flags=re.S))
    assert set(captions) == set(names) and all(v.strip() for v in captions.values()), 'Caption required for each final figure'
    # Relative links keep the extracted handoff portable; full local paths remain in receipts.
    return '\n\n'.join(f"![{name[:-4].replace('_', ' ')}](figures/{name})\n\n{captions[name].strip()}" for name in names)

def export_reserve_protection(audit):
    """Join independently audited execution guards with final reporting guards, metadata only."""
    assert audit['mode'] == 'FULL_REQUIRE_TERMINAL' and not audit['errors'], 'Qualified full native audit required'
    proof = audit['reserve_protection']
    assert proof['status'] == 'VERIFIED_RECORDED_APPLICATION_GUARDS' and not proof['missing'], 'Final reserve evidence incomplete'
    assert proof['development_cases'] == 180 and proof['protected_reserve_cases'] == 60
    assert proof['reserve_task_model_accesses'] == proof['reserve_task_performance_accesses'] == 0, 'Recorded reserve task access is not zero'
    scenes = manifest()['scenes']
    assert len(scenes) == 240 and len({s['case_id'] for s in scenes}) == 240
    allowed = {s['case_id'] for s in scenes if s['split'] == 'development' and s['task_scoring_allowed'] is True}
    assert len(allowed) == 180
    for row in proof['components']:
        verify_binding(row['receipt'])
    components = []
    for name in ('aggregate', 'package', 'figures'):
        path = REPORT / 'access' / (name + '.json')
        data = read(path)
        assert data['component'] == name and set(data['allowed_development_cases']) == allowed
        assert len(data['allowed_development_cases']) == 180 and data['metadata_rows_parsed'] == 240
        assert data['reserve_task_accesses'] == 0, 'Reporting guard recorded reserve task access'
        assert all(isinstance(n, int) and n >= 0 for n in data['permitted_operation_calls'].values())
        components.append({'receipt': bind(path), 'component': name,
                           'permitted_operation_calls': data['permitted_operation_calls'],
                           'denied_before_open': data['denied_before_open'],
                           'metadata_rows_parsed': data['metadata_rows_parsed'], 'reserve_task_accesses': 0})
    result = {'schema': 'jp_s5_reserve_protection_v1', 'status': 'VERIFIED_RECORDED_APPLICATION_GUARDS',
              'utc': now(), 'final_audit': bind(REPORT / 'FINAL_AUDIT.json'),
              'canonical_scene_manifest': bind(BANK / 'SCENE_MANIFEST.json'),
              'development_cases': 180, 'protected_reserve_cases': 60,
              'reserve_task_model_accesses': 0, 'reserve_task_performance_accesses': 0,
              'audited_execution_components': proof['components'], 'reporting_components': components,
              'reserve_metadata_parsing_allowed': True,
              'scope': 'Verified recorded application guards plus final audit task-directory checks. Reserve metadata rows may be parsed; metadata parsing and blocked-before-open attempts are not task evaluations. No OS-wide file-access trace or inferred zero from absent receipts.'}
    save(REPORT / 'RESERVE_PROTECTION.json', result)
    return result

def report_data():
    stats = read(REPORT / 'SUMMARY_METRICS.json')
    assert stats['status'] in ('COMPLETE_PANEL', 'COMPLETE_PANEL_WITH_FAILURES'), 'No final handoff from partial diagnostic'
    audit = read(REPORT / 'FINAL_AUDIT.json')
    assert str(audit['status']).startswith(('PASS', 'VERIFIED_TERMINAL')), 'Final audit must qualify the native panel'
    decision = read(REPORT / 'OUTPUT_DECISION.json')
    assert decision['scope'] == 'development'
    assert {decision['primary_for_S6'], decision['fallback']} == {'O0', 'O1'}
    assert decision['summary_metrics_binding'] == bind(REPORT / 'SUMMARY_METRICS.json'), 'Decision must bind final numeric evidence'
    assert decision['exact_recipes']['O0']['host_gain_scalar'] == GAINS['O0']
    assert decision['exact_recipes']['O1']['host_gain_scalar'] == GAINS['O1']
    with (REPORT / 'SHORT_TURN_SUMMARY.csv').open(encoding='utf-8', newline='') as f:
        short = list(csv.DictReader(f))
    return stats, audit, decision, short

def write_reports():
    s, audit, d, short = report_data()
    resources_table = resource_table(audit)
    figures_markdown = figure_bundle()
    p, cp, ov = s['primary'], s['cpwer_all_complete_speech'], s['overlap_mimo']
    sup = s['support']
    ci = s['uncertainty'].get('paired_O1_minus_O0_wer_pp_percentile95')
    ci_text = f"[{ci[0]:+.2f}, {ci[1]:+.2f}] percentage points" if ci else 'unavailable'
    recipe_table = table(['Output', 'Frozen device source', 'Host adapter', 'Canonical input'], [
        ['O0', 'ASR-oriented output; device AEC_ASROUTGAIN=1', '+3 dB, scalar1.4125375446227544 once', 'Recorded mono16kHz PCM24 -> FLOAT adapter -> unchanged native PCM16'],
        ['O1', 'Postprocessed auto output', 'Unity scalar1.0', 'Same format/conversion convention; original rails retained']])
    word_table = table(['Metric / population', 'Paired scenes', 'O0', 'O1', 'O1 minus O0'], [
        ['Ordinary WER, full-reference nonoverlap', p['paired_scenes'], score_cell(p, 'O0'), score_cell(p, 'O1'), f"{num(p['O1_minus_O0_wer_pp'])} pp"],
        ['MIMO WER, complete-reference overlap', ov['paired_scenes'], score_cell(ov, 'O0'), score_cell(ov, 'O1'), f"{num(ov['O1_minus_O0_wer_pp'])} pp"],
        ['cpWER, all complete-reference speech', cp['paired_scenes'], score_cell(cp, 'O0'), score_cell(cp, 'O1'), f"{num(cp['O1_minus_O0_wer_pp'])} pp"],
        ['cpWER, nonoverlap only', s['cpwer_primary']['paired_scenes'], score_cell(s['cpwer_primary'], 'O0'), score_cell(s['cpwer_primary'], 'O1'), f"{num(s['cpwer_primary']['O1_minus_O0_wer_pp'])} pp"],
        ['cpWER, overlap only', s['cpwer_overlap']['paired_scenes'], score_cell(s['cpwer_overlap'], 'O0'), score_cell(s['cpwer_overlap'], 'O1'), f"{num(s['cpwer_overlap']['O1_minus_O0_wer_pp'])} pp"]])
    continuity_rows = []
    for pop in ('primary_nonoverlap', 'overlap_complete', 'ambient_incomplete'):
        for stream in ('O0', 'O1'):
            v = sup[stream]['continuity_by_population'][pop]
            rc = v['return_classifications']
            continuity_rows.append([pop, stream, v['supported_turns'], v['turns_without_evidence'], v['dominant_ties'],
                 v['multilabel_turns'], v['within_turn_switches'],
                 f"{rc.get('consistent', 0)}/{rc.get('inconsistent', 0)}/{rc.get('unknown', 0)} of {v['return_groups']}"])
    continuity_table = table(['Population', 'Output', 'Supported turns', 'No contained evidence', 'Dominant ties', 'Multilabel turns', 'Within-turn switches', 'Repeated-person groups C/I/U'], continuity_rows)
    short_table_rows = []
    for definition in ('whole_clip_bin', 'active_duration_bin'):
        for bucket in ('<1s', '1-<2s', '>=2s'):
            a, b = [next(r for r in short if r['scope'] == 'single_source_attributable' and r['duration_definition'] == definition
                        and r['corpus'] == 'ALL' and r['duration_bin'] == bucket and r['stream'] == out) for out in ('O0', 'O1')]
            short_table_rows.append([definition, bucket, f"{a['positive_supported_flags']}/{a['observed_turns']}",
                f"{b['positive_supported_flags']}/{b['observed_turns']}", f"{a['no_positive_on_observed_support']}/{b['no_positive_on_observed_support']}",
                f"{a['turns_without_contained_embedding']}/{b['turns_without_contained_embedding']}"])
    short_table = table(['Duration definition', 'Bin', 'O0 positive/observed', 'O1 positive/observed', 'No-positive O0/O1', 'No contained embedding O0/O1'], short_table_rows)
    workload_table = table(['Measured quantity', 'O0', 'O1'], [
        ['Native embedding decisions', sup['O0']['successful_embedding_calls'], sup['O1']['successful_embedding_calls']],
        ['Eligible reconstructed hops', sup['O0']['gate_counts']['eligible_hops_reconstructed'], sup['O1']['gate_counts']['eligible_hops_reconstructed']],
        ['Eligible hops without native decision', sup['O0']['gate_counts'].get('eligible_without_decision', 'unavailable'), sup['O1']['gate_counts'].get('eligible_without_decision', 'unavailable')],
        ['Native decisions despite reconstructed ineligibility', sup['O0']['gate_counts'].get('decision_despite_ineligible', 'unavailable'), sup['O1']['gate_counts'].get('decision_despite_ineligible', 'unavailable')],
        ['Unique evidence audio, seconds', num(sup['O0']['unique_evidence_audio_s']), num(sup['O1']['unique_evidence_audio_s'])],
        ['Total overlapping-window audio processed, seconds', num(sup['O0']['total_processed_window_s']), num(sup['O1']['total_processed_window_s'])],
        ['Embedding calls / decoded minute', num(sup['O0']['embedding_calls_per_decoded_minute']), num(sup['O1']['embedding_calls_per_decoded_minute'])],
        ['Raw PCM24 rail samples / total', f"{sup['O0']['raw_levels']['rail_samples']}/{sup['O0']['raw_levels']['samples']}", f"{sup['O1']['raw_levels']['rail_samples']}/{sup['O1']['raw_levels']['samples']}"],
        ['Raw rail-affected outputs', sup['O0']['raw_levels']['scenes_with_rails'], sup['O1']['raw_levels']['scenes_with_rails']],
        ['Longest raw rail run, samples', sup['O0']['raw_levels']['longest_rail_run_samples'], sup['O1']['raw_levels']['longest_rail_run_samples']],
        ['Fresh canonical child wall, seconds', num(s['timing']['fresh_s5']['O0']['model_child_wall_s']), num(s['timing']['fresh_s5']['O1']['model_child_wall_s'])],
        ['Reused historical child wall, seconds', num(s['timing']['reused_s45']['O0']['model_child_wall_s']), num(s['timing']['reused_s45']['O1']['model_child_wall_s'])]])
    controls_table = table(['Output', 'Strict controls', 'Inserted words', 'Affected controls', 'Decoded seconds', 'Words / decoded minute'], [
        [out, v['controls'], v['inserted_words'], v['affected_controls'], num(v['decoded_duration_s']), num(v['words_per_decoded_minute'])]
        for out, v in s['strict_empty'].items()])
    ambient_table = table(['Output', 'Incomplete-reference scenes', 'Native speech-flag / decoded support', 'Embedding decisions', 'Target-only diagnostic'], [
        [out, sup[out]['by_population']['ambient_incomplete']['outputs'],
         pct(sup[out]['by_population']['ambient_incomplete']['native_speech_flag_fraction_decoded']),
         sup[out]['by_population']['ambient_incomplete']['successful_embedding_calls'],
         score_cell(s['ambient_target_only_LIMITED'], out)] for out in ('O0', 'O1')])
    room_rows = [r for r in s['strata'] if r['population'] == 'primary' and r['dimension'] == 'room']
    room_table = table(['Fixed development room', 'Scenes', 'O0 WER', 'O1 WER', 'O1−O0 pp'],
                       [[r['level'], r['paired_scenes'], pct(r['O0']['wer']), pct(r['O1']['wer']), num(r['O1_minus_O0_wer_pp'])] for r in room_rows])
    source_rows = [r for r in s['strata'] if r['population'] == 'primary' and r['dimension'] in ('corpus', 'quality_partition')]
    source_table = table(['Stratum', 'Scenes', 'O0 errors/words', 'O1 errors/words', 'O1−O0 pp'],
        [[r['level'], r['paired_scenes'], f"{r['O0']['errors']}/{r['O0']['reference_words']}", f"{r['O1']['errors']}/{r['O1']['reference_words']}", num(r['O1_minus_O0_wer_pp'])] for r in source_rows])
    practical = table(['Planning reference', 'Point inside band', 'Conditional interval inside band', 'Interval favors O0 beyond band', 'Interval favors O1 beyond band'],
        [[r['threshold_absolute_wer_pp'], r['point_inside_practical_band'], r['conditional_interval_entirely_inside_band'],
          r['conditional_interval_entirely_favors_O0_beyond_threshold'], r['conditional_interval_entirely_favors_O1_beyond_threshold']]
         for r in s['uncertainty'].get('practical_difference_sensitivity', [])])
    proscons = table(['Function / condition', 'O0', 'O1', 'Decision implication'], d['pros_cons_table'])
    rep_note = (REPORT / 'representation/HANDOFF.md').read_text(encoding='utf-8').split('\n', 2)[2]
    description = f"""# S5 complete development output comparison

**COMPLETE_WITH_LIMITATIONS. Primary for S6: {d['primary_for_S6']}; retain {d['fallback']} as fallback.**
{d['rationale']}

The final panel contains {s['reliability']['complete']}/360 native completed output jobs on180 development scenes:
{s['reliability']['reused']} compatible historical outputs and {s['reliability']['new_complete']} new canonical outputs.
There were {s['reliability']['failed']} terminal failures, {s['reliability']['quarantined']} quarantines and {s['reliability']['retry_jobs']} retried jobs.
All60 reserve task evaluations remain closed. This is a development operating choice with evidence strength
**{d['evidence_strength']}**, not a claim of broad product readiness.

## Decision and costs

{proscons}

Change the choice only under the following evidence condition: {d['condition_that_would_change_choice']}
No split ASR/embedding input, automatic mode switching, cue fusion, tuning, training or deployment was implemented.

## Scope, reusable evidence and exact recipes

The exclusive populations are117 complete-reference nonoverlap speech scenes,36 complete-reference overlap
scenes,19 incomplete-ambient-reference scenes and8 strict empty-reference controls. Real noise occurs in39
development scenes and is an overlapping diagnostic population. S5 does not add the24 old dry jobs to the360.
The24 prior development scenes were already inspected; this is not blind preregistration or pristine held-out testing.

{recipe_table}

Apply the recipe scalar only when constructing an adapter from original PCM24 output.
Indexed FLOAT adapters and native PCM16 journals already contain that scalar; consume them at unity.

H2 retained Sherpa streaming Zipformer English2023-06-21, Pyannote segmentation3.0, ReDimNet2 B2,
and the existing online punctuation assets. CPU execution uses2 ASR threads,2 speaker threads and1 punctuation
thread, one fresh independent canonical process/session per output. Segmentation remains10s/0.75s;
embedding remains0.5s/0.25s. Existing scientific thresholds and enrollment/session-memory rules are unchanged.
Only the previously validated S4.5 runtime/CLI durability repair remains in the tracked H2 diff.
Eight assets and exact configuration/source identities are bound in execution_contract.json.

Every consumed output is joined to its accepted capture and saved hash. Reuse verifies raw bytes, one fixed gain,
assets/config/provider/code/lifecycle, native summary/events and the exact full PCM16 journal.
The final audit independently checks these joins and actual process closure; its evidence is not only a status flag.
Positive raw PCM24 rail/near-rail samples can meet the unchanged native PCM16 clamp. They are retained and counted,
not erased or reclassified as a gain repair. An overstrict preflight assertion was corrected before new inference;
the failed preflight contract and correction receipt remain local.

## Words and attributed text

{word_table}

Primary CER: O0 {pct(s['primary_character_counts']['O0']['cer'])}
({s['primary_character_counts']['O0']['errors']}/{s['primary_character_counts']['O0']['reference_characters']});
O1 {pct(s['primary_character_counts']['O1']['cer'])}
({s['primary_character_counts']['O1']['errors']}/{s['primary_character_counts']['O1']['reference_characters']}).
Empty primary hypotheses: O0 {s['primary_empty_hypotheses']['O0']}, O1 {s['primary_empty_hypotheses']['O1']}.
O0 has fewer word errors in {p['O0_better_scenes']} primary scenes; O1 in {p['O1_better_scenes']};
{p['equal_error_scenes']} have equal error counts.

Normalization exactly reproduces S4.5: lowercase, delete ASCII punctuation, collapse whitespace, and remove
normalized spaces for CER; no number or contraction expansion. The48 historical text/count dispositions reproduce
exactly:47/480 O0 and41/480 O1 on the15 historical ordinary cases. Final native raw ASR text is scored,
not punctuation display text.

MeetEval0.4.3 is installed only in an isolated analysis environment. MIMO keeps every original ordered utterance
within each reference speaker stream and uses exactly one output hypothesis stream; it permits cross-speaker
utterance serialization, not arbitrary word shuffling. Fixtures include both valid speaker orders, missing speech,
duplicates and forbidden word interleaving. This is not time-resolved overlap recall or source separation.
cpWER uses actual final speaker-labelled text streams with one global assignment per scene. Missing and extra
streams remain counted; values above100% can be valid. It is final-snapshot attributed-text quality, not
reconciled identity accuracy, full DER/JER or enrolled-name accuracy.

## Conditions and uncertainty

{room_table}

{source_table}

Mixed HiFi quality stays mixed. The full condition table includes family, room, corpus/quality, pose, obstruction,
source level, requested noise SNR and requested speech SIR. These are fixed-scene contrasts, not causal
age/accent/gender effects. SIR uses the native requested_sir_db field; no absent SIR is assigned a number.

The paired O1-minus-O0 primary difference is {num(p['O1_minus_O0_wer_pp'])} absolute WER points.
The2,000-replicate, deterministic matched-block percentile interval is {ci_text}. It resamples85 explicit
matched blocks within the four observed rooms. Shared people, prompts/books, RIRs and noise parents still cross
those blocks. Collapsing all dependencies gives one117-scene component: this conditional interval can be
optimistic and is not a room/source-population confidence claim.

Equal-room difference: {num(s['uncertainty'].get('room', {}).get('equal_room_delta_pp'))} points.
UNCERTAINTY.json contains leave-one-room-out and six uneven speaker-connected-component deletion sensitivities.
Neither four rooms nor six components justify a broad population CI. Pooled rates sum counts; scene macro and
equal-room results are separate, not replacements for the pooled denominator.

{practical}

The1.0-point reference and0.5/2.0 sensitivities are new S5 planning conventions, not validated product/runtime
requirements. Nonsignificance is not equivalence. Failure sensitivity is
{s['failed_empty_sensitivity']['status']}; failed outputs are never silently successful zero-error observations.

## Short turns, segmentation and anonymous continuity

{short_table}

These rows are single-scheduled-source temporal proxies. Whole-file duration differs from estimated active
speech duration. A positive exported segmentation interval intersecting source support is not word recognition;
negative observed support and genuinely unobserved gaps remain distinct. No native word intervals exist, so
event-local insertion counts and recognized-turn omission are unavailable. There is no Common Voice
whole-clip sub-two-second result; strict source/identity cohort gaps remain in the coverage tables.
The emitted segmentation flag summarizes44 tail frames (~0.7425s) at0.75s hops; its boundary intervals are coarse.

{continuity_table}

Repeated-participant groups include isolated/adjacent repeats. RETURN_GROUPS.csv separately labels actual
returns after another speaker, silent relocation/long pauses, folded spatial contrasts, scheduled overlap and
short replies from frozen metadata. F05 is a folded spatial comparison and is not mislabeled as speech overlap.
Dominant ties and missing labels stay unknown. Unknown ambient speech cannot establish source-specific identity
or misses. Labels and contemporaneous cluster IDs are observations; no retrospective merging, inherited
post-merge lineage or reconciled transcript identity is invented.

## Noise, strict controls and retained direction

{controls_table}

Strict-control WER is undefined. Music vocals=N is the existing source annotation, not new frame-level listening
certification. The19 incomplete-reference cases retain their native output and diagnostics:

{ambient_table}

Target-only error rates compare the whole mixed output with annotated target text, so untranscribed ambient
speech can contribute insertions. They are LIMITED diagnostics and are excluded from primary all-speaker WER.
Noise-associated flags are not proven false speech.

All39 real-noise scenes have frozen source/crop-derived activity windows and a shared direction analysis.
Output-local timing is available for32/39 cases on each recipe. Seven music-only controls have no saved output
lag; the silence control is also unmapped, leaving172/180 mapped outputs per recipe overall. Those cases
retain whole-output words, speech flags, evidence and rails. No zero lag or favorable shift was invented.

The adapter uses the existing20ms source RMS activity rule, the retained800-sample RIR origin exactly once,
saved capture offset and saved output lag. Quiet lies outside full scheduled convolution envelopes; uncertain
tails are separate. Source schedules, RIR origin, microphone capture, processed output and host availability
remain distinct clocks. Manual bearing uncertainty is about±5 degrees, not an XVF accuracy threshold.
NOISE_EVENT_METRICS.csv and REGION_METRICS.csv retain support/observed denominators, flags and raw/adapter levels.
SHARED_NOISE_DIRECTION.csv and SUMMARY_METRICS.shared_noise_direction contain the39 physical traces once.
Neither output is credited with improving the same shared telemetry. No nonlinear mixture-energy contrast is
called a target-only SNR improvement.

## Evidence workload, headroom and timing

{workload_table}

{region_level_table(sup)}

RMS distributions describe nonzero per-scene energy on the stated mapped support, with zero-RMS scene
counts shown separately. They are not pooled dB averages or clean-target SNR. Missing timing is unavailable,
not a zero-level observation; raw and native-adapter support lengths are retained in REGION_METRICS.csv.

Gate reason categories overlap. Eligible-without-decision and decision-despite-ineligible counts are reported
directly; unlogged rejected embedding calls stay unavailable. Overlapping windows are not independent new
speech: their union and summed processed durations are different quantities. Raw PCM24, FLOAT adapters and
native PCM16 are distinguished; active/support/quiet energy is not whole-file speech SNR.
Raw residual rails remain LIMITED under the unchanged gross-saturation rule.

Fresh paired child-wall O1-minus-O0 median is
{num(s['timing']['fresh_paired_O1_minus_O0_child_wall_s']['median'])}s over
{s['timing']['fresh_paired_O1_minus_O0_child_wall_s']['n']} fresh scene pairs.
These are offline accelerated costs, not live word/name latency or CM5 fit. Historical reuse timing is separate.
Host load included concurrent analysis. One intermediate refresh briefly used two four-thread analysis
pools (eight worker slots), exceeding the intended six-slot analysis cap; EXECUTION_NOTES.json records
this deviation. Final text/support scoring uses three workers each after canonical inference closes.
Canonical inference used one worker throughout. Timing is not an idle-host or repeated speed experiment.
TIMING_SUMMARY.csv records measured process-start, session/source-start, native completion and child-exit
boundaries; model loading and isolated summary-writing time are not guessed. Queue waits include earlier
serial work. Partial-text prefix additions, lexical rewrites and label changes are exported snapshot changes,
not edits corrected against reference truth or evidence of reconciliation.

{resources_table}

SSD health is the audit's mapped Windows provider observation, not a comprehensive SMART test. Resource
samples and the separate oracle-process RSS observation do not establish a simultaneous system-wide peak
or 2 GB CM5 fit. End-to-end wall time includes S5 preparation and reporting through the named audit boundary;
RUN_MANIFEST_FINAL.json extends it through package assembly start, and PACKAGE_RECEIPT.json records ZIP completion.

## Bounded representation diagnostic

{rep_note}

## Coverage, provenance and limitations that remain

The fixed bank uses CMU ARCTIC, HiFiTTS clean/other and Common Voice26 self-reported60+.
L2-ARCTIC and DEMAND were not used. Development has34 corpus-qualified IDs and342 unique probe clips;
cross-corpus human uniqueness is unverified. There are33 development RIRs across four room/table settings,
7 upright and7 obstructed scenes. All240 captures together use39 of120 eligible RIRs;81 eligible paths remain
unused, and one clock-sensitive path is ineligible for canonical/HIL selection. RIR_COVERAGE.csv includes all121 paths.
Unused/rare paths are not called inferior or equivalent. Upper Loeb remains in protected acoustic/joint reserve.
All121 acquisition records in this library are REVIEW; the canonical RIR validation PASS status is a separate
validation result, not an acquisition-status upgrade. Historical testing and RETAKE acquisitions are excluded
by the preserved upstream selection. The clock-sensitive flat R13 path is excluded from canonical/HIL
selection entirely, with zero scene uses. The two original100 m metadata unit errors were user-confirmed as
100 cm = 1.00 m: low-table Opening Behind Listener, flat/upright R05, both +20 degrees with about +/-5 degrees
manual uncertainty. The corrected flat path is used in6 development scenes; the upright path is unused.
No selected distance exceeds5 m. No measurement/RIR was regenerated in S5.

The pack prompt contained a malformed57-character RIR hash. The current manifest and two qualified prior
receipts agree on the64-character hash468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546;
the original pack and library were not changed. V10 remains read-only; this handoff includes only a reviewed
insertion proposal. Prior Windows snapshot/I/O incident context is retained without claiming a proven cause
or changing services. No physical XVF playback occurred in S5.

Unsupported conclusions remain: full DER/JER, enrolled naming, precise live text/name latency, reliable
direction-to-person assignment, new voices/rooms, walking/final-enclosure behavior and2GB CM5 operation.
The deterministic failure catalogue includes O0-helping, O1-helping, shared difficult and equal-error cases;
audio was not listened to as part of this analysis. Source rights/notice/training caveats remain bound to the
prior source manifests; this comparison is not automatic clearance for future training.

## Four figures and their exact plotted data

The following figures are bound by figures/FIGURE_RECEIPT.json to this final panel. Captions and every
plotted value are retained in figures/CAPTIONS.md and figures/plotdata.csv.

{figures_markdown}

## Reproduce and stop

Use scripts/README_S5.md and the component READMEs. JOB_MANIFEST.json binds every accepted raw output and exact
execution identity; LOCAL_ARTIFACT_INDEX.json resolves native sessions, audio, logs, plans, test receipts and
omitted large artifacts. FINAL_AUDIT.json and RESERVE_PROTECTION.json qualify closure and zero reserve task
access. The archive has member hashes and a strict20MiB cap, with a10MiB target.

Next authorized planning question: {d['next_S6_question']}
S5 stops here. No S6 implementation, new capture, reserve scoring, model training or CM5 deployment was launched.
"""
    (REPORT / 'S5_REPORT.md').write_text(description, encoding='utf-8')
    start = f"""# S5 handoff: start here

**COMPLETE_WITH_LIMITATIONS — primary {d['primary_for_S6']}, fallback {d['fallback']}.**

{d['rationale']}

Coverage:180 development scenes, {s['reliability']['complete']}/360 native outputs,
{s['reliability']['reused']} reused and {s['reliability']['new_complete']} new;
{s['reliability']['failed']} terminal failures; zero reserve task evaluations.
O0 uses+3dB host gain once (1.4125375446227544); O1 uses unity.

Primary WER: O0 {score_cell(p, 'O0')}; O1 {score_cell(p, 'O1')}.
Paired O1−O0 difference {num(p['O1_minus_O0_wer_pp'])} points; conditional block interval {ci_text}.
This is development evidence with crossed source/RIR dependencies, not a population confidence claim.

Biggest tradeoff: {d['biggest_tradeoff']}

Read S5_REPORT.md for the completed function/condition pros-and-cons table, then OUTPUT_DECISION.json.
Use SUMMARY_METRICS.json, PAIRED_METRICS.json, condition/short-turn/return/noise/timing tables and
the four figures for verification. Full audio/logs/vectors remain local through LOCAL_ARTIFACT_INDEX.json.
WORKBOOK_UPDATE.md is an insertion proposal for the existing V10 master, which was not rewritten.

Noise windows now cover39 development cases;32 have defensible output-local timing, and all39 have shared
direction analysis counted once. Incomplete ambient references, exact word timing, reconciled identity,
enrolled names, live latency, untested paths and CM5 operation remain limited or unavailable.

Next S6 question: {d['next_S6_question']}
Keep all60 reserve task scores closed until later locked evaluation. S5 execution is complete; stop here.
"""
    (REPORT / 'START_HERE.md').write_text(start, encoding='utf-8')
    (REPORT / 'WORKBOOK_UPDATE.md').write_text(f"""# Proposed light-yellow insertion into V10

Review this narrative for insertion into the existing S5 results section of XVF_Measurement_V10.docx.
Do not replace or independently rebuild the master. These are actual S5 results; S6 remains future planning.

{start.split(chr(10), 2)[2]}

## Small results table

{word_table}

## Evidence and remaining limits

{workload_table}

The0.5s oracle representation diagnostic used222 paired windows/34 development IDs and444 calls,
with104 genuine and104 balanced impostor comparisons. Mean separation was0.11837 O0 and0.11787 O1,
with broad overlap; this did not establish online identity accuracy or a winner.

Retain the source/room/short-duration gaps, conditional uncertainty and unsupported naming/DER/live/CM5 claims.
Figure captions and plotted data are supplied in the figures directory; use its four final figures only.
The60 reserve scenes were not scored. V10's source, measurement geometry and prior S0–S4.5 history remain unchanged.
""", encoding='utf-8')
    recipes = bind(REPORT / 'OUTPUT_RECIPES_V1.json')
    jobs = bind(REPORT / 'JOB_MANIFEST.json')
    (REPORT / 'NEXT_PHASE_INPUTS.md').write_text(f"""# Exact inputs for later S6 planning

Primary: {d['primary_for_S6']}. Fallback: {d['fallback']}.
Decision: {REPORT / 'OUTPUT_DECISION.json'}

{d['next_S6_question']}

Use the unchanged H2 baseline in execution_contract.json and the existing accepted paired captures.
O0 host scalar1.4125375446227544 once; O1 unity. Device ASR gain was1 during capture.
Apply that scalar only to the original PCM24 output. The indexed FLOAT adapters and native
PCM16 journals already contain it; their downstream input gain must be unity.
Recipes: {recipes['path']}
SHA256: {recipes['sha256']}
Complete360-job mapping: {jobs['path']}
SHA256: {jobs['sha256']}
Scene manifest: {BANK / 'SCENE_MANIFEST.json'}
SHA256: {MANIFEST_SHA}
Current RIR manifest: {SIM / 'rir_library/v1/RIR_MANIFEST.json'}
SHA256:468b2b306f994937a7d02db611080d38c7a4bcc7dc89ce7dc73d93762380f546
Old accepted hardware/native payloads: G:\\Just_Peachy_S4_5\\20260909T031300Z
New canonical adapters/journals: {PAYLOAD / 'h2'}
All exact per-file paths/hashes: LOCAL_ARTIFACT_INDEX.json and native completion receipts.

Resolved: complete development paired comparison; old48 reuse; validated MIMO/cpWER; source-derived
noise windows; explicit short-turn/evidence/continuity definitions; default and fallback.
Limited: untranscribed ambient speech, source/room/dependency gaps, partial timing coverage,
anonymous-label fragmentation, no reconciled lineage/names/full DER, no live or CM5 qualification.

Retained source gaps are recorded in INPUT_COVERAGE_REVIEW.json under prior_source_limits, with the
upstream evidence bound there. In particular, only5 of34 development IDs have dedicated noise-free isolated
development scenes;34 optional reference inputs were prepared but deliberately not captured. The other
source/partner/role/short-clip gaps are not repaired by the larger output panel. CMU bare clip basenames are
speaker-qualified names, not reliable global prompt IDs; use the retained normalized lexical groups.

Keep60 reserves closed:30 new-source,20 Upper Loeb acoustic and10 joint cases. No reserve predictions,
direction scores or task performance may choose or tune the output/fusion. Metadata inventory is separate.
Do not regenerate RIRs, scenes or captures, refill corpora, change scientific H2 policies, train,
create split ASR/embedding paths or automatically start S6 from this handoff.
""", encoding='utf-8')
    for name in ('S5_REPORT.md', 'START_HERE.md', 'WORKBOOK_UPDATE.md', 'NEXT_PHASE_INPUTS.md'):
        path = REPORT / name
        path.write_text(readable_prose(path.read_text(encoding='utf-8')), encoding='utf-8')
    return s, d

def artifact_index():
    jm = read(REPORT / 'JOB_MANIFEST.json')
    guard = DevelopmentGuard(manifest()['scenes'], 'package')
    entries = []
    for job in jm['jobs']:
        guard.require(job['case_id'], 'artifact_metadata_index')
        rp = Path(job['report_dir']) / 'run_receipt.json'
        row = {'case_id': job['case_id'], 'stream': job['stream'], 'raw_output': job['raw_audio'],
               's5_completion_receipt': bind(rp), 'reused_s45': bool(job['reuse'])}
        native_path = job['reuse']['receipt']['path'] if job['reuse'] else str(rp)
        native = read(native_path)
        if native['status'] == 'COMPLETE':
            row.update(native_receipt=bind(native_path), session_dir=native['session_dir'],
                       adapter=native['adapter']['output_binding'], journal=native['completion_evidence']['journal'],
                       events=native['events_binding'], summary=native['session_summary_binding'],
                       native_metrics=native['metrics_binding'])
        entries.append(row)
    roots = {'new_payload': str(PAYLOAD), 'old_payload': 'G:/Just_Peachy_S4_5/20260909T031300Z',
             'scene_bank': str(BANK), 'report': str(REPORT), 'canonical_rir_library': str(SIM / 'rir_library/v1')}
    extra = [bind(p) for p in sorted((REPORT / 'representation').glob('*')) if p.is_file()]
    code = [bind(p) for pattern in ('s5_*.py', 'test_s5_*.py', 'README_S5*.md') for p in sorted((SIM / 'scripts').glob(pattern))]
    setup_tests = component_test_bindings()
    save(REPORT / 'LOCAL_ARTIFACT_INDEX.json', {'schema': 'jp_s5_local_artifact_index_v1', 'roots': roots,
        'jobs': entries, 'representation': extra, 's5_code': code, 'component_setup_and_tests': setup_tests,
        'component_test_index_scope': 'Selected top-level receipt/review/smoke/test-output/install-log files and explicit v-number review folders only; no environment or dataset-tree traversal.',
        'workbook_context_only': bind(WORKBOOK),
        'omitted_from_zip': ['raw/adapter audio', 'full native frame/event logs', 'embedding vectors', 'model weights',
                             'full source/capture/RIR trees', 'prior ZIPs', 'master Word workbook'],
        'reproduction': str(SIM / 'scripts/README_S5.md'), 'reserve_task_payload_indexed': False})
    guard.flush()
    source = SIM / 'scripts/s5_support_metrics.py'
    diff = ''.join(difflib.unified_diff([], source.read_text(encoding='utf-8').splitlines(keepends=True),
                                     fromfile='/dev/null', tofile='scripts/s5_support_metrics.py'))
    (REPORT / 'S5_NOISE_SUPPORT_ADAPTER.diff').write_text(diff, encoding='utf-8')

def component_test_bindings():
    paths = set()
    patterns = ('*RECEIPT*.json', '*REVIEW*.json', '*SMOKE*.json', '*OUTPUT*.txt', '*install*.log')
    for component in (SIM / 'staging').glob('s5_*'):
        if not component.is_dir():
            continue
        folders = [component] + [p for p in component.glob('v*') if p.is_dir() and re.fullmatch(r'v\d+(?:_.*)?', p.name)]
        for folder in folders:
            for pattern in patterns:
                paths.update(p for p in folder.glob(pattern) if p.is_file())
    return [bind(p) for p in sorted(paths)]

def package():
    s, d = write_reports()
    artifact_index()
    export_reserve_protection(read(REPORT / 'FINAL_AUDIT.json'))
    wanted = ['START_HERE.md', 'S5_REPORT.md', 'SCORING_PROTOCOL.json', 'DECISION_PROTOCOL.md',
              'OUTPUT_DECISION.json', 'OUTPUT_RECIPES_V1.json', 'JOB_MANIFEST.json', 'COMPLETION_LEDGER.json',
              'SUMMARY_METRICS.json', 'PAIRED_METRICS.json', 'CONDITION_SUMMARY.csv', 'SHORT_TURN_SUMMARY.csv',
              'TURN_METRICS.csv', 'RETURN_GROUPS.csv', 'REGION_METRICS.csv', 'NOISE_EVENT_METRICS.csv',
              'SHARED_NOISE_DIRECTION.csv', 'TIMING_SUMMARY.csv', 'UNCERTAINTY.json', 'BOOTSTRAP_DRAWS.csv',
              'RIR_COVERAGE.csv', 'SCENE_COVERAGE.csv', 'INPUT_COVERAGE_REVIEW.json', 'DEPENDENCY_BLOCKS.json',
              'FAILURE_CATALOGUE.json', 'WORKBOOK_UPDATE.md', 'NEXT_PHASE_INPUTS.md', 'LOCAL_ARTIFACT_INDEX.json',
              'run_manifest.json', 'execution_contract.json', 'FINAL_AUDIT.json', 'RESERVE_PROTECTION.json',
              'RESOURCE_PREFLIGHT.json', 'RUNNER_CLEANUP.json', 'INDEPENDENT_RUNNER_REVIEW.json',
              'PREFLIGHT_CORRECTION.json', 'EXECUTION_NOTES.json', 'S45_TEXT_REGRESSION.json', 'TEST_RECEIPT.json',
              'representation/SUMMARY_COMPACT.json', 'representation/HANDOFF.md', 'representation/PROCESS_CLOSURE.json']
    files = [(name, REPORT / name) for name in wanted]
    figure_bundle()  # Recheck exact four images, captions, plotted data and numeric input bindings before ZIP reads.
    files += [(str(p.relative_to(REPORT)).replace('\\', '/'), p) for p in sorted((REPORT / 'figures').glob('*')) if p.is_file()]
    files.append(('S5_NOISE_SUPPORT_ADAPTER.diff', REPORT / 'S5_NOISE_SUPPORT_ADAPTER.diff'))
    for pattern in ('s5_*.py', 'test_s5_*.py', 'README_S5*.md'):
        files += [('code/' + p.name, p) for p in sorted((SIM / 'scripts').glob(pattern))]
    assert all(p.exists() for _, p in files), 'Required deliverable missing'
    assert len({name for name, _ in files}) == len(files)
    runner_status_path = REPORT / 'RUNNER_FINAL_STATUS.json'
    if not runner_status_path.exists():
        assert read(REPORT / 'status.json')['phase'] == 'H2_PANEL_FINISHED'
        save(runner_status_path, read(REPORT / 'status.json'))
    final_status = {'status': 'COMPLETE_WITH_LIMITATIONS', 'phase': 'S5_COMPLETE', 'utc': now(),
                    'run_id': RUN_ID, 'requested_scenes': 180, **s['reliability'],
                    'primary_for_S6': d['primary_for_S6'], 'fallback': d['fallback'],
                    'hardware_invocations': 0, 'training_jobs': 0, 'S6_started': False,
                    'native_runner_status': bind(runner_status_path),
                    'final_audit': bind(REPORT / 'FINAL_AUDIT.json'),
                    'limitations': d['unsupported_claims']}
    final_run_manifest = {'schema': 'jp_s5_final_run_manifest_v1', 'run_id': RUN_ID,
                          'frozen_initial_manifest': bind(REPORT / 'run_manifest.json'),
                          'status': final_status, 'summary_metrics': bind(REPORT / 'SUMMARY_METRICS.json'),
                          'decision': bind(REPORT / 'OUTPUT_DECISION.json'),
                          'elapsed_through_package_assembly_start': elapsed_through(now()),
                          'elapsed_scope': 'S5 end-to-end wall time through assembly start; ZIP completion is recorded separately in PACKAGE_RECEIPT.json.',
                          'audited_resource_snapshot': bind(REPORT / 'FINAL_AUDIT.json'),
                          'reserve_protection': bind(REPORT / 'RESERVE_PROTECTION.json')}
    member_data = {}
    for name, p in files:
        assert p.suffix.lower() not in ('.wav', '.pcm16', '.npz', '.npy', '.onnx', '.docx', '.zip')
        member_data[name] = p.read_bytes()
    member_data['status.json'] = (json.dumps(final_status, indent=2) + '\n').encode()
    member_data['RUN_MANIFEST_FINAL.json'] = (json.dumps(final_run_manifest, indent=2) + '\n').encode()
    member_data['RUNNER_FINAL_STATUS.json'] = runner_status_path.read_bytes()
    checksums = {'schema': 'jp_s5_zip_member_checksums_v1', 'members': [
        {'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in sorted(member_data.items())]}
    member_data['MEMBER_CHECKSUMS.json'] = (json.dumps(checksums, indent=2) + '\n').encode()
    target = SIM / 'handoffs' / ('S5_CHATGPT_HANDOFF_' + RUN_ID + '.zip')
    temp = target.with_suffix('.tmp.zip')
    target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(member_data.items()):
            z.writestr(name, data)
    assert temp.stat().st_size <= 20 * 2**20, 'Hard20MiB ZIP cap'
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == set(member_data)
        for entry in checksums['members']:
            data = z.read(entry['name'])
            assert len(data) == entry['bytes'] and hashlib.sha256(data).hexdigest() == entry['sha256']
    os.replace(temp, target)
    # Publish final status only after the deliverable passes CRC/member validation.
    atomic_bytes(REPORT / 'status.json', member_data['status.json'])
    atomic_bytes(REPORT / 'RUN_MANIFEST_FINAL.json', member_data['RUN_MANIFEST_FINAL.json'])
    receipt = {'status': 'VERIFIED', 'utc': now(), 'zip': bind(target), 'members': len(member_data),
               'crc_and_all_member_hashes': True, 'target_10_mib_met': target.stat().st_size <= 10 * 2**20,
               'hard_20_mib_met': True, 'primary_for_S6': d['primary_for_S6'], 'fallback': d['fallback'],
               'reserve_task_evaluations': 0, 'all_s5_wall_s': (dt.datetime.now(dt.timezone.utc) - START).total_seconds()}
    save(REPORT / 'PACKAGE_RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reports-only', action='store_true')
    args = parser.parse_args()
    if args.reports_only:
        write_reports()
        artifact_index()
        export_reserve_protection(read(REPORT / 'FINAL_AUDIT.json'))
    else:
        package()
