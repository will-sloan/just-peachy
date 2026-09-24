"""Explicit selected-excerpt review; ordinary text/identity untouched. See README_TRANSCRIPT_REVIEW.md."""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict,replace
import json
from .paths import read_json
from .transcript_review import ReviewWorker,MAX_SECONDS,MAX_TEXT,desktop_supported,resource_ok,audio_digest,digest,validate_choice,HELPER_STATUS

class TranscriptReviewWorkflow:
    def _review_initialize(self):self.transcript_review=ReviewWorker();self.audio_review_enabled=False
    def _review_cancel(self,reason):
        if hasattr(self,'transcript_review'):self.transcript_review.cancel(reason)
    def review_action(self,action,**values):self._enqueue('review',action,values)
    def review_snapshot(self):
        return dict(self.transcript_review.snapshot() if hasattr(self,'transcript_review') else {},
            enabled=getattr(self,'audio_review_enabled',False),available=desktop_supported(),language_helper=HELPER_STATUS)
    def _review_job(self,identifier,row_id):
        row=next((r for r in self.session_store.iter_rows(identifier) if r.get('caption_key')==row_id),None)
        if row is None or not row.get('final'):raise ValueError('Select an existing finalized utterance')
        start,end=row['source_start_sample'],row['source_end_sample']
        if not 0<=start<end or end-start>MAX_SECONDS*16000:raise ValueError('Review requires a complete recorded utterance of at most 20 seconds; no silent truncation')
        text=row.get('text','')
        if not isinstance(text,str) or len(text)>MAX_TEXT:raise ValueError('Original caption exceeds review limit')
        folder=self.session_store.epoch(identifier,row['archive_epoch_id']);meta=read_json(folder/'epoch.json')
        integrity=meta.get('capture_integrity')
        if (meta.get('state')!='CLOSED' or meta.get('archive_error') or meta.get('pipeline_terminal_state')=='FAILED'
            or (integrity is not None and not integrity.get('ok',False))):raise ValueError('Incomplete/gapped source; review abstains')
        x=self.session_store.audio_slice(identifier,row['archive_epoch_id'],start,end,stream='asr')
        from edge_speech_pipeline.research_profiles import ResearchProfile
        if not meta.get('effective_profile'):raise ValueError('Original decoder profile is missing; review abstains')
        archived={a['component_id']:a['sha256'] for a in meta.get('model_manifest',[])}
        for name in ('sherpa_giga_encoder_int8','sherpa_giga_decoder_fp32','sherpa_giga_joiner_int8','sherpa_giga_tokens'):
            if archived.get(name)!=self.config.asset(name).sha256:raise ValueError('Original ASR model/tokenizer binding missing or different; review abstains')
        source_config=ResearchProfile.from_dict(meta['effective_profile']).apply(self.config)
        decoder_config={k:v for k,v in asdict(source_config).items() if k.startswith(('asr_','endpoint_'))}
        job=dict(conversation=identifier,caption_id=row_id,epoch_id=row['archive_epoch_id'],controller_epoch=self.epoch,
            source_start_sample=start,source_end_sample=end,stream='asr',audio_sha256=audio_digest(x),original=text,
            original_sha256=digest(text),text_revision_id=row.get('text_revision_id'),
            annotations_sha256=digest(self.session_store.metadata(identifier)['corrections']),
            route=deepcopy(meta.get('route')),enhancement=deepcopy(meta.get('enhancement')),
            decoder_config=decoder_config,
            asr_asset_sha256={name:archived[name] for name in archived if name.startswith('sherpa_giga_')},
            scope='exact recorded ASR stream; coarse utterance, not word alignment; no extra gain or enhancement')
        return job,x
    def _review_current(self,job):
        if job['controller_epoch']!=self.epoch:raise ValueError('Review belongs to an earlier capture epoch')
        current,_=self._review_job(job['conversation'],job['caption_id'])
        if current!=job:raise ValueError('Source/audio/text/annotations changed; review again')
    def _do_review(self,action,values):
        worker=self.transcript_review
        if action=='switch':
            value=values.get('enabled')
            if type(value) is not bool:raise ValueError('Choose explicit review On/Off')
            if value and not desktop_supported():raise ValueError('Review is Windows desktop only; CM5 not qualified')
            self._review_cancel('review setting changed');self.audio_review_enabled=value
            self.status='Audio review '+('On' if value else 'Off')+'. Only an explicitly selected recorded utterance is analyzed.';return
        if action=='cancel':self._review_cancel('user cancelled; original caption retained');return
        if not self.audio_review_enabled or not desktop_supported():raise ValueError('Enable desktop audio review first')
        if self.state in ('RUNNING','STARTING','ENROLLING','STOPPING') or self.enrollment.get('state') in ('RECORDING','DRAINING','ANALYZING','READY'):
            self._review_cancel('deferred: live capture/enrollment keeps priority; no caption changes')
            self.status='Review deferred while live captions/capture continue. Stop before requesting review.';return
        if action=='request':
            if values.get('consent') is not True:raise ValueError('Explicit selected-audio review confirmation required')
            self._review_cancel('new selected excerpt')
            if not resource_ok():
                self.status='Review unavailable under memory pressure; original caption retained.';return
            if worker.thread and worker.thread.is_alive():raise ValueError('Previous optional job is releasing its stream; retry shortly')
            job,x=self._review_job(values['identifier'],values['row_id'])
            if len(self.session_store.metadata(job['conversation']).get('audio_reviews',[]))>=20:raise ValueError('Conversation has 20 retained reviews; no automatic overwrite')
            _,stream=self.models.acquire(replace(self.config,**job['decoder_config']),caption_only=True)
            # Only explicitly authored, unlinked vocabulary. No People/UUID/gallery
            # data or automatic text substitutions are passed into candidate decoding.
            with self.text_assistance.lock:
                vocabulary=[dict(text=e['preferred'],kind=e['kind']) for e in self.text_assistance.config['entries'] if not e.get('person_id')][:64]
            worker.start(job,x,stream,lambda generation,result:self._enqueue('review_result',generation,result),vocabulary)
            self.status='Review started on selected recorded ASR audio. Original captions remain unchanged.'
        elif action=='adopt':
            result=worker.snapshot().get('result')
            if not result or values.get('review_id')!=result['id']:raise ValueError('Review is no longer current')
            if values.get('consent') is not True:raise ValueError('Explicit adoption required')
            self._review_current(result['request'])
            choice=validate_choice(json.dumps({'candidate_id':values.get('candidate_id')}),result['candidates'])
            if choice in ('abstain','original'):self._review_cancel('original retained');return
            candidate=next(c for c in result['candidates'] if c['id']==choice)
            if candidate['protected'] and values.get('protected_ack') is not True:raise ValueError('Confirm that you checked the highlighted meaning-sensitive changes against audio')
            job=result['request'];identifier=job['conversation']
            self.session_store.annotate(identifier,'',row_id=job['caption_id'],correction=candidate['text'],
                review=dict(review_id=result['id'],candidate_id=choice,audio_sha256=job['audio_sha256'],protected_ack=values.get('protected_ack',False)))
            self.session_annotations=dict(identifier=identifier,**{k:self.session_store.metadata(identifier)[k][-20:] for k in ('notes','corrections')})
            if identifier in (self.opened_conversation,self.conversation_id):
                with self.lock:self.rows=OrderedDict((r.get('caption_key',r['utterance_id']),r) for r in self.session_store.rows(identifier))
            self._review_cancel('adopted as separate user correction; raw/final ASR retained')
            self.status='Review adopted as a separate user correction. Use Sessions → Undo correction to revert.'
        else:raise ValueError('Unknown review action')
    def _do_review_result(self,generation,result):
        worker=self.transcript_review
        with worker.lock:
            if generation!=worker.generation or not self.audio_review_enabled:return
            try:
                if self.state in ('RUNNING','STARTING','ENROLLING','STOPPING'):raise ValueError('Live capture began; optional result discarded')
                self._review_current(result['request'])
                identifier=result['request']['conversation'];reviews=self.session_store.metadata(identifier).get('audio_reviews',[])
                if len(reviews)>=20 or len(json.dumps(reviews+[result],allow_nan=False).encode())>256*1024:raise ValueError('Review evidence limit; unchanged caption')
                self.session_store.update(identifier,audio_reviews=reviews+[result])
                worker.state=dict(status='READY',result=deepcopy(result),reason='Proposal saved separately; no words changed. Listen before adopting.')
                self.status='Audio review ready. No words changed.';self._refresh_sessions()
            except Exception as exc:worker.state=dict(status='ABSTAINED',result=None,reason=str(exc),unchanged=True)
