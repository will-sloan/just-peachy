"""Nemotron activity -> common coarse revision spans, online. See README_N2.md."""
from collections import deque
from copy import deepcopy
import math
import threading
import time
import numpy as np
from .pipeline import PrototypeEngine
from .mode_policy import NAMED_MODES
from .n2_identity import N2NameMap,N2Gallery


class ActivityTimeline:
    """Bounded immutable native frames, available only after their actual call."""
    def __init__(self,reserve_sec=120,threshold=.5):
        self.frames=deque();self.reserve_sec=reserve_sec;self.threshold=threshold
        self.next_frame=0;self.seen_slots=set();self.end=0.;self.frame_sec=.01

    def append(self,update):
        if update.frame_start!=self.next_frame:raise ValueError('D1 activity frame discontinuity')
        self.frame_sec=update.seconds_per_frame
        for index,probability in enumerate(update.probabilities):
            start=(update.frame_start+index)*self.frame_sec
            end=min(start+self.frame_sec,update.audio_received_sec)
            # Preserve native endpoint overhang in raw events; it supplies no
            # real audio and is never silently turned into query support.
            if end<=start:continue
            active=tuple(np.flatnonzero(probability>=self.threshold).tolist())
            self.frames.append((start,end,active,update.available_at_monotonic))
            self.seen_slots.update(active);self.end=end
        self.next_frame=update.frame_end
        while self.frames and self.frames[0][1]<self.end-self.reserve_sec:self.frames.popleft()

    def associate(self,start,end):
        if end<=start or end>self.end+1e-6:return None
        rows=[r for r in self.frames if min(end,r[1])-max(start,r[0])>1e-7]
        if not rows or rows[0][0]>start+1e-6:return None
        voiced=[r for r in rows if r[2]]
        slots={slot for r in voiced for slot in r[2]}
        covered=sum(min(end,r[1])-max(start,r[0]) for r in voiced)
        overlap=any(len(r[2])>1 for r in voiced)
        # Coarse ASR revision windows may span multiple turns. Do not assign
        # that window to its majority speaker or invent exact word positions.
        slot=next(iter(slots)) if len(slots)==1 and not overlap and covered>=min(.08,(end-start)*.5) else None
        return dict(slot=slot,slots=sorted(slots),overlap=overlap,voiced_sec=covered,
            available_at_monotonic=max(r[3] for r in rows),
            reason='single_activity_channel_in_coarse_window' if slot is not None else 'mixed_overlap_or_unvoiced_coarse_window')

    def exclusive_tail(self):
        if not self.frames or len(self.frames[-1][2])!=1:return None
        last=self.frames[-1];slot=last[2][0];start=last[0];end=last[1]
        for row in reversed(self.frames):
            if row[2]!=(slot,) or row[1]<start-1e-6:break
            start=row[0]
            if end-start>=2.:start=end-2.;break
        return slot,start,end

    def exclusive_runs(self,*,final=False):
        """All retained singleton runs, including runs that ended within a chunk."""
        runs=[];current=None
        for start,end,active,_ in self.frames:
            slot=active[0] if len(active)==1 else None
            if current is not None and (slot!=current[0] or start>current[2]+1e-6):
                runs.append((*current,True));current=None
            if slot is not None:
                current=(slot,start,end) if current is None else (slot,current[1],end)
        if current is not None:runs.append((*current,bool(final)))
        return runs

    def exclusive_windows(self,last_query,*,minimum_sec=.5,hop_sec=.5,maximum_sec=2.):
        """Causal fixed-hop real windows; ended turns are not lost to silence.

        The grid begins at each observed exclusive run's actual start. No
        repetition, silence removal or evaluator boundary enters selection.
        """
        selected=[];cursor=dict(last_query)
        for slot,start,end,_ in self.exclusive_runs():
            next_end=max(start+minimum_sec,cursor.get(slot,-math.inf)+hop_sec)
            while next_end<=end+1e-6:
                actual_end=min(next_end,end)
                selected.append((slot,max(start,actual_end-maximum_sec),actual_end,start))
                cursor[slot]=actual_end;next_end+=hop_sec
        return selected


