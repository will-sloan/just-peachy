"""Evaluator-only conversion of sealed N4 method output. README_INTEGRATED_SCORING.md."""
from collections import defaultdict
import gzip
import hashlib
import json
import math

from common import verify
from metrics import canonical,lexical,score_cell,speaker_words


def read_artifact(binding):
    """Pure standard-library bounded reader; never imports application/model code."""
    verify(binding['compressed'])
    with gzip.open(binding['compressed']['path'],'rb') as stream:data=stream.read(32*1024**2+1)
    if (len(data)>32*1024**2 or len(data)!=binding['expanded_bytes']
            or hashlib.sha256(data).hexdigest()!=binding['expanded_sha256']):
        raise ValueError('Expanded method artifact changed or exceeded bound')
    return json.loads(data)


def read_component_events(cell):
    verify(cell['events'])
    with gzip.open(cell['events']['path'],'rb') as stream:data=stream.read(32*1024**2+1)
    expected=cell['events_expanded']
    if (len(data)>32*1024**2 or len(data)!=expected['uncompressed_bytes']
            or hashlib.sha256(data).hexdigest()!=expected['uncompressed_sha256']):
        raise ValueError('Expanded component artifact changed or exceeded bound')
    return [json.loads(line) for line in data.splitlines()]


def finite_number(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Nonfinite or nonnumeric activity value')
    return value


def native_activity(events,job_id,duration):
    """Actual D1 slots, .5 native threshold, intersection with delivered support.

    Never infer global D0 identities from speech masks or embedding windows.
    Native overhang is reported, not aligned to the evaluator's reference.
    """
    if finite_number(duration)<=0:raise ValueError('Positive file duration required')
    frames=0;overhang=0.;segments=[];next_frame=0;step_value=None;received=0.
    expected_tracks=[f'{job_id}:nemotron-slot-{i}' for i in range(8)]
    for row in events:
        if row['event_type']!='n2_diarization_frames':continue
        p=row['payload'];step=finite_number(p['frame_step_sec']);current=finite_number(p['audio_received_sec'])
        if (type(p['frame_start']) is not int or p['frame_start']!=next_frame or step<=0
                or current<received or current<0 or current>duration+1e-9
                or (step_value is not None and step_value!=step) or p['track_ids']!=expected_tracks
                or p.get('activity_threshold',.5)!=.5):raise ValueError('Native D1 frame/session/support contract changed')
        received=current;step_value=step;support=min(duration,current)
        for offset,probabilities in enumerate(p['probabilities']):
            if len(probabilities)!=8 or any(not 0<=finite_number(v)<=1 for v in probabilities):
                raise ValueError('Native probability shape or value changed')
            start=(next_frame+offset)*step;end=start+step;frames+=1
            overhang+=max(0.,end-max(start,support))
            if start>=support:continue
            for slot,value in enumerate(probabilities):
                if value>=.5:segments.append(dict(start=start,end=min(end,support),label=p['track_ids'][slot]))
        next_frame+=len(p['probabilities'])
    return (segments if frames else None),dict(native_frames=frames,overhang_seconds=overhang,
        threshold=.5,rule='Intersection with actual delivered waveform; original events retained; no reference-fitted shift',
        global_activity_status='RECORDED_D1_NATIVE_SLOTS' if frames else 'UNAVAILABLE_NO_NATIVE_FRAMES')


def raw_projection(publication,projection):
    """Rejoin exact raw fragments in admitted utterance/token order, no truth input."""
    if (publication.get('status')!='PASS_MODELED_MODE_APPLICATION_METHODS_ONLY'
            or projection.get('status')!='PASS_ACTUAL_CONSUMER_AND_LABEL_PROJECTION_ONLY'
            or publication.get('publication_method_qualification')!='ACTUAL_METHODS_WITH_MODELED_MODULE_CLOCKS'
            or publication['contract']!=projection['contract'] or projection.get('controller_closed') is not True
            or projection.get('consumer_thread_alive') is not False or projection.get('physical_widget_observed') is not False):
        raise ValueError('Require closed explicitly modeled publication/Controller artifacts')
    state=publication['presentation']['rows'];groups=defaultdict(list);raw_rows={}
    if len({r['caption_key'] for r in state})!=len(state):raise ValueError('Duplicate caption-state key')
    for row in projection['controller_raw_rows']:
        if row['caption_key'] in raw_rows:raise ValueError('Duplicate Controller raw row')
        raw_rows[row['caption_key']]=row
    for row in projection['final_rows']:
        if not isinstance(row.get('raw_asr_text'),str) or row.get('visible') is not True:
            raise ValueError('Missing or hidden primary raw caption fragment')
        groups[row['caption_key']].append(row)
    expected={r['caption_key'] for r in state}
    if set(groups)!=expected or set(raw_rows)!=expected:raise ValueError('Dropped or invented final caption')
    segments=[];texts=[];formatting=[];utterances=set()
    for parent in state:
        uid=parent['utterance_id'];key=parent['caption_key']
        if uid in utterances:raise ValueError('Duplicate independent utterance')
        utterances.add(uid)
        parts=sorted(groups[key],key=lambda r:r['token_range'][0]);end=0
        for row in parts:
            bounds=row['token_range']
            if (len(bounds)!=2 or any(type(v) is not int for v in bounds) or bounds[0]!=end or bounds[1]<bounds[0]
                    or row['utterance_id']!=uid or row['final']!=parent['final']):
                raise ValueError('Overlapping, missing or foreign raw token fragment')
            end=bounds[1]
            # Explicit None check preserves a legitimate numeric tracker ID zero.
            track=row.get('track_id');segments.append(dict(text=row['raw_asr_text'],track='Unknown' if track is None else str(track)))
        text=''.join(row['raw_asr_text'] for row in parts)
        if (text!=parent['text'] or text!=raw_rows[key]['text'] or end!=len(parent['word_spans'])
                or raw_rows[key]['utterance_id']!=uid):raise ValueError('Raw words or token coverage changed')
        texts.append(text)
        if parent['final']:
            formatting.append(dict(utterance_id=uid,raw_text=text,display_text=parent['display_text'],
                diagnostic='Lexical preservation relative to actual ASR words; no formatting gold implied'))
    return ' '.join(texts),segments,formatting


def convert(publication,projection,speaker_events,job,diarizer):
    if diarizer not in ('D0','D1') or publication['contract']['diarization']!=diarizer:
        raise ValueError('Diarizer contract differs')
    raw,segments,formatting=raw_projection(publication,projection)
    duration=job['frames']/16000
    if diarizer=='D1':activity,support=native_activity(speaker_events,job['job_id'],duration)
    else:
        if any(r['event_type']=='n2_diarization_frames' for r in speaker_events):raise ValueError('D1 activity cannot substitute for D0')
        activity=None;support=dict(global_activity_status='UNAVAILABLE_D0_GLOBAL_SPEAKER_TIMELINE',
            native_frames=0,overhang_seconds=None,rule='Binary speech/overlap and sparse embedding tracks are not global speaker activity')
    return dict(job_id=job['job_id'],status='COMPLETE',raw_text=raw,segments=segments,activity=activity,
        activity_support=support,formatting= formatting,
        naming_metrics_status='UNAVAILABLE_ACTUAL_WIDGET_VISIBILITY_NOT_RECORDED',
        first_widget_visibility='UNAVAILABLE_MODELED_METHOD_REPLAY_ONLY',
        resource_metrics_status='UNAVAILABLE_COMPLETE_STACK_NOT_RUN')


def score_prediction(truth,prediction):
    """Pinned counts and explicit scope. No recognizer sees evaluator references."""
    result=score_cell(truth,prediction)
    result.update(naming_metrics_status='UNAVAILABLE_ACTUAL_WIDGET_VISIBILITY_NOT_RECORDED',
        first_widget_visibility='UNAVAILABLE_MODELED_METHOD_REPLAY_ONLY',integrated_N4_cells=0)
    if prediction['status']!='COMPLETE':return result
    result['activity_support']=prediction['activity_support']
    changed=[];format_totals=dict(utterances=0,errors=0,words=0,substitutions=0,deletions=0,insertions=0)
    for row in prediction['formatting']:
        measured=lexical(canonical(row['raw_text']),canonical(row['display_text']))
        format_totals['utterances']+=1
        for k in ('errors','words','substitutions','deletions','insertions'):format_totals[k]+=measured[k]
        if measured['errors']:changed.append(dict(utterance_id=row['utterance_id'],counts=measured))
    result['formatting_lexical_preservation']=dict(status='ASR_WORD_PRESERVATION_DIAGNOSTIC_NOT_PUNCTUATION_ACCURACY',
        totals=format_totals,changed_utterances=changed)
    result['hypothesis_words']=len(canonical(prediction['raw_text']).split())
    if truth['reference_class'] in ('complete_nonoverlap','complete_overlap'):
        # Identity names have no effect on permutation-invariant speaker metrics.
        # These two controls deliberately show that blind spot, not recognition.
        control=speaker_words(truth['turns'],[dict(text=s['text'],track='ALL_UNKNOWN') for s in prediction['segments']])
        result['constant_speaker_controls']=dict(all_unknown=control,all_one_name=control,
            interpretation='Identical permutation-invariant scores; neither control supplies evidence of correctly recognized names')
    return result
