"""Bind all 360 development output jobs and freeze S5 protocols. README_S5.md."""
from __future__ import annotations
import collections
import json
from pathlib import Path
import subprocess
import zipfile
import xml.etree.ElementTree as ET
import psutil
from s5_common import *
from s45_h2_run import baseline_contract, accepted_for, load_alignment, verify_native_completion
from s4_h2_run import fixed_gain_copy
from s45_final_audit import ssd_and_space

def immutable(path, value):
    if path.exists():
        assert read(path) == value, 'Frozen S5 artifact differs: ' + str(path)
    else:
        save(path, value)

def protocol():
    return {
        'schema': 'jp_s5_scoring_protocol_v1', 'stage_start_utc': START.isoformat(),
        'prior_outcomes_known': '24 development scenes / 48 S4.5 output jobs previously inspected; not blind preregistration.',
        'population_expected': {'primary_nonoverlap': 117, 'overlap_complete': 36, 'ambient_incomplete': 19, 'strict_empty': 8},
        'development_scenes': 180, 'output_jobs': 360, 'reserve_task_jobs': 0,
        'real_noise_overlapping_diagnostic_scenes': 39,
        'recipes': {'O0': {'source': 'recorded PCM24 ASR output', 'capture_AEC_ASROUTGAIN': 1,
                           'host_gain_scalar': GAINS['O0'], 'host_gain_db': 3, 'applications': 1},
                    'O1': {'source': 'recorded PCM24 postprocessed auto output', 'host_gain_scalar': 1, 'applications': 1}},
        'adapter': '16 kHz mono FLOAT, fixed scalar once; unchanged native PCM16 conversion; no normalization/resampling/enhancement/repair.',
        'normalization': 'lowercase_remove_ascii_punctuation_collapse_whitespace_v1; delete string.punctuation; no number/contraction expansion; CER removes normalized spaces',
        'hypothesis': 'Native final raw text in emitted order, not display_text or punctuation output',
        'primary': 'Exact S/D/I and reference words/CER; sum counts for pooled rates; scene macro and equal-room separately; empty hypotheses retained',
        'overlap': {'implementation': 'MeetEval 0.4.3 MIMO, isolated analysis environment',
                    'references': 'speaker_key -> original whole utterances ordered by source_start_sample; boundaries/repetitions retained',
                    'hypothesis': 'ONE_OUTPUT -> joined native finals; reference_sort=False; hypothesis_sort=False',
                    'scope': 'Order-tolerant multi-reference-speaker utterance serialization to one output stream, not free word reordering and not time-constrained WER',
                    'bounded_fallback': 'If pinned backend cannot be built after bounded local attempt, mark MIMO unavailable/LIMITED; never substitute ordinary concatenated WER'},
        'cpwer': {'implementation': 'MeetEval 0.4.3 cp_word_error_rate, one global assignment per scene',
                  'references': 'speaker_key -> joined ordered original utterances',
                  'hypotheses': 'Actual emitted final label -> joined native final raw text; no truth-driven label merging',
                  'scope': 'Final-snapshot attributed transcript quality; missing/extra streams retained; values above 100% valid; not DER or reconciled identity'},
        'ambient': 'Unknown speech excluded from all-speaker WER; target-only whole-output diagnostic separate and LIMITED; do not label unknown words false',
        'strict_empty': 'Eight controls: insertion count, affected fraction and words/decoded minute; WER undefined; vocals=N is source annotation only',
        'timing': {'clocks': ['source schedule', 'retained RIR origin', 'microphone capture', 'processed output', 'host availability'],
                   'rir_samples': 800, 'sample_rate': 16000,
                   'mapping': 'Saved capture offset and output lag only; activity ranges already include 800 RIR samples; add it once only to whole-source bounds. No refit or invented missing lag.',
                   'confidence': 'Estimated numerical source activity and file support, not phonetic word boundaries or calibrated physical latency'},
        'support': {'noise_activity': 'Exact prepared crop; unchanged20ms RMS >=max(-50dBFS, crop-frame-p95 minus25dB); shift source_start+800 once',
                    'noise_schedule': 'Full convolution support retained separately as possible-tail envelope',
                    'quiet': 'Outside all scheduled convolution support, not merely below activity threshold',
                    'masks': 'Frozen from sources/schedules, independent of O0/O1 outcomes; noise-active/speech-active/overlap/quiet separate',
                    'segmentation': 'Actual emitted0.75s hops with44 tail frames (~0.7425s); support intersection and boundary intervals, not exact phonetic latency',
                    'embedding': 'Actual emitted windows;0.5s duration and0.25s hop from baseline; report strict-active and single-envelope containment, union/total duration, crossing boundaries, missing evidence',
                    'gates': 'Reconstruct from exact native PCM16 and current exported segmentation state; reason categories overlap; unlogged rejects unavailable',
                    'returns': 'Dominant actual label with ties/missing retained; consistent/inconsistent/unknown denominator; ordinary/silent-seat/overlap/short separated'},
        'duration_bins_seconds': ['<1', '1<=duration<2', '>=2'],
        'duration_scope': 'Report original whole-clip and estimated active duration separately; known empty Common Voice short bins retained',
        'direction': 'Shared hardware trace once per scene, never separate O0/O1 treatment effect. Manual angle uncertainty +/-5 degrees is not accuracy/default tolerance/jitter.',
        'audio_levels': 'Raw and fixed-adapter RMS/peaks/rails separate; source support/active/quiet/padding distinguish; mixture energy is not target-only SNR',
        'failures': 'One identical retry maximum with preserved attempts; native completion plus exact full PCM16 required. Failed rows not zero error. Complete-pair primary and failed-empty-output sensitivity.',
        'uncertainty': {'replicates': 2000, 'seed': 20260909,
                        'blocks': 'Connected components of explicit matched_pair_id + matched_group_id across all development, retain primary members; resample blocks within each of4 fixed rooms',
                        'expected_primary_blocks': 85,
                        'interval': 'Paired O1-minus-O0 pooled WER difference, conditional on observed development support; not independent room/population CI',
                        'sensitivity': ['equal-room summary', 'leave-one-room-out', 'leave-one-speaker-connected-component-out',
                                        'all source/text/book/RIR/noise dependency graph connectivity'],
                        'warning': 'Speakers/text/books/RIR/noise cross matched blocks; collapsing all dependencies can produce one component. Four rooms do not support broad room-population inference.'},
        'decision': {'practical_wer_pp': 1.0, 'sensitivity_pp': [0.5, 2.0],
                     'priority': 'Reliable complete input and word usability first; quantify competing continuity/short-turn/noise/headroom/workload costs. No opaque combined score.',
                     'tie_default': 'O0 if word difference is practically small/uncertain and no contrary material diagnostic; engineering preference for preserved headroom and fewer transformations, not proven superiority.',
                     'tradeoff': 'Choose provisional default with explicit cost if word and speaker evidence disagree; keep other fallback. No split paths or mode switching implemented.',
                     'requirements': 'Thresholds are S5 planning conventions, not validated product/runtime thresholds. Nonsignificance is not equivalence.'},
        'optional_representation': {'window_s': 0.5, 'maximum_windows_per_participant_scene': 4, 'maximum_paired_windows': 1000,
                                    'selection': 'Deterministic development reference-aligned intervals before cosine scores; same source intervals per output mapped by saved offsets, exclude ambiguous overlap/boundaries',
                                    'comparisons': 'Same-person different-utterance genuine; deterministic balanced different-person impostors; no duplicate clip/RIR trials',
                                    'scope': 'Unchanged backend/preprocessing; oracle-window distribution diagnostic only; no tuning/enrollment/vector feedback'},
        'resources': {'model_workers': 1, 'provider': 'unchanged CPU baseline', 'parallelism_parity_test': 'Not needed: no second canonical worker',
                      'analysis_workers_max': 6, 'process_tree_ram_gib_max': 40, 'available_os_ram_gib_min': 8,
                      'free_gib_min': {'C': 50, 'G': 75}, 'new_outputs_gib_max': 40,
                      'heartbeat_s': 20, 'job_timeout_s': 240, 'maximum_retries_per_job': 1,
                      'deadline_utc': DEADLINE.isoformat(), 'launch_cutoff_utc': LAUNCH_CUTOFF.isoformat()},
        'unsupported': ['full DER/JER without defensible hypothesis activity timeline', 'enrolled-name accuracy without enrollment',
                        'precise live word/name latency', 'CM5 resource fit', 'general held-out room or source performance'],
    }

