"""Opt-in observed policy admission and live freshness. See README_RESEARCH_S7_POLICY.md."""
from collections import OrderedDict
from copy import deepcopy
import math
import threading
import time

EVIDENCE_HISTORY_LIMIT = 4096
PRUNE_INTERVAL = 128
HISTORY_CLOCK = 'immutable observed upstream admission'
LEGACY_FIRST_TIMES_CLOCK = 'observed input timeline; not policy finish or GUI application'


def predictor_payload(event):
    """Original V3 field allowlist; extra clocks/reference data stay in a sidecar."""
    required={'kind','event_id','source_start_sec','source_end_sec','available_at_sec'}
    extra={'segmentation':{'speech','overlap'},
        'embedding':{'vector','speech','overlap','receptive_start_sec','receptive_end_sec','evidence_kind',
            'clean_intervals','rms','clipping_fraction','clean_fraction','observation_id'},
        'asr':{'utterance_id','text','final','display_text','punctuation','asr_decode_ms'}}
    if not isinstance(event,dict) or event.get('kind') not in extra or not required<=event.keys() or set(event)-(required|extra[event['kind']]):
        raise ValueError('Only original prediction payload fields are admitted')
    if not isinstance(event['event_id'],str) or not 0<len(event['event_id'])<=128:
        raise ValueError('Stable bounded predictor event ID required')
    values=[event[k] for k in ('source_start_sec','source_end_sec','available_at_sec')]
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values) or not 0<=values[0]<=values[1]<=values[2]:
        raise ValueError('Invalid original prediction source/modeled clock')
    return deepcopy(event)


def publication_freshness(payload,origin,publication_monotonic):
    """Re-evaluate fixed source expiry under the actual publication lock."""
    now=publication_monotonic-origin
    if not math.isfinite(now) or now<payload['observed_policy_decision_ready_at_sec']:
        raise ValueError('Actual publication precedes policy result readiness')
    end=payload.get('live_evidence_source_end_sec');expiry=payload.get('source_evidence_expiry_at_sec')
    age=now-end if end is not None else None
    fresh=bool(payload.get('live_evidence_fresh')) and age is not None and 0<=age and now<=expiry+1e-9
    permission=bool(payload.get('current_source_permission')) and fresh
    scope=payload['application_scope']
    if scope=='CURRENT_SOURCE_EVIDENCE' and not permission:scope='HISTORICAL_ONLY'
    return {'live_evidence_fresh_at_policy_ready':payload.get('live_evidence_fresh',False),
        'live_evidence_age_at_policy_ready_sec':payload.get('live_evidence_age_sec'),
        'live_evidence_fresh_at_publication':fresh,'live_evidence_age_at_publication_sec':age,
        'live_evidence_fresh':fresh,'live_evidence_age_sec':age,'observed_publication_at_sec':now,
        'application_scope':scope,'current_source_permission':permission}


