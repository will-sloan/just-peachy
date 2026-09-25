"""Causal, total D0 activity evidence observer. README_D0_ACTIVITY.md."""
from copy import deepcopy
import math


def number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError('Finite numeric time required')
    return float(value)


class D0ActivityEvidence:
    """Observe full masks and explicit track claims without changing prediction.

    Mask updates retain first and latest observations. Track claims apply only
    to their original clean support; contradictory IDs remain a conflict. This
    is evidence coverage, not a diarization decoder or a caption/widget clock.
    """
    def __init__(self, frames, *, clock_kind, max_events=4096, max_segments=100000):
        if type(frames) is not int or not 0 < frames <= 120*16000:
            raise ValueError('One bounded <=120-second mono16k scene required')
        if clock_kind not in ('modeled_component_availability', 'observed_policy_availability'):
            raise ValueError('Explicit availability clock required')
        if type(max_events) is not int or type(max_segments) is not int or min(max_events,max_segments) <= 0:
            raise ValueError('Positive integer observer bounds required')
        self.duration = frames/16000
        self.clock_kind = clock_kind
        self.max_events, self.max_segments = max_events, max_segments
        self.clock = -1.; self.events = {}; self.observations = {}
        self.spans = [(0., self.duration, (None, None, ()))]

    def _admit(self, event_id, end, available):
        end, available = number(end), number(available)
        if (not isinstance(event_id,str) or not 0 < len(event_id) <= 128 or event_id in self.events
                or len(self.events) >= self.max_events or not 0 <= end <= self.duration
                or available < end or available < self.clock):
            raise ValueError('Duplicate, over-budget or noncausal observer event')
        return end, available

    def _overlay(self, intervals, transform):
        """Linear sweep, preserving unknown gaps and original float boundaries."""
        output=[]; j=0
        def append(a,b,value):
            if b <= a:
                return
            if output and output[-1][1] == a and output[-1][2] == value:
                output[-1] = (output[-1][0], b, value)
            else:
                output.append((a,b,value))
        for start,end,value in self.spans:
            at=start
            while j < len(intervals) and intervals[j][1] <= at:
                j+=1
            while j < len(intervals) and intervals[j][0] < end:
                left,right,update=intervals[j]
                append(at,min(end,left),value)
                a,b=max(at,left),min(end,right)
                if b > a:
                    append(a,b,transform(value,update));at=b
                if right <= end:
                    j+=1
                else:
                    break
            append(at,end,value)
        if len(output) > self.max_segments:
            raise ValueError('Activity observer segment bound exceeded')
        self.spans=output

    def segmentation(self, event_id, payload):
        end,available=self._admit(event_id,payload['source_end_sec'],payload['modeled_available_at_sec']
            if self.clock_kind=='modeled_component_availability' else payload['observed_available_at_sec'])
        step=number(payload['frame_step_sec']); width=number(payload['frame_duration_sec'])
        if (step != .016875 or width != .0619375 or payload['receptive_end_sec'] != end
                or payload['receptive_start_sec'] != max(0.,end-10.)
                or payload['left_padding_sec'] != max(0.,10.-end)):
            raise ValueError('D0 receptive field differs from frozen geometry')
        speech,overlap=payload['speech_frames'],payload['overlap_frames']
        if not speech or len(speech)!=len(overlap) or len(speech)>1000:
            raise ValueError('Complete equal-length activity masks required')
        intervals=[]; observations={}
        for i,(s,o) in enumerate(zip(speech,overlap)):
            if s not in (0,1,False,True) or o not in (0,1,False,True) or o > s:
                raise ValueError('Invalid speech/overlap mask')
            # Exact half-sample ticks avoid accidental gaps between adjacent
            # binary frame cells; there is no truth-fitted temporal shift.
            center_ticks=round(end*32000)-320000+991+i*540
            a=max(0.,(center_ticks-270)/32000);b=min(end,(center_ticks+270)/32000)
            if b <= a:
                continue
            mask='overlap' if o else 'speech' if s else 'silence'
            key=event_id+':'+mask
            observations[key]=dict(event_id=event_id,mask=mask,available_at_sec=available,source_end_sec=end)
            intervals.append((a,b,key))
        self._overlay(intervals,lambda old,key:(key if old[0] is None else old[0],key,old[2]))
        self.observations.update(observations)
        self.events[event_id]=dict(kind='segmentation',available_at_sec=available,source_end_sec=end)
        self.clock=available

    def track(self, event_id, *, source_start_sec, source_end_sec, available_at_sec,
              track_id, clean_intervals, observation_id, committed):
        """Accept an actual predictor decision plus its exact embedding support.

        No roster, name, vector or reference field enters this interface. The
        caller must bind decision and observation IDs to their immutable events.
        Provisional IDs remain marked; no commitment or lineage is inferred.
        """
        end,available=self._admit(event_id,source_end_sec,available_at_sec)
        start=number(source_start_sec)
        if (not 0 <= start < end or type(committed) is not bool
                or (track_id is not None and (type(track_id) is not int or track_id <= 0))
                or not isinstance(observation_id,str) or not 0 < len(observation_id) <= 128):
            raise ValueError('Invalid anonymous decision metadata')
        intervals=[];previous=start
        for a,b in clean_intervals:
            a,b=number(a),number(b)
            if not start <= a < b <= end or a < previous:
                raise ValueError('Clean support outside decision or overlapping intervals')
            intervals.append((a,b,event_id));previous=b
        self._overlay(intervals,lambda old,key:(old[0],old[1],(*old[2],key)))
        self.events[event_id]=dict(kind='track',available_at_sec=available,source_start_sec=start,
            source_end_sec=end,track_id=track_id,observation_id=observation_id,committed=committed)
        self.clock=available

    def snapshot(self):
        spans=[];seconds={};assigned=unassigned=conflict=overlap=0.
        for start,end,(first,latest,claims) in self.spans:
            state='unobserved' if latest is None else self.observations[latest]['mask']
            ids=sorted({self.events[c]['track_id'] for c in claims if self.events[c]['track_id'] is not None})
            assignment=('not_speech' if state in ('silence','unobserved') else
                'overlap_unassigned' if state=='overlap' else 'conflicting_tracks' if len(ids)>1 else
                'supported_track' if ids else 'unassigned_speech')
            seconds[state]=seconds.get(state,0.)+end-start
            if assignment=='supported_track':assigned+=end-start
            elif assignment=='unassigned_speech':unassigned+=end-start
            elif assignment=='conflicting_tracks':conflict+=end-start
            elif assignment=='overlap_unassigned':overlap+=end-start
            spans.append(dict(start=start,end=end,state=state,assignment=assignment,
                track_id=ids[0] if assignment=='supported_track' else None,
                has_committed_track_support=assignment=='supported_track' and any(self.events[c]['committed']
                    and self.events[c]['track_id']==ids[0] for c in claims),
                unresolved_claim_also_present=any(self.events[c]['track_id'] is None for c in claims),
                candidate_track_ids=ids,claim_event_ids=list(claims),first_mask_observation=first,
                latest_mask_observation=latest))
        return dict(schema='n4-d0-activity-evidence-v1',duration_sec=self.duration,
            clock_kind=self.clock_kind,availability_through_sec=self.clock if self.events else None,
            first_masks_are_first_observation_not_widget_visibility=True,
            global_diarization_or_DER_qualified=False,unassigned_is_not_a_person_or_collapsed_Unknown_cluster=True,
            mask_seconds=seconds,supported_single_speech_sec=assigned,unassigned_single_speech_sec=unassigned,
            conflicting_single_speech_sec=conflict,overlap_without_global_source_assignment_sec=overlap,
            events=deepcopy(self.events),observations=deepcopy(self.observations),spans=spans)