DECISION = """# S5 decision protocol, frozen before new full-panel comparisons

The 24 S4.5 development scenes were already inspected. This is a complete
development comparison, not blind preregistration or a pristine test set.

Primary word evidence is pooled ordinary WER across117 complete-reference,
nonoverlap scenes. Report exact paired counts, the2000-replicate conditional
matched-block interval, room/source/dependency sensitivity, and practical
references of1.0 absolute WER point plus0.5/2.0 sensitivity. These are new
planning conventions, not validated product requirements. A non-significant
difference is not equivalence.

Reliability and usable words have first priority for an audio benchmark default.
Evaluate overlap words, actual final-snapshot cpWER, short-turn segmentation,
embedding evidence/anonymous continuity, ambient/strict-control behavior,
rails/headroom and workload alongside them. Use no opaque combined score.
If meaningful word benefit opposes material continuity/noise/reliability cost,
declare and quantify the tradeoff and choose one provisional default explicitly.
If no clear practical word advantage is supported and neither has a decisive
functional drawback, prefer O0 as an engineering default for preserved raw
headroom and fewer processing stages; do not call it a proven winner.

Each choice retains the other output as fallback. Neither choice certifies
diarization, naming, arrows, live latency, CM5 deployment, new voices or rooms.
No reserve result may break a tie. No split ASR/embedding input or automatic
mode switch is implemented. Stop after the S5 handoff.
"""