class ObservedClock:
    """One actual source epoch and bounded link metadata; never infer an old clock."""
    def __init__(self, trace=None, clock=time.perf_counter):
        self.trace=trace;self.clock=clock;self.origin=None;self.lock=threading.RLock()
        self.records=OrderedDict();self.bound=1;self.pending=set();self.ready={}
        self.total_admitted=0;self.history=OrderedDict();self.history_bound=4096

    def set_origin(self, origin):
        with self.lock:
            if self.origin is not None or isinstance(origin,bool) or not isinstance(origin,(int,float)) or not math.isfinite(origin):
                raise ValueError('Actual source origin must be bound exactly once')
            self.origin=float(origin)

    def relative(self, stamp=None):
        stamp=self.clock() if stamp is None else stamp
        if self.origin is None or not math.isfinite(stamp) or stamp<self.origin:
            raise ValueError('Actual source epoch missing or future')
        return stamp-self.origin

    def trace_row(self,kind,**fields):
        if self.trace is not None:self.trace.record(kind,**fields)

    def admit(self, prepared,lane,stamp):
        with self.lock:
            ready=self.relative(stamp);end=prepared['source_end_sec']
            if ready<end or prepared.get('receptive_end_sec',end)>ready:
                raise ValueError('Observed admission precedes actual source support; no clamp')
            eid=prepared['event_id']
            if eid in self.records or len(self.records)>=self.bound:
                raise RuntimeError('Duplicate or bounded observed clock metadata exhausted')
            row=dict(prepared);row['available_at_sec']=ready
            self.records[eid]={'input_event_id':eid,'lane':lane,'source_start_sec':prepared['source_start_sec'],
                'source_end_sec':end,'modeled_available_at_sec':prepared['available_at_sec'],
                'observed_input_available_at_sec':ready,'queue_admission_monotonic_sec':stamp}
            self.pending.add(eid);self.total_admitted+=1
            return ('push',(row,lane))

    def mark(self,eid,stage,stamp=None):
        stamp=self.clock() if stamp is None else stamp
        with self.lock:
            info=self.records[eid]
            if stamp<info['queue_admission_monotonic_sec']:raise ValueError('Policy clock moved before queue admission')
            info[stage+'_monotonic_sec']=stamp
            self.trace_row('policy_'+stage,**dict(info),stage_source_relative_sec=self.relative(stamp))
        return stamp

    def completed_record(self,record,policy):
        """Called on a fully constructed policy record, before its native emit sink."""
        stamp=self.clock();now=self.relative(stamp);eid=record['input_event_id']
        with self.lock:
            info=self.records[eid]
            if stamp<info.get('worker_receipt_monotonic_sec',info['queue_admission_monotonic_sec']):
                raise ValueError('Decision result precedes policy worker receipt')
            if record['event_type']=='speaker_decision':
                self.ready[eid]=now
                if policy._scheduling_history:
                    _,context=policy._scheduling_history[-1]
                    published=deepcopy(context)
                    for row in published:
                        row['snapshot_input_available_at_sec']=row.get('snapshot_available_at_sec')
                        row['snapshot_available_at_sec']=now
                    policy._scheduling_history[-1]=(now,published)
            evidence=record.get('evidence_id')
            if evidence is None and record.get('evidence_ids'):evidence=record['evidence_ids'][0]
            if record['event_type'] in {'speaker_decision','identity_decision'}:evidence=eid
            support=self.records.get(evidence)
            age=now-support['source_end_sec'] if support else None
            fresh=age is not None and 0<=age<=policy.evidence_expiry+1e-9
            historical=(record['event_type']=='transcript_label_revision'
                and record.get('revision_scope')!='ongoing_utterance_display'
                or record.get('attribution_reason')=='finalization retains prior utterance label')
            diagnostic=bool(record.get('diagnostic_control') or record.get('decision',{}).get('diagnostic_control'))
            permission=fresh and not historical and not diagnostic
            scope=('CURRENT_SOURCE_EVIDENCE' if permission else
                'HISTORICAL_ONLY' if historical or support is not None and not diagnostic else 'UNRESOLVED_OR_DIAGNOSTIC')
            actual={'observed_policy_decision_ready_at_sec':now,'policy_decision_finish_monotonic_sec':stamp,
                'input_available_at_sec':info['observed_input_available_at_sec'],
                'modeled_available_at_sec':info['modeled_available_at_sec'],'available_at_sec':now,
                'availability_clock':'observed_policy_result_ready','queue_admission_monotonic_sec':info['queue_admission_monotonic_sec'],
                'policy_worker_receipt_monotonic_sec':info.get('worker_receipt_monotonic_sec'),
                'live_evidence_id':evidence,'live_evidence_age_sec':age,'live_evidence_fresh':fresh,
                'live_evidence_source_end_sec':support['source_end_sec'] if support else None,
                'source_evidence_expiry_at_sec':support['source_end_sec']+policy.evidence_expiry if support else None,
                'source_epoch_monotonic_sec':self.origin,
                'application_scope':scope,'current_source_permission':permission,
                'current_source_permission_scope':'temporal permission only; identity, speech, ownership and route gates remain required',
                'historical_eligibility_clock':HISTORY_CLOCK,'legacy_first_times_clock':LEGACY_FIRST_TIMES_CLOCK}
            utterance=record.get('utterance_id')
            if utterance is not None:
                if utterance not in self.history:
                    if len(self.history)>=policy.max_utterances:raise RuntimeError('Bounded actual utterance history exhausted')
                    self.history[utterance]={}
                history=self.history[utterance]
                if record['event_type'] in {'transcript_partial','transcript_final'}:
                    history.setdefault('observed_first_display_ready_at_sec',now)
                if record['event_type']=='transcript_final':history.setdefault('observed_first_final_ready_at_sec',now)
                if record.get('latest_known_name'):history.setdefault('observed_first_known_name_ready_at_sec',now)
                history.update(latest_policy_ready_at_sec=now,latest_policy_event_id=record['event_id'],
                    latest_policy_application_scope=scope)
                actual.update(history)
            record.update(actual)
            self.trace_row('policy_decision_finish',**dict(info),policy_event_id=record['event_id'],
                event_type=record['event_type'],decision_finish_monotonic_sec=stamp,
                observed_policy_decision_ready_at_sec=now,live_evidence_age_sec=age,live_evidence_fresh=fresh)
        return record

    def prune(self,policy):
        with self.lock:
            retained=self.pending|{r[3]['event_id'] for r in policy._heap}|{e['event_id'] for e,d in policy._decisions}|{e['event_id'] for e in policy._segmentation}
            # Preserve recent diagnostic metadata plus every still-pending or retained evidence row.
            recent=set(list(self.records)[-EVIDENCE_HISTORY_LIMIT:]);retained|=recent
            for eid in list(self.records):
                if eid not in retained:self.records.pop(eid);self.ready.pop(eid,None)

    def snapshot(self):
        with self.lock:
            return {'clock':'observed','origin_monotonic_sec':self.origin,'metadata_retained':len(self.records),
                'metadata_bound':self.bound,'pending_admissions':len(self.pending),'admitted':self.total_admitted,
                'decision_ready_retained':len(self.ready),'actual_utterance_histories':len(self.history),
                'history_clock':'observed_input_admission','live_freshness_clock':'actual policy decision/result clock'}

    def annotate_snapshot(self,result):
        """Export actual readiness beside immutable legacy history; never a live cue."""
        with self.lock:
            for row in result['utterances']:
                row.update(deepcopy(self.history.get(row['utterance_id'],{})))
                row.update(historical_eligibility_clock=HISTORY_CLOCK,
                    legacy_first_times_clock=LEGACY_FIRST_TIMES_CLOCK,
                    source_epoch_monotonic_sec=self.origin,
                    application_scope='HISTORICAL_ONLY',current_source_permission=False)
        return result


