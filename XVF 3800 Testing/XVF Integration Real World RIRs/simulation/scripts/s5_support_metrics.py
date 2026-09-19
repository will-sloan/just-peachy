"""Frozen-source S5 support diagnostics; no models or hardware. See README_S5_SUPPORT_METRICS.md."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import threading
from pathlib import Path

RATE = 16000
POLICY = {
    'schema': 'jp_s5_support_policy_v1',
    'intervals': 'Integer 16-kHz half-open sample intervals; clip to decoded output only after mapping',
    'speech_activity': 'Existing absolute activity_ranges_samples_estimated includes retained RIR +800 samples; use without another RIR shift',
    'missing_speech_activity': 'Whole dry-file support plus800 once, labelled fallback; never call this estimated active speech',
    'noise_activity': {'frame_samples': 320, 'threshold': 'max(10**(-50/20), frame_rms_p95*10**(-25/20))',
                       'scope': 'Exact scheduled prepared crop, unscaled source, whole320-sample frames; last incomplete frame is unknown'},
    'quiet': 'Outside union of complete scheduled convolution envelopes; low estimated energy alone is not quiet',
    'output_mapping': 'source-with-RIR + saved capture_minus_source_offset_samples + saved per-output relative_delay_median_samples; no fitted new shifts',
    'unknown_output_lag': 'Output-local reference diagnostics unavailable; retain whole-output and native evidence diagnostics',
    'timing_uncertainty': '20-ms source activity grid plus saved across-utterance lag spread; not calibrated phonetic/device latency; RIR tails separately retained',
    'duration_bins': ['<1s', '1-<2s', '>=2s'],
    'embedding': {'window_s': .5, 'hop_s': .25, 'minimum_rms': .002,
                  'continuity': 'Entire actual embedding window contained in one RIR-shifted whole-clip support and intersects no other scheduled utterance; dominant ties/missing remain unknown',
                  'strict_active': 'Additionally report windows fully contained in one estimated active union; no overlapping-window independence'},
    'segmentation': {'hop_s': .75, 'frame_step_s': .016875, 'tail_frames': 44,
                     'nominal_tail_s': .7425, 'scope': 'Boolean from mean of last44 model frames, not exported frame labels; interval intersections are coarse supported indications, not exact VAD boundaries'},
    'direction': 'One shared trace per physical scene; callback availability and last-received causal age <=250ms; unknown DSP freshness',
    'transcript_timing': 'Final cursor is consumed-audio cursor, not word interval; no event-local insertion or turn-omission claim without real word intervals',
}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def union(ranges):
    result = []
    for start, stop in sorted((int(a), int(b)) for a, b in ranges if b > a):
        if result and start <= result[-1][1]:
            result[-1][1] = max(stop, result[-1][1])
        else:
            result.append([start, stop])
    return result


def intersection(left, right):
    a, b = union(left), union(right)
    result, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            result.append([lo, hi])
        if a[i][1] < b[j][1]: i += 1
        else: j += 1
    return union(result)


def subtract(left, right):
    result = []
    for start, stop in union(left):
        at = start
        for a, b in union(right):
            if b <= at: continue
            if a >= stop: break
            if a > at: result.append([at, min(a, stop)])
            at = max(at, b)
        if at < stop: result.append([at, stop])
    return result


def samples(ranges):
    return sum(b-a for a, b in union(ranges))


def contained(window, ranges):
    return samples(intersection([window], ranges)) == window[1]-window[0]


def duration_bin(seconds):
    return '<1s' if seconds < 1 else '1-<2s' if seconds < 2 else '>=2s'


class DevelopmentGuard:
    """Check scene permission before filesystem access; cache exact binding verification."""
    def __init__(self, scenes, *, scoring_protocol_sha256=None):
        self.scenes = {s['case_id']: s for s in scenes}
        if len(self.scenes) != len(scenes): raise ValueError('Duplicate scene IDs')
        self.protocol = scoring_protocol_sha256
        self.accesses = collections.Counter()
        self.refusals = []
        self.verified = {}
        self.lock = threading.RLock()

    def require(self, scene, operation='performance_scoring'):
        cid = scene['case_id'] if isinstance(scene, dict) else scene
        canonical = self.scenes.get(cid)
        if canonical is None or canonical.get('split') != 'development' or canonical.get('task_scoring_allowed') is not True:
            with self.lock: self.refusals.append({'case_id': cid, 'operation': operation})
            raise PermissionError('Development allowlist refusal BEFORE access: '+str(cid))
        if isinstance(scene, dict) and fingerprint(scene) != fingerprint(canonical):
            raise PermissionError('Scene metadata differs from guard allowlist')
        if operation == 'performance_scoring' and not self.protocol:
            raise PermissionError('Bind frozen scoring protocol before performance scoring')
        with self.lock: self.accesses[(cid, operation)] += 1
        return canonical

    def verified_path(self, scene, binding, operation):
        self.require(scene, operation)
        p = Path(binding['path'])
        if not binding.get('sha256'): raise ValueError('An expected binding is required')
        stat = p.stat()
        key = (str(p.resolve()), stat.st_size, stat.st_mtime_ns, binding['sha256'])
        with self.lock:
            if key not in self.verified:
                h = hashlib.sha256()
                with p.open('rb') as f:
                    for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
                after = p.stat()
                if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns): raise ValueError('Input changed during verification')
                if h.hexdigest() != binding['sha256']: raise ValueError('Input hash mismatch: '+str(p))
                if 'bytes' in binding and stat.st_size != binding['bytes']: raise ValueError('Input byte-count mismatch')
                self.verified[key] = {'path': str(p.resolve()), 'sha256': h.hexdigest(), 'bytes': stat.st_size}
        return p

    def read_json(self, scene, binding, operation='task_metadata'):
        return json.loads(self.verified_path(scene, binding, operation).read_text(encoding='utf-8'))

    def receipt(self):
        return {'schema': 'jp_s5_support_reserve_access_v1', 'scoring_protocol_sha256': self.protocol,
                'allowed_development_count': sum(s.get('split') == 'development' and s.get('task_scoring_allowed') is True for s in self.scenes.values()),
                'reserve_task_model_accesses': 0, 'reserve_performance_scoring_accesses': 0,
                'accesses': [{'case_id': k[0], 'operation': k[1], 'count': v} for k, v in sorted(self.accesses.items())],
                'refused_before_access': list(self.refusals), 'verified_inputs': list(self.verified.values()),
                'scope': 'This helper only; coordinator combines other component access receipts. No model invocation API exists.'}


def noise_activity(audio):
    """Same frozen20-ms/p95 estimator as S4 active_stats; no output-dependent mask."""
    import numpy as np
    x = np.asarray(audio, dtype=np.float64)
    if x.ndim != 1 or not np.isfinite(x).all() or not len(x): raise ValueError('Invalid mono noise crop')
    n = len(x)//320
    if not n: return [], {'threshold_fs': None, 'unestimated_tail_samples': len(x), 'reason': 'less_than_one_20ms_frame'}
    rms = np.sqrt(np.mean(x[:n*320].reshape(n, 320)**2, axis=1))
    threshold = max(10**(-50/20), float(np.percentile(rms, 95))*10**(-25/20))
    ranges = union([[i*320, (i+1)*320] for i in range(n) if rms[i] >= threshold])
    return ranges, {'threshold_fs': threshold, 'frame_samples': 320, 'unestimated_tail_samples': len(x)-n*320,
                    'uses_device_or_model_output': False, 'active_samples': samples(ranges)}


def freeze_scene_support(scene, capture_result, audio_metrics, noise_catalog, guard):
    """Input-only record; noise_catalog is keyed by noise_id or its prepared_segments list."""
    import soundfile as sf
    guard.require(scene, 'support_freeze')
    if capture_result.get('case_id', scene['case_id']) != scene['case_id'] or audio_metrics.get('case_id') != scene['case_id']:
        raise ValueError('Capture/timing scene mismatch')
    if int(scene.get('sample_rate_hz', RATE)) != RATE: raise ValueError('Require16000Hz source schedule')
    lookup = {n['noise_id']: n for n in noise_catalog['prepared_segments']} if 'prepared_segments' in noise_catalog else noise_catalog
    turns, noises, envelopes = [], [], []
    for index, seg in enumerate(scene['segments']):
        start, stop = int(seg['source_start_sample']), int(seg['source_stop_sample'])
        end = int(seg['convolution_stop_sample'])
        envelopes.append([start, end])
        crop = list(seg['source_crop_samples'])
        if stop-start != crop[1]-crop[0]: raise ValueError('Crop/schedule duration mismatch')
        if seg['kind'] == 'utterance':
            known = seg.get('activity_ranges_samples_estimated') is not None
            active = union(seg.get('activity_ranges_samples_estimated') or [])
            file_support = [[start+800, stop+800]]
            if any(a < start+800 or b > stop+800 for a, b in active): raise ValueError('Activity outside retained-RIR file support')
            turns.append({'segment_index': index, 'source_id': seg['source_id'], 'speaker_key': seg['speaker_key'],
                          'participant_id': seg['participant_id'], 'dataset': seg.get('dataset'), 'quality_partition': seg.get('quality_partition'),
                          'rir_id': seg['rir_id'], 'role': seg.get('role'), 'clip_samples': stop-start,
                          'whole_clip_duration_s': (stop-start)/RATE, 'whole_clip_bin': duration_bin((stop-start)/RATE),
                          'active_samples_estimated': samples(active) if known else None,
                          'active_duration_s_estimated': samples(active)/RATE if known else None,
                          'active_duration_bin': duration_bin(samples(active)/RATE) if known else None,
                          'activity_available': known, 'active_ranges': active,
                          'file_support': file_support, 'support_ranges': active if known else file_support,
                          'timing_scope': 'estimated_source_activity_20ms' if known else 'whole_clip_fallback_no_activity',
                          'source_crop_samples': crop})
        elif seg['kind'] == 'real_noise':
            source = lookup[seg['source_id']]
            if source.get('split') != 'development': raise PermissionError('Noise parent outside development partition')
            binding = {'path': source['prepared_path'], 'sha256': source['prepared_sha256']}
            p = guard.verified_path(scene, binding, 'source_audio_for_support')
            with sf.SoundFile(p) as f:
                if f.samplerate != RATE or f.channels != 1 or not 0 <= crop[0] < crop[1] <= len(f): raise ValueError('Invalid exact noise crop')
                f.seek(crop[0]); audio = f.read(crop[1]-crop[0], dtype='float64')
            ranges, estimator = noise_activity(audio)
            active = [[a+start+800, b+start+800] for a, b in ranges]
            noises.append({'segment_index': index, 'source_id': seg['source_id'], 'parent_id': seg['parent_id'],
                           'category': seg['category'], 'speech_content': seg['speech_content'],
                           'strict_nonspeech_eligible': bool(seg['strict_nonspeech_eligible']), 'source_binding': binding,
                           'source_crop_samples': crop, 'source_start_sample': start, 'active_ranges': active,
                           'possible_convolution_envelope': [[start, end]], 'activity_estimator': estimator,
                           'interpretation': 'strict_annotation_based_nonspeech' if seg['strict_nonspeech_eligible'] else 'noise_associated_unknown_speech_not_false_speech'})
        else: raise ValueError('Unsupported source component kind: '+str(seg['kind']))
    speech = union([r for t in turns for r in t['support_ranges']])
    overlapping = []
    for i, t in enumerate(turns):
        for other in turns[i+1:]:
            if t['speaker_key'] != other['speaker_key']: overlapping += intersection(t['support_ranges'], other['support_ranges'])
    noise = union([r for n in noises for r in n['active_ranges']])
    envelopes = union(envelopes)
    duration = round(scene['duration_s']*RATE)
    regions = {'speech_active': speech, 'noise_active': noise, 'speech_noise_overlap': intersection(speech, noise),
               'multiple_speaker_active': union(overlapping), 'noise_without_estimated_speech': subtract(noise, speech),
               'speech_without_estimated_noise': subtract(speech, noise), 'quiet_outside_all_convolution_envelopes': subtract([[0,duration]], envelopes),
               'possible_component_envelopes': envelopes,
               'inactive_or_tail_uncertain_within_envelopes': subtract(envelopes, union(speech+noise))}
    offset = capture_result['payload']['capture_minus_source_offset_samples']
    mappings = {}
    for output in ['O0', 'O1']:
        lag = audio_metrics.get('streams', {}).get(output, {}).get('relative_delay_median_samples')
        detail = audio_metrics.get('output_alignment', {}).get(output, {})
        mappings[output] = {'capture_minus_source_offset_samples': offset, 'saved_processed_minus_input_samples': lag,
                            'source_with_rir_to_output_offset_samples': int(offset+lag) if offset is not None and lag is not None else None,
                            'observed_lag_spread_s': detail.get('uncertainty_s'), 'source_activity_grid_s': .02,
                            'status': 'SAVED_APPROXIMATE_MAPPING' if offset is not None and lag is not None else 'UNAVAILABLE_NO_SAVED_MAPPING',
                            'new_output_shift_fitted': False}
    result = {'schema': 'jp_s5_reference_support_v1', 'policy_sha256': fingerprint(POLICY), 'case_id': scene['case_id'],
              'scene_metadata_sha256': fingerprint(scene), 'duration_samples': duration, 'sample_rate_hz': RATE,
              'capture_minus_source_offset_samples': offset, 'turns': sorted(turns, key=lambda t:(t['file_support'][0][0],t['segment_index'])),
              'noise_events': noises, 'regions_source_with_rir_samples': regions, 'output_mappings': mappings,
              'all_speaker_reference_complete': bool(scene['all_speaker_reference_complete']),
              'input_only_masks': True, 'hardware_direction_evidence_units': 1,
              'uncertainty': 'RIR convention800 samples already in activity; onset/tail and20ms estimates are not exact word timing. Whole convolution envelopes retain pre-onset/tail uncertainty.'}
    result['support_sha256'] = fingerprint(result)
    return result


def validate_support(scene, support):
    if support['case_id'] != scene['case_id'] or support['scene_metadata_sha256'] != fingerprint(scene): raise ValueError('Support belongs to different scene')
    value = dict(support); expected = value.pop('support_sha256')
    if fingerprint(value) != expected or support['policy_sha256'] != fingerprint(POLICY): raise ValueError('Changed support or policy')


def mapped_ranges(ranges, offset, length):
    return union([[max(0,a+offset), min(length,b+offset)] for a,b in ranges])


def embedding_windows(events, window_samples=8000):
    result = []
    for order, e in enumerate(events):
        if e['event_type'] != 'speaker_decision': continue
        end = round(float(e['source_time_sec'])*RATE)
        exported = e['payload'].get('spatial_evidence')
        if exported:
            start = round(float(exported['source_start_sec'])*RATE)
            stop = round(float(exported['source_end_sec'])*RATE)
            if stop != end or stop-start != window_samples or exported.get('source_clock') != 'audio_sample_clock':
                raise ValueError('Native embedding evidence interval differs from fixed contract')
            provenance = 'actual_exported_spatial_evidence_interval'
        else:
            start, stop = end-window_samples, end
            provenance = 'configured_unchanged_window_from_actual_decision_cursor'
        if start < 0: raise ValueError('Embedding before complete configured window')
        result.append({'start':start, 'stop':stop, 'anonymous_label': e['payload'].get('anonymous_label'),
                       'cluster_id':e['payload'].get('cluster_id'), 'journal_order':order, 'provenance':provenance})
    return sorted(result, key=lambda w:(w['stop'],w['journal_order']))


def segmentation_intervals(events):
    nominal = round(POLICY['segmentation']['nominal_tail_s']*RATE)
    result = []
    for order,e in enumerate(events):
        if e['event_type'] == 'segmentation':
            end = round(float(e['source_time_sec'])*RATE)
            result.append({'start':max(0,end-nominal), 'stop':end, 'speech':bool(e['payload']['speech']),
                           'overlap':bool(e['payload']['overlap']), 'source_cursor_s':e['source_time_sec'], 'journal_order':order})
    return sorted(result,key=lambda r:(r['stop'],r['journal_order']))


def gate_diagnostics(pcm16, events):
    import numpy as np
    x = np.asarray(pcm16, dtype=np.float32)/32768
    state_events = {round(float(e['source_time_sec'])*RATE):e['payload'] for e in events if e['event_type']=='segmentation'}
    decisions = collections.Counter(round(float(e['source_time_sec'])*RATE) for e in events if e['event_type']=='speaker_decision')
    if any(v != 1 for v in decisions.values()): raise ValueError('Duplicate embedding decisions at one hop')
    count = collections.Counter(); speech = overlap = False
    for end in range(4000,len(x)+1,4000):
        if end in state_events: speech, overlap = bool(state_events[end]['speech']), bool(state_events[end]['overlap'])
        rms = float(np.sqrt(np.mean(x[end-4000:end]**2,dtype=np.float64)))
        flags = {'no_speech':not speech, 'overlap':overlap, 'short_window':end<8000, 'below_minimum_rms':rms<.002}
        eligible = not any(flags.values()); has = end in decisions
        count.update({'total_hops':1,'eligible_hops_reconstructed':int(eligible),'emitted_embedding_decisions':int(has),
                      'eligible_without_decision':int(eligible and not has),'decision_despite_ineligible':int(has and not eligible)})
        for name, flag in flags.items(): count['blocked_'+name] += flag
    if any(end % 4000 or end > len(x) for end in decisions): raise ValueError('Embedding cursor outside fixed audio hop schedule')
    return {'counts':dict(count),'unlogged_rejected_calls':None,'unanalysed_final_partial_hop_samples':len(x)%4000,
            'scope':'Exact PCM16 input/current last segmentation state at0.25s hops; blocking reasons overlap. Absence is not an observed embed rejection.'}


def continuity(turns, windows, regions, family_id, *, reference_complete=True):
    per_turn=[]
    for t in turns:
        eligible=[]
        for w in windows:
            bounds=[w['start'],w['stop']]
            if not contained(bounds,t['file_support']): continue
            if any(other['segment_index']!=t['segment_index'] and samples(intersection([bounds],other['file_support']))>0 for other in turns): continue
            eligible.append(w)
        labels=[str(w['anonymous_label']) for w in eligible if w['anonymous_label'] is not None]
        counts=collections.Counter(labels);ranked=counts.most_common()
        tied=bool(len(ranked)>1 and ranked[0][1]==ranked[1][1])
        dominant=ranked[0][0] if ranked and not tied else None
        per_turn.append({**{k:t[k] for k in ['segment_index','source_id','speaker_key','participant_id','whole_clip_bin','active_duration_bin','whole_clip_duration_s','active_duration_s_estimated','rir_id']},
                         'decision_count':len(eligible),'missing_label_count':sum(w['anonymous_label'] is None for w in eligible),
                         'decision_label_counts':dict(counts),'cluster_id_observations':dict(collections.Counter(str(w['cluster_id']) for w in eligible if w['cluster_id'] is not None)),
                         'dominant_label':dominant,'dominant_tied':tied,'missing_evidence':not eligible,
                         'within_turn_label_switches':sum(a!=b for a,b in zip(labels,labels[1:])),
                         'strict_active_decisions':sum(contained([w['start'],w['stop']],t['active_ranges']) for w in eligible),
                         'source_attribution_status':'SINGLE_SCHEDULED_SOURCE_TEMPORAL_PROXY' if reference_complete else 'UNAVAILABLE_UNKNOWN_AMBIENT_SPEECH',
                         'evidence_unique_samples':samples([[w['start'],w['stop']] for w in eligible])})
    groups=[]
    for person in dict.fromkeys(t['speaker_key'] for t in turns):
        group=[t for t in per_turn if t['speaker_key']==person]
        if len(group)<2: continue
        labels=[t['dominant_label'] for t in group]
        unknown=not reference_complete or any(label is None or t['missing_label_count'] for label,t in zip(labels,group))
        classification='unknown' if unknown else 'consistent' if len(set(labels))==1 else 'inconsistent'
        strata=['returning_person']
        if len(set(t['rir_id'] for t in group))>1: strata.append('changed_measured_seat')
        if family_id=='F06': strata.append('silent_gap_return_family')
        if family_id in ['F04','F05']: strata.append('close_or_overlap_family')
        if any(t['whole_clip_bin']!='>=2s' for t in group): strata.append('short_reply_present')
        groups.append({'speaker_key':person,'turn_indices':[t['segment_index'] for t in group],
                       'dominant_labels':labels,'classification':classification,'strata':strata,
                       'unknown_reason':'unknown_ambient_speech_precludes_source_attribution' if not reference_complete else 'missing_or_tied_dominant_label' if unknown else None})
    crossing={'speech_support_boundary':0,'multiple_speaker_active_boundary_or_overlap':0,'whole_clip_boundary':0}
    for w in windows:
        a,b=w['start'],w['stop'];length=b-a
        n=samples(intersection([[a,b]],regions['speech_active']))
        crossing['speech_support_boundary'] += 0<n<length
        crossing['multiple_speaker_active_boundary_or_overlap'] += samples(intersection([[a,b]],regions['multiple_speaker_active']))>0
        crossing['whole_clip_boundary'] += any(a<edge<b for t in turns for r in t['file_support'] for edge in r)
    return {'turns':per_turn,'returning_participant_groups':groups,'return_group_counts':dict(collections.Counter(g['classification'] for g in groups)),
            'window_crossings':crossing,'supported_turn_count':len(turns),'turns_without_contained_evidence':sum(t['missing_evidence'] for t in per_turn),
            'scope':'Anonymous native decision evidence and exported contemporaneous cluster IDs only; no inferred cluster lineage, transcript identity correction, DER/JER or enrollment accuracy.'}


def sample_levels(values, ranges, *, bits):
    import numpy as np
    x=np.asarray(values);valid=intersection(ranges,[[0,len(x)]])
    chunks=[x[a:b] for a,b in valid];n=sum(len(a) for a in chunks)
    if not n:return {'samples':0,'rms_fs':None,'peak_fs':None,'rail_samples':0,'rail_runs':0,'longest_rail_run_samples':0}
    limit=2**(bits-1);energy=0.;peak=0.;rails=0;runs=0;longest=0
    for part in chunks:
        energy+=float(np.sum((part.astype(np.float64)/limit)**2));peak=max(peak,float(np.max(np.abs(part.astype(np.float64))))/limit)
        # Packed XVF23-bit payload in PCM24 clears the LSB; retain inherited
        # positive-rail criterion8388606. PCM16 journal reaches32767 normally.
        mask=(part<=-limit)|(part>=limit-(2 if bits==24 else 1));rails+=int(mask.sum())
        change=np.diff(np.r_[False,mask,False].astype(np.int8));lengths=np.flatnonzero(change==-1)-np.flatnonzero(change==1)
        runs+=len(lengths);longest=max(longest,int(max(lengths,default=0)))
    return {'samples':n,'rms_fs':math.sqrt(energy/n),'peak_fs':peak,'rail_samples':rails,'rail_runs':runs,'longest_rail_run_samples':longest}


def score_output(scene, support, output, events, pcm16, raw_pcm24, guard):
    """Arrays are exact H2 journal PCM16 and raw preadapter PCM24 integer counts."""
    import numpy as np
    guard.require(scene);validate_support(scene,support)
    if output not in ['O0','O1']: raise ValueError('Output must be O0/O1')
    if len(pcm16)!=len(raw_pcm24): raise ValueError('Journal/raw duration differs')
    for values,bits in [(pcm16,16),(raw_pcm24,24)]:
        x=np.asarray(values)
        if x.ndim!=1 or not np.issubdtype(x.dtype,np.signedinteger) or np.any(x < -2**(bits-1)) or np.any(x > 2**(bits-1)-1):
            raise ValueError('Require signed integer PCM counts in declared bit range')
    length=len(pcm16);windows=embedding_windows(events);segs=segmentation_intervals(events)
    whole=[[0,length]];window_ranges=[[w['start'],w['stop']] for w in windows]
    if any(b>length for a,b in window_ranges):raise ValueError('Evidence beyond decoded audio')
    result={'schema':'jp_s5_output_support_metrics_v1','case_id':scene['case_id'],'output':output,'support_sha256':support['support_sha256'],
            'scoring_protocol_sha256':guard.protocol,'decoded_samples':length,'decoded_duration_s':length/RATE,
            'raw_full_output_levels':sample_levels(raw_pcm24,whole,bits=24),'post_adapter_pcm16_full_output_levels':sample_levels(pcm16,whole,bits=16),
            'embedding_gate':gate_diagnostics(pcm16,events),'successful_embedding_calls':len(windows),
            'embedding_calls_per_decoded_minute':len(windows)/(length/RATE/60) if length else None,
            'unique_evidence_audio_samples':samples(window_ranges),'total_processed_window_samples':sum(b-a for a,b in window_ranges),
            'unique_evidence_audio_s':samples(window_ranges)/RATE,'total_processed_window_s':sum(b-a for a,b in window_ranges)/RATE,
            'native_segmentation_event_count':len(segs),'native_segmentation_scope':POLICY['segmentation']['scope'],
            'native_whole_output_segmentation':{'observed_interval_samples':samples([[s['start'],s['stop']] for s in segs]),
                'speech_flag_interval_samples':samples([[s['start'],s['stop']] for s in segs if s['speech']]),
                'overlap_flag_interval_samples':samples([[s['start'],s['stop']] for s in segs if s['overlap']]),
                'decoded_samples':length},
            'event_localized_insertion_words':None,'event_localized_insertion_reason':'Native final cursor is not recognized word/support timing; no word intervals exported',
            'transcript_omission_by_turn':None,'transcript_omission_reason':'Do not equate timestamped transcript output with recognized turn; text scoring is separate',
            'shared_hardware_direction':{'scored_here':False,'join_by_case_id':scene['case_id'],'evidence_units':0}}
    shift=support['output_mappings'][output]['source_with_rir_to_output_offset_samples']
    result['timing_mapping']=support['output_mappings'][output]
    if shift is None:
        result.update(reference_local_status='UNAVAILABLE_NO_SAVED_OUTPUT_MAPPING',regions=None,short_turns=None,continuity=None)
        return result
    regions={key:mapped_ranges(ranges,shift,length) for key,ranges in support['regions_source_with_rir_samples'].items()}
    turns=[]
    for source in support['turns']:
        t=dict(source)
        for key in ['active_ranges','file_support','support_ranges']:t[key]=mapped_ranges(t[key],shift,length)
        turns.append(t)
    detected=union([[s['start'],s['stop']] for s in segs if s['speech']])
    observed=union([[s['start'],s['stop']] for s in segs]);overlap=union([[s['start'],s['stop']] for s in segs if s['overlap']])
    result.update(reference_local_status='AVAILABLE_APPROXIMATE_SOURCE_SUPPORT',regions={},short_turns=[])
    for key,ranges in regions.items():
        result['regions'][key]={'support_samples':samples(ranges),'segmentation_observed_samples':samples(intersection(ranges,observed)),
                                'speech_flag_intersection_samples':samples(intersection(ranges,detected)),
                                'overlap_flag_intersection_samples':samples(intersection(ranges,overlap)),
                                'raw_levels':sample_levels(raw_pcm24,ranges,bits=24),'adapter_pcm16_levels':sample_levels(pcm16,ranges,bits=16)}
    for t in turns:
        ranges=t['support_ranges'];n=samples(ranges);obs=samples(intersection(ranges,observed));hit=samples(intersection(ranges,detected))
        positive=[s for s in segs if s['speech'] and samples(intersection([[s['start'],s['stop']]],ranges))]
        spread=support['output_mappings'][output].get('observed_lag_spread_s') or 0
        uncertainty=round((.02+spread)*RATE)
        boundaries=None
        if positive:
            boundaries={'first_supported_positive_interval_samples':[max(0,positive[0]['start']-uncertainty),min(length,positive[0]['stop']+uncertainty)],
                        'last_supported_positive_interval_samples':[max(0,positive[-1]['start']-uncertainty),min(length,positive[-1]['stop']+uncertainty)],
                        'scope':'Coarse positive source-support intersection, NOT exact detected phonetic onset/offset'}
        other_support=union([r for other in turns if other['segment_index']!=t['segment_index'] for r in other['file_support']])
        scheduled_overlap=samples(intersection(t['file_support'],other_support))>0
        attribution_ok=bool(scene['all_speaker_reference_complete']) and not scheduled_overlap
        attribution_status=('UNAVAILABLE_UNKNOWN_AMBIENT_SPEECH' if not scene['all_speaker_reference_complete'] else
                            'AGGREGATE_FLAG_DURING_OVERLAPPING_TURN_NOT_SOURCE_SPECIFIC' if scheduled_overlap else
                            'SINGLE_SCHEDULED_SOURCE_TEMPORAL_PROXY_NOT_RECOGNITION')
        result['short_turns'].append({**{k:t[k] for k in ['segment_index','source_id','speaker_key','participant_id','dataset','quality_partition','whole_clip_bin','active_duration_bin','whole_clip_duration_s','active_duration_s_estimated']},
                                    'support_samples':n,'segmentation_observed_samples':obs,'speech_flag_intersection_samples':hit,
                                    'detected_supported_flag':bool(hit) if obs else None,
                                    'missed_supported_flag':not bool(hit) if n and obs==n else False if hit else None,
                                    'no_positive_on_observed_support':not bool(hit) if obs else None,
                                    'source_attribution_status':attribution_status,
                                    'source_specific_supported_detection':bool(hit) if obs and attribution_ok else None,
                                    'fully_observed_support':obs==n if n else False,'boundary_interval_uncertainty':boundaries})
    result['continuity']=continuity(turns,windows,regions,scene['family_id'],reference_complete=scene['all_speaker_reference_complete'])
    result['noise_events']=[]
    for noise in support['noise_events']:
        ranges=mapped_ranges(noise['active_ranges'],shift,length)
        result['noise_events'].append({**{k:noise[k] for k in ['segment_index','source_id','parent_id','category','speech_content','strict_nonspeech_eligible','interpretation']},
                                       'active_samples':samples(ranges),'speech_flag_intersection_samples':samples(intersection(ranges,detected)),
                                       'observed_segmentation_samples':samples(intersection(ranges,observed)),
                                       'speech_reference_overlap_samples':samples(intersection(ranges,regions['speech_active'])),
                                       'raw_levels':sample_levels(raw_pcm24,ranges,bits=24),'adapter_pcm16_levels':sample_levels(pcm16,ranges,bits=16)})
    return result


def analyze_bound_output(scene, support, output, job_receipt, guard):
    import numpy as np
    import soundfile as sf
    guard.require(scene)
    if job_receipt['case_id']!=scene['case_id'] or job_receipt['stream']!=output or job_receipt['status']!='COMPLETE' or job_receipt['exit_code']!=0:
        raise ValueError('Require matching complete native job')
    expected=1.4125375446227544 if output=='O0' else 1.
    if job_receipt['adapter']['gain_scalar']!=expected:raise ValueError('Frozen host gain differs')
    events_path=guard.verified_path(scene,job_receipt['events_binding'],'task_logs')
    events=[json.loads(line) for line in events_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if sum(e['event_type']=='session_completed' for e in events)!=1 or any(e['event_type'] in ['failure','session_stopped'] for e in events):
        raise ValueError('Bound journal does not have a unique successful completion')
    journal=guard.verified_path(scene,job_receipt['completion_evidence']['journal'],'task_audio')
    pcm=np.fromfile(journal,dtype='<i2')
    if len(pcm)!=job_receipt['completion_evidence']['exact_full_pcm16_samples'] or len(pcm)!=job_receipt['adapter']['samples']:
        raise ValueError('Native journal length differs from bound full-input completion')
    rawpath=guard.verified_path(scene,job_receipt['raw_audio'],'task_audio')
    with sf.SoundFile(rawpath) as f:
        if f.samplerate!=RATE or f.channels!=1 or f.subtype!='PCM_24':raise ValueError('Raw output must remain16kHz monoPCM24')
        raw=f.read(dtype='int32')>>8
    return score_output(scene,support,output,events,pcm,raw,guard)


def shared_direction_metrics(scene, support, capture_result, callback_metadata, telemetry_rows, guard):
    from s4_spatial_analysis import Availability, ReceiptTimeline, STREAMS, summarize_window
    guard.require(scene);validate_support(scene,support)
    available=Availability(callback_metadata,capture_result['framing']['startup_frames_excluded'],capture_result['payload']['capture_minus_source_offset_samples'])
    timeline=ReceiptTimeline(telemetry_rows);rows=[]
    for noise in support['noise_events']:
        ranges=union([v for a,b in noise['active_ranges'] for v in available.source_range(a,b)])
        rows.append({'segment_index':noise['segment_index'],'parent_id':noise['parent_id'],'interpretation':noise['interpretation'],
                     'source_active_samples':samples(noise['active_ranges']),'host_support_ns':samples(ranges),
                     'streams':{name:summarize_window(timeline,name,ranges) for name in STREAMS}})
    allranges=union([v for n in support['noise_events'] for a,b in n['active_ranges'] for v in available.source_range(a,b)])
    return {'schema':'jp_s5_shared_noise_direction_v1','case_id':scene['case_id'],'support_sha256':support['support_sha256'],
            'physical_trace_evidence_units':1,'paired_output_evidence_units':0,'noise_events':rows,
            'all_noise_union_host_support_ns':samples(allranges),'all_noise_union_streams':{name:summarize_window(timeline,name,allranges) for name in STREAMS},
            'scope':POLICY['direction'],'comparison_restriction':'Shared retained direction indication; neither O0 nor O1 caused an improvement in this shared trace'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe-policy',action='store_true',required=True)
    parser.parse_args()
    print(json.dumps({'policy':POLICY,'policy_sha256':fingerprint(POLICY)},indent=2))


if __name__=='__main__':main()