class N2Engine(PrototypeEngine):
    def _admit_research_gallery(self,gallery,maximum_profiles):
        from .people import PersonalGallery
        from .n2_models import redim_namespace
        if not isinstance(gallery,(N2Gallery,PersonalGallery)):
            raise ValueError('N2 requires an explicit model-compatible gallery object')
        embedding=getattr(self.resident,'embedding','E0')
        expected=(self.resident.document['embedding_namespace'] if embedding=='E1'
                  else redim_namespace(self.config))
        actual=getattr(gallery,'namespace',None)
        if actual is None and embedding=='E0':
            receipt=gallery.receipt
            if receipt.get('backend_sha256')!=expected['model_sha256'] or receipt.get('preprocessing')!=expected['preprocessing']:
                raise ValueError('N2 baseline gallery model/preprocessing differs')
        elif actual!=expected:raise ValueError('N2 gallery differs from the selected encoder namespace')
        if gallery.receipt.get('loaded_count')!=len(gallery.ids) or len(gallery.ids)>maximum_profiles:
            raise ValueError('N2 gallery count differs or exceeds the configured bound')
        return gallery

    def __init__(self,*args,diarization='D1',n2_observer_factory=None,**kwargs):
        self.n2_diarization=diarization;self._n2_lock=threading.RLock()
        self.n2_observer_factory=n2_observer_factory;self.n2_observer=None
        self._n2_observer_lock=threading.Lock()
        self._n2_timeline=ActivityTimeline();self._n2_names={};self._n2_revision=0
        self._n2_span_signatures={};self._n2_last_query={};self._n2_embedding_serial=0
        self._n2_associations={}
        self._n2_name_history={};self._n2_reported_runs=set();self._n2_admitted_runs=set()
        self._n2_short_run_count=0;self._n2_short_run_sec=0.;self._n2_reported_run_end=-1.
        super().__init__(*args,**kwargs)
        self.n2_name_map=N2NameMap(self._research_gallery,closed=self.mode=='selected_closed')

    def begin(self):
        super().begin()
        # N2 galleries use their own C calibration. D0 association still uses
        # the original tracker, segmentation and window-admission implementation.
        if self.n2_diarization=='D0':
            from edge_speech_pipeline.research_s7_policy import _MeasuredDelegate
            self.prototype_identity=self.n2_name_map
            self._scheduler.scheduler.identity_resolver=_MeasuredDelegate(self.n2_name_map,self._s7_observed_clock,'identity')
        else:self.prototype_identity=self.n2_name_map if self.mode in NAMED_MODES else None
        self._ensure_n2_observer()

    def _ensure_n2_observer(self):
        if self.n2_observer_factory is not None:
            with self._n2_observer_lock:
                if self.n2_observer is None:
                    self.n2_observer=self.n2_observer_factory(self._session_dir.name)

    def _s6d_write_event(self,event):
        # The serialized writer receives the exact stamped publication event.
        # Its observer queue never executes on Sherpa's event producer thread.
        super()._s6d_write_event(event)
        self._ensure_n2_observer()
        if self.n2_observer is not None:
            self.n2_observer.event(event.event_type,event.source_time_sec,event.payload)

    def _emit(self,event_type,source_sec,payload):
        super()._emit(event_type,source_sec,payload)
        if self.n2_diarization=='D1' and event_type in ('s6d_text_ready','transcript_partial','transcript_final'):
            # The text producer never waits for identity/model work. The active
            # speaker worker catches up using already published rows instead.
            self._revise_supported_spans(utterance_id=payload.get('utterance_id'),blocking=False)

    def _speaker_loop(self,models):
        if self.n2_diarization=='D0':return super()._speaker_loop(models)
        journal=self._identity_journal;cursor=0;ready=0.
        try:
            diarizer=self.resident.acquire_diarizer(self._session_dir.name)
            self._emit('n2_diarization_binding',0.,diarizer.manifest())
            while True:
                if self._state=='FAILED':raise RuntimeError('D1 lane abort after session failure')
                audio=journal.read(cursor,1600)
                if len(audio):
                    cursor+=len(audio)
                    update=diarizer.push(audio)
                    self._accept_activity(update,models)
                    ready=self._s7_observed_clock.relative()
                    self._scheduler_advance('speaker',cursor/16000,ready)
                    self._telemetry.update(speaker_cursor_sec=cursor/16000,
                        speaker_analyzed_through_sec=self._n2_timeline.end,
                        speaker_lag_sec=max(0.,journal.duration_sec-self._n2_timeline.end))
                elif journal.finished and cursor>=journal.committed_samples:break
            self._accept_activity(diarizer.finish(),models)
            self._telemetry.update(speaker_cursor_sec=cursor/16000,speaker_lag_sec=0.,
                n2_seen_slots=sorted(self._n2_timeline.seen_slots),n2_embedding_calls=self._n2_embedding_serial,
                n2_name_map=self.n2_name_map.snapshot(),identity_audio_samples=cursor,paired_audio_samples=self._journal.committed_samples)
            self._telemetry.update(n2_exclusive_runs_below_embedding_minimum=self._n2_short_run_count,
                n2_exclusive_seconds_below_embedding_minimum=self._n2_short_run_sec)
        except Exception as exc:self._fail('N2 identity lane failed: '+str(exc))
        finally:self._scheduler_advance('speaker',float('inf'),ready)

    def _accept_activity(self,update,models):
        if not len(update.probabilities) and not update.is_final:return
        with self._n2_lock:
            if len(update.probabilities):self._n2_timeline.append(update)
            self._emit('n2_diarization_frames',update.audio_received_sec,dict(
                frame_start=update.frame_start,probabilities=update.probabilities.tolist(),
                frame_step_sec=update.seconds_per_frame,audio_received_sec=update.audio_received_sec,
                native_frame_end_sec=update.emitted_audio_end_sec,
                endpoint_overhang_sec=max(0.,update.emitted_audio_end_sec-update.audio_received_sec),
                available_at_monotonic=update.available_at_monotonic,received_at_monotonic=update.received_at_monotonic,
                compute_sec=update.compute_sec,is_final=update.is_final,track_ids=list(update.track_ids),
                capacity_status=update.capacity_status,activity_threshold=.5,activity_is_identity_confidence=False))
            candidates=self._n2_timeline.exclusive_windows(self._n2_last_query)
            for slot,start,end,run_start in candidates:
                # Dispatch the same genuine contiguous waveform windows for E0
                # and E1. No concatenated turns, overlap removal or Q oracle.
                if end-start>=.5-1e-6 and end-self._n2_last_query.get(slot,-1e9)>=.5-1e-6:
                    first,last=round(start*16000),round(end*16000)
                    audio=self._identity_journal.read(first,last-first,wait_sec=0)
                    if len(audio)!=last-first:raise RuntimeError('D1 selected window unavailable in bounded audio ring')
                    vector=models.embed(audio);self._n2_embedding_serial+=1;self._n2_last_query[slot]=end
                    self._n2_admitted_runs.add((slot,run_start))
                    eid=f'n2-embedding:{self._n2_embedding_serial:08d}'
                    event=dict(event_id=eid,source_start_sec=first/16000,source_end_sec=last/16000,
                        # Archive the exact half-open waveform slice supplied
                        # to embed(), after rounding native frame coordinates.
                        receptive_start_sec=first/16000,receptive_end_sec=last/16000,
                        left_padding_sec=0.,available_source_cursor_sec=update.audio_received_sec,
                        availability_method='observed native activity then exact contiguous waveform embedding; no source padding',
                        available_at_sec=self._s7_observed_clock.relative(),vector=vector.tolist(),speech=True,
                        overlap=False,evidence_kind='mature' if end-start>=1.5 else 'short',
                        clean_intervals=[[first/16000,last/16000]])
                    track=update.track_ids[slot]
                    decision=self.n2_name_map.resolve(dict(tracker_id=track,cluster_id=track,anonymous_label=f'Speaker {slot+1}',
                        state='committed',committed=True),event)
                    self._n2_names[slot]=dict(decision,event_id=eid,evidence_start_sec=start,evidence_end_sec=end,
                        available_at_monotonic=time.perf_counter())
                    # Keep bounded temporal support for delayed captions. A
                    # later returning turn cannot relabel unrelated old spans.
                    history=self._n2_name_history.setdefault(slot,[])
                    name=self._n2_names[slot]
                    history.append({key:name.get(key) for key in ('display_label','known_profile_id','known_name',
                        'naming_state','event_id','evidence_start_sec','evidence_end_sec','available_at_monotonic')})
                    floor=self._n2_timeline.end-self._n2_timeline.reserve_sec
                    self._n2_name_history[slot]=[item for item in history if item['evidence_end_sec']>=floor][-256:]
                    self._emit('research_embedding',end,dict(**{k:v for k,v in event.items() if k!='vector'},
                        normalized_embedding=vector.tolist(),evidence_event_id=eid,model_namespace=models.namespace,
                        compute_ms=models.last_embed_ms,actual_selected_window=True,model_slot=slot,tracker_id=track,
                        available_at_monotonic=self._n2_names[slot]['available_at_monotonic'],
                        admission=dict(reason='exclusive_native_activity_contiguous',clean_fraction=1.,
                            selection_threshold=.5,not_ground_truth=True)))
                    self._emit('speaker_decision',end,dict(decision,event_id=eid,source_start_sec=start,source_end_sec=end,
                        available_at_sec=event['available_at_sec']))
            for slot,start,end,closed in self._n2_timeline.exclusive_runs(final=update.is_final):
                key=(slot,start,end)
                # A retained run's start can move when the 120-second ring
                # expires. Its fixed end must not become a new denominator.
                if not closed or end<=self._n2_reported_run_end+1e-7:continue
                self._n2_reported_runs.add(key)
                self._n2_reported_run_end=end
                short=end-start<.5-1e-6
                if short:self._n2_short_run_count+=1;self._n2_short_run_sec+=end-start
                self._emit('n2_exclusive_run_coverage',end,dict(model_slot=slot,source_start_sec=start,
                    source_end_sec=end,duration_sec=end-start,minimum_embedding_sec=.5,
                    embedding_selected=(slot,start) in self._n2_admitted_runs,
                    unavailable_reason='BELOW_EMBEDDING_MINIMUM' if short else None,
                    denominator_scope='predicted_contiguous_exclusive_activity_not_reference_turns'))
            if len(self._n2_reported_runs)>8192:
                floor=self._n2_timeline.end-self._n2_timeline.reserve_sec
                self._n2_reported_runs={key for key in self._n2_reported_runs if key[2]>=floor}
                self._n2_admitted_runs={key for key in self._n2_admitted_runs if key[1]>=floor}
            self._revise_supported_spans()

    def _name_for_span(self,slot,start,end):
        if slot is None:return {}
        for name in reversed(self._n2_name_history.get(slot,[])):
            if min(end,name['evidence_end_sec'])-max(start,name['evidence_start_sec'])>1e-7:
                return name
        return {}

    def _revise_supported_spans(self,utterance_id=None,blocking=True):
        if getattr(self,'_s6d_presentation',None) is None:return
        if not self._n2_lock.acquire(blocking=blocking):return
        try:
            for row in self._s6d_presentation.snapshot_rows():
                if utterance_id is not None and row['utterance_id']!=utterance_id:continue
                groups={}
                for span in row.get('word_spans',[]):
                    a,b=span['source_start_sec'],span['source_end_sec']
                    key=(span['id'],row['text_revision_id'])
                    if b<self._n2_timeline.end-self._n2_timeline.reserve_sec and key in self._n2_span_signatures:
                        # Expired evidence is not a reason to erase a label
                        # already published on an older caption span.
                        continue
                    association=self._n2_associations.get((a,b))
                    if association is None:
                        association=self._n2_timeline.associate(a,b)
                        if association is not None:self._n2_associations[(a,b)]=association
                    if association is None:continue
                    slot=association['slot'];name=self._name_for_span(slot,a,b)
                    track=f'{self._session_dir.name}:nemotron-slot-{slot}' if slot is not None else None
                    anonymous=f'Speaker {slot+1}' if slot is not None else 'Unknown'
                    label=(name.get('display_label') or 'Unknown') if self.mode in NAMED_MODES else anonymous
                    signature=(track,label,name.get('known_profile_id'),name.get('naming_state'),association['reason'])
                    if self._n2_span_signatures.get(key)==signature:continue
                    self._n2_span_signatures[key]=signature
                    group_key=(a,b,signature)
                    groups.setdefault(group_key,dict(ids=[],association=association,name=name))['ids'].append(span['id'])
                for (a,b,signature),group in groups.items():
                    self._n2_revision+=1;track,label,pid,state,reason=signature
                    name=group['name'];now=self._s7_observed_clock.relative()
                    payload=dict(event_id=f'n2-caption:{self._n2_revision:08d}',utterance_id=row['utterance_id'],
                        target_text_revision_id=row['text_revision_id'],target_span_ids=group['ids'],
                        source_start_sec=a,source_end_sec=b,target_source_start_sec=row['source_start_sec'],
                        target_source_end_sec=row['source_end_sec'],available_at_sec=now,latest_label_time=now,
                        identity_version=self._n2_revision,latest_label=label,replacement_tracker_id=track,
                        latest_anonymous_label=f"Speaker {group['association']['slot']+1}" if track else 'Unknown',
                        latest_known_profile_id=pid,latest_known_name=name.get('known_name'),latest_naming_state=state or 'unknown',
                        evidence_ids=[name['event_id']] if name else [],association=group['association'],
                        association_reason=reason,timing_kind='ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT',
                        changes_raw_words=False,name_evidence_end_sec=name.get('evidence_end_sec'),
                        publication_freshness='historical_caption_annotation_only')
                    self._emit('transcript_label_revision',b,payload)
            if len(self._n2_span_signatures)>16384:
                retained={s['id'] for r in self._s6d_presentation.snapshot_rows() for s in r.get('word_spans',[])}
                self._n2_span_signatures={k:v for k,v in self._n2_span_signatures.items() if k[0] in retained}
            if len(self._n2_associations)>16384:
                floor=self._n2_timeline.end-self._n2_timeline.reserve_sec
                self._n2_associations={k:v for k,v in self._n2_associations.items() if k[1]>=floor}
        finally:self._n2_lock.release()
