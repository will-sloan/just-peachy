"""Post-closure S6C paced observations. See README_S6C_PACED_ANALYSIS_V1.md."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / 'reports/S6C/20260910T123540Z'
SCHEMA = 'jp_s6c_paced_observation_analysis.v1'
EPOCH4_SHA = '720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945'
INVENTORY_SOURCE_SHA = '426a4eaada68e51d0e6af6decd8b9b56fa3c9660b3cca005f959862c03177876'
NAME_EMISSION_SHA = 'f3314d18dbd9578a9c2a6bf19b6aabb9306ab2415db9488aeae9fa1968ea2a3e'
SCORER_MAP_SHA = 'ed13643358be9e5d36a8a093a4b7ccac90108f5b4b5cc208d5f80360f49aea8f'
EXECUTION_FIELDS = {'identity_compute_sec', 'policy_compute_sec', 'tracker_compute_sec',
    'scheduler_state_overhead_sec', 'release_watermark_lower_bound_sec',
    'release_after_all_lanes_closed', 'compute_finished_elapsed_sec',
    'modeled_available_at_sec', 'policy_total_sec', 'loaded_elapsed_sec'}

def fail(message):
    raise ValueError(message)

def number(v):
    if type(v) not in (int, float) or not math.isfinite(v):
        fail('Finite numeric observation required')
    return float(v)

def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items() if k not in EXECUTION_FIELDS}
    if isinstance(value, list):
        return [canonical(v) for v in value]
    return value

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def utc_seconds(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        fail('Timezone-aware native event timestamp required')
    return dt.timestamp()

def stats(values):
    present = [number(v) for v in values if v is not None]
    ordered = sorted(present)
    def quantile(q):
        if not ordered:
            return None
        position = (len(ordered) - 1) * q
        a, b = math.floor(position), math.ceil(position)
        return ordered[a] + (ordered[b] - ordered[a]) * (position - a)
    return dict(observed=len(present), missing=len(values)-len(present),
        min=min(present) if present else None, max=max(present) if present else None,
        mean=sum(present)/len(present) if present else None,
        p50=quantile(.5), p95=quantile(.95))

class ExactReader:
    """Cache exact bytes within one cell; never confuse a changed binding with reuse."""
    def __init__(self):
        self.buffers = {}
        self.reads = []

    def raw(self, binding):
        p = Path(binding['path']).resolve()
        key = str(p).casefold()
        expected = (binding['bytes'], binding['sha256'])
        if key in self.buffers:
            old_expected, raw = self.buffers[key]
            if old_expected != expected:
                fail('Conflicting exact artifact bindings')
            return raw
        if type(binding['bytes']) is not int or not 0 <= binding['bytes'] <= 256 * 2**20:
            fail('Bounded exact observation file required')
        raw = p.read_bytes()
        if len(raw) != binding['bytes'] or hashlib.sha256(raw).hexdigest() != binding['sha256']:
            fail('Exact observed bytes differ: ' + str(p))
        self.buffers[key] = (expected, raw)
        self.reads.append(dict(binding=binding, read_bytes=len(raw)))
        return raw

    def json(self, binding):
        return json.loads(self.raw(binding), parse_constant=lambda x: fail('Nonfinite JSON: '+x))

    def lines(self, binding):
        return [json.loads(row, parse_constant=lambda x: fail('Nonfinite JSON: '+x))
            for row in self.raw(binding).decode('utf-8-sig').splitlines() if row.strip()]

def unique_artifact(artifacts, name):
    rows = [b for b in artifacts if Path(b['path']).name == name]
    if len(rows) != 1:
        fail('Exactly one bound artifact required: ' + name)
    return rows[0]

def native_event_observations(events, duration):
    """Keep actual emitted order and distinguish UTC emission from modeled support."""
    starts = [e for e in events if e['event_type'] == 'source_started']
    if len(starts) != 1:
        fail('Exactly one actual source_started event required')
    origin = utc_seconds(starts[0]['wall_time_utc'])
    counts = Counter(e['event_type'] for e in events)
    if counts['session_completed'] != 1 or counts['failure']:
        fail('Native event completion/failure differs')
    emissions = []
    clock_reversals = []
    previous = None
    for i, e in enumerate(events):
        stamp = utc_seconds(e['wall_time_utc'])
        if previous is not None and stamp < previous:
            clock_reversals.append(dict(event_index=i, previous_utc_seconds=previous, utc_seconds=stamp))
        previous = stamp
        kind = e['event_type']
        if kind.startswith('transcript_') or kind == 'identity_decision':
            source = number(e['source_time_sec'])
            if source < 0 or source > duration+1e-6:
                fail('Native emitted source cursor outside exact input')
            emissions.append(dict(event_index=i, event_type=kind,
                emitted_wall_time_utc=e['wall_time_utc'],
                emitted_from_source_started_sec=stamp-origin,
                source_time_sec=source, emission_minus_source_cursor_sec=stamp-origin-source,
                modeled_available_at_sec=e['payload'].get('available_at_sec'), payload=deepcopy(e['payload'])))
    by_kind = {}
    for kind in sorted({r['event_type'] for r in emissions}):
        rows = [r for r in emissions if r['event_type'] == kind]
        by_kind[kind] = dict(count=len(rows),
            elapsed_from_source_started_sec=stats([r['emitted_from_source_started_sec'] for r in rows]),
            emission_minus_source_cursor_sec=stats([r['emission_minus_source_cursor_sec'] for r in rows]))
    return dict(event_counts=dict(counts), source_started=starts[0], emissions=emissions,
        summary=by_kind, wall_timestamp_reversals=clock_reversals,
        scope='Actual native UTC emission order, relative to source_started; publication occurs before the producer sleep. Values are not GUI display, phonetic-onset, hardware DSP or CM5 latency. Wall reversals remain visible; no timing correction or interpolation is applied.')

def trajectory_observations(samples):
    times = []
    process = defaultdict(list)
    telemetry = defaultdict(list)
    backlogs = []
    for row in samples:
        t = number(row['elapsed_from_native_launch_sec'])
        if t < 0 or times and t < times[-1]:
            fail('Nonmonotonic native process observation clock')
        times.append(t)
        for field in ('rss_sum_upper_bound_bytes','private_resident_uss_bytes',
                'windows_private_commit_bytes','cpu_sec','write_bytes','available_ram_bytes'):
            process[field].append(row.get('process', {}).get(field))
        for field in ('source_duration_sec','asr_cursor_sec','speaker_cursor_sec',
                'asr_lag_sec','speaker_lag_sec','audio_frames_dropped',
                'portaudio_input_overflows','raw_capture_reserve_failures'):
            telemetry[field].append(row.get('telemetry', {}).get(field))
        backlogs.append(row.get('event_queue_backlog'))
    if not samples or samples[-1].get('phase') != 'terminal_after_finalization':
        fail('Terminal post-finalization observation required')
    trends = {}
    for field, values in process.items():
        pairs = [(t, number(v)) for t,v in zip(times, values) if v is not None]
        delta = pairs[-1][1]-pairs[0][1] if len(pairs) >= 2 else None
        interval = pairs[-1][0]-pairs[0][0] if len(pairs) >= 2 else None
        trends[field] = dict(**stats(values), first_observed=pairs[0] if pairs else None,
            last_observed=pairs[-1] if pairs else None, sampled_first_to_last_delta=delta,
            sampled_interval_sec=interval,
            sampled_delta_per_sec=delta/interval if interval is not None and interval > 0 else None)
    return dict(samples=len(samples), max_sample_gap_sec=max((b-a for a,b in zip(times,times[1:])),default=None),
        process=trends, telemetry={k:stats(v) for k,v in telemetry.items()},
        event_queue_backlog=stats(backlogs), terminal=samples[-1],
        scope='Observed sample maxima and first-to-last trends; no continuous maxima or leak proof. Native samples begin after model startup. CPU/write deltas are process-tree sampled counters, not additive to wall time; membership changes and missing fields are retained in the original bound trajectory.')

def active_context_observations(events,evidence_policy='dual'):
    """Native gate speech, not reference truth: no_speech_gate is the first rejection."""
    if evidence_policy not in ('dual','short_only','mature_only'):
        fail('Unadmitted evidence-role policy')
    expected_roles={'short','mature'} if evidence_policy=='dual' else {'short'} if evidence_policy=='short_only' else {'mature'}
    by_end = {}; roles = defaultdict(set)
    allowed = {'no_speech_gate','overlap_gate','insufficient_contiguous_audio',
        'below_rms','clipped_window','unclean_window','cadence_budget','admitted'}
    for e in events:
        if e['event_type'] != 'research_embedding_admission':
            continue
        p = e['payload']
        if p['reason'] not in allowed:
            fail('Unadmitted native gate reason')
        end = number(p['source_end_sec'])
        role=p['evidence_kind']
        if role not in ('short','mature') or role in roles[end]:
            fail('Missing, unsupported or duplicate native evidence role')
        roles[end].add(role)
        active = p['reason'] != 'no_speech_gate'
        value = dict(active=active, context_age_sec=p.get('tracking_context_age_sec'),
            context_empty=p.get('tracking_context_empty'), cue_event=p['cue_event'])
        if end in by_end and by_end[end] != value:
            fail('Dual-role speech/shared context differs')
        by_end[end] = value
    if any(v!=expected_roles for v in roles.values()):
        fail('Incomplete registered-role native dispatch')
    all_rows = list(by_end.values())
    active = [v for v in all_rows if v['active']]
    inactive = [v for v in all_rows if not v['active']]
    return dict(shared_dispatches=len(all_rows), native_speech_gate_active=len(active),
        native_speech_gate_inactive=len(inactive),
        all_context_age_sec=stats([r['context_age_sec'] for r in all_rows]),
        active_context_age_sec=stats([r['context_age_sec'] for r in active]),
        inactive_context_age_sec=stats([r['context_age_sec'] for r in inactive]),
        active_empty_context=sum(r['context_empty'] is True for r in active),
        active_context_missing=sum(r['context_age_sec'] is None for r in active),
        scope='One shared source dispatch, deduplicated across short/mature roles. Native speech-gate status is inferred from the pinned first rejection test; overlap remains within active speech. It is not ground-truth activity, per-track age or evidence that the due voice was served.')

def file_binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def save_json(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')
    return file_binding(p)

def load_frozen_modules(spec,reader):
    """Import reviewed pure extraction/policy code; never construct neural models."""
    from importlib.metadata import version
    if version('numpy') != spec['versions']['numpy']:
        fail('Exact native NumPy version required for policy/vector parity')
    root=Path(spec['root']).resolve()
    os.environ['JP_S6C_SIM']=str(SIM)
    for b in spec['execution_files']:
        reader.raw(b)
    for folder in (root/'app',root/'scripts'):
        sys.path.insert(0,str(folder))
    names=('s6c_common','s6c_execution','s6c_replay','s6c_native_replay_v3')
    modules={}
    for name in names:
        mod=importlib.import_module(name)
        if Path(mod.__file__).resolve()!=root/'scripts'/(name+'.py'):
            fail('Frozen analysis import origin differs: '+name)
        modules[name]=mod
    if modules['s6c_common'].SIM!=SIM:
        fail('Frozen common module resolved the wrong study root')
    from edge_speech_pipeline.research_profiles import ResearchProfile,JsonSpatialProvider
    from edge_speech_pipeline.research_identity_v3 import ResearchGallery
    for name in ('edge_speech_pipeline.research_profiles','edge_speech_pipeline.research_identity_v3'):
        if not Path(sys.modules[name].__file__).resolve().is_relative_to(root/'app'):
            fail('Policy import outside actual admitted app')
    return modules,ResearchProfile,JsonSpatialProvider,ResearchGallery

def validate_no_gallery(loads,receipt):
    if loads!=[dict(mode='none',loaded_count=0,private_gallery_accessed=False)] or receipt is not None:
        fail('Exactly one explicit native no-gallery marker and null gallery receipt required')

def validate_gallery_load(load,binding,manifest,maximum):
    if (load['manifest']!=binding or load['gallery_id']!=manifest['gallery_id'] or
        load['backend_sha256']!=manifest['backend_sha256'] or load['dimension']!=192 or
        load['dtype']!='float32' or load['templates']!=manifest['profiles'] or
        load['loaded_count']!=len(manifest['profiles']) or len(manifest['profiles'])>maximum):
        fail('Actual gallery receipt/roster/backend/current profile cap differs')

def validate_provider(provider,binding,rows):
    if provider.sha256!=binding['sha256'] or Path(provider.path).resolve()!=Path(binding['path']).resolve():
        fail('Actual reconstructed cue provider binding differs')
    ordered=sorted(rows,key=lambda r:float(r['available_at_sec']))
    if len(provider.rows)!=len(ordered):
        fail('Actual reconstructed cue row count differs')
    for (available,observation),row in zip(provider.rows,ordered):
        # The original provider reads its path twice. Verify actual in-memory
        # observations as well as its digest against the once-admitted buffer.
        if available!=float(row['available_at_sec']) or asdict(observation)!=asdict(type(observation)(**row)):
            fail('Actual reconstructed cue observations differ from admitted bytes')

def native_prediction(events,summary,job,source_binding,spec,modules,classes,reader,galleries):
    """Reuse the exact native observations and verify emitted logical parity."""
    Profile,Provider,Gallery=classes
    telemetry=summary['telemetry'];scheduler=telemetry['scheduler']
    if summary['state']!='COMPLETED' or scheduler['closed'] is not True or scheduler['pending_events']!=0:
        fail('Native scheduler must be durably closed before conversion')
    for field in ('audio_frames_dropped','portaudio_input_overflows','raw_capture_reserve_failures'):
        if telemetry[field]!=0:
            fail('Native audio loss: '+field)
    vectors,features,observations,seg,asr,costs=modules['s6c_execution'].extract(events)
    evidence=dict(features=features,embedding_observations=observations,segmentation=seg,
        asr_observations=asr,costs=costs)
    profile=Profile.from_dict(job['profile_row']['profile'])
    source=reader.json(job['source'])
    cue=source['telemetry'] if job['profile_row']['cue_condition']=='REAL_ALIGNED_CUES' else None
    if job['profile_row']['cue_condition'] not in ('CUES_OFF','REAL_ALIGNED_CUES'):
        fail('Unsupported native cue condition')
    provider=None
    if cue:
        cue_rows=reader.lines(cue);provider=Provider(Path(cue['path']))
        validate_provider(provider,cue,cue_rows)
    gallery=None
    if job['gallery']:
        manifest=reader.json(job['gallery'])
        if job['gallery']['sha256'] not in galleries:
            galleries[job['gallery']['sha256']]=Gallery(Path(job['gallery']['path']),
                manifest['backend_sha256'],profile.identity.max_gallery_profiles)
        gallery=galleries[job['gallery']['sha256']]
        validate_gallery_load(gallery.receipt,job['gallery'],manifest,profile.identity.max_gallery_profiles)
    value=modules['s6c_replay'].run_policy(profile,provider,evidence,vectors,gallery)
    expected=dict(decisions=[e['payload']['decision'] for e in events if e['event_type']=='speaker_decision'],
        transcript_events=[e['payload'] for e in events if e['event_type'].startswith('transcript_')],
        identity_events=[e['payload'] for e in events if e['event_type']=='identity_decision'])
    difference=modules['s6c_native_replay_v3'].differences
    mismatches=[]
    for field,actual in expected.items():
        mismatches+=difference(canonical(value[field]),canonical(actual),'/'+field,subset=field!='decisions')
    # Independently compare final retained native utterances; policy execution
    # costs and actual release/watermark metadata remain in their own records.
    wanted=[u for u in scheduler['utterances'] if u['is_final']]
    got=[u for u in value['snapshot']['scheduler']['utterances'] if u['is_final']]
    mismatches+=difference(canonical(got),canonical(wanted),'/retained_native_utterances')
    if mismatches:
        return None,dict(status='FAIL',mismatch_count=len(mismatches),mismatches=mismatches)
    identity=dict(schema='jp_s6c_paced_prediction_identity.v1',execution_digest=spec['execution_digest'],
        profile=job['profile_row']['profile'],source=source_binding,canonical_source=job['source'],
        telemetry=cue,cue_condition=job['profile_row']['cue_condition'],gallery=job['gallery'],
        gallery_condition=job['profile_row']['gallery_condition'],enrollment_tier=job['profile_row']['enrollment_tier'],
        repetition=job['repetition'],oracle_like=False,orchestrator=file_binding(__file__),
        evidence_support='Actual closed paced native observations with exact logical event parity; native wall clocks remain separate')
    value.update(status='COMPLETE',schema='jp_s6c_prediction.v1',prediction_key=digest(identity),identity=identity,
        case_id=job['case_id'],stream=job['asr_tap'],identity_tap=job['identity_tap'],
        profile_id=job['candidate_id'],candidate_id=job['candidate_id'],recipe_id=job['profile_row']['recipe_id'],
        duration_sec=source['duration_sec'],repetition=job['repetition'],oracle_like=False,
        execution_mode='ACTUAL_SOURCE_PACED_NATIVE_WITH_EXACT_SHARED_REPLAY_PARITY',
        native_execution_epoch=spec['epoch'],
        policy_wall_sec_scope='Actual post-closure policy replay wall only; neural/native timing is separate. No models are executed by this converter.',
        tracker_snapshot_scope='Reconstructed through the identical policy using actual native observations and exact emitted-decision parity. Original native scheduler snapshot and process trajectories remain separately bound.',
        created_utc=datetime.now(timezone.utc).isoformat())
    return value,dict(status='PASS',compared='Every nested speaker decision, shared transcript/identity field and retained final native utterance in order',
        excluded_execution_fields=sorted(EXECUTION_FIELDS),embedding_calls=len(features),segmentation_calls=len(seg),
        asr_observations=len(asr),decision_events=len(expected['decisions']),transcript_events=len(expected['transcript_events']),
        identity_events=len(expected['identity_events']),mismatch_count=0)

def name_module():
    path=SIM/'scripts/s6c_paced_name_emissions.py'
    if file_binding(path)['sha256']!=NAME_EMISSION_SHA:
        fail('Independently reviewed name-emission helper changed')
    module=importlib.import_module('s6c_paced_name_emissions')
    if Path(module.__file__).resolve()!=path.resolve():
        fail('Name-emission import origin differs')
    return module

def name_context(reader):
    """Original completed enrollment and all777 Q/support authorities, no vectors."""
    module=name_module();core=module.names.core
    completion_b=file_binding(REPORT/'enrollment/ENROLLMENT_COMPLETION.json')
    completion=reader.json(completion_b)
    map_b=file_binding(REPORT/'enrollment/SCORER_GALLERY_MAP.json')
    if map_b['sha256']!=SCORER_MAP_SHA:
        fail('Original completed scorer gallery map changed')
    scoremap=reader.json(map_b)
    if (completion['status']!='COMPLETE' or map_b not in completion['outputs'] or
        scoremap['status']!='COMPLETE' or scoremap['runtime_input'] is not False or completion['plan']!=scoremap['plan']):
        fail('Completed evaluator-only enrollment authority differs')
    plan=reader.json(scoremap['plan']);qb=plan['query_manifest'];qraw=reader.json(qb)['rows']
    q={(r['case_id'],r['segment_index']):r for r in qraw}
    if len(q)!=777 or len(qraw)!=777:
        fail('All777 unique corpus-qualified Q occurrences required')
    input_b=file_binding(core.S6B/'INPUT_INDEX.json');bank_b=file_binding(core.BANK)
    if input_b['sha256']!=core.INPUT_SHA or bank_b['sha256']!=core.BANK_SHA:
        fail('Original support index or scene bank changed')
    inputs=reader.json(input_b)['rows'];lookup={(r['case_id'],r['stream']):r for r in inputs}
    bank=reader.json(bank_b);scenes={r['case_id']:r for r in bank['scenes']}
    if len(lookup)!=480 or len(inputs)!=480 or len(scenes)!=240 or len(bank['scenes'])!=240:
        fail('Original all240/two-tap source authority denominator differs')
    return dict(module=module,scoremap=scoremap,q=q,inputrows=lookup,scenes=scenes,
        bindings=dict(enrollment_completion=completion_b,scorer_map=map_b,enrollment_plan=scoremap['plan'],
            Q=qb,input_index=input_b,bank=bank_b,name_helper=file_binding(module.__file__)))

def paced_name_observations(events,value,chain,finalization,reader,context):
    if context is None:
        fail('Actual paced name analysis requires original admitted source context')
    job=chain['job'];cell=chain['cell'];native=chain['native'];module=context['module']
    support_b=context['inputrows'][job['case_id'],job['identity_tap']]['support']
    support=reader.json(support_b)['support']
    module.names.validate_support(context['scenes'][job['case_id']],support)
    gallery=module.names.gallery_for(value,context['scoremap'])
    if value['identity']['gallery']!=job['gallery'] or gallery['manifest']!=job['gallery']:
        fail('Name scorer resolved a different actual gallery')
    admission=dict(source_kind=cell['source_kind'],realtime=True,
        native_session_complete=native['status']=='COMPLETE' and cell['status']=='COMPLETE',
        source_offset_samples=cell['source_offset_samples'],inserted_gap_samples=cell['inserted_gap_samples'],
        case_id=job['case_id'],profile_id=job['candidate_id'],asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],
        pacing_authority='Inventory-admitted unchanged native function calls start_paired_files(realtime=True,accelerated_factor=0); actual source/trajectory observations remain separate',
        actual_cell=chain['cell_binding'],actual_native=chain['native_binding'],completion=chain['complete_binding'])
    result=module.analyze(events,value,support,gallery,context['q'],admission,finalization)
    result['source_bindings']=dict(**context['bindings'],support=support_b,actual_gallery=job['gallery'],
        actual_events=unique_artifact(chain['artifacts'],'events.jsonl'),
        finalization=unique_artifact(chain['artifacts'],'session_finalization_v3.json'),
        same_native_semantic_prediction_sha256=digest({k:value[k] for k in
            ('decisions','transcript_events','identity_events','final_transcripts_latest')}))
    return result

def convert_closed_cell(chain,plan,spec,modules,classes,galleries,names_context):
    job=chain['job'];native=chain['native'];artifacts=chain['artifacts'];reader=ExactReader()
    source=reader.json(job['source'])
    events_binding=unique_artifact(artifacts,'events.jsonl');events=reader.lines(events_binding)
    summary_binding=unique_artifact(artifacts,'session_summary.json');summary=reader.json(summary_binding)
    expected_cue=source['telemetry']['sha256'] if job['profile_row']['cue_condition']=='REAL_ALIGNED_CUES' else None
    research=summary['research']
    if (research['profile']!=job['profile_row']['profile'] or research['telemetry_sha256']!=expected_cue or
        research['model_weights_changed'] is not False or research['input_gain']!=1.0):
        fail('Actual application summary profile/cue/weight/gain differs')
    finalization=reader.json(unique_artifact(artifacts,'session_finalization_v3.json'))
    if finalization['finalization_error'] is not None or finalization['state']!='COMPLETED':
        fail('Native finalization error cannot be scored as completed')
    observed=native_event_observations(events,source['duration_sec'])
    if observed['event_counts']!=native['event_counts']:
        fail('Exact driver/native event denominators differ')
    loads=[e['payload'] for e in events if e['event_type']=='research_gallery_loaded']
    if job['gallery'] is None:
        validate_no_gallery(loads,native['gallery_load_receipt'])
    else:
        gm=reader.json(job['gallery'])
        if len(loads)!=1 or loads[0]!=native['gallery_load_receipt']:
            fail('Exactly one actual gallery load event must match the native receipt')
        validate_gallery_load(loads[0],job['gallery'],gm,job['profile_row']['profile']['identity']['max_gallery_profiles'])
    start=observed['source_started']['payload']
    if (start['mode']!='paired_wav' or start['expected_samples']!=source['duration_samples'] or
        Path(start['asr_path']).resolve()!=Path(source['audio'][job['asr_tap']]['path']).resolve() or
        Path(start['identity_path']).resolve()!=Path(source['audio'][job['identity_tap']]['path']).resolve() or
        start['pipeline_sample_rate']!=16000 or start['gain_in_producer']!=1.0):
        fail('Actual producer source/route/rate/gain differs')
    if native['source_duration_sec']!=source['duration_sec'] or summary['telemetry']['asr_cursor_sec']!=source['duration_sec']:
        fail('Actual complete source duration differs')
    latest=reader.lines(unique_artifact(artifacts,'latest_labelled_transcript.jsonl'))
    native_final=[u for u in summary['telemetry']['scheduler']['utterances'] if u['is_final']]
    if [{k:v for k,v in u.items() if k!='schema_version'} for u in latest]!=native_final:
        fail('Retained native export differs from final scheduler utterances')
    value,parity=native_prediction(events,summary,job,chain['native_binding'],spec,modules,classes,reader,galleries)
    if value is None:
        return dict(status='FAILED_LOGICAL_PARITY',job=job,parity=parity,consumed_observations=reader.reads),None
    samples=reader.lines(native['process_samples'])
    if type(native['process_sample_count']) is not int or len(samples)!=native['process_sample_count']:
        fail('Exact native process trajectory denominator differs')
    trajectory=trajectory_observations(samples)
    external_binding=unique_artifact(artifacts,'PROCESS_TREE_SAMPLES.jsonl')
    external=reader.lines(external_binding)
    if len(external)!=chain['complete']['external_process_samples']:
        fail('Exact outer trajectory denominator differs')
    owned={(o['pid'],o['creation_time']) for o in chain['complete']['owned_processes']}
    for row in external:
        if any((o['pid'],o['creation_time']) not in owned for o in row['process']['processes']):
            fail('Observed process omitted from completed closure')
    external_stats={field:stats([s['process'].get(field) for s in external]) for field in
        ('rss_sum_upper_bound_bytes','private_resident_uss_bytes','windows_private_commit_bytes','cpu_sec','available_ram_bytes')}
    return dict(status='COMPLETE',job_id=job['job_id'],candidate_id=job['candidate_id'],case_id=job['case_id'],
        asr_tap=job['asr_tap'],identity_tap=job['identity_tap'],repetition=job['repetition'],
        source=job['source'],native_result=chain['native_binding'],cell_result=chain['cell_binding'],
        completion=chain['complete_binding'],native_metadata_scope=chain['scope'],
        native_gallery_load_events=loads,
        measured_cell=chain['complete']['measurement'],native_scheduler=summary['telemetry']['scheduler'],
        actual_events=observed,trajectory=trajectory,external_process_samples=len(external),external_process_statistics=external_stats,
        active_context=active_context_observations(events,job['profile_row']['profile']['embedding']['evidence_policy']),
        actual_name_emissions=paced_name_observations(events,value,chain,finalization,reader,names_context),
        parity=parity,consumed_observations=reader.reads,
        payload_verification_scope='Exact event/summary/finalization/export/process buffers read and hashed once per cell. Original paired PCM and model hashes remain transitively admitted by the closed native/COMPLETE chain; no new audio or model inference.',
        repetition_scope='Each repetition is retained separately; repeats are not new independent scenes.'),value

def inventory_module():
    path=SIM/'scripts/s6c_execution_inventory_v4.py'
    if INVENTORY_SOURCE_SHA is None or file_binding(path)['sha256']!=INVENTORY_SOURCE_SHA:
        fail('Final independently reviewed inventory source is not yet pinned')
    mod=importlib.import_module('s6c_execution_inventory_v4')
    if Path(mod.__file__).resolve()!=path.resolve():
        fail('Inventory import origin differs')
    return mod

def safe_output(namespace):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',namespace):
        fail('Simple explicit fresh output namespace required')
    root=REPORT/'paced_analysis'/namespace
    if root.exists():
        fail('Preserve existing paced analysis namespace')
    return root

def source_bindings():
    module=name_module()
    names=('s6c_paced_analysis_v1.py','README_S6C_PACED_ANALYSIS_V1.md',
        's6c_execution_inventory_v4.py','README_S6C_EXECUTION_INVENTORY_V4.md',
        's6c_execution_inventory_v3.py','s6c_execution_inventory.py',
        's6c_paced_name_emissions.py','README_S6C_PACED_NAME_EMISSIONS.md',
        's6c_name_analysis_v3.py','README_S6C_NAME_ANALYSIS_V3.md',*module.names.core.CODES)
    return [file_binding(SIM/'scripts'/name) for name in dict.fromkeys(names)]

def closed_coordinators(inv,reader,plan,pb):
    records,owners=inv.invocation_rows(reader,plan,pb)
    if not records or not any(r.get('status')=='COMPLETE' and r.get('closure_status')=='QUIET_LEASE_RELEASED' for r in records):
        fail('Complete coordinator outcome and released quiet lease required')
    if any(r.get('closure_status')!='QUIET_LEASE_RELEASED' for r in records):
        fail('An earlier paced coordinator lacks verified quiet-lease release')
    if any(o['process_state']['alive'] is not False for o in owners):
        fail('Recorded paced coordinators remain live or closure unavailable')
    return dict(invocations=records,owner_observations=owners)

def prepare(args):
    if (REPORT/'PACED_QUIET_OWNER.json').exists():
        fail('Paced quiet lease remains; do not start heavy post-analysis')
    inv=inventory_module();out=safe_output(args.namespace);out.mkdir(parents=True)
    reader=inv.base.MetadataReader(out)
    try:
        manifest=file_binding(args.manifest);plan,pb,spec=inv.admit_plan(reader,manifest)
        if plan['schema']!=inv.CANONICAL:
            fail('This analysis adapter admits canonical C-candidate cells only')
        ib=file_binding(args.index);index,ib=inv.admit_paced_index(reader,ib,plan,pb)
        closure=closed_coordinators(inv,reader,plan,pb)
        name_reader=ExactReader();context=name_context(name_reader)
        result=dict(schema=SCHEMA,status='PREPARED_NO_NEW_INFERENCE_OR_EVENT_SCAN',
            created_utc=datetime.now(timezone.utc).isoformat(),namespace=args.namespace,
            manifest=pb,paced_index=ib,execution_manifest=plan['execution_manifest'],
            sources=source_bindings(),metadata_admission=closure,metadata_sources=reader.sources,
            name_context_sources=context['bindings'],name_context_reads=name_reader.reads,
            expected_cells=len(plan['jobs']),repetitions=sorted({j['repetition'] for j in plan['jobs']}),
            tests=checks(),scope='Post-closure actual paced/native observation conversion; no new models, no source audio re-read and no historical control substitution.')
        return save_json(out/'PLAN.json',result)
    except Exception as exc:
        save_json(out/'PREPARATION_FAILURE.json',dict(status='FAILED_PREPARATION',error=repr(exc),metadata_sources=reader.sources))
        raise

def run(args):
    if (REPORT/'PACED_QUIET_OWNER.json').exists():
        fail('Paced quiet lease remains; do not start heavy post-analysis')
    rb=file_binding(args.plan);exact=ExactReader();request=exact.json(rb)
    out=Path(rb['path']).parent
    if (out/'RESULT.json').exists() or (out/'FAILURE.json').exists():
        fail('Preserve completed or failed observation analysis; a fresh namespace is required')
    if (request['schema']!=SCHEMA or request['status']!='PREPARED_NO_NEW_INFERENCE_OR_EVENT_SCAN' or
        out!=REPORT/'paced_analysis'/request['namespace'] or Path(rb['path']).name!='PLAN.json' or
        request['sources']!=source_bindings()):
        fail('Changed analysis plan/source/namespace')
    inv=inventory_module();reader=inv.base.MetadataReader(out);started=time.perf_counter()
    produced=[];metrics=[];parities=[]
    try:
        plan,pb,spec=inv.admit_plan(reader,request['manifest'])
        index,ib=inv.admit_paced_index(reader,request['paced_index'],plan,pb)
        if len(plan['jobs'])!=request['expected_cells']:
            fail('Prepared cell denominator differs')
        closure=closed_coordinators(inv,reader,plan,pb)
        name_reader=ExactReader();context=name_context(name_reader)
        if context['bindings']!=request['name_context_sources']:
            fail('Original naming context changed since preparation')
        modules,Profile,Provider,Gallery=load_frozen_modules(spec,exact)
        classes=(Profile,Provider,Gallery);galleries={}
        references={r['job_id']:r for r in index['rows']}
        for job in plan['jobs']:
            if (REPORT/'PACED_QUIET_OWNER.json').exists():
                fail('A new paced quiet lease appeared; stop analysis at cell boundary')
            chain=inv.admit_complete_cell(reader,job,plan,pb,spec)
            if chain['complete_binding']!=references[job['job_id']]['completion']:
                fail('Indexed completed cell differs from admitted exact chain')
            measurement,value=convert_closed_cell(chain,plan,spec,modules,classes,galleries,context)
            mb=save_json(out/'cells'/(job['job_id']+'.json'),measurement);metrics.append(mb)
            parities.append(dict(job_id=job['job_id'],**measurement['parity']))
            if value is None:
                fail('Actual paced/native logical parity failed; full differences preserved')
            path=out/'predictions'/(job['job_id']+'.json.gz');path.parent.mkdir(exist_ok=True)
            raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
            with path.open('xb') as f:f.write(gzip.compress(raw,compresslevel=5,mtime=0))
            produced.append(dict(candidate_id=job['candidate_id'],case_id=job['case_id'],stream=job['asr_tap'],
                identity_tap=job['identity_tap'],repetition=job['repetition'],recipe_id=job['profile_row']['recipe_id'],
                status='COMPLETE',result=file_binding(path),native_completion=chain['complete_binding'],measurement=mb))
            print(json.dumps(dict(phase='PACED_NATIVE_POST_ANALYSIS',completed=len(produced),requested=len(plan['jobs']),
                elapsed_sec=time.perf_counter()-started)),flush=True)
        indices=[]
        for repetition in request['repetitions']:
            rows=[r for r in produced if r['repetition']==repetition]
            cases=sorted({r['case_id'] for r in rows})
            routes=sorted({(r['candidate_id'],r['stream'],r['identity_tap']) for r in rows})
            wanted={(p,t,i,c) for p,t,i in routes for c in cases}
            got={(r['candidate_id'],r['stream'],r['identity_tap'],r['case_id']) for r in rows}
            if len(rows)!=len(got) or got!=wanted:
                fail('Do not silently flatten uneven repetition grids')
            value=dict(schema=SCHEMA,status='COMPLETE',requested=len(rows),completed=len(rows),rows=rows,
                case_ids=cases,profile_routes=[dict(candidate_id=p,stream=t,identity_tap=i) for p,t,i in routes],
                repetition=repetition,execution_manifest=plan['execution_manifest'],source_indices=[ib],
                scope='One explicitly separate actual paced repetition; source scenes are dependent on other repetitions and offline results.')
            indices.append(save_json(out/('REPETITION_'+str(repetition)+'_PREDICTION_INDEX.json'),value))
        result=dict(schema=SCHEMA,status='COMPLETE',plan=rb,manifest=pb,paced_index=ib,
            requested=len(plan['jobs']),completed=len(produced),failed=0,indices=indices,cell_measurements=metrics,
            parity=parities,metadata_admission=closure,metadata_sources=reader.sources,
            execution_source_reads=exact.reads,elapsed_sec=time.perf_counter()-started,
            name_context_sources=context['bindings'],name_context_reads=name_reader.reads,
            new_neural_calls=0,policy_replay_performed=True,
            scope='All actual paced native cells retained, exact logical parity checked. Actual emitted/resource evidence is distinct from modeled-support core/name scoring. This receipt does not declare full S6C acceptance.')
        return save_json(out/'RESULT.json',result)
    except Exception as exc:
        save_json(out/'FAILURE.json',dict(schema=SCHEMA,status='FAILED_PRESERVED',plan=rb,error=repr(exc),
            completed=len(produced),produced=produced,cell_measurements=metrics,parity=parities,
            metadata_sources=reader.sources,elapsed_sec=time.perf_counter()-started,new_neural_calls=0))
        raise

def checks():
    checked = []
    assert stats([None, 0, 2]) == dict(observed=2, missing=1, min=0., max=2., mean=1., p50=1., p95=1.9)
    checked.append('Missing observations remain distinct from numeric zero')
    assert stats([None])['max'] is None
    checked.append('All-missing maxima unavailable')
    for value in (True, float('nan'), float('inf'), '1'):
        try: number(value)
        except ValueError: checked.append('Reject nonnumeric or nonfinite observation '+repr(value))
        else: raise AssertionError('Invalid numeric accepted')
    start=dict(event_type='source_started',source_time_sec=0.,wall_time_utc='2026-09-10T00:00:00Z',payload={})
    final=dict(event_type='transcript_final',source_time_sec=1.,wall_time_utc='2026-09-10T00:00:00.9Z',payload={'text':'word','available_at_sec':1.2})
    stop=dict(event_type='session_completed',source_time_sec=1.,wall_time_utc='2026-09-10T00:00:01Z',payload={})
    measured=native_event_observations([start,final,stop],1.)
    assert abs(measured['emissions'][0]['emission_minus_source_cursor_sec']+.1)<1e-6
    checked.append('Block-before-sleep negative source-relative lag retained')
    assert measured['emissions'][0]['modeled_available_at_sec']==1.2
    checked.append('Modeled availability not substituted for actual emission')
    for invalid in ([start,start,stop],[start,final], [start,dict(final,source_time_sec=2.),stop]):
        try: native_event_observations(invalid,1.)
        except ValueError: checked.append('Reject missing/duplicate/out-of-range native completion evidence')
        else: raise AssertionError('Invalid event sequence accepted')
    def admission(role,reason,end=.5,age=None):
        return dict(event_type='research_embedding_admission',payload=dict(evidence_kind=role,reason=reason,
            source_end_sec=end,tracking_context_age_sec=age,tracking_context_empty=age is None,cue_event=False))
    q=active_context_observations([admission('short','overlap_gate'),admission('mature','overlap_gate'),
        admission('short','no_speech_gate',1.,.2),admission('mature','no_speech_gate',1.,.2)])
    assert q['shared_dispatches']==2 and q['native_speech_gate_active']==1 and q['active_context_age_sec']['missing']==1
    checked.append('Role deduplication and active-overlap/missing-age conditioning')
    try: active_context_observations([admission('short','admitted'),admission('mature','no_speech_gate')])
    except ValueError: checked.append('Contradictory shared role state rejected')
    else: raise AssertionError('Contradictory roles accepted')
    sample=dict(phase='terminal_after_finalization',elapsed_from_native_launch_sec=1.,process={},telemetry={},event_queue_backlog=None)
    assert trajectory_observations([sample])['process']['cpu_sec']['sampled_first_to_last_delta'] is None
    checked.append('One missing trajectory observation does not create CPU time')
    try: trajectory_observations([sample,dict(sample,elapsed_from_native_launch_sec=.5)])
    except ValueError: checked.append('Nonmonotonic sampled clock rejected')
    else: raise AssertionError('Nonmonotonic samples accepted')
    marker=dict(mode='none',loaded_count=0,private_gallery_accessed=False)
    validate_no_gallery([marker],None)
    checked.append('Exact explicit native no-gallery marker admitted')
    for loads,receipt in (([],None),([marker,marker],None),([dict(marker,loaded_count=1)],None),([marker],{})):
        try: validate_no_gallery(loads,receipt)
        except ValueError: checked.append('Missing/duplicate/contradictory no-gallery evidence rejected')
        else: raise AssertionError('Invalid no-gallery evidence admitted')
    binding=dict(path='explicit',bytes=12,sha256='abc')
    manifest=dict(gallery_id='gallery',backend_sha256='backend',profiles=[dict(profile_id='p')])
    receipt=dict(manifest=binding,gallery_id='gallery',backend_sha256='backend',dimension=192,
        dtype='float32',templates=manifest['profiles'],loaded_count=1)
    validate_gallery_load(receipt,binding,manifest,1)
    checked.append('Actual bound gallery receipt admitted within current cap')
    for altered,limit in ((receipt,0),(dict(receipt,manifest=dict(binding,sha256='changed')),1),
        (dict(receipt,backend_sha256='changed'),1),(dict(receipt,templates=[]),1),(dict(receipt,loaded_count=0),1)):
        try: validate_gallery_load(altered,binding,manifest,limit)
        except ValueError: checked.append('Cached cap/manifest/backend/template/count mismatch rejected')
        else: raise AssertionError('Invalid actual gallery receipt admitted')
    from dataclasses import make_dataclass
    from types import SimpleNamespace
    Observation=make_dataclass('Observation',[('available_at_sec',float),('valid',bool)])
    cue_binding=dict(path=str(Path(__file__).resolve()),sha256='cue')
    cue_rows=[dict(available_at_sec=.1,valid=True)]
    provider=SimpleNamespace(path=cue_binding['path'],sha256='cue',rows=[(.1,Observation(.1,True))])
    validate_provider(provider,cue_binding,cue_rows)
    checked.append('Actual reconstructed cue rows match admitted buffer')
    for altered in (SimpleNamespace(**dict(vars(provider),sha256='foreign')),
        SimpleNamespace(**dict(vars(provider),rows=[(.1,Observation(.1,False))])),
        SimpleNamespace(**dict(vars(provider),rows=[]))):
        try: validate_provider(altered,cue_binding,cue_rows)
        except ValueError: checked.append('Cue digest/actual-row/count change rejected')
        else: raise AssertionError('Changed actual cue input admitted')
    for invalid in ([admission('short','admitted')],
        [admission('short','admitted'),admission('short','admitted')],
        [admission('foreign','admitted')]):
        try: active_context_observations(invalid)
        except ValueError: checked.append('Missing/duplicate/foreign evidence role rejected')
        else: raise AssertionError('Invalid native role denominator admitted')
    assert active_context_observations([admission('short','admitted')],'short_only')['shared_dispatches']==1
    checked.append('Declared single-role policy admitted without inventing a mature observation')
    return dict(status='PASS',checks=checked,scope='Pure transformations only; no actual paced source admitted or models constructed')

def context_checks():
    reader=ExactReader();context=name_context(reader)
    return dict(status='PASS_READ_ONLY_ORIGINAL_CONTEXT',sources=context['bindings'],
        Q_occurrences=len(context['q']),source_routes=len(context['inputrows']),scenes=len(context['scenes']),
        exact_metadata_reads=reader.reads,models=0,policy_replays=0,actual_paced_cells=0,
        scope='Read-only original naming/support authority admission; no native events, PCM or model payload read.')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    sub.add_parser('checks')
    sub.add_parser('context-check')
    prep=sub.add_parser('prepare');prep.add_argument('--manifest',type=Path,required=True)
    prep.add_argument('--index',type=Path,required=True);prep.add_argument('--namespace',required=True)
    execution=sub.add_parser('run');execution.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(checks() if args.action=='checks' else context_checks() if args.action=='context-check' else prepare(args) if args.action=='prepare' else run(args),indent=2,allow_nan=False))
