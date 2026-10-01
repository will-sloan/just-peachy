"""Actual installed history controller on one exact private copy; README_FIELD_TRANSFER_V3.md."""
from pathlib import Path
import sys
from types import SimpleNamespace
from field_live_controller_v8 import sha,config_writer,derive_close,compile_method
from field_live_source_outputs_v4 import Outputs,bounded_json
from field_transfer_files_v2 import make_class
from field_transfer_v2 import bind_installed,verify_zip

def create(root, admission):
    root=Path(root);base=Path(admission['installed_release']);data=root/'data'
    expected='274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
    if sha(base/'RELEASE_MANIFEST.json')!=expected:raise ValueError('Installed release changed')
    manifest={r['path']:r for r in bounded_json(base/'RELEASE_MANIFEST.json',1048576)['files']}
    pins={r['path']:r for r in admission['files']}
    copy=admission['saved_copy'];identifier=copy['conversation']
    if set(p.name for p in (data/'conversations').iterdir())!={identifier}:raise ValueError('One copied conversation required')
    for name in ('people','sessions'):
        if any((data/name).iterdir()):raise ValueError('Saved workflow requires empty '+name)
    for row in copy['files']:
        path=root/row['relative']
        if sha(path)!=row['sha256'] or path.stat().st_size!=row['bytes']:raise ValueError('Copy drift before constructor')
    sys.path[:0]=[str(base),str(base/'vendor'),str(base/'native')]
    from app import controller as cm,paths,sessions,text_assistance
    from native import field_entry_v5 as entry
    def origins():
        checked=[]
        for name,m in tuple(sys.modules.items()):
            file=getattr(m,'__file__',None)
            if not file or (name.split('.')[0] not in ('app','native','edge_speech_pipeline','release_tools') and not name.startswith(('field_','isolated_','d1_'))):continue
            p=Path(file).resolve()
            if p.parent==root/'code':
                if str(p) not in pins or sha(p)!=pins[str(p)]['sha256']:raise ValueError('Unpinned helper '+name)
            else:
                rel=p.relative_to(base).as_posix()
                if rel not in manifest or sha(p)!=manifest[rel]['sha256']:raise ValueError('Installed origin changed '+name)
            checked.append(name)
        return checked
    origins()
    if entry.ROOT.resolve()!=base or paths.ROOT.resolve()!=base:raise ValueError('Installed root changed')
    Field,backend=entry.controller_type()
    outputs=Outputs(root,'parent')
    owner=SimpleNamespace(stop=lambda reason=None:outputs.stop_event.set())
    config=config_writer(root,outputs,owner)
    cm.atomic_json=paths.atomic_json=text_assistance.atomic_json=config
    publication=[]
    def reject_saved_mutation(path,value):
        raise ValueError('Copied saved metadata is read-only during transfer')
    sessions.atomic_json=reject_saved_mutation
    transfer=dict(phase=0,binding=None,actions=[])
    destination=root/'conversation_exports/transfer.zip'
    expected_actions=[
        ('export',dict(identifier=identifier,path=str(destination),audio=True,consent=True)),
        ('delete',dict(identifier=identifier,confirmed=True)),
        ('import',dict(path=str(destination),consent=True)),
        ('open',dict(identifier=identifier)),
    ]
    def check_action(action,values):
        if transfer['phase']>=len(expected_actions) or (action,values)!=expected_actions[transfer['phase']]:
            raise ValueError('Exact one-use export/delete/import/open sequence required')
        if outputs.stop_event.is_set():raise RuntimeError('Transfer first fault is latched')
    _,close_node=derive_close(Path(cm.__file__).read_bytes())
    safe_close=compile_method(close_node,cm.__dict__,str(cm.__file__)+':saved-bounded-close')
    class SavedController(Field):
        _do_close=safe_close
        def request_archive_stop(self,reason):
            outputs.stop_event.set()
            self.error=self.error or str(reason)
        def _enqueue(self,action,*args,**kwargs):
            if action not in ('select_backend','switch','stop','close','session_action'):
                raise ValueError('Capture, models and other data actions are unavailable in this saved qualification')
            if action=='session_action':
                if len(args)!=2 or (args[0],args[1]) not in expected_actions:
                    raise ValueError('Only exact copied transfer actions are admitted')
            return super()._enqueue(action,*args,**kwargs)
        def _do_session_action(self,action,values):
            check_action(action,values)
            try:
                if action=='delete':
                    with guard.allow_copied_delete(self.session_store.folder(identifier),transfer['binding'],destination):
                        result=super()._do_session_action(action,values)
                else:
                    result=super()._do_session_action(action,values)
                if action=='export':
                    transfer['binding']=verify_zip(derived,destination,self.session_store.folder(identifier),identifier)
                if action=='import':
                    checked={name:dict(bytes=(self.session_store.folder(identifier)/name).stat().st_size,
                                       sha256=sha(self.session_store.folder(identifier)/name))
                             for name in transfer['binding']['files']}
                    if checked!=transfer['binding']['files']:raise RuntimeError('Imported bytes changed')
                transfer['actions'].append(dict(action=action,complete=True))
                transfer['phase']+=1
                return result
            except BaseException as exc:
                outputs.fail('entry',exc,outputs.stop_event.set)
                raise
        def _start_session(self):raise ValueError('Start unavailable: saved-copy qualification')
        def _do_start_live(self,*args,**kwargs):raise ValueError('Capture unavailable: saved-copy qualification')
        def _do_start_file(self,*args,**kwargs):raise ValueError('Model execution unavailable: saved-copy qualification')
    files={Path(r['path']).name:r['bytes'] for r in admission['files'] if Path(r['path']).parent==root/'code'}
    guard=make_class(admission['transfer']['import_token'])(root,files,outputs.stop_event.set).install()
    import field_archive_v3 as archive_module
    pin=manifest['native/field_archive_v3.py']['sha256']
    if Path(archive_module.__file__).resolve()!=base/'native/field_archive_v3.py':
        raise ValueError('Exact installed transfer module origin required')
    derived=bind_installed(archive_module,pin,guard)
    import uuid
    allocated=[]
    def one_import_uuid():
        if allocated:raise ValueError('Only one staged import is admitted')
        allocated.append(True)
        return uuid.UUID(hex=admission['transfer']['import_token'])
    derived.uuid=SimpleNamespace(uuid4=one_import_uuid)
    contract,_=entry.artifact_contract()
    controller=SavedController(data,Path(contract['models_root']),saved_audio_only=True)
    try:
        controller.select_backend(backend);controller.commands.join()
        controller.switch(mode='open_with_names',recipe='balanced',tap='O0');controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        checked=origins()
    except BaseException:
        controller.close();controller.commands.join();controller.worker.join(10)
        raise
    return controller,dict(outputs=outputs,guard=guard,configuration=config,publication=publication,origins=checked,transfer=transfer,derived=derived)
