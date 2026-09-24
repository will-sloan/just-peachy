"""Opt-in controller integration, off capture callback. See README_ADAPTATION.md."""
from copy import deepcopy
import hashlib
from .reference_adaptation import BaseAnchors,SessionBank
from .mode_policy import NAMED_MODES

class AdaptationWorkflow:
    def _adaptation_initialize(self):
        self.reference_bank=None;self.collect_references=False;self.use_references=False
    def _adaptation_start(self,gallery):
        self.reference_bank=None
        if self.collect_references or self.use_references:self._adaptation_prepare(gallery)
    def _adaptation_prepare(self,gallery):
        full=self.store.gallery(self.route())
        if not full.ids:raise ValueError('Compatible original enrollments are required for reference collection')
        bank=SessionBank(BaseAnchors(full),'epoch-'+str(self.epoch),collect=self.collect_references,persisted=full.environment_bank)
        if getattr(self,'source_kind',None)=='file':
            if self.file_path.stat().st_size>128*1024**2:raise ValueError('Reference collection file exceeds bounded 128MiB source')
            with self.file_path.open('rb') as source:bank.source_id='file:'+hashlib.file_digest(source,'sha256').hexdigest()
            bank.source_offset=self.file_offset
        bank.enabled=self.use_references;self.reference_bank=bank
        if gallery is not None:gallery.adaptation=bank
        return bank
    def _adaptation_bind_engine(self,engine):
        bank=getattr(self,'reference_bank',None)
        if bank:
            bank.session_id=str(engine.session_dir or ('epoch-'+str(self.epoch)))
            bank.log_match=lambda payload:engine._emit('prototype_reference_match',engine._source_time(),payload)
    def adaptation_action(self,action,**values):self._enqueue('adaptation',action,values)
    def _do_adaptation(self,action,values):
        bank=self.reference_bank
        if action in ('collect','use'):
            enabled=values.get('enabled')
            if type(enabled) is not bool:raise ValueError('Explicit On/Off required')
            if enabled and values.get('consent') is not True:raise ValueError('Explicit reference collection/matching consent required')
            if enabled and (self.mode not in NAMED_MODES or self.mode=='assigned_direction'):raise ValueError('Choose a voice name mode to collect/use references')
            if enabled and not self.store.gallery(self.route()).ids:raise ValueError('Compatible consenting enrollments are required first')
            if action=='collect':self.collect_references=enabled
            else:self.use_references=enabled
            if bank is None and self.engine is not None:
                bank=self._adaptation_prepare(self.engine._research_gallery);self._adaptation_bind_engine(self.engine)
            if bank:
                with bank.lock:
                    bank.collect=self.collect_references;bank.enabled=self.use_references
            self.status='References: collection '+('On' if self.collect_references else 'Off')+', matching '+('On' if self.use_references else 'Off')+'. Fresh Start clears session candidates; original anchors unchanged.'
        elif action=='confirm':
            if bank is None:raise ValueError('No session candidates')
            bank.confirm(values['id'],values['person_id'],consent=values.get('consent',False))
            self.status='Confirmed for this session; permanent promotion is separate.'
        elif action=='freeze':
            if bank:bank.freeze('user_reported_music_overlap_or_wrong_speaker')
            self.status='Reference collection/matching frozen. Fresh Start required; captions continue.'
        elif action=='discard':
            if bank:bank.discard()
            self.collect_references=False;self.use_references=False
            self.status='Session candidates discarded; original and previously promoted references retained. Matching Off.'
        elif action=='promote':
            self._ensure_no_enrollment()
            if bank is None:raise ValueError('No session candidates')
            if values.get('consent') is not True:raise ValueError('Approve selected permanent references explicitly')
            self._stop_session()
            self.store.promote_candidates(bank,values['ids'],values['person_id'],consent=True)
            bank.log_match=None;self.status='Selected references promoted separately. Microphone stopped. Undo remains available after restart.'
        elif action=='undo':
            self._ensure_no_enrollment()
            if values.get('consent') is not True:raise ValueError('Confirm Undo explicitly')
            self._stop_session();self.store.undo_enrichment(values['person_id'],consent=True)
            if bank:bank.discard()
            self.reference_bank=None;self.collect_references=False;self.use_references=False
            self.status='Latest personal enrichment undone; original enrollments retained. Matching Off.'
        else:raise ValueError('Unknown reference action')
        engine=self.engine
        if engine and engine.state=='RUNNING':engine._emit('prototype_reference_action',engine._source_time(),
            dict(action=action,values=deepcopy(values),state=self.adaptation_snapshot()))
    def _adaptation_event(self,engine,event):
        bank=getattr(self,'reference_bank',None)
        if bank is None:return
        p=event.payload;kind=event.event_type
        if kind in ('fatal','failure','enhancement_fallback'):
            bank.freeze(kind);return
        if kind in ('research_segmentation','research_embedding','research_embedding_admission') and p.get('overlap') is True:
            if bank.collect or bank.enabled:bank.freeze('overlap_detected')
        if kind!='research_embedding' or not bank.collect or bank.frozen or p.get('evidence_kind')!='mature':return
        try:
            start=round(p['source_start_sec']*16000);end=round(p['source_end_sec']*16000)
            audio=engine._identity_journal.read(start,end-start,wait_sec=0)
            provenance=dict(mode=self.mode,recipe=self.recipe,identity_labels_are_not_confirmation=True,
                seat=self.seating_snapshot(),decision=deepcopy(self.metrics.get('recent_identity_decisions',[])[-1:]),
                noise=self.noise_snapshot().get('observations',{}))
            candidate=bank.observe(p,audio,self.route(),provenance)
            if candidate:engine._emit('prototype_reference_candidate',p['source_end_sec'],
                {k:v for k,v in candidate.items() if k not in ('vector','provenance')})
        except Exception as exc:
            bank.freeze('candidate_window_error: '+str(exc))
            self.metrics['reference_collection_error']=str(exc) # Optional feature must not terminate captions.
    def adaptation_snapshot(self):
        bank=getattr(self,'reference_bank',None)
        return dict(bank.snapshot() if bank else {},collect=getattr(self,'collect_references',False),enabled=getattr(self,'use_references',False))