def prepare():
    REPORT.mkdir(parents=True, exist_ok=True)
    PAYLOAD.mkdir(parents=True, exist_ok=True)
    assert not (REPORT / 'JOB_MANIFEST.json').exists(), 'Preparation already frozen; run the resumable runner instead'
    current = resources(scan=True)
    save(REPORT / 'RESOURCE_PREFLIGHT.json', {'status': 'PASS', **current, 'ssd': ssd_and_space(),
          'cpu_logical': psutil.cpu_count(), 'cpu_physical': psutil.cpu_count(logical=False),
          'memory': dict(psutil.virtual_memory()._asdict()), 'model_workers': 1})
    m = manifest()
    guard = DevelopmentGuard(m['scenes'], 'prepare')
    assert len(guard.allowed) == 180 and len(m['scenes']) == 240
    ids = sorted(guard.allowed)
    counts = dict(collections.Counter(population(guard.scenes[c]) for c in ids))
    assert counts == protocol()['population_expected']
    baseline = baseline_contract()
    old_contract = read(PRIOR / 'h2/execution_contract.json')
    assert baseline == old_contract['baseline'], 'Current scientific/code baseline differs from reusable jobs'
    policy = read(PRIOR / 'OUTPUT_LEVEL_POLICY.json')
    assert policy['fixed_host_gain'] == GAINS and policy['frozen']
    selected = accepted_for(ids, guard.scenes, policy)
    workbook = bind(WORKBOOK, 'b9427c76a98965ab418ef252ec0d480b979945d85d4aa0e4e2de6dd41514a67b')
    with zipfile.ZipFile(WORKBOOK) as z:
        doc = ET.fromstring(z.read('word/document.xml'))
    paragraphs = [''.join(p.itertext()) for p in doc.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')]
    (REPORT / 'WORKBOOK_CONTEXT.txt').write_text('\n'.join(paragraphs), encoding='utf-8')
    immutable(REPORT / 'SCORING_PROTOCOL.json', protocol())
    (REPORT / 'DECISION_PROTOCOL.md').write_text(DECISION, encoding='utf-8')
    immutable(REPORT / 'OUTPUT_RECIPES_V1.json', {'fixed_host_gain': GAINS, 'prior_frozen_capture_policy': policy,
              'normalization': False, 'gain_once_only': True, 'raw_audio_preserved': True})
    code = [bind(SIM / 'scripts' / name) for name in ('s5_common.py', 's5_prepare.py', 's5_runner.py',
             's45_h2_run.py', 's4_h2_run.py', 's4_h2_analysis.py', 's4_common.py')]
    contract = {'schema': 'jp_s5_execution_contract_v1', 'baseline': baseline, 'code': code,
                'scoring_protocol': bind(REPORT / 'SCORING_PROTOCOL.json'),
                'decision_protocol': bind(REPORT / 'DECISION_PROTOCOL.md'),
                'recipes': bind(REPORT / 'OUTPUT_RECIPES_V1.json'),
                'scene_manifest': bind(BANK / 'SCENE_MANIFEST.json', MANIFEST_SHA),
                'accepted_selection': bind(PRIOR / 'ACCEPTED_CAPTURES.json'), 'workbook': workbook,
                'historical_contract': bind(PRIOR / 'h2/execution_contract.json'), 'limits': protocol()['resources']}
    cp = REPORT / 'execution_contract.json'
    if cp.exists() and read(cp) != contract:
        assert not list((REPORT / 'h2').glob('*/O*/run_receipt.json')), 'No contract revision after jobs'
        prior_contract = read(cp)
        save(REPORT / 'preflight_archive' / ('execution_contract_' + stable_hash(prior_contract) + '.json'), prior_contract)
        save(REPORT / 'PREFLIGHT_CORRECTION.json', {
             'utc': now(), 'reason': 'Removed overstrict zero PCM16-clamp assertion: unchanged native converter clamps raw positive PCM24 rail/near-rail samples. These are retained and reported, not new gain clipping or exclusion.',
             'new_models_before_correction': 0, 'new_full_panel_comparisons_before_correction': 0,
             'scientific_protocol_changed': False, 'prior_contract_sha256': stable_hash(prior_contract)})
        save(cp, contract)
    else:
        immutable(cp, contract)
    jobs = []
    for i, cid in enumerate(ids):
        guard.require(cid, 'accepted_output_verification')
        scene, sel = guard.scenes[cid], selected[cid]
        order = ['O0', 'O1'] if i % 2 == 0 else ['O1', 'O0']
        for stream in order:
            raw = bind(sel['folder'] / (stream + '.wav'), sel['capture']['output_audio'][stream]['sha256'])
            alignment, ab, eb, gate = load_alignment(None, cid, stream, sel)
            identity = {'contract_sha256': stable_hash(contract), 'case_id': cid, 'stream': stream,
                        'raw_audio_sha256': raw['sha256'], 'gain_scalar': GAINS[stream],
                        'input_case_result_sha256': sel['case_result_binding']['sha256'],
                        'scene_reference_sha256': stable_hash(scene)}
            job = {'case_id': cid, 'stream': stream, 'population': population(scene),
                   'order_index': len(jobs), 'pair_order': order, 'identity': identity, 'job_key': stable_hash(identity),
                   'raw_audio': raw, 'gain': GAINS[stream], 'level_gate': gate, 'alignment': alignment,
                   'input_provenance': {'case_result': sel['case_result_binding'], 'accepted_record': sel['selection_record']},
                   'analysis_provenance': {'audio_metrics': ab, 'alignment_mapping': eb},
                   'report_dir': str(REPORT / 'h2' / cid / stream),
                   'payload_root': str(PAYLOAD / 'h2' / cid / stream), 'reuse': None}
            oldpath = PRIOR / 'h2' / cid / stream / 'run_receipt.json'
            if oldpath.exists():
                guard.require(cid, 'reuse_native_verification')
                old = read(oldpath)
                assert old['status'] == 'COMPLETE' and old['exit_code'] == 0
                assert old['identity']['contract_sha256'] == stable_hash(old_contract)
                assert old['raw_audio'] == raw and old['identity']['gain_scalar'] == GAINS[stream]
                assert old['input_provenance'] == job['input_provenance']
                assert old['initial_profile_files'] == 0 and old['labels_or_transcripts_sent_to_model'] is False
                assert old['model_success_has_internal_asset_validation'] is True
                for key in ('metrics_binding', 'session_summary_binding', 'events_binding'):
                    bind(old[key]['path'], old[key]['sha256'])
                ap = old['adapter']['output_binding']
                bind(ap['path'], ap['sha256'])
                adapter = fixed_gain_copy(raw['path'], ap['path'], GAINS[stream])
                assert adapter['journal_clip_input_samples'] == old['adapter']['journal_clip_input_samples']
                completion = verify_native_completion(Path(old['session_dir']), Path(ap['path']))
                job['reuse'] = {'receipt': bind(oldpath), 'native_completion_reverified': completion,
                                'same_audio_gain_assets_config_provider_code_lifecycle': True,
                                'prior_adapter_exact_array_reverified': True}
            jobs.append(job)
        if (i + 1) % 15 == 0:
            print(json.dumps({'phase': 'BINDING', 'scenes': i + 1, 'total': 180}), flush=True)
            guard.flush()
    assert len(jobs) == 360 and sum(j['reuse'] is not None for j in jobs) == 48
    immutable(REPORT / 'JOB_MANIFEST.json', {'schema': 'jp_s5_jobs_v1', 'created_utc': now(),
              'development_ids': ids, 'expected_population': counts, 'jobs': jobs,
              'requested': 360, 'compatible_reuse': 48, 'new_planned': 312, 'reserve_jobs': 0,
              'order_rule': 'Sorted scene IDs; alternate O0/O1 then O1/O0 by scene index; one worker'})
    guard.flush()
    save(REPORT / 'run_manifest.json', {'run_id': RUN_ID, 'start_utc': START.isoformat(),
         'deadline_utc': DEADLINE.isoformat(), 'launch_cutoff_utc': LAUNCH_CUTOFF.isoformat(),
         'protocol_frozen_utc': now(), 'contract': bind(REPORT / 'execution_contract.json'),
         'jobs': bind(REPORT / 'JOB_MANIFEST.json'), 'pack_files': [bind(p) for p in sorted(PACK.rglob('*')) if p.is_file()],
         'status': 'BOUND_READY_FOR_H2', 'hardware_invocations': 0})
    print(json.dumps({'status': 'BOUND_READY_FOR_H2', 'jobs': 360, 'reuse': 48, 'new': 312, 'population': counts}), flush=True)

if __name__ == '__main__':
    prepare()
