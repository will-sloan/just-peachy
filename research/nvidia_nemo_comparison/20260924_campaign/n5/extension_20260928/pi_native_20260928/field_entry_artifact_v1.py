"""Offline candidate entry point; see docs/README_FIELD_ARTIFACT_INSTALL_V1.md."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time


ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'native')]


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def artifact_contract():
    from field_artifact_binding_v1 import bound_limits
    contract=json.loads((ROOT/"config/field_contract.json").read_text())
    return contract,bound_limits(ROOT,contract)


def health():
    from release_tools.release import verify_release, verify_assets
    manifest=verify_release(ROOT)
    alsa=ROOT/'config/alsa_hw_only_v1.conf'
    if not alsa.is_file() or sha(alsa)!='d81bc353dcab14d172e78b26c6116bfc8462b96e45e44b1a93ac3f217898564d':
        raise RuntimeError('Offline ALSA configuration missing or changed')
    contract,limits=artifact_contract()
    if platform.machine()!='aarch64' or sys.version_info[:2]!=(3,11):raise RuntimeError('Candidate requires native aarch64 Python3.11')
    if shutil.disk_usage(ROOT).free<contract['minimum_free_bytes']:raise RuntimeError('Device free-space reserve')
    if Path(sys.prefix).resolve()!=Path(contract['runtime_prefix']).resolve():raise RuntimeError('Wrong offline runtime')
    assets=verify_assets(ROOT,Path(contract['models_root']))
    extra=[]
    for row in contract['extra_assets']:
        path=Path(row['path'])
        if not path.is_file() or path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise RuntimeError('Missing or changed offline dependency: '+str(path))
        extra.append(dict(path=str(path),bytes=path.stat().st_size,sha256=row['sha256']))
    return dict(status='OFFLINE_CODE_AND_ASSETS_HEALTHY',version=manifest['version'],code_files=len(manifest['files']),
                assets=assets,extra_assets=extra,contract=contract,artifact_limits=limits,artifact_limits_binding=contract["artifact_limits"],capture_opened=False,models_loaded=False)


def controller_type():
    from app.controller import Controller as Base
    from app import pipeline
    from app.backends import backend_catalog
    from isolated_pipeline_source_v2 import IsolatedLiveConfig,bind_pipeline
    bind_pipeline(pipeline)
    supported=next(x['id'] for x in backend_catalog() if x['key']=='nemotron_hybrid')
    class FieldController(Base):
        def _artifact_limits_for_epoch(self):
            from field_artifact_limits_v1 import resolved
            contract,limits=artifact_contract()
            if resolved(self.session_store.policy.get("artifact_limits"))!=limits:
                raise ValueError("Installed archive policy conflicts with artifact contract")
            return limits

        def _sessions_initialize(self):
            from field_archive_v3 import FieldArchiveStore
            contract,limits=artifact_contract()
            self.session_store=FieldArchiveStore(self.data_root,contract,before_publish=self._validate_import_projection,artifact_limits=limits)
            self.conversation_id=None;self.opened_conversation=None;self.archive=None;self.playback=None
            self.output_choices=[];self.chosen_output=None;self.session_rows=[]
            self.session_listing=[];self.session_usage={};self._refresh_sessions();self.session_annotations={}
        def _validate_import_projection(self,folder,identifier):
            # Detached view uses the actual history/controller consumers without publishing
            # staging rows to the running UI or taking ownership of another application.
            import copy,threading
            from collections import OrderedDict
            from app.sessions import SessionStore
            from field_archive_schema_v2 import projected_rows
            store=SessionStore.__new__(SessionStore);store.root=folder.parent
            store.active={};store.policy=self.session_store.policy.copy();store.lock=threading.RLock()
            view=copy.copy(self);view.lock=threading.RLock();view.session_store=store
            view._refresh_sessions()
            metadata=store.metadata(identifier);rows=store.rows(identifier)
            view.rows=OrderedDict((r.get('caption_key',r['utterance_id']),r) for r in rows)
            if len(view.rows)!=len(rows):raise ValueError('Duplicate raw caption key')
            view.session_annotations=dict(identifier=identifier,notes=metadata['notes'][-20:],corrections=metadata['corrections'][-20:])
            result=projected_rows(view.snapshot()['rows'])
            result.update(raw_rows=len(rows),history_rows=len(view.session_listing),consumer='Actual SessionStore.list/rows,Controller._refresh_sessions/snapshot on detached view')
            return result
        def session_action(self,action,**values):
            if action=='import':self._enqueue('session_action',action,values)
            else:return super().session_action(action,**values)
        def _do_session_action(self,action,values):
            if action!='import':return super()._do_session_action(action,values)
            self._ensure_no_enrollment()
            if self.engine is not None or self.archive is not None or self.playback is not None:
                raise RuntimeError('Stop capture and playback before importing a conversation.')
            identifier=self.session_store.import_archive(values['path'],consent=values.get('consent',False))
            super()._do_session_action('open',dict(identifier=identifier))
            self.status='Private archive imported and reopened. Microphone off. Imported labels retain their original provenance.'

        def _do_select_backend(self,identifier):
            if identifier!=supported:raise ValueError('This candidate supports B01. Other backends need a separately qualified launcher.')
            return super()._do_select_backend(identifier)
        def _do_switch(self,mode,recipe,tap,selected_ids,strict):
            if (mode or self.mode,recipe or self.recipe,tap or self.tap)!=('open_with_names','balanced','O0'):
                raise ValueError('This candidate supports Open with names, Balanced and O0. Spatial and other recipes are unavailable.')
            return super()._do_switch(mode,recipe,tap,selected_ids,strict)
        def _do_enrollment_start(self,*args,**kwargs):raise ValueError('Enrollment is unavailable in this candidate.')
        def _live_config(self):
            import uuid
            directory=self.data_root/'source_receipts'/(str(self.epoch)+'-'+uuid.uuid4().hex);directory.mkdir(parents=True,exist_ok=False)
            cfg=dict(source_module='source_quiet_factory_v1',source_factory='create',capture=True,quiet_only=True,
                     prototype=str(ROOT),case_directory=str(directory),backpressure_seconds=1,
                     authority=str(ROOT/'config/AUTONOMOUS_QUIET_AUTHORIZATION_V1.json'),
                     alsa_config=str(ROOT/'config/alsa_hw_only_v1.conf'),live_config=str(self.data_root/'live_config.json'))
            with (directory/'CONFIG.json').open('x') as f:json.dump(cfg,f,indent=2)
            return IsolatedLiveConfig(directory/'CONFIG.json',ROOT)
        def _start_session(self):
            self._artifact_limits_for_epoch()  # Reject drift before state/epoch/writer publication.
            contract=json.loads((ROOT/'config/field_contract.json').read_text())
            used=self.session_store.usage()['bytes']
            if used+contract['session_reservation_bytes']>contract['private_data_quota_bytes']:raise ValueError('Recording storage limit reached; export or manage history before starting.')
            if shutil.disk_usage(self.data_root).free<contract['minimum_free_bytes']+contract['session_reservation_bytes']:raise ValueError('Device storage reserve reached.')
            return super()._start_session()
        def snapshot(self):
            value=super().snapshot()
            for backend in value['backends']:
                if backend['id']!=supported:backend.update(available=False,reason='Unavailable in this candidate; no automatic fallback.')
            value['backend']['label']='B01: Sherpa + Nemotron'
            value['field_candidate']=dict(maximum_recording_seconds=125,spatial_available=False,enrollment_available=False,
                                          sequential_refinement_available=False,field_release_accepted=False)
            return value
    return FieldController,supported


def create_controller(data):
    contract,limits=artifact_contract()  # Missing config must fail before creating private data.
    cls,backend=controller_type()
    controller=cls(data,Path(contract['models_root']),saved_audio_only=False)
    try:
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        controller.select_backend(backend);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        controller.switch(mode='open_with_names',recipe='balanced',tap='O0');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
    except BaseException:
        if not controller.closed:controller.close()
        controller.commands.join();controller.worker.join(10)
        raise
    return controller


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['health','controller-check','gui'])
    p.add_argument('--data-root',type=Path)
    p.add_argument('--launch-admission',type=Path)
    args=p.parse_args()
    info=health()
    if args.command=='health':print(json.dumps(info));return 0
    if args.data_root is None:p.error('--data-root required')
    if args.command=='gui':
        # GUI execution is separately admitted; package health does not authorize capture.
        if args.launch_admission is None:p.error('GUI requires a fresh bounded --launch-admission')
        a=json.loads(args.launch_admission.read_text())
        if a['release_manifest_sha256']!=sha(ROOT/'RELEASE_MANIFEST.json') or not a['autonomous_quiet_authorized']:
            raise RuntimeError('GUI admission binding')
        if not time.time()<a['expires_unix']<=time.time()+600:raise RuntimeError('GUI admission expired or exceeds600s')
        if a['data_root']!=str(args.data_root.resolve()):raise RuntimeError('GUI data binding')
        import resource
        if sorted(os.sched_getaffinity(0))!=[2,3] or resource.getrlimit(resource.RLIMIT_AS)!=(768*1024**2,)*2:
            raise RuntimeError('Run through admitted CPU/virtual-memory supervisor')
        if resource.getrlimit(resource.RLIMIT_STACK)!=(1024**2,)*2:raise RuntimeError('Required stack limit absent')
        group=next(x.split(':',2)[2] for x in Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
        quota,period=(Path('/sys/fs/cgroup')/group.lstrip('/')/'cpu.max').read_text().split()
        if quota=='max' or int(quota)/int(period)>2:raise RuntimeError('Shared CPU quota absent')
    os.environ['ALSA_CONFIG_PATH']=str(ROOT/'config/alsa_hw_only_v1.conf')
    controller=create_controller(args.data_root)
    try:
        if args.command=='controller-check':
            s=controller.snapshot()
            assert s['state']=='IDLE' and controller.engine is None and controller.models.asr_loads==controller.models.speaker_loads==0
            blocked=[]
            for action in [lambda:controller._do_switch('spatial','balanced','O0',None,None),lambda:controller._do_select_backend('unsupported'),lambda:controller._do_enrollment_start()]:
                try:action()
                except ValueError as e:blocked.append(str(e))
                else:raise AssertionError('Unsupported candidate action accepted')
            print(json.dumps(dict(status='INSTALLED_CONTROLLER_IDLE_CHECK_PASS',backend=s['backend']['id'],mode=s['mode'],
                                 unavailable_rejections=blocked,field_candidate=s['field_candidate'],model_loads=0,capture_opened=False)))
            return 0
        import signal
        import tkinter as tk
        from app.ui import PrototypeUI
        class FieldUI(PrototypeUI):
            def __init__(self,*values,**options):
                super().__init__(*values,**options)
                self.root.attributes('-fullscreen',True)
            def _show_status(self):
                super()._show_status()
                self.preview_label.configure(text='Offline B01')
            def _paragraph_label(self,parent,value,muted=False):
                if 'experimental marker never blocks' in value or 'Experimental modes remain selectable' in value or value.startswith('✓ simulation-supported'):
                    value='Open with names is available. Other modes are unavailable in this candidate. Field validation is still in progress.'
                elif value.startswith('Developer archive'):
                    value='Private history stays on this device, unencrypted. Import and export include sensitive recordings. Nothing is deleted automatically.'
                elif value.startswith('Archive ') and 'Up to 10' in value:
                    u=self._session_data().get('usage',{})
                    value=f"Private data {u.get('bytes',0)/1024**2:.1f} / 512 MiB · free {u.get('free_bytes',0)/1024**3:.1f} GiB\n5 GiB stays free. Start reserves 64 MiB. Up to 10 drafts; manage history explicitly."
                return super()._paragraph_label(parent,value,muted)
            def show_sessions(self):
                super().show_sessions()
                first=self.actions['new_text'].master
                self.button(first.master,'Import private conversation…',self._import_archive,key='session_import').pack(before=first,fill='x',padx=self.px(12),pady=self.px(3))
            def _import_archive(self):
                def choose():
                    self.keyboard('Private archive ZIP path','',lambda path:self._session_command('import',path=path,consent=True),cancel=self.show_sessions)
                self.confirm('Import private conversation?',
                    'Import a complete saved archive exported by this candidate. Audio, text and labels remain private and unencrypted. Existing conversations are never overwritten. Text-only and older exports are not supported.',
                    'Choose archive path',choose,cancel=self.show_sessions)
            def _limit_mode_buttons(self):
                for key,button in self.actions.items():
                    if key.startswith('mode_') and key!='mode_open_with_names' and button.winfo_exists():
                        button.configure(text=str(button.cget('text'))+' · unavailable',state='disabled')
            def show_modes(self):
                super().show_modes();self._limit_mode_buttons()
            def show_advanced(self):
                super().show_advanced();self._limit_mode_buttons()
            def show_backends(self):
                self.page='backends';frame=self._page('Backend');self._show_status()
                self._paragraph_label(frame,'B01 provides captions and delayed speaker labels. Other backends are unavailable in this candidate.',True)
                for backend in self.snapshot['backends']:
                    title='B01: Sherpa + Nemotron · active' if backend['available'] else backend['label']+' · unavailable'
                    self.button(frame,title,lambda b=backend:self._select_backend(b['id']),key='backend_'+backend['key'],height=64).pack(fill='x',padx=self.px(12),pady=self.px(5))
                    if not backend['available']:self.actions['backend_'+backend['key']].configure(state='disabled')
                self._paragraph_label(frame,'Speaker names require compatible saved voice profiles. An empty gallery does not identify people. No automatic backend fallback.',True)
            def show_recipes(self):
                super().show_recipes()
                for key,button in self.actions.items():
                    if ((key.startswith('recipe_') and key!='recipe_balanced') or (key.startswith('tap_') and key!='tap_O0')) and button.winfo_exists():
                        button.configure(text=str(button.cget('text'))+' · unavailable',state='disabled')
            def enrollment_form(self,*values,**options):
                self._notice='Enrollment is unavailable in this candidate.';self.home();self._show_status()
        root=tk.Tk();ui=FieldUI(root,controller,allow_auto_start=False)
        def tick():
            if time.time()>=a['expires_unix']:ui.close();return
            source=getattr(controller.engine,'_source',None)
            if source is not None and getattr(source,'sent',0)>=2000000 and controller.state=='RUNNING':controller.stop()
            root.after(50,tick)
        for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda *unused:root.after(0,ui.close))
        root.after(50,tick);root.mainloop()
    finally:
        if not controller.closed:controller.close()
        controller.commands.join();controller.worker.join(10)
        if not controller.closed or controller.worker.is_alive():raise RuntimeError('Controller ownership remains open')
    return 0


if __name__=='__main__':raise SystemExit(main())