class _MeasuredDelegate:
    def __init__(self,target,clock,role):self.target=target;self.clock=clock;self.role=role
    def __getattr__(self,name):return getattr(self.target,name)
    def update(self,*args,**kwargs):
        eid=kwargs['observation_id'];self.clock.mark(eid,'tracker_start')
        value=self.target.update(*args,**kwargs);self.clock.mark(eid,'tracker_finish');return value
    def resolve(self,decision,event):
        eid=event['event_id'];self.clock.mark(eid,'naming_start')
        value=self.target.resolve(decision,event);self.clock.mark(eid,'naming_finish');return value


class ObservedEligibility:
    """Keep immutable admitted-event ordering; only current freshness uses wall age."""
    def _eligible(self,event):
        diagnostic=getattr(getattr(self.tracker,'config',None),'mode',None)
        if diagnostic in {'one_person','all_unknown'}:return super()._eligible(event)
        now=self.observed_clock.relative()
        eligible=[(e,d) for e,d in self._decisions if e['source_end_sec']<=event['source_end_sec']
            and e['available_at_sec']<=event['available_at_sec'] and e['source_end_sec']>event['source_start_sec']
            and e['event_id'] in self.observed_clock.ready and self.observed_clock.ready[e['event_id']]<=now
            and 0<=now-e['source_end_sec']<=self.evidence_expiry+1e-9]
        segments=[e for e in self._segmentation if e['source_end_sec']<=event['source_end_sec']
            and e['available_at_sec']<=event['available_at_sec'] and 0<=now-e['source_end_sec']<=self.evidence_expiry+1e-9]
        overlap=bool(segments and segments[-1].get('overlap',False));decision=eligible[-1][1] if eligible else None
        label=decision.get('display_label',decision.get('anonymous_label','Speaker_?')) if decision else 'Speaker_?'
        state=decision.get('state','pending') if decision else 'pending'
        if overlap:label,state='Speaker_? + overlapping speaker','overlap_uncertain'
        return label,state,decision,overlap

    def _asr(self,event):
        self.observed_clock.mark(event['event_id'],'caption_policy_start')
        result=super()._asr(event)
        self.observed_clock.mark(event['event_id'],'caption_policy_finish')
        return result


