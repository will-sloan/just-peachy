"""Independent, model-free S4.5 native evidence review. See README_S45_NATIVE_REVIEW.md."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import soundfile as sf

SIM = Path(__file__).resolve().parent.parent
REPORT = SIM / 'reports/S4_5/20260909T031300Z'
BANK = SIM / 'scene_bank/s45_v2_20260909T031300Z'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=str).encode()).hexdigest()


class Evidence:
    def __init__(self):
        self.rows, self.stats = {}, {}

    def bind(self, path, expected=None):
        p = Path(path).resolve(); key = str(p)
        st = p.stat(); identity = (st.st_size, st.st_mtime_ns)
        if key not in self.rows:
            h = hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda: f.read(1024 * 1024), b''):
                    h.update(block)
            require(identity == (p.stat().st_size, p.stat().st_mtime_ns), 'File changed while hashing: ' + key)
            self.rows[key] = {'path': key, 'sha256': h.hexdigest(), 'bytes': st.st_size}
            self.stats[key] = identity
        require(identity == self.stats[key], 'Evidence changed during review: ' + key)
        b = self.rows[key]
        require(expected is None or b['sha256'] == expected, 'Hash differs: ' + key)
        return b

    def ref(self, b):
        actual = self.bind(b['path'], b['sha256'])
        require('bytes' not in b or actual['bytes'] == b['bytes'], 'Byte count differs')
        return actual

    def read(self, p, expected=None):
        self.bind(p, expected)
        x = json.loads(Path(p).read_text(encoding='utf-8-sig'))
        self.bind(p, expected)
        return x


def json_stream(text):
    """CLI stdout has JSON event lines plus a pretty-printed final object."""
    result, pos, decoder = [], 0, json.JSONDecoder()
    while pos < len(text):
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos == len(text):
            break
        item, pos = decoder.raw_decode(text, pos)
        result.append(item)
    return result


def verify_event_metrics(events, summary, metrics, stdout):
    counts = Counter(e['event_type'] for e in events)
    require(all(counts[k] == 1 for k in ('session_created', 'session_started', 'source_started', 'session_completed')), 'Lifecycle event count differs')
    require(not counts['failure'] and not counts['session_stopped'], 'Native failure/stop event')
    require(events[-1]['event_type'] == 'session_completed', 'Completion was not last')
    require([e['event_type'] for e in events[:3]] == ['session_created', 'session_started', 'source_started'], 'Startup ordering differs')
    require(stdout[:-1] == events, 'Stdout and journal events differ')
    telem = summary['telemetry']; completion = events[-1]['payload']['telemetry']
    omit_elapsed = lambda x: {k: v for k, v in x.items() if k != 'elapsed_wall_sec'}
    require(omit_elapsed(telem) == omit_elapsed(completion) == omit_elapsed(stdout[-1]), 'Completion telemetry differs')
    require(completion['elapsed_wall_sec'] <= telem['elapsed_wall_sec'] <= stdout[-1]['elapsed_wall_sec'], 'Elapsed telemetry ordering differs')
    require(all(telem[k] == 0 for k in ('audio_frames_dropped', 'portaudio_input_overflows', 'raw_capture_reserve_failures')), 'Dropped source input')
    require(summary['state'] == metrics['state'] == 'COMPLETED' and 'reconstruction_provenance' not in summary, 'Non-native or incomplete summary')
    require(metrics['event_counts'] == dict(counts) and metrics['failure_events'] == [], 'Metric event counts differ')
    require(metrics['telemetry'] == telem and metrics['scientific_policy'] == summary['scientific_policy'], 'Metric summary differs')
    finals = [e for e in events if e['event_type'] == 'transcript_final']
    require(len({e['payload']['utterance_index'] for e in finals}) == len(finals), 'Duplicate final utterance')
    require(metrics['final_transcripts'] == [{'source_cursor_s': e['source_time_sec'], **e['payload']} for e in finals], 'Final transcript snapshots differ')
    labels = [e['payload']['anonymous_label'] for e in events if e['event_type'] == 'speaker_decision']
    speaker = metrics['speaker']
    require(speaker['emitted_final_labels'] == [e['payload']['speaker'] for e in finals], 'Emitted labels differ')
    require(speaker['decision_label_counts'] == dict(Counter(labels)), 'Decision label counts differ')
    require(speaker['decision_label_switches'] == sum(a != b for a, b in zip(labels, labels[1:])), 'Decision switches differ')
    require(speaker['embedding_calls_successful'] == len(labels), 'Embedding decision count differs')
    require(speaker['embedding_calls_rejected'] is None and speaker['reconciled_labels'] is None and speaker['naming_accuracy'] is None, 'Unavailable identity evidence incorrectly asserted')
    require(speaker['reconciliation_status'] == 'UNAVAILABLE_IN_UNCHANGED_EDGE_BASELINE', 'Unexpected reconciled lineage claim')
    return {'event_counts': dict(counts), 'emitted_final_label_counts': dict(Counter(speaker['emitted_final_labels'])),
            'decision_label_counts': dict(Counter(labels)), 'decision_label_switches': speaker['decision_label_switches']}


def verify_audio(raw, adapter, pcm, gain):
    require(raw.shape == adapter.shape and raw.ndim == 2 and raw.shape[1] == 1, 'Explicit mono input required')
    expected_adapter = (raw[:, 0].astype(np.float64) * gain).astype(np.float32)
    require(np.array_equal(expected_adapter, adapter[:, 0]), 'Raw-to-adapter fixed gain differs')
    require(np.isfinite(adapter).all(), 'Nonfinite adapter')
    quantized = np.round(np.clip(adapter[:, 0], -1, .999969) * 32768).astype('<i2')
    require(quantized.tobytes() == pcm, 'Full native journal differs from adapter PCM16')
    return quantized.astype(np.float32) / 32768


def verify_gate(audio, events, metrics, science):
    gate = metrics['embedding_gate_evidence']; rate = science['sample_rate']
    hop = round(science['embedding_hop_sec'] * rate); minimum = science['minimum_rms']
    require(gate['minimum_rms'] == minimum and gate['hop_s'] == science['embedding_hop_sec'] and gate['embedding_window_s'] == science['embedding_window_sec'], 'Embedding gate policy differs')
    segments = {round(e['source_time_sec'] * rate): e['payload'] for e in events if e['event_type'] == 'segmentation'}
    decisions = {round(e['source_time_sec'] * rate) for e in events if e['event_type'] == 'speaker_decision'}
    counters = Counter(); speech = overlap = False
    for end in range(hop, len(audio) + 1, hop):
        if end in segments:
            speech, overlap = bool(segments[end]['speech']), bool(segments[end]['overlap'])
        rms = float(np.sqrt(np.mean(np.square(audio[end-hop:end]), dtype=np.float64)))
        blocked = {'no_speech': not speech, 'overlap': overlap, 'short_window': end < round(science['embedding_window_sec'] * rate), 'below_minimum_rms': rms < minimum}
        eligible, emitted = not any(blocked.values()), end in decisions
        for k, v in {'total_hops': 1, 'eligible_hops_reconstructed': eligible, 'emitted_embedding_decisions': emitted,
                     'eligible_without_decision': eligible and not emitted, 'decision_despite_ineligible': not eligible and emitted,
                     'single_speech_hops': speech and not overlap, 'single_speech_hops_below_rms': speech and not overlap and rms < minimum,
                     **{'blocked_' + k: v for k, v in blocked.items()}}.items():
            counters[k] += int(v)
    require(dict(counters) == gate['counts'], 'Gate evidence differs from native PCM16 and segmentation')
    require(gate['embedded_window_unique_speech_seconds'] is None, 'Overlapping windows treated as independent support')
    return dict(counters)


def verify_turns(events, metrics, segments, offset):
    evidence = metrics['speaker'].get('reference_turn_evidence')
    if evidence is None:
        return None
    turns = sorted((s for s in segments if s.get('transcript')), key=lambda s: s['source_start_sample'])
    require(len(evidence['turns']) == len(turns) and evidence['alignment_offset_s'] == offset, 'Turn reference count/alignment differs')
    windows = [(s['source_start_sample'] / 16000 + offset, s['source_stop_sample'] / 16000 + offset) for s in turns]
    decisions = [e for e in events if e['event_type'] == 'speaker_decision']
    for i, (turn, bounds, actual) in enumerate(zip(turns, windows, evidence['turns'])):
        eligible = []
        for e in decisions:
            end = float(e['source_time_sec']); start = end - .5
            if start >= bounds[0] and end <= bounds[1] and sum(end > a and start < b for a, b in windows) == 1:
                eligible.append(e['payload']['anonymous_label'])
        counts = Counter(eligible); ordered = counts.most_common()
        dominant = ordered[0][0] if ordered and (len(ordered) == 1 or ordered[0][1] > ordered[1][1]) else None
        require(actual == {'turn_index': i, 'participant_id': turn['speaker_key'], 'decision_count': len(eligible), 'labels': dict(counts),
                           'dominant_label': dominant, 'label_switches': sum(a != b for a, b in zip(eligible, eligible[1:])),
                           'fragment_count': len(counts), 'missing_evidence': not eligible}, 'Turn label evidence differs')
    expected = []
    for participant in dict.fromkeys(t['speaker_key'] for t in turns):
        rows = [x for x in evidence['turns'] if x['participant_id'] == participant]
        if len(rows) > 1:
            labels = [x['dominant_label'] for x in rows]
            expected.append({'participant_id': participant, 'turn_indices': [x['turn_index'] for x in rows],
                             'dominant_labels': labels, 'consistent': len(set(labels)) == 1 if all(labels) else None})
    require(evidence['returning_participants'] == expected, 'Return continuity differs or missing evidence became consistency')
    return {'turns': len(turns), 'returning_participants': len(expected), 'consistent': sum(x['consistent'] is True for x in expected),
            'inconsistent': sum(x['consistent'] is False for x in expected), 'unknown': sum(x['consistent'] is None for x in expected)}


def qualified_alignment(capture, mapping):
    if not mapping:
        return None
    delay = mapping.get('processed_output_minus_recaptured_input_s')
    require(isinstance(delay, (int, float)) and math.isfinite(delay) and mapping.get('evidence'), 'Unqualified measured output alignment')
    source_offset = capture['payload']['capture_minus_source_offset_samples'] / 16000
    return {'alignment_offset_s': source_offset + .05 + delay, 'recaptured_input_offset_s': source_offset,
            'rir_retained_margin_s': .05, 'processed_output_delay_s': delay, 'evidence': mapping['evidence'],
            'uncertainty_s': mapping.get('uncertainty_s'),
            'scope': 'Descriptive input/output alignment and retained RIR convention; file support is not exact phonetic timing or full physical latency.'}


def join_primary_bindings(ev, contract, current_paths, dry_plan=None):
    """Bind active authorities to the executed contract, including dry-plan parents."""
    actual = {}
    for key, path in current_paths.items():
        require(Path(contract[key]['path']).resolve() == Path(path).resolve(), 'Contract authority path differs: ' + key)
        actual[key] = ev.ref(contract[key])
        require(ev.bind(path) == actual[key], 'Current authority differs from contract: ' + key)
    if dry_plan is not None:
        for key in ('scene_manifest', 'sentinel_plan'):
            parent = dry_plan['identity'][key]
            require(Path(parent['path']).resolve() == Path(current_paths[key]).resolve(), 'Dry-plan parent path differs: ' + key)
            require(ev.ref(parent) == actual[key], 'Dry-plan parent hash differs: ' + key)
    return actual


def verify_metric_identity(row, metrics, gain, level):
    require((metrics['case_id'], metrics['stream'], metrics['kind']) == (row['case_id'], row['stream'], row['kind']), 'Metric job identity differs')
    require(metrics['fixed_host_gain'] == gain, 'Metric fixed gain differs')
    if row['status'] == 'QUARANTINED':
        require(level == row['level_gate'] == metrics['level_gate'] == 'QUARANTINED_GROSS_SATURATION', 'Quarantine level-gate evidence differs')


def context(ev):
    contract = ev.read(REPORT / 'h2/execution_contract.json')
    primary_paths = {'scene_manifest': BANK / 'SCENE_MANIFEST.json', 'sentinel_plan': REPORT / 'SENTINEL_PLAN.json',
                     'dry_plan': REPORT / 'DRY_CONTROL_PLAN.json', 'output_policy': REPORT / 'OUTPUT_LEVEL_POLICY.json'}
    join_primary_bindings(ev, contract, primary_paths)
    baseline = ev.read(contract['baseline']['baseline_manifest']['path'], contract['baseline']['baseline_manifest']['sha256'])
    fix = ev.read(contract['baseline']['durability_fix']['path'], contract['baseline']['durability_fix']['sha256'])
    require(Path(contract['baseline']['durability_fix']['path']).resolve() == (SIM / 'staging/s45_h2_fix/v3/FIX_RECEIPT.json').resolve(), 'Expected active v3 repair')
    require(fix['schema'] == 'jp_s45_h2_durability_fix_v3' and fix['status'] == 'PASS_MODEL_FREE_REGRESSIONS', 'Repair not qualified')
    current_sources = {str(Path(x['path']).resolve()): x for x in contract['baseline']['source_identities']}
    changes = {str(Path(x['path']).resolve()): x for x in fix['changed_sources']}
    require({Path(p).name for p in changes} == {'runtime.py', 'cli.py'}, 'Unexpected scientific code change set')
    for source in baseline['source_bindings']:
        p = str(Path(source['path']).resolve()); expected = source['sha256']
        if p in changes:
            require(changes[p]['before_sha256'] == expected, 'Wrong original source baseline')
            ev.ref(changes[p]['original_backup']); expected = changes[p]['after']['sha256']
        require(current_sources[p]['sha256'] == expected, 'Baseline source identity differs')
    for source in contract['code'] + contract['baseline']['source_identities']:
        ev.ref(source)
    science = {k: v for k, v in baseline['config'].items() if k not in ('session_root', 'profile_root')}
    require(science == fix['scientific_config'] == contract['baseline']['scientific_config'], 'Scientific configuration differs')
    require(contract['reserve_jobs'] == 0 and contract['scientific_policy_changed'] is False, 'Reserve/scientific policy changed')
    bank = ev.read(BANK / 'SCENE_MANIFEST.json'); plan = ev.read(REPORT / 'SENTINEL_PLAN.json'); dry = ev.read(REPORT / 'DRY_CONTROL_PLAN.json')
    join_primary_bindings(ev, contract, primary_paths, dry)
    selected = ev.read(REPORT / 'ACCEPTED_CAPTURES.json'); policy = ev.read(REPORT / 'OUTPUT_LEVEL_POLICY.json')
    all_scenes = {x['case_id']: x for x in bank['scenes']}
    require(len(plan['scene_ids']) == len(set(plan['scene_ids'])) == 24, 'Sentinel count differs')
    scenes = {cid: all_scenes[cid] for cid in plan['scene_ids']}
    require(all(s['split'] == 'development' and s['task_scoring_allowed'] is True for s in scenes.values()), 'Reserve or disabled sentinel')
    controls = {x['control_id']: x for x in dry['identity']['controls']}
    require(len(controls) == dry['count'] == 24 and set(controls) == set(dry['control_ids']), 'Dry control count differs')
    require(all(c['source']['split'] == 'development' and c['source']['usage'] == 'probe' for c in controls.values()), 'Reserve/non-probe dry input')
    return contract, science, scenes, controls, {s['case_id']: s for s in selected['accepted']}, policy


def check_job(ev, path, row, contract, science, scenes, controls, selected, policy):
    cid, stream, kind = row['case_id'], row['stream'], row['kind']
    require(row['identity']['contract_sha256'] == stable(contract) and row['job_key'] == stable(row['identity']), 'Job identity differs')
    require(row['identity']['id'] == cid and row['identity']['stream'] == stream and row['identity']['kind'] == kind, 'Identity fields differ')
    require(row['identity']['input_provenance'] == row['input_provenance'] and row['identity']['raw_audio_sha256'] == row['raw_audio']['sha256'], 'Input provenance differs')
    require(row['labels_or_transcripts_sent_to_model'] is False, 'Truth exclusion not recorded')
    raw_binding = ev.ref(row['raw_audio'])
    if kind == 'outputs':
        require(cid in scenes and stream in ('O0', 'O1'), 'Unexpected output job')
        scene = scenes[cid]; selection = selected[cid]
        capture = ev.read(row['input_provenance']['case_result']['path'], row['input_provenance']['case_result']['sha256'])
        require(row['input_provenance']['case_result']['sha256'] == selection['case_result']['sha256'], 'H2 selected a different take')
        require(capture['status'] == 'PASS' and capture['output_audio'][stream]['sha256'] == raw_binding['sha256'], 'Raw output not from accepted PASS')
        require(capture['input_scene_sha256'] == scene['canonical_audio']['sha256'] and capture['recipe'] == policy['hardware_recipe'], 'Capture input/recipe differs')
        gain = policy['fixed_host_gain'][stream]
        segments = scene['segments']
    else:
        require(kind == 'dry' and cid in controls and stream == 'DRY', 'Unexpected dry job')
        control = controls[cid]; source = control['source']
        require(row['input_provenance'] == {'dry_control': control}, 'Dry control identity differs')
        require(raw_binding['sha256'] == source['decoded_16k_binding']['sha256'], 'Wrong dry source')
        gain = control['fixed_gain_scalar']
        segments = [{'source_start_sample': 0, 'source_stop_sample': source['samples'], 'speaker_key': source['identity'], 'transcript': source['transcript']}]
        scene = {'all_speaker_reference_complete': True, 'transcript_valid': True, 'overlap_intervals': []}
    require(row['identity']['gain_scalar'] == gain, 'Fixed gain differs')
    metric_binding = ev.ref(row['metrics_binding']); metrics = ev.read(metric_binding['path'])
    alignment = level = None
    if kind == 'outputs':
        provenance = metrics['analysis_provenance']
        analysis_path = Path(row['input_provenance']['case_result']['path']).parent / 's45_analysis_receipt.json'
        analysis_receipt = ev.read(analysis_path)
        require(analysis_receipt['case_result']['sha256'] == row['input_provenance']['case_result']['sha256'], 'Audio analysis selected different capture')
        audio_binding = ev.ref(provenance['audio_metrics']); audio_metrics = ev.read(audio_binding['path'])
        require(audio_binding['sha256'] == analysis_receipt['audio_metrics']['sha256'], 'Audio analysis binding differs')
        require(audio_metrics['input_scene_sha256'] == capture['input_scene_sha256'] and audio_metrics['input_payload'] == capture['payload'], 'Audio alignment input differs')
        level = analysis_receipt['task_use_by_output'][stream]
        require(level in ('QUARANTINED_GROSS_SATURATION', 'LIMITED_RESIDUAL_RAILS', 'LEVEL_GATE_NO_RAILS'), 'Unknown level disposition')
        require((level == 'QUARANTINED_GROSS_SATURATION') == (row['status'] == 'QUARANTINED'), 'Gross output quarantine was bypassed or invented')
        if provenance.get('alignment_mapping'):
            ev.ref(provenance['alignment_mapping'])
            mapping = ev.read(provenance['alignment_mapping']['path']).get(cid, {}).get(stream)
        else:
            mapping = audio_metrics['output_alignment'].get(stream)
        alignment = qualified_alignment(capture, mapping)
    require(row['analysis_identity'] == stable({'alignment': alignment, 'provenance': metrics['analysis_provenance'], 'code': contract['code']}), 'Analysis identity differs')
    verify_metric_identity(row, metrics, gain, level)
    if row['status'] == 'QUARANTINED':
        require(kind == 'outputs' and row['model_invocations'] == 0 and not row.get('owned_process_pid'), 'Quarantine contains a model invocation')
        require(metrics['state'] == 'NOT_RUN_QUARANTINED' and metrics['model_invocations'] == 0 and metrics['text']['status'] == 'QUARANTINED', 'Quarantine metric differs')
        require(metrics['text']['wer'] is None and metrics['text']['cer'] is None, 'Quarantined output scored')
        return {'case_id': cid, 'stream': stream, 'kind': kind, 'status': 'VERIFIED_QUARANTINED', 'receipt': ev.bind(path)}
    require(row['status'] == 'COMPLETE' and row['exit_code'] == 0 and not row.get('error'), 'Native job did not complete successfully')
    require(row['initial_profile_files'] == 0 and row['external_asset_hash_passes'] == 0 and row['model_success_has_internal_asset_validation'] is True, 'Execution isolation/asset policy differs')
    for k in ('session_summary_binding', 'events_binding', 'execution_release'):
        ev.ref(row[k])
    release = ev.read(row['execution_release']['path'])
    require(release['status'] == 'AUTHORIZED_OFFLINE_H2' and release['allow_during_physical_capture'] is False, 'Unexpected model execution release')
    adapter_binding = ev.ref(row['adapter']['output_binding']); spool_binding = ev.ref(row['completion_evidence']['journal'])
    summary = ev.read(row['session_summary_binding']['path']); folder = Path(row['session_dir'])
    require(Path(row['session_summary_binding']['path']).parent == folder and Path(row['events_binding']['path']).parent == folder and Path(spool_binding['path']).parent == folder, 'Native session paths differ')
    require(not list(folder.glob('.session_summary.json.*.tmp')), 'Unfinished atomic summary export')
    events = [json.loads(line) for line in Path(row['events_binding']['path']).read_text(encoding='utf-8').splitlines() if line.strip()]
    stdout_path = path.parent / 'stdout.jsonl'; ev.bind(stdout_path); ev.bind(path.parent / 'stderr.txt')
    stdout = json_stream(stdout_path.read_text(encoding='utf-8-sig'))
    labels = verify_event_metrics(events, summary, metrics, stdout)
    assets = [{'component_id': a['component_id'], 'sha256': a['sha256']} for a in science['assets']]
    require(summary['assets'] == assets and len(assets) == 8, 'Native assets differ from S0')
    require(summary['scientific_policy'] == {k: science[k] for k in summary['scientific_policy']}, 'Native science differs')
    require(summary['xvf']['result_effects_enabled'] is False, 'XVF effects unexpectedly enabled inside H2')
    raw, rr = sf.read(raw_binding['path'], dtype='float32', always_2d=True)
    adapter, ar = sf.read(adapter_binding['path'], dtype='float32', always_2d=True)
    require(rr == ar == 16000, 'Sample rate differs')
    pcm = Path(spool_binding['path']).read_bytes(); quantized = verify_audio(raw, adapter, pcm, gain)
    require(row['adapter']['samples'] == row['completion_evidence']['exact_full_pcm16_samples'] == len(quantized), 'Sample denominator differs')
    require(row['completion_evidence']['native_summary'] is True and row['completion_evidence']['unique_completion_event'] is True, 'Native completion proof missing')
    telem = summary['telemetry']; duration = len(quantized) / 16000
    require(telem['source_duration_sec'] == telem['speaker_cursor_sec'] == telem['asr_cursor_sec'] == duration, 'Incomplete source cursor')
    require(abs(telem['speaker_analyzed_through_sec'] + telem['speaker_unanalyzed_short_tail_sec'] - duration) < 1e-8, 'Short-tail accounting differs')
    require(row['argv'][1:4] == ['-m', 'app.edge_speech_pipeline', 'file'] and row['argv'][-1] == '--accelerated' and row['argv'][4] == adapter_binding['path'], 'Model input argv differs')
    gate = verify_gate(quantized, events, metrics, science)
    require(metrics['reference_scope']['reserve_task_scored'] is False, 'Reserve task score claimed')
    complete_reference = scene['all_speaker_reference_complete']
    require(metrics['reference_scope']['all_speaker_reference_complete'] == complete_reference, 'Reference completeness differs')
    if not complete_reference:
        require(metrics['text']['status'] == 'LIMITED' and 'reference_turn_evidence' not in metrics['speaker'], 'Incomplete ambient reference scored as complete')
    if scene.get('overlap_intervals'):
        require(metrics['text']['status'] == 'LIMITED', 'Overlap ordinary WER not limited')
    align = metrics['source_to_output_turn_scoring']; offset = align.get('alignment_offset_s', 0.)
    if kind == 'outputs':
        for b in metrics['analysis_provenance'].values():
            if b:
                ev.ref(b)
        if align['status'] == 'LIMITED':
            require('reference_turn_evidence' not in metrics['speaker'], 'Unqualified alignment used for turn labels')
        require(({k: v for k, v in align.items() if k != 'status'} if align['status'] == 'DESCRIPTIVE_FILE_SUPPORT_ONLY' else None) == alignment, 'Turn label time origin differs from measured alignment')
    turns = verify_turns(events, metrics, segments, offset)
    require(metrics['fixed_host_gain'] == gain and metrics['case_id'] == cid and metrics['stream'] == stream, 'Metric output identity differs')
    return {'case_id': cid, 'stream': stream, 'kind': kind, 'status': 'VERIFIED_NATIVE_COMPLETE', 'receipt': ev.bind(path),
            'owned_process_pid': row['owned_process_pid'], 'adapter_path': adapter_binding['path'], 'samples': len(quantized),
            'model_wall_s': row['model_wall_s'], 'session_elapsed_s': telem['elapsed_wall_sec'], 'speaker_short_tail_s': telem['speaker_unanalyzed_short_tail_sec'],
            'labels': labels, 'gate_counts': gate, 'return_evidence': turns, 'text_status': metrics['text']['status']}


def process_snapshot(rows):
    pids = sorted({int(r['owned_process_pid']) for r in rows if r['status'] == 'VERIFIED_NATIVE_COMPLETE'})
    if not pids:
        return {'observed_utc': utc(), 'processes': [], 'completed_job_pid_count': 0}
    query = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)\n$ids=@(" + ','.join(map(str, pids)) + ")\n@{observed_utc=[DateTime]::UtcNow.ToString('o');processes=@(Get-CimInstance Win32_Process | Where-Object {$_.ProcessId -in $ids} | Select-Object ProcessId,ParentProcessId,Name,CommandLine)} | ConvertTo-Json -Depth 4 -Compress"
    encoded = base64.b64encode(query.encode('utf-16le')).decode()
    output = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded], capture_output=True, check=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    snapshot = json.loads(output.stdout.decode('utf-8-sig'))
    for process in snapshot['processes']:
        require(process.get('CommandLine'), 'Recorded PID exists but its identity is unavailable')
        matching = [r for r in rows if r.get('owned_process_pid') == process['ProcessId']]
        require(not any(r['adapter_path'].casefold() in process['CommandLine'].casefold() for r in matching), 'Completed native model PID is still active')
    snapshot['completed_job_pid_count'] = len(pids)
    snapshot['scope'] = 'Completed job PIDs only; known unrelated PID reuse is retained, and later pending model jobs are not claimed closed.'
    return snapshot


def review():
    ev = Evidence(); contract, science, scenes, controls, selected, policy = context(ev)
    test_receipt_path = SIM / 'staging/s45_native_review/v2/TEST_RECEIPT.json'
    test_receipt = ev.read(test_receipt_path)
    require(test_receipt['status'] == 'PASS_MODEL_FREE_FIXTURES' and test_receipt['tests_passed'] == test_receipt['tests_run'] and test_receipt['failures'] == 0, 'Review tests are not recorded PASS')
    for name in ('s45_native_review.py', 'test_s45_native_review.py', 'README_S45_NATIVE_REVIEW.md'):
        require(Path(test_receipt['bindings'][name]['path']).resolve() == (SIM / 'scripts' / name).resolve(), 'Test receipt binding path differs')
        ev.ref(test_receipt['bindings'][name])
    rows, errors = [], []
    expected = [(REPORT / 'h2' / cid / stream / 'run_receipt.json', cid, stream, 'outputs') for cid in scenes for stream in ('O0', 'O1')]
    expected += [(REPORT / 'h2_dry' / cid / 'run_receipt.json', cid, 'DRY', 'dry') for cid in controls]
    observed = set((REPORT / 'h2').glob('*/*/run_receipt.json')) | set((REPORT / 'h2_dry').glob('*/run_receipt.json'))
    require(observed <= {x[0] for x in expected}, 'Unexpected or reserve model receipt path')
    for path, cid, stream, kind in expected:
        base = {'case_id': cid, 'stream': stream, 'kind': kind}
        if not path.exists():
            rows.append({**base, 'status': 'PENDING_NO_RECEIPT'}); continue
        try:
            raw = path.read_bytes(); receipt = json.loads(raw.decode('utf-8-sig'))
        except (OSError, ValueError) as exc:
            rows.append({**base, 'status': 'PENDING_TRANSITIONAL_RECEIPT', 'observation': str(exc)}); continue
        if receipt.get('status') not in ('COMPLETE', 'QUARANTINED'):
            rows.append({**base, 'status': 'PENDING_OR_UNSUCCESSFUL', 'recorded_status': receipt.get('status')}); continue
        try:
            ev.bind(path, hashlib.sha256(raw).hexdigest())
            require((receipt['case_id'], receipt['stream'], receipt['kind']) == (cid, stream, kind), 'Job path/identity mismatch')
            rows.append(check_job(ev, path, receipt, contract, science, scenes, controls, selected, policy))
        except Exception as exc:
            errors.append({'case_id': cid, 'stream': stream, 'error': type(exc).__name__ + ': ' + str(exc)})
            rows.append({**base, 'status': 'REVIEW_FAILED', 'error': errors[-1]['error']})
    snapshot = process_snapshot(rows)
    counts = {kind: dict(Counter(r['status'] for r in rows if r['kind'] == kind)) for kind in ('outputs', 'dry')}
    terminal = sum(r['status'] in ('VERIFIED_NATIVE_COMPLETE', 'VERIFIED_QUARANTINED') for r in rows)
    for path in ev.rows:
        ev.bind(path)
    return {'schema': 'jp_s45_native_review_v1', 'run_id': '20260909T031300Z', 'observed_utc': utc(),
            'status': 'FAIL_EVIDENCE_REVIEW' if errors else 'PASS_ALL_72_DISPOSITIONS_REVIEWED' if terminal == 72 else 'PARTIAL_NATIVE_REVIEW',
            'intended_outputs': 48, 'intended_dry': 24, 'counts': counts, 'verified_terminal_jobs': terminal, 'errors': errors,
            'execution_contract_sha256': stable(contract), 'active_fix': contract['baseline']['durability_fix'],
            'review_test_receipt': ev.bind(test_receipt_path), 'review_tests_passed': test_receipt['tests_passed'],
            'scientific_config_matches_S0': True, 'model_assets_rehashed': False, 'reserve_task_results_read': False,
            'process_snapshot': snapshot, 'jobs': rows, 'consumed_bindings': list(ev.rows.values()),
            'review_code': ev.bind(Path(__file__)),
            'scope': 'Independent native completion, full gained adapter/journal samples, gate/label evidence and provenance. Pending files are not failures; no model/hardware/scorer execution. Labels are session-local emitted evidence, not reconciled identities, names, or DER. No causal output winner inferred.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--final', action='store_true', help='Exclusively create final review; requires all72 intended jobs verified terminal')
    args = parser.parse_args()
    result = review()
    path = REPORT / ('H2_FINAL_NATIVE_REVIEW.json' if args.final else 'H2_NATIVE_REVIEW_PROGRESS.json')
    if args.final:
        require(result['status'] == 'PASS_ALL_72_DISPOSITIONS_REVIEWED', 'Final review requires all48 outputs and24 dry jobs; preserve partial progress instead')
        with path.open('x', encoding='utf-8') as f:
            json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    else:
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8'); temporary.replace(path)
    print(json.dumps({'status': result['status'], 'counts': result['counts'], 'errors': result['errors'], 'output': str(path)}, indent=2))
    return 2 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
