"""Controller-command integration for linked sessions. See README_SESSIONS.md."""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict
import hashlib
from pathlib import Path
import time

from .paths import ROOT, read_json
from .sessions import SessionStore


class SessionWorkflow:
    def _sessions_initialize(self):
        self.session_store=SessionStore(self.data_root)
        self.conversation_id=None;self.opened_conversation=None;self.archive=None;self.playback=None
        self.output_choices=[];self.chosen_output=None;self.session_rows=[]
        self.session_listing=[];self.session_usage={};self._refresh_sessions()
        self.session_annotations={}

    def _refresh_sessions(self):
        self.session_listing=[{k:r[k] for k in ('id','title','state','pinned','audio_requested','size_bytes','created_utc','issues')}
                              for r in self.session_store.list()][:100]
        self.session_usage=self.session_store.usage()

    def session_action(self,action,**values):
        allowed={'new','save','open','rename','delete','note','correct','undo_correction','export','outputs','output','play','stop_playback','window'}
        if action not in allowed:raise ValueError('Unknown session action')
        self._enqueue('session_action',action,values)

    def _stop_playback(self):
        if getattr(self,'playback',None) is not None:
            self.playback.stop();self.playback=None

    def _archive_prepare(self,profile):
        self._stop_playback()
        if not getattr(self,'session_store',None):return None
        if self.opened_conversation is not None or self.conversation_id is None or self.session_store.metadata(self.conversation_id)['pinned']:
            self.conversation_id=self.session_store.new()
            with self.lock:self.rows.clear()
        self.opened_conversation=None
        info=dict(conversation_id=self.conversation_id,mode=self.mode,recipe=self.recipe,tap=self.tap,
            roster_ids=list(self.selected_ids),features=dict(mode=self.mode,recipe=self.recipe,tap=self.tap,
                strict_filter=self.strict,spatial_mode=self.mode.startswith('spatial') or self.mode.startswith('strongly_spatial'),
                display_preferences=deepcopy(self.settings)),route=self.route(),source_kind=self.source_kind,
            prepared_file=str(self.file_path) if self.source_kind=='file' else None,
            prepared_file_start_sample=self.file_offset if self.source_kind=='file' else None,
            pipeline_input_gain=1.,model_manifest=read_json(ROOT/'config/assets.json'),
            effective_profile=profile.to_dict() if hasattr(profile,'to_dict') else asdict(profile),
            mode_configuration=self.mode_configuration(profile,getattr(self.engine,'_research_gallery',None)),
            source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                for directory in ('app','vendor','config') for p in (ROOT/directory).rglob('*')
                if p.is_file() and p.suffix in ('.py','.json')},
            clock_map=dict(sample_domain='epoch-local mono16k half-open samples',host_clock='time.perf_counter',
                utc_quality='host wall clock, not acoustic synchronization',source_origin='source_started event',
                adc_clock='upstream capture metadata only; keep quality flags; never infer calibrated arrival'))
        from .enhancement import route_binding
        info['enhancement']=route_binding(self.settings.get('enhancement_route','bypass'))
        self.archive=self.session_store.begin(self.conversation_id,info)
        return self.archive

    def _archive_end(self,archive):
        if archive is None:return
        engine=archive.engine
        if engine is not None:
            archive.metadata['pipeline_terminal_state']=getattr(engine,'state',None)
            archive.metadata['native_session_path']=str(getattr(engine,'session_dir',None))
            archive.metadata['capture_integrity']=deepcopy(getattr(getattr(engine,'_source',None),'integrity',None))
        receipt=self.session_store.ended(archive.metadata['conversation_id'],archive)
        self.metrics['last_archive']=receipt
        if self.archive is archive:self.archive=None
        self._refresh_sessions()

    def _do_session_action(self,action,values):
        if action in ('new','open','delete','correct','undo_correction'):self._review_cancel('session or annotation changed')
        store=self.session_store;identifier=values.get('identifier') or self.conversation_id
        if action=='outputs':
            from .session_playback import outputs
            self.output_choices=outputs();return
        if action=='output':
            choice=next((d for d in self.output_choices if d['index']==values['index']),None)
            if choice is None:raise ValueError('Refresh and explicitly select an output')
            self._stop_playback();self.chosen_output=deepcopy(choice);return
        if action=='stop_playback':self._stop_playback();self.status='Listening stopped; microphone off.';return
        self._ensure_no_enrollment();self._stop_playback()
        if action in ('new','save','open','play'):
            self._stop_session();self.source_kind=None;self.state='STOPPED'
        if action=='new':
            self.conversation_id=store.new(values.get('audio',False),values.get('consent',False),values.get('title'))
            self.opened_conversation=None;self.session_rows=[]
            with self.lock:self.rows.clear()
            self.status='New transcript ready. Previous unsaved conversation remains a draft. Press Start to listen.'
        elif not identifier:raise ValueError('Create or open a conversation first')
        elif action=='save':
            store.save(identifier);self.status='Conversation saved and pinned; audio capture is off.'
        elif action=='open':
            rows=store.rows(identifier)
            with self.lock:self.rows=OrderedDict((r.get('caption_key',r['utterance_id']),r) for r in rows)
            self.opened_conversation=identifier
            self.session_annotations=dict(identifier=identifier,**{k:store.metadata(identifier)[k][-20:] for k in ('notes','corrections')})
            self.session_rows=[dict(id=r.get('caption_key'),epoch=r['archive_epoch_id'],start=r['source_start_sample'],end=r['source_end_sample'],
                text=(r.get('display_text') or r.get('text',''))[:200],quality=r['audio_link_quality']) for r in rows]
            self.status='Saved transcript view; microphone off. Audio links are coarse utterance intervals.'
        elif action=='rename':store.rename(identifier,values['title']);self.status='Conversation renamed.'
        elif action=='delete':
            store.delete(identifier,values.get('confirmed',False))
            if identifier==self.conversation_id:self.conversation_id=None
            if identifier==self.opened_conversation:
                self.opened_conversation=None;self.session_rows=[]
                with self.lock:self.rows.clear()
            self.status='Conversation deleted; enrolled people retained.'
        elif action in ('note','correct','undo_correction'):
            source=dict(epoch=self.archive.path.name,sample=self.archive.source_samples) if self.archive is not None and identifier==self.conversation_id else None
            if action=='undo_correction':store.undo_correction(identifier,values['edit_id'])
            else:store.annotate(identifier,values.get('note',''),row_id=values.get('row_id'),correction=values.get('correction') if action=='correct' else None,source=source)
            self.session_annotations=dict(identifier=identifier,**{k:store.metadata(identifier)[k][-20:] for k in ('notes','corrections')})
            if action!='note' and identifier in (self.opened_conversation,self.conversation_id):
                with self.lock:self.rows=OrderedDict((r.get('caption_key',r['utterance_id']),r) for r in store.rows(identifier))
            self.status='User annotation saved separately from automatic text.'
        elif action=='export':
            self.status='Sensitive local export: '+store.export(identifier,values['path'],include_audio=values.get('audio',False),consent=values.get('consent',False))
        elif action=='window':
            self.status='Window export: '+store.export_window(identifier,values['epoch'],values['window_id'],values['path'])
        elif action=='play':
            if self.chosen_output is None:raise ValueError('Explicitly select a listening output first')
            if self.engine is not None:raise RuntimeError('Capture owner has not released; playback blocked')
            from .session_playback import SessionPlayback
            samples=store.audio_slice(identifier,values['epoch'],values['start'],values['end'],stream=values.get('stream','input'))
            self.playback=SessionPlayback(samples,self.chosen_output)
            self.status='Listening on '+self.chosen_output['name']+' · microphone off; Start stops playback first.'
        self._refresh_sessions()

    def session_snapshot(self):
        if not hasattr(self,'session_store'):return {}
        archive=self.archive.snapshot() if self.archive is not None else None
        playback=self.playback.snapshot() if self.playback is not None else None
        return dict(current_id=self.conversation_id,opened_id=self.opened_conversation,library=deepcopy(self.session_listing),
            usage=deepcopy(self.session_usage),archive=archive,last_archive=deepcopy(self.metrics.get('last_archive')),
            caption_links=deepcopy(self.session_rows),outputs=deepcopy(self.output_choices),selected_output=deepcopy(self.chosen_output),
            annotations=deepcopy(self.session_annotations),playback=playback)