class ObservedPolicyDispatcher:
    """Same single bounded worker, source watermarks and finish path; measured admission."""
    def __init__(self,scheduler,capacity,clock):
        from .research_s6d import BoundedWorker
        self.scheduler=scheduler;self.clock=clock;self._context=();self.commands=0
        # Heap + queued admissions + 2 evidence histories + recent diagnostics,
        # plus one active command and at most 127 commands since the last prune.
        clock.bound=scheduler.max_pending_limit+capacity+3*EVIDENCE_HISTORY_LIMIT+PRUNE_INTERVAL
        scheduler.observed_clock=clock
        scheduler.tracker=_MeasuredDelegate(scheduler.tracker,clock,'tracker')
        scheduler.identity_resolver=_MeasuredDelegate(scheduler.identity_resolver,clock,'identity')
        original_emit=scheduler.emit
        def emit(record):
            record=clock.completed_record(record,scheduler)
            if original_emit is not None:original_emit(record)
        scheduler.emit=emit
        self.worker=BoundedWorker('edge-s7-observed-policy',self._handle,capacity)

    def push(self,event,lane):
        if lane not in self.scheduler.watermarks:raise ValueError('Unknown prediction lane')
        prepared=predictor_payload(event)
        # Metadata wait must also precede the admission stamp. The worker never
        # holds its admission lock or queue mutex while invoking a callback.
        with self.clock.lock:
            self.worker.submit_at_admission(lambda stamp:self.clock.admit(prepared,lane,stamp),self.clock.clock)

    def advance(self,watermarks):
        # Source-progress lower bounds remain unchanged; even before origin M0 can close its absent lane.
        for lane,value in watermarks.items():
            if lane not in self.scheduler.watermarks or isinstance(value,bool) or not isinstance(value,(int,float)) or math.isnan(value) or value<0:
                raise ValueError('Invalid source-progress watermark')
            if math.isfinite(value) and value>self.clock.relative():
                raise ValueError('Source-progress watermark is ahead of observed source time')
        self.worker.submit(('advance',dict(watermarks)))

    def _handle(self,command):
        op,arg=command
        if op=='push':
            eid=arg[0]['event_id'];info=self.clock.records[eid]
            self.clock.trace_row('policy_input_admission',**dict(info))
            self.clock.mark(eid,'worker_receipt')
            self.scheduler.push(*arg)
            with self.clock.lock:self.clock.pending.remove(eid)
        elif op=='advance':self.scheduler.advance(arg)
        elif op=='finish':self.scheduler.finish()
        else:raise ValueError('Unknown policy command')
        self._context=tuple(self.scheduler._scheduling_history)
        self.commands+=1
        if self.commands%PRUNE_INTERVAL==0 or op=='finish':self.clock.prune(self.scheduler)

    def tracking_context(self,available_at_sec):
        eligible=[rows for stamp,rows in self._context if stamp<=available_at_sec]
        return deepcopy(eligible[-1]) if eligible else []

    def finish(self):
        self.worker.submit(('finish',None));self.worker.close()

    def snapshot(self):
        result=self.clock.annotate_snapshot(self.scheduler.snapshot())
        return {**result,'s6d_dispatch':self.worker.snapshot(),'s7_observed_policy':self.clock.snapshot()}
