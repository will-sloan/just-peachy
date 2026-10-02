"""Nested broker controller; README_FIELD_OPERATOR_BROKER_QUALIFICATION_V7.md."""
import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import inspect
from pathlib import Path
import sys
import textwrap
import threading

BASE_MANIFEST = '274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'
COMMANDS = frozenset(('select_backend','switch','start_live','start_file','stop','close','session_action','motion_event'))


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def derive_field(source):
    """Retain installed restrictions; replace only Base, source and store wiring."""
    tree = ast.parse(source)
    original = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='controller_type')
    node = deepcopy(original)
    assert not node.args.args
    node.args.args = [ast.arg(arg=name) for name in ('required_base','source_module','store_type')]
    first = next(n for n in node.body if isinstance(n,ast.ImportFrom) and n.module=='app.controller')
    assert ast.unparse(first)=='from app.controller import Controller as Base'
    node.body[node.body.index(first)] = ast.parse('Base = required_base').body[0]
    imp = next(n for n in node.body if isinstance(n,ast.ImportFrom) and n.module=='isolated_pipeline_source_v2')
    assert ast.unparse(imp)=='from isolated_pipeline_source_v2 import IsolatedLiveConfig, bind_pipeline'
    i = node.body.index(imp)
    node.body[i:i+1] = ast.parse('IsolatedLiveConfig = source_module.IsolatedLiveConfig\nbind_pipeline = source_module.bind_pipeline').body
    cls = next(n for n in node.body if isinstance(n,ast.ClassDef) and n.name=='FieldController')
    methods = {n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    sessions = methods['_sessions_initialize']
    assert ast.unparse(sessions.body[0])=='from field_archive_v3 import FieldArchiveStore'
    sessions.body[0] = ast.parse('FieldArchiveStore = store_type').body[0]
    methods['_live_config'].body = ast.parse('return _delivery_live_config(self, IsolatedLiveConfig)').body
    return original,ast.fix_missing_locations(node)


def derive_close(source):
    cls = next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Controller')
    old = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_do_close')
    new = deepcopy(old)
    indices = [i for i,n in enumerate(new.body) if isinstance(n,ast.Expr)
               and isinstance(n.value,ast.Call) and ast.unparse(n.value.func)=='atomic_json']
    if len(indices)!=1:
        raise ValueError('Installed close publication boundary changed')
    i = indices[0]
    guard = ast.parse("try:\n pass\nexcept Exception as exc:\n self.request_archive_stop('TERMINAL_CONFIG: '+str(exc))\n self.metrics['terminal_configuration_failure'] = type(exc).__name__+': '+str(exc)[:512]").body[0]
    guard.body = [new.body[i]]
    new.body[i] = guard
    # The preceding physical Stop checks and following models/lease release stay exact.
    return old,ast.fix_missing_locations(new)


def derive_presentation(source):
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Controller')
    old=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='record_presentation')
    new=deepcopy(old)
    branch=new.body[-1].body[-1]
    if not isinstance(branch,ast.If) or ast.unparse(branch.test)!='session' or len(branch.body)!=1:
        raise ValueError('Installed presentation writer boundary changed')
    if not isinstance(branch.body[0],ast.Try) or 'path.open' not in ast.unparse(branch.body[0]):
        raise ValueError('Installed presentation publication changed')
    branch.body=ast.parse('self._delivery_write_presentation(value)').body
    return old,ast.fix_missing_locations(new)


def compile_method(node, namespace, origin):
    scope = dict(namespace)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),origin,'exec'),scope)
    return scope[node.name]


class ControllerRef:
    """Nonblocking reference available before constructors and writer callbacks."""
    def __init__(self):
        self.controller = None
        self.early_failure = None

    def stop(self, reason='REQUIRED_DELIVERY_WRITER_FAILED'):
        if self.controller is None or not hasattr(self.controller,'_archive_failure_lock'):
            self.early_failure = self.early_failure or str(reason)[:512]
            return
        self.controller.request_archive_stop(reason)


def config_writer(root, outputs, owner):
    """Three physical data paths, each using one retained64KiB slot as two32KiB copies."""
    from field_archive_budget_v4 import encode_control,publish
    import types
    terminal_publish=types.FunctionType(publish.__code__,dict(publish.__globals__,encode_control=terminal_encode),publish.__name__,publish.__defaults__,publish.__closure__)
    from field_operator_layout_v2 import finite_json
    import shutil
    data = Path(root)/'data'
    lock = threading.RLock()
    failed = []
    attempts = {}
    allowed = {'settings.json':32,'DATA_SCHEMA.json':1,'last_application.json':1}

    def atomic(path,value):
        path = Path(path)
        with lock:
            if failed:
                raise RuntimeError('Configuration publication failed; inspect preserved primary/pending')
            raw = None
            try:
                if path.parent!=data or path.name not in allowed or data.resolve()!=data:
                    raise ValueError('Unmapped private configuration write')
                count=attempts.get(path.name,0)
                if count>=allowed[path.name]:
                    raise ValueError('Configuration publication count exhausted')
                attempts[path.name]=count+1
                serialize=terminal_encode if path.name=='last_application.json' else encode_control
                raw=serialize(value,32768);finite_json(raw)
                if shutil.disk_usage(data).free<5*1024**3+len(raw):
                    raise OSError('Pi free floor')
                writer=terminal_publish if path.name=='last_application.json' else publish
                result=writer(path,value,32768)
                if path.read_bytes()!=raw:raise IOError('Exact configuration readback')
                if path.name=='last_application.json' and terminal_encode(decode_terminal(raw),32768)!=raw:raise IOError('Complete terminal metadata readback')
                return result
            except Exception as exc:
                failed.append(dict(path=str(path),error=repr(exc)[:512],replaced=getattr(exc,'replaced',None)))
                outputs.fail('entry',exc,lambda:owner.stop('CONFIG: '+str(exc)),raw)
                raise
    atomic.attempts=attempts
    atomic.failures=failed
    atomic.physical_paths={name:dict(primary=str(data/name),pending=str(data/('.'+name+'.pending')),
                                   primary_maximum=32768,pending_maximum=32768)
                           for name in allowed}
    return atomic


def store_class(installed,sessions,outputs,owner,budget):
    """Keep every installed FieldArchiveStore method, including constructor contract checks."""
    class OneRunStore(sessions.SessionStore):
        def __init__(self,data_root,policy=None):
            folder=Path(data_root)/'conversations'
            if folder.is_symlink() or not folder.is_dir() or any(folder.iterdir()):
                raise ValueError('Fresh empty admitted conversation parent required')
            self.delivery_new=False;self.delivery_epoch=False
            self.delivery_identifier=None;self.delivery_failure=None
            selected=dict(policy or {})
            if selected.get('quota_mib')!=512 or selected.get('free_floor_mib')!=5120:
                raise ValueError('Installed field storage limits changed')
            selected.update(archive_budget=deepcopy(budget),record_bytes=65536)
            super().__init__(data_root,policy=selected)

        def _publish(self,path,value):
            if self.delivery_failure is not None:
                raise RuntimeError('Conversation publisher failed; no retry')
            try:
                path=Path(path)
                if path.name!='conversation.json' or path.parent.parent!=self.root:
                    raise ValueError('Unmapped conversation control')
                identifier=path.parent.name
                if self.folder(identifier)!=path.parent or not self.delivery_new:
                    raise ValueError('Conversation publication before reserved attempt')
                if self.delivery_identifier not in (None,identifier):
                    raise ValueError('Second conversation not reserved')
                self.delivery_identifier=identifier
                return super()._publish(path,value)
            except Exception as exc:
                self.delivery_failure=repr(exc)[:512]
                outputs.fail('entry',exc,lambda:owner.stop('CONVERSATION: '+str(exc)))
                # SessionStore.ended must not swallow an OSError and claim success.
                raise RuntimeError('Required conversation publication failed') from exc

        def enforce(self,exclude=None):
            if len(self.list())>=self.policy['draft_limit'] or self.usage()['bytes']>=512*1024**2:
                raise OSError('Archive limit; retained history is never automatically deleted')

        def new(self,*args,**kwargs):
            if self.delivery_new or self.delivery_failure is not None:
                raise RuntimeError('One conversation attempt per fresh process')
            self.delivery_new=True
            return super().new(*args,**kwargs)

        def begin(self,identifier,metadata,**options):
            if self.delivery_epoch or self.delivery_failure is not None or identifier!=self.delivery_identifier or options:
                raise RuntimeError('One admitted archive epoch without fixture options required')
            self.delivery_epoch=True
            # Create the sole mapped parent before EpochArchive's recursive mkdir.
            # Unexpected existence or any real failure remains latched by the guard.
            parent=self.folder(identifier)/'epochs'
            if parent.exists() or parent.is_symlink():
                raise RuntimeError('Fresh empty epochs parent required')
            parent.mkdir()
            return super().begin(identifier,metadata)

    source=Path(installed.__file__).read_bytes()
    tree=ast.parse(source)
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FieldArchiveStore')
    if [ast.unparse(n) for n in node.bases]!=['SessionStore']:
        raise ValueError('Installed store inheritance changed')
    scope=dict(installed.__dict__,SessionStore=OneRunStore)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(installed.__file__)+':one-run-base','exec'),scope)
    return scope['FieldArchiveStore']


def module_at(name,path):
    path=Path(path)
    if name in sys.modules:
        raise RuntimeError('Fresh process required before binding '+name)
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    try:spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


def create(config_path):
    """Actual production constructor. Caller owns the admitted process and outer guards.

    No GUI, capture auto-start, installation pointer or baseline is changed here.
    A caller must additionally enforce and census the complete run/mirror layout.
    """
    from field_live_source_outputs_v6 import load,bounded_json
    cfg,admission,outputs=load(config_path)
    base=Path(cfg['prototype']);root=Path(cfg['output_root']);data=root/'data'
    if sha(base/'RELEASE_MANIFEST.json')!=BASE_MANIFEST:
        raise ValueError('Exact installed v12 manifest required')
    manifest={r['path']:r for r in bounded_json(base/'RELEASE_MANIFEST.json',1024**2)['files']}
    pins={r['path']:r for r in admission['files']}
    code=Path(__file__).resolve().parent
    required=('field_operator_controller_v6.py','field_live_d1_v1.py','d1_modes_v1.py','d1_endpoint_contract_v3.py','d1_method_controls_v1.py','archive_stop_sessions_v1.py','field_controller_stop_v1.py',
              'field_archive_stop_v1.py','field_archive_records_v1.py','field_operator_actions_v3.py','field_operator_files_v2.py','field_operator_layout_v2.py','field_transfer_v2.py','field_operator_transfer_files_v1.py','field_operator_paths_v1.py','field_archive_budget_v4.py','field_native_binding_v1.py',
              'field_native_text_v2.py','isolated_pipeline_source_v11.py')
    for name in required:
        path=code/name
        if str(path) not in pins or sha(path)!=pins[str(path)]['sha256']:
            raise ValueError('Required composition source not admitted: '+name)
    if data.resolve()!=data or data.is_symlink():
        raise ValueError('Real data root required')
    for name in ('people','sessions','conversations','.archive-imports'):
        path=data/name
        if not path.is_dir() or path.is_symlink() or any(path.iterdir()):
            raise ValueError('This first live integration requires empty private '+name)
    # Additional private features are excluded before any application constructor.
    if {p.name for p in data.iterdir()}-{'people','sessions','conversations','live_config.json','settings.json','n2_runtime.json','DATA_SCHEMA.json','.archive-imports'}:
        raise ValueError('Unexpected initial private path')
    settings=bounded_json(data/'settings.json')
    if settings.get('enhancement_route','bypass')!='bypass' or settings.get('spatial_visualization',False):
        raise ValueError('Only unenhanced nonspatial input is admitted')
    for name in ('settings.json','DATA_SCHEMA.json'):
        if (data/name).stat().st_size>32768:
            raise ValueError('Initial config exceeds its primary half-slot')
    for name in ('live_config.json','n2_runtime.json','settings.json','DATA_SCHEMA.json'):
        path=data/name
        if str(path) not in pins or sha(path)!=pins[str(path)]['sha256']:
            raise ValueError('Private setup bytes are not admitted')
        bounded_json(path)
    sys.path[:0]=[str(base),str(base/'vendor'),str(base/'native')]
    import app
    if Path(app.__file__).resolve()!=base/'app/__init__.py':
        raise ValueError('Installed app origin mismatch')
    sessions=module_at('app.sessions',code/'archive_stop_sessions_v1.py');app.sessions=sessions
    from app import controller as cm,paths,pipeline,text_assistance
    from native import field_entry_v5 as entry
    import field_archive_v3 as installed_store
    from edge_speech_pipeline import runtime,research_s7
    import isolated_pipeline_source_v11 as source_module
    import field_archive_budget_v4 as budget_module
    from field_controller_stop_v1 import controller_class
    from field_archive_stop_v1 import archive_class
    from field_native_binding_v1 import NativeOwner,bind as bind_native

    def verify_loaded():
        checked=[]
        for name,module in tuple(sys.modules.items()):
            origin=getattr(module,'__file__',None)
            if not origin or (name.split('.')[0] not in ('app','native','edge_speech_pipeline','release_tools')
                              and not name.startswith(('field_','isolated_','d1_'))):
                continue
            path=Path(origin).resolve()
            if name=='app.sessions':
                if path!=code/'archive_stop_sessions_v1.py' or sha(path)!=pins[str(path)]['sha256']:
                    raise ValueError('Session overlay origin/digest')
            elif path.parent==code:
                if str(path) not in pins or sha(path)!=pins[str(path)]['sha256']:
                    raise ValueError('Loaded helper origin/digest is not admitted: '+name)
            else:
                rel=path.relative_to(base).as_posix()
                if rel not in manifest or sha(path)!=manifest[rel]['sha256']:
                    raise ValueError('Installed import origin/manifest mismatch: '+name)
            checked.append(name)
        for module,relative in ((entry,'native/field_entry_v5.py'),(installed_store,'native/field_archive_v3.py')):
            if Path(module.__file__).resolve()!=base/relative or sha(base/relative)!=manifest[relative]['sha256']:
                raise ValueError('Exact field module origin/hash required')
        return checked

    verify_loaded()
    if entry.ROOT.resolve()!=base or paths.ROOT.resolve()!=base:
        raise ValueError('Installed root changed')
    contract,limits=entry.artifact_contract()
    budget=budget_module.validate(budget_module.DEFAULT)
    owner=ControllerRef();writer=config_writer(root,outputs,owner)
    outputs.request_stop=lambda:owner.stop('PHYSICAL_OUTPUT')
    cm.atomic_json=paths.atomic_json=text_assistance.atomic_json=writer
    policy=dict(archive_budget=budget,artifact_limits=limits,quota_mib=512,free_floor_mib=5120,record_bytes=65536)
    Required=controller_class(cm,sessions,outputs,policy,manifest['app/controller.py']['sha256'])
    OriginalStore=store_class(installed_store,sessions,outputs,owner,budget)
    from field_transfer_v2 import derive as transfer_derive
    from field_operator_actions_v3 import Actions
    from types import SimpleNamespace
    import uuid
    derived=transfer_derive(Path(installed_store.__file__).read_bytes(),
                            manifest['native/field_archive_v3.py']['sha256'])
    derived.rename_noreplace=outputs.physical_files.publish_import
    allocated=[]
    def one_import_uuid():
        if allocated:raise ValueError('One import allocation per recording process')
        allocated.append(True)
        return uuid.UUID(hex=admission['transfer']['import_token'])
    derived.uuid=SimpleNamespace(uuid4=one_import_uuid)
    # Cooperative MRO preserves the transfer class body and the one-run base.
    # Transfer super().__init__ reaches OneRunStore before the actual SessionStore.
    OneRunStore=OriginalStore.__bases__[0]
    if derived.FieldArchiveStore.__bases__!=(sessions.SessionStore,):
        raise ValueError('Transfer/session overlay inheritance changed')
    Store=type('OperatorArchiveStore',(derived.FieldArchiveStore,OneRunStore),{})
    actions=Actions(root,outputs,derived)
    from field_archive_records_v1 import archive_class as record_archive,chunked_binary
    sessions.CompactBinary=chunked_binary(sessions.CompactBinary)
    sessions.EpochArchive=record_archive(archive_class(sessions.EpochArchive,outputs,owner.stop))

    def live_config(controller,Config):
        if controller.source_kind!='live' or controller.epoch!=1:
            raise ValueError('Exactly one live epoch is admitted')
        current,_,_=load(config_path)
        if current!=cfg:raise ValueError('Source binding changed before Start')
        return Config(Path(config_path),base)

    runtime_profile=admission.get('runtime_profile')
    if type(runtime_profile) is not dict or set(runtime_profile)!={'definition','galleries'}:
        raise ValueError('Exact admitted runtime profile/gallery binding')
    definition=runtime_profile['definition'];selection=definition['selection']
    if selection['input_kind'] not in ('microphone','saved'):raise ValueError('Exact input route')
    if selection['input_kind']=='saved' and selection['engine_mode'] not in ('streaming','chunk52'):raise ValueError('Exact saved mode')
    broker=admission['session_broker'];broker_root=Path(broker['root'])
    broker_policy=bounded_json(broker_root/'RELEASE.json')
    if (sha(broker_root/'RELEASE.json')!=broker['policy_sha256']
        or broker_policy['profile']!=selection['profile']
        or root!=broker_root/'recordings'/broker['slot']):
        raise ValueError('Actual operation/profile/recording binding')
    from app import backends as runtime_backends,people as runtime_people,n2_people as runtime_n2_people
    catalog_path=base/'config/backends.json'
    if sha(catalog_path)!=manifest['config/backends.json']['sha256']:
        raise ValueError('Actual installed backend catalogue pin')
    selected_id=bind_registry(runtime_backends,catalog_path.read_bytes(),definition)
    gallery_root=Path(broker_policy['runtime_root']).with_name(Path(broker_policy['runtime_root']).name+'-galleries')
    for encoder,descriptor in runtime_profile['galleries'].items():
        if descriptor['root']!=str(gallery_root/encoder/'people') or descriptor['manifest_path']!=str(gallery_root/encoder/'MANIFEST.json'):
            raise ValueError('Versioned independent gallery snapshot path')
    def profile_guard():
        from datetime import datetime,timezone
        import shutil
        if datetime.now(timezone.utc)>=datetime.fromisoformat(admission['expires_utc']):
            raise TimeoutError('Runtime profile binding deadline')
        available=next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))
        if available<192*1024**2 or shutil.disk_usage(root).free<5*1024**3:
            raise RuntimeError('Profile binding RAM/disk floor')
    document=bounded_json(data/'n2_runtime.json')
    namespace=document.get('embedding_namespace') if selection['embedding']=='E1' else None
    if selection['embedding']=='E1':
        from edge_speech_pipeline import titanet_embedding
        adapter=base/'vendor/edge_speech_pipeline/titanet_embedding.py'
        if Path(titanet_embedding.__file__).resolve()!=adapter or sha(adapter)!=manifest['vendor/edge_speech_pipeline/titanet_embedding.py']['sha256']:
            raise ValueError('Original installed TitaNet adapter origin/pin')
        bind_titanet_memory(titanet_embedding,adapter)
    readonly=readonly_store_type(runtime_people,data,runtime_profile['galleries'],namespace,profile_guard)
    cm.PersonalStore=readonly;runtime_n2_people.PersonalStore=readonly

    original,node=derive_field(Path(entry.__file__).read_bytes())
    node=specialize_factory(node,definition)
    factory=compile_method(node,dict(entry.__dict__,_delivery_live_config=live_config),str(entry.__file__)+':delivery')
    Field,backend=factory(Required,source_module,Store)
    _,close_node=derive_close(Path(cm.__file__).read_bytes())
    safe_close=compile_method(close_node,cm.__dict__,str(cm.__file__)+':bounded-close')
    _,presentation_node=derive_presentation(Path(cm.__file__).read_bytes())
    presentation=compile_method(presentation_node,cm.__dict__,str(cm.__file__)+':bounded-presentation')
    command=ast.parse(textwrap.dedent(inspect.getsource(Required._commands))).body[0]
    calls=[n for n in ast.walk(command) if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
           and ast.unparse(n.value.func).startswith('getattr(self,')]
    if len(calls)!=1:raise ValueError('Required command dispatch boundary changed')
    class Insert(ast.NodeTransformer):
        def visit_Expr(self,node):
            if node is calls[0]:
                return ast.parse('self._delivery_command(action,args,kwargs)').body+[node]
            return node
    command=Insert().visit(command)
    guarded_commands=compile_method(command,Required._commands.__globals__,'required-commands:delivery')

    class DeliveryController(Field):
        _commands=guarded_commands
        _do_close=safe_close
        record_presentation=presentation

        def __init__(self,*args,**kwargs):
            owner.controller=self
            self._delivery_attempted=False;self._delivery_new_requested=False
            super().__init__(*args,**kwargs)

        def _delivery_command(self,action,args,kwargs):
            if action not in COMMANDS:
                raise ValueError('Action unavailable in this bounded live integration')
            if action in ('start_live','start_file'):
                expected='start_file' if selection['input_kind']=='saved' else 'start_live'
                if action!=expected or self._delivery_attempted:raise ValueError('Source route/one Start attempt')
                if action=='start_file':
                    if len(args)!=1 or kwargs:raise ValueError('One explicit prepared input path')
                    if not self._delivery_new_requested:raise ValueError('Choose recording before Start')
                    self._saved_pin=saved_input_pin(args[0],selection['engine_mode'],profile_guard)
                    outputs.source('SOURCE_START.json',dict(schema='just-peachy.saved-source-start.v1',input=self._saved_pin,physical_microphone=False))
            if action in ('select_backend','switch') and self._delivery_attempted:
                raise ValueError('Return to a fresh process to change runtime/mode')
            if action=='session_action' and (len(args)!=2 or args[0] not in ('new','save','open','export','delete','import')):
                raise ValueError('Only audio New, Save, Open and bounded full transfer are available')
            if action=='session_action' and args[0]=='new':
                if self._delivery_new_requested or self._delivery_attempted or self.conversation_id is not None:
                    raise ValueError('One explicit audio conversation before Start is admitted')
                value=args[1]
                if type(value) is not dict or set(value) not in ({'audio','consent'},{'audio','consent','title'},{'audio','consent','raw_microphones'},{'audio','consent','title','raw_microphones'}) or type(value['audio']) is not bool or type(value['consent']) is not bool or value['audio'] != value['consent']:
                    raise ValueError('Choose audio Off, or Processed with storage consent')
                if 'title' in value and (type(value['title']) is not str or not value['title'].strip() or len(value['title'])>160 or len(value['title'].encode('utf-8'))>640):
                    raise ValueError('Use a bounded conversation title')
                raw=value.get('raw_microphones',False)
                if type(raw) is not bool or (raw and (not value['audio'] or selection['input_kind']!='microphone')):
                    raise ValueError('Raw physical microphones require live input and audio consent')
                outputs.groups['config'].write('RAW_SELECTION.json',encoded(dict(
                    schema='just-peachy.raw-selection.v1',raw_microphones=raw,audio_requested=value['audio'])))
                value.pop('raw_microphones',None)
                self._delivery_new_requested=True

        def _do_session_action(self,action,values):
            if action=='new':return super()._do_session_action(action,values)
            # The installed history page uses Save-current without an identifier.
            # Resolve only this owned, explicit audio conversation; all other
            # explicit action identities are checked by the action budget.
            if action=='save' and values=={}:
                if self.conversation_id!=self.session_store.delivery_identifier:
                    raise ValueError('Save-current identity changed')
                values={'identifier':self.conversation_id}
            return actions.run(self,action,values,super()._do_session_action)

        def _start_session(self):
            expected_kind='file' if selection['input_kind']=='saved' else 'live'
            if self._delivery_attempted or self.source_kind!=expected_kind:
                raise ValueError('One live recording attempt per fresh process')
            if not self._delivery_new_requested or not self.session_store.delivery_new or self.conversation_id!=self.session_store.delivery_identifier:
                raise ValueError('Choose recording Off or consented Processed before Start')
            meta=self.session_store.metadata(self.conversation_id)
            if type(meta.get('audio_requested')) is not bool or meta.get('consent',{}).get('audio_storage') is not meta['audio_requested']:
                raise ValueError('This recording requires explicit audio-storage consent')
            self._delivery_attempted=True
            try:return super()._start_session()
            except BaseException as exc:
                self.request_archive_stop('LIVE_START: '+str(exc))
                raise

        def _artifact_limits_for_epoch(self):
            result=super()._artifact_limits_for_epoch()
            if self.session_store.archive_budget!=budget or self.session_store.policy['archive_budget']!=budget:
                raise ValueError('Prepared archive budget drift')
            return result

        def _do_stop(self):
            if self.closed:
                self._reassert_archive_failure()
                return
            return super()._do_stop()

        def _delivery_write_presentation(self,value):
            raw=None
            try:
                from field_live_layout_v3 import encoded
                raw=encoded(value)+b'\n'
                outputs.publish('presentation','telemetry',raw)
                self.metrics['gui_presentation_log']=str(root/'telemetry/presentation.jsonl')
            except Exception as exc:
                outputs.fail('presentation',exc,lambda:owner.stop('PRESENTATION: '+str(exc)),raw)
                raise

        def snapshot(self):
            value=super().snapshot()
            value['field_candidate'].update(maximum_recording_seconds=120,one_run_per_process=True,
                save_open_available=True,interchange_available=True,delete_available=True,
                input_kind=selection['input_kind'],maximum_input_seconds=30 if selection['engine_mode']=='streaming' else 120,
                physical_touch_qualified=False,field_release_accepted=False)
            return value

    native=NativeOwner(data/'sessions',outputs,owner.stop)
    bind_native(pipeline,runtime,research_s7,native,
                {key:manifest[rel]['sha256'] for key,rel in
                 (('pipeline','app/pipeline.py'),('runtime','vendor/edge_speech_pipeline/runtime.py'),
                  ('trace','vendor/edge_speech_pipeline/research_s7.py'))})
    d1_state=None
    if selection['diarization']=='D1':
        from field_live_d1_v1 import bind as bind_d1
        from d1_method_controls_v1 import MethodCatalog
        binding=admission.get('d1_binding',{})
        if set(binding)!={'mode','campaign','method_contract','method_evidence','maximum_samples'}:
            raise ValueError('Explicit admitted live D1 method binding required')
        if binding['mode']!=selection['engine_mode'] or type(binding['maximum_samples']) is not int or binding['maximum_samples']!=2080000:
            raise ValueError('Only the selected bounded delayed live method is admitted')
        broker=admission.get('session_broker')
        if type(broker) is not dict or set(broker)!={'root','owner','policy_sha256','slot'}:
            raise ValueError('Exact nested broker binding required')
        import re
        campaign=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
        broker_root=Path(broker['root'])
        if (Path(binding['campaign']).resolve()!=campaign or broker_root.parent!=campaign
            or not re.fullmatch(r'field-operator-sessions-v[1-9][0-9]*',broker_root.name)
            or not re.fullmatch(r'slot-0[1-4]',broker['slot'])
            or root!=broker_root/'recordings'/broker['slot']
            or sha(broker_root/'RELEASE.json')!=broker['policy_sha256']):
            raise ValueError('Exact nested live D1 campaign/root/policy binding mismatch')
        if Path(binding['method_contract'])!=code/'D1_METHOD_CONTRACT_V1.json':
            raise ValueError('Method contract must use the admitted code capsule')
        for path in (Path(binding['method_contract']),Path(binding['method_evidence']),
                     code/'D1_MODE_CATALOG_V1.json',code/'D1_ENDPOINT_CONTRACT_V3.json'):
            if str(path) not in pins or sha(path)!=pins[str(path)]['sha256']:
                raise ValueError('D1 method/catalogue/endpoint evidence is not admitted')
        catalog=MethodCatalog(binding['method_contract'],binding['method_evidence'])
        d1_state=bind_d1(base,Path(binding['campaign']),manifest,
                         bounded_json(data/'n2_runtime.json'),catalog,outputs,owner.stop,mode=selection['engine_mode'])

    if selection['input_kind']=='saved':
        pipeline.FileSource=saved_source_type(pipeline,lambda:getattr(owner.controller,'_saved_pin',None),
            selection['engine_mode'],profile_guard,outputs,owner.stop)
    mounted_worker,mounted_config=_bind_mounted_runtime(base,manifest)
    controller=DeliveryController(data,Path(contract['models_root']),saved_audio_only=selection['input_kind']=='saved')
    try:
        if controller.imu is not None:raise RuntimeError('Unexpected second IMU owner')
        controller.imu=mounted_worker(mounted_config,controller.motion_event).start()
        controller.settings['spatial_visualization']=selection['input_kind']=='microphone'
        controller.metrics['mounted_motion_binding']=dict(config_sha256=_MOUNTED_CONFIG_SHA,
            display_frame='device',logic_frame='relative_anchor_front_assumed',
            translation_position_available=False,saved_audio_uses_live_pose=False)
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        controller.select_backend(backend);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        controller.switch(mode=selection['ui_mode'],recipe='balanced',tap='O0');controller.commands.join()
        if controller.error or owner.early_failure:raise RuntimeError(controller.error or owner.early_failure)
        if controller.backend_id!=selected_id:
            raise RuntimeError('Selected backend did not reach actual Controller')
        actual=getattr(controller,'_n2_components',None)
        if selection['backend_key']!='baseline' and (not actual or actual['embedding']!=selection['embedding'] or actual['diarization']!=selection['diarization']):
            raise RuntimeError('Actual resident backend differs from selected encoder/diarizer')
        origins=verify_loaded()
    except BaseException:
        if not controller.closed:controller.close()
        controller.commands.join();controller.worker.join(10)
        if controller.worker.is_alive():raise RuntimeError('Controller construction cleanup remains owned')
        raise
    return controller,dict(native_owner=native,outputs=outputs,configuration=writer,
                           installed_origins=origins,source_binding=cfg,admission=admission,
                           d1_binding=d1_state,runtime_profile=definition,physical_files=outputs.physical_files,actions=actions,transfer=derived,runtime_accepted=False)

"""Backend/embedding selection reused from the application; README_FIELD_RUNTIME_PROFILES_V1.md."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import time

SCHEMA = 'just-peachy.runtime-profile.v1'
TITANET_MODEL = 'e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3'
TITANET_ONNX = '86b64bc03a7b151231f59745a8d36619fbc68b739a4abb253bd0d9ce0c350610'
TITANET_FRONTEND = '582f92d2fa2a29be70f6fdc13d67fc1376083ca66cb35401f8335ed85c4115b6'
TITANET_PREPROCESSING = 'nemo-cf724ac3-mel80-16k-eval-v1'
REDIMNET = '5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609'
ROOT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928'
# Explicit retained routes. This is a configuration table, not a test sweep.
ROUTES = {
    'baseline': ('baseline', 'D0', 'E0', 'baseline', 'microphone', 'open_with_names'),
    'baseline-titanet': ('titanet', 'D0', 'E1', 'baseline', 'microphone', 'open_with_names'),
    'd1-delayed': ('nemotron_hybrid', 'D1', 'E0', 'delayed', 'microphone', 'open_with_names'),
    'd1-delayed-titanet': ('nemotron_titanet', 'D1', 'E1', 'delayed', 'microphone', 'open_with_names'),
    'd1-streaming-saved': ('nemotron_hybrid', 'D1', 'E0', 'streaming', 'saved', 'open_with_names'),
    'd1-streaming-titanet-saved': ('nemotron_titanet', 'D1', 'E1', 'streaming', 'saved', 'open_with_names'),
    'd1-chunk52-saved': ('nemotron_hybrid', 'D1', 'E0', 'chunk52', 'saved', 'open_with_names'),
    'd1-chunk52-titanet-saved': ('nemotron_titanet', 'D1', 'E1', 'chunk52', 'saved', 'open_with_names'),
    'd1-anonymous': ('nemotron_hybrid', 'D1', 'E0', 'delayed', 'microphone', 'anonymous_conversation'),
    'baseline-anonymous': ('baseline', 'D0', 'E0', 'baseline', 'microphone', 'anonymous_conversation'),
}
NATIVE_PROFILES = dict(delayed='native_v3_delayed', streaming='native_v3_streaming', chunk52='native_cm5_chunk52')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def select(name):
    if type(name) is not str or name not in ROUTES:
        raise ValueError('Unknown profile; no backend or embedding fallback')
    backend, diarizer, embedding, mode, source, ui_mode = ROUTES[name]
    return dict(profile=name, backend_key=backend, diarization=diarizer, embedding=embedding,
                engine_mode=mode, input_kind=source, ui_mode=ui_mode)


def strict_json(raw, maximum=131072):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise ValueError('Bounded metadata bytes required')
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError('Duplicate JSON key')
            value[key] = item
        return value
    def bad(value):
        raise ValueError('Nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def titanet_namespace(manifest):
    expected = dict(backend_id='titanet_large_fp32', dimension=192,
                    source_model_sha256=TITANET_MODEL, preprocessing_version=TITANET_PREPROCESSING,
                    normalization='l2', minimum_samples=8000)
    for key, value in expected.items():
        if type(manifest.get(key)) is not type(value) or manifest[key] != value:
            raise ValueError('Previous pinned TitaNet representation changed: ' + key)
    for key, name, pin in (('onnx', 'titanet_embedding.onnx', TITANET_ONNX),
                           ('frontend', 'titanet_frontend.npz', TITANET_FRONTEND)):
        if manifest.get(key) != dict(filename=name, sha256=pin):
            raise ValueError('Exact previous TitaNet artifact required: ' + key)
    return dict(model_sha256=TITANET_MODEL, preprocessing=TITANET_PREPROCESSING,
                dimension=192, normalization='L2', minimum_samples=8000,
                onnx_sha256=TITANET_ONNX, frontend_sha256=TITANET_FRONTEND)


def verify_titanet(directory, *, deadline, guard):
    """Read existing artifacts only. No model import, download, conversion or copy."""
    if not callable(guard) or not isinstance(deadline, (int, float)) or isinstance(deadline, bool):
        raise ValueError('Caller resource guard and monotonic deadline required')
    remaining = deadline - time.monotonic()
    if not 0 < remaining <= 600:
        raise ValueError('Bounded current verification deadline required')
    root = Path(directory).absolute()
    for parent in (root, *root.parents):
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError('Existing real asset directory required')
    def read(name, maximum, expected=None):
        guard()
        path = root/name
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum or before.st_nlink != 1:
            raise ValueError('Bounded real artifact')
        h = hashlib.sha256()
        raw = bytearray() if name.endswith('.json') else None
        count = 0
        with path.open('rb') as stream:
            while True:
                guard()
                if time.monotonic() >= deadline:
                    raise TimeoutError('Asset verification deadline')
                block = stream.read(16384)
                if not block:
                    break
                count += len(block); h.update(block)
                if raw is not None:
                    raw.extend(block)
                if count > before.st_size:
                    raise ValueError('Asset grew while read')
        after = path.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
        if any(getattr(before, k) != getattr(after, k) for k in fields) or count != before.st_size:
            raise ValueError('Asset identity changed while read')
        if expected is not None and h.hexdigest() != expected:
            raise ValueError('Existing TitaNet artifact hash mismatch')
        return dict(name=name, bytes=count, sha256=h.hexdigest()), bytes(raw) if raw is not None else None
    manifest_row, raw = read('titanet_manifest.json', 16384)
    manifest = strict_json(raw, 16384)
    namespace = titanet_namespace(manifest)
    onnx, _ = read('titanet_embedding.onnx', 88610787, TITANET_ONNX)
    frontend, _ = read('titanet_frontend.npz', 84358, TITANET_FRONTEND)
    if onnx['bytes'] != 88610787 or frontend['bytes'] != 84358:
        raise ValueError('Pinned prior export sizes changed')
    guard()
    return dict(schema='just-peachy.titanet-local-assets.v1', directory=str(root),
                namespace=namespace, files=[manifest_row, onnx, frontend],
                model_loaded=False, native_execution=False)


def backend_manifest(catalog_raw, profile):
    """Select the old implementation and derive a new mode-specific immutable ID."""
    route = select(profile)
    catalog = strict_json(catalog_raw, 1024*1024)
    if catalog.get('schema') != 'just-peachy.backend-catalog.v1':
        raise ValueError('Existing backend catalogue required')
    rows = catalog.get('backends')
    if type(rows) is not list or not 1 <= len(rows) <= 64:
        raise ValueError('Bounded backend catalogue')
    if len({r['key'] for r in rows}) != len(rows):
        raise ValueError('Duplicate backend key')
    for row in rows:
        if row['manifest_id'] != 'sha256:' + digest(row['composition']):
            raise ValueError('Original backend composition digest changed')
    matches = [r for r in rows if r['key'] == route['backend_key']]
    if len(matches) != 1:
        raise ValueError('Previous backend implementation missing')
    old = matches[0]
    comp = deepcopy(old['composition'])
    if 'n3' in comp or 'Nemotron' in comp['components']['asr']['name']:
        raise ValueError('Sherpa ASR must be retained')
    enrollment = comp['components']['enrollment']
    expected_model = TITANET_MODEL if route['embedding'] == 'E1' else REDIMNET
    if route['embedding'] == 'E1':
        if (enrollment.get('artifact_sha256') != expected_model
                or enrollment.get('onnx_sha256') != TITANET_ONNX
                or enrollment.get('frontend_sha256') != TITANET_FRONTEND):
            raise ValueError('Original TitaNet model/export pins differ')
    elif not any(a['sha256'] == expected_model for a in enrollment['assets']):
        raise ValueError('Original ReDimNet model pin differs')
    if route['backend_key'] == 'baseline':
        if comp.get('n2'):
            raise ValueError('Original baseline path changed')
    else:
        if comp['n2']['diarization'] != route['diarization'] or comp['n2']['embedding'] != route['embedding']:
            raise ValueError('Previous actual resident-model route differs')
    if route['diarization'] == 'D1':
        comp['n2']['streaming_profile'] = NATIVE_PROFILES[route['engine_mode']]
    encoder = 'TitaNet' if route['embedding'] == 'E1' else 'ReDimNet'
    diarizer = 'Nemotron' if route['diarization'] == 'D1' else 'Pyannote'
    label = 'Sherpa + ' + diarizer + ' + ' + encoder
    if route['diarization'] == 'D1':
        label += ' · ' + route['engine_mode'].capitalize()
    if route['ui_mode'] == 'anonymous_conversation':
        label += ' · Anonymous'
    if route['input_kind'] == 'saved':
        label += ' · Saved audio'
    return dict(schema=SCHEMA, selection=route, label=label,
                source_manifest_id=old['manifest_id'], backend_manifest_id='sha256:' + digest(comp),
                composition=comp, native_availability='NOT_YET_QUALIFIED',
                automatic_capture=False, silent_fallback=False)


def runtime_document(original, profile, *, d1_catalog_raw=None, native_titanet_manifest=None, titanet_manifest_raw=None):
    """Pure configuration; the caller must hash-verify deployed artifacts independently."""
    route = select(profile)
    if type(original) is not dict or original.get('schema') != 'just-peachy.n2.runtime.v1':
        raise ValueError('Existing N2 runtime document required')
    result = deepcopy(original)
    if result.get('native_device') != dict(kind='cpu', gpu_index=-1):
        raise ValueError('Existing CPU-only runtime required')
    if route['diarization'] == 'D1':
        if (type(d1_catalog_raw) is not bytes or hashlib.sha256(d1_catalog_raw).hexdigest()
                != 'ff431b358c7140addcddd95c313f2ec82272289dce2a9815e8d63b60f6bde7c5'):
            raise ValueError('Retained complete D1 mode catalogue pin required')
        modes = strict_json(d1_catalog_raw)['modes']
        selected = next(row for row in modes if row['id'] == route['engine_mode'])
        if selected['profile'] != NATIVE_PROFILES[route['engine_mode']]:
            raise ValueError('Exact retained D1 native profile required')
        native_root = PurePosixPath(ROOT)/selected['retained_run']
        assets = {row['name']: row for row in selected['assets']}
        library = 'nemo-arm64/lib/libnemo_speech_asr_c.so.1'
        result.update(streaming_profile=selected['profile'], nemotron_model=str(native_root/'D1.gguf'),
            nemotron_library=str(native_root/library), nemotron_library_sha256=assets[library]['sha256'],
            native_runtime_files=[dict(path=str(native_root/name), sha256=row['sha256'])
                for name, row in sorted(assets.items()) if name.startswith('nemo-arm64/lib/')])
        if not result['native_runtime_files']:
            raise ValueError('Complete retained native library set required')
    keys = ('titanet_manifest', 'titanet_manifest_sha256', 'embedding_namespace')
    for key in keys:
        result.pop(key, None)
    if route['embedding'] == 'E1':
        if type(native_titanet_manifest) is not str:
            raise ValueError('Explicit installed TitaNet manifest required')
        path = PurePosixPath(native_titanet_manifest)
        if (str(path) != native_titanet_manifest or not path.is_relative_to(ROOT)
                or path.name != 'titanet_manifest.json' or '..' in path.parts):
            raise ValueError('Canonical local deployed TitaNet asset path required')
        manifest = strict_json(titanet_manifest_raw, 16384)
        result.update(titanet_manifest=native_titanet_manifest,
                      titanet_manifest_sha256=hashlib.sha256(titanet_manifest_raw).hexdigest(),
                      embedding_namespace=titanet_namespace(manifest))
    elif native_titanet_manifest is not None or titanet_manifest_raw is not None:
        raise ValueError('ReDimNet must not acquire a TitaNet dependency')
    return result


def desktop_entry(profile, release_id, label):
    """Prepared .desktop content only; launcher must enforce the installed profile pin."""
    select(profile)
    if type(release_id) is not str or not re.fullmatch('field-runtime-v[1-9][0-9]*', release_id):
        raise ValueError('Exact versioned release required')
    if type(label) is not str or not 1 <= len(label) <= 150 or any(c in label for c in '\r\n\\'):
        raise ValueError('Single-line desktop label required')
    executable = ROOT + '/' + release_id + '/bin/launch-profile'
    return ('[Desktop Entry]\nType=Application\nVersion=1.0\nName=Just Peachy · ' + label +
            '\nComment=Open idle; Start recording explicitly.\nExec=' + executable +
            ' --profile ' + profile + '\nTerminal=false\nCategories=AudioVideo;Audio;\n'
            'StartupNotify=true\nX-JustPeachy-CaptureOnLaunch=false\n').encode()

"""Reuse installed backend/controller/gallery bindings; README_RUNTIME_CONTROLLER_PROFILE_V1.md."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path,PurePosixPath
import stat
import textwrap

profile_definition=backend_manifest
profile_digest=digest


def selected_backend(catalog_raw, definition):
    """Recompute the actual composition from the pinned original catalogue."""
    if type(definition) is not dict or type(definition.get('selection')) is not dict:
        raise ValueError('Explicit prepared profile definition')
    expected=profile_definition(catalog_raw,definition['selection']['profile'])
    if profile_digest(expected)!=profile_digest(definition):
        raise ValueError('Profile differs from existing model/runtime implementation')
    rows=json.loads(catalog_raw)['backends']
    original=next(r for r in rows if r['key']==definition['selection']['backend_key'])
    if original['implemented'] is not True:
        raise ValueError('Original backend implementation is unavailable')
    selected=deepcopy(original)
    selected.update(key=definition['selection']['profile'],label=definition['label'],
                    manifest_id=definition['backend_manifest_id'],composition=deepcopy(definition['composition']))
    return selected


def bind_registry(module,catalog_raw,definition):
    """Fresh-process in-memory selection; original catalogue files stay unchanged."""
    selected=selected_backend(catalog_raw,definition)
    original=json.loads(catalog_raw)['backends']
    if module._BACKENDS!=original:
        raise ValueError('Previously changed backend registry')
    if module.manifest_id(selected['composition'])!=selected['manifest_id']:
        raise ValueError('Actual installed backend ID convention differs')
    rows=deepcopy(original)
    matches=[i for i,row in enumerate(rows) if row['manifest_id']==selected['manifest_id']]
    if len(matches)>1:raise ValueError('Duplicate actual backend identity')
    if matches:rows[matches[0]]=selected
    else:rows.append(selected)
    module._BACKENDS=rows
    actual=module.require_backend(selected['manifest_id'],definition['selection']['ui_mode'],'O0')
    if actual['composition']!=selected['composition']:
        raise ValueError('Actual registry consumer returned another implementation')
    return selected['manifest_id']


def specialize_factory(node,definition):
    """Retain installed Field methods, changing only the explicit profile selectors."""
    if not isinstance(node,ast.FunctionDef) or node.name!='controller_type':
        raise ValueError('Actual derived Field controller factory required')
    node=deepcopy(node);before=deepcopy(node)
    supported=[n for n in node.body if isinstance(n,ast.Assign) and len(n.targets)==1
               and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='supported']
    if len(supported)!=1 or "nemotron_hybrid" not in ast.unparse(supported[0].value):
        raise ValueError('Installed backend selector boundary changed')
    supported[0].value=ast.Constant(definition['backend_manifest_id'])
    cls=next(n for n in node.body if isinstance(n,ast.ClassDef) and n.name=='FieldController')
    methods={n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
    switch=methods['_do_switch'];text=ast.unparse(switch)
    old="('open_with_names', 'balanced', 'O0')"
    if text.count(old)!=1:raise ValueError('Installed mode/tap guard changed')
    new=repr((definition['selection']['ui_mode'],'balanced','O0'))
    replacement=ast.parse(text.replace(old,new).replace(
        'This candidate supports Open with names, Balanced and O0. Spatial and other recipes are unavailable.',
        'This shortcut pins its logical mode, Balanced and O0. Return to modes to select another profile.')).body[0]
    cls.body[cls.body.index(switch)]=replacement
    selector=methods['_do_select_backend']
    for n in ast.walk(selector):
        if isinstance(n,ast.Constant) and n.value=='This candidate supports B01. Other backends need a separately qualified launcher.':
            n.value='This process is pinned to its selected backend and embedding model. Return to modes to change it.'
    snapshot=methods['snapshot'];labels=[n for n in ast.walk(snapshot) if isinstance(n,ast.Constant) and n.value=='B01: Sherpa + Nemotron']
    if len(labels)!=1:raise ValueError('Installed backend display boundary changed')
    labels[0].value=definition['label']
    old_cls=next(n for n in before.body if isinstance(n,ast.ClassDef) and n.name=='FieldController')
    changed={'_do_switch','_do_select_backend','snapshot'}
    bodies=lambda c:{n.name:ast.dump(n,include_attributes=False) for n in c.body if isinstance(n,ast.FunctionDef) and n.name not in changed}
    if bodies(old_cls)!=bodies(cls):raise ValueError('Unrelated installed Field method changed')
    return ast.fix_missing_locations(node)


def verify_gallery(root,manifest_raw,manifest_sha256,namespace,guard):
    """Read an independently reserved immutable gallery snapshot; never convert vectors."""
    if type(manifest_raw) is not bytes or len(manifest_raw)>65536 or hashlib.sha256(manifest_raw).hexdigest()!=manifest_sha256:
        raise ValueError('Pinned bounded gallery snapshot manifest')
    document=json.loads(manifest_raw)
    if set(document)!={'schema','namespace','files','directories','reserved_bytes'} or document['schema']!='just-peachy.runtime-gallery-snapshot.v1':
        raise ValueError('Exact gallery snapshot')
    if document['namespace']!=namespace:
        raise ValueError('Gallery belongs to a different embedding/preprocessing space')
    root=Path(root).absolute()
    for parent in (root,*root.parents):
        s=parent.lstat()
        if not stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:
            raise ValueError('Real gallery snapshot path')
    files=document['files'];dirs=document['directories']
    if type(files) is not dict or len(files)>256 or type(dirs) is not list or not 1<=len(dirs)<=64 or '' not in dirs or len(set(dirs))!=len(dirs):
        raise ValueError('Finite gallery member/directory allocation')
    if type(document['reserved_bytes']) is not int or not 0<document['reserved_bytes']<=134217728:
        raise ValueError('Explicit independent gallery reservation')
    aliases=set()
    for name in list(files)+[n for n in dirs if n]:
        path=PurePosixPath(name)
        if type(name) is not str or str(path)!=name or path.is_absolute() or any(p in ('.','..') for p in path.parts) or ':' in name or '\\' in name or name.casefold() in aliases:
            raise ValueError('Portable unique gallery member')
        aliases.add(name.casefold())
        parent=path.parent.as_posix()
        if ('' if parent=='.' else parent) not in dirs:raise ValueError('Complete gallery parents')
    actual_files=set();actual_dirs={''};before={}
    for p in root.rglob('*'):
        guard();rel=p.relative_to(root).as_posix();s=p.lstat()
        if stat.S_ISLNK(s.st_mode) or getattr(s,'st_file_attributes',0)&0x400:raise ValueError('Gallery link')
        if stat.S_ISDIR(s.st_mode):actual_dirs.add(rel)
        elif stat.S_ISREG(s.st_mode) and s.st_nlink==1:
            actual_files.add(rel);before[rel]=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
        else:raise ValueError('Real gallery member')
        if len(actual_files)>256 or len(actual_dirs)>64:raise ValueError('Actual gallery cardinality')
    if actual_files!=set(files) or actual_dirs!=set(dirs):raise ValueError('Complete pinned gallery membership')
    total=len(dirs)*65536
    for name,row in files.items():
        if type(row) is not dict or set(row)!={'bytes','sha256'} or type(row['bytes']) is not int or not 0<=row['bytes']<=33554432 or before[name][2]!=row['bytes']:
            raise ValueError('Exact bounded gallery member')
        total+=row['bytes']
        if total>document['reserved_bytes']:raise ValueError('Independent gallery allocation exhausted')
        h=hashlib.sha256()
        with (root/name).open('rb') as stream:
            while True:
                guard();block=stream.read(16384)
                if not block:break
                h.update(block)
        s=(root/name).lstat()
        if h.hexdigest()!=row['sha256'] or before[name]!=(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns):
            raise ValueError('Gallery changed during verification')
    after_files=set();after_dirs={''}
    for p in root.rglob('*'):
        guard();(after_dirs if p.is_dir() else after_files).add(p.relative_to(root).as_posix())
    if after_files!=actual_files or after_dirs!=actual_dirs:raise ValueError('Gallery membership changed')
    return root


def readonly_store_type(people_module,data_root,galleries,namespace,guard):
    """Reuse the original initializer and TitaNet subclass; redirect only verified roots."""
    expected={'E0':dict(model_sha256=REDIMNET,preprocessing='mono-float32-16k-redimnet2-native-l2-v1',dimension=192,normalization='L2',minimum_samples=8000)}
    if namespace is not None:
        exact=dict(model_sha256=TITANET_MODEL,preprocessing=TITANET_PREPROCESSING,dimension=192,normalization='L2',minimum_samples=8000,onnx_sha256=TITANET_ONNX,frontend_sha256=TITANET_FRONTEND)
        if namespace!=exact:raise ValueError('Original TitaNet namespace required')
        expected['E1']=exact
    if type(galleries) is not dict or set(galleries)!=set(expected):
        raise ValueError('Separate exact required gallery namespaces')
    roots={}
    for key,descriptor in galleries.items():
        if type(descriptor) is not dict or set(descriptor)!={'root','manifest_path','manifest_sha256'}:
            raise ValueError('Pinned independent gallery descriptor')
        path=Path(descriptor['manifest_path']);info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>65536 or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('Bounded real gallery manifest')
        roots[key]=verify_gallery(descriptor['root'],path.read_bytes(),descriptor['manifest_sha256'],expected[key],guard)
    if len(set(roots.values()))!=len(roots):raise ValueError('Distinct gallery snapshot paths')
    data=Path(data_root).absolute()
    namespace_key=None if namespace is None else profile_digest(namespace)
    original=people_module.PersonalStore
    source=Path(people_module.__file__).read_bytes()
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='PersonalStore')
    node=deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__'))
    if ast.unparse(node.body[0])!='self.root = Path(root).resolve()' or ast.unparse(node.body[1])!='self.root.mkdir(parents=True, exist_ok=True)':
        raise ValueError('Actual PersonalStore constructor boundary changed')
    node.body[0]=ast.parse('self.root = _runtime_gallery_root(root, backend, self.preprocessing)').body[0]
    del node.body[1]
    def mapped(root,backend,preprocessing):
        requested=Path(root).absolute()
        if backend==REDIMNET and preprocessing==people_module.PREPROCESSING and requested==data/'people':
            return roots['E0']
        if (namespace_key is not None and backend==TITANET_MODEL and preprocessing=='titanet:'+namespace_key
                and requested==data/'embedding_spaces'/namespace_key/'people'):
            return roots['E1']
        raise ValueError('No cross-encoder root or preprocessing fallback')
    namespace_globals=dict(people_module.__dict__,_runtime_gallery_root=mapped)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                 str(people_module.__file__)+':readonly-gallery', 'exec'),namespace_globals)
    class ReadOnlyStore(original):
        __init__=namespace_globals['__init__']
    return ReadOnlyStore



def saved_input_pin(path, mode, guard):
    import stat
    import wave
    path=Path(path).absolute()
    allowed=Path.home()/'JustPeachy'
    if not path.is_relative_to(allowed) or len(str(path).encode())>1024 or path.suffix.lower()!='.wav':
        raise ValueError('Choose a prepared WAV inside JustPeachy')
    for parent in (path.parent,*path.parent.parents):
        if parent.is_symlink() or not parent.is_dir():raise ValueError('Real saved-input directory required')
    before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or not 44<before.st_size<=32*1024**2:
        raise ValueError('Bounded real saved-input file required')
    maximum={'streaming':30,'chunk52':120}.get(mode)
    if maximum is None:raise ValueError('Saved input requires Streaming or Chunk52')
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            guard();block=stream.read(16384)
            if not block:break
            h.update(block)
    with wave.open(str(path),'rb') as wavefile:
        if (wavefile.getnchannels(),wavefile.getframerate(),wavefile.getsampwidth(),wavefile.getcomptype())!=(1,16000,2,'NONE'):
            raise ValueError('Prepared mono16k PCM16 WAV required; no implicit resampling or gain')
        frames=wavefile.getnframes()
        if not 0<frames<=maximum*16000:raise ValueError('Saved file exceeds this mode time budget')
    after=path.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns')
    identity={key:int(getattr(before,key)) for key in fields}
    if identity!={key:int(getattr(after,key)) for key in fields}:raise RuntimeError('Saved input changed while verified')
    return dict(path=str(path),identity=identity,sha256=h.hexdigest(),samples=frames,
        sample_rate=16000,channels=1,format='PCM16',gain=1,mode=mode,maximum_seconds=maximum)


def saved_source_type(pipeline, get_pin, mode, guard, outputs, request_stop):
    """Wrap the actual installed paced FileSource; never open microphone hardware."""
    original=pipeline.FileSource
    class CheckedSavedSource(original):
        def __init__(self,journal,path,status_callback,*,start_sample=0,maximum_seconds=3600):
            selected=get_pin()
            if selected is None or start_sample!=0 or saved_input_pin(path,mode,guard)!=selected:
                raise ValueError('Saved source differs from explicit Start input')
            self.input_pin=selected;self.error=None;self.integrity=None;self.stop_receipt=None
            self._saved_done=threading.Event();self._saved_closed=False
            def callback(kind,value):
                if kind=='fatal':self.error=str(value.get('reason','Saved input failed'))
                if kind=='source_started':value=dict(value,input_sha256=selected['sha256'],input_samples=selected['samples'],input_identity=selected['identity'],physical_microphone=False)
                return status_callback(kind,value)
            super().__init__(journal,path,callback,start_sample=0,maximum_seconds=selected['maximum_seconds'])

        def _run(self):
            try:
                super()._run()
                if saved_input_pin(self.path,mode,guard)!=self.input_pin:
                    raise RuntimeError('Saved source identity/hash changed during processing')
                if self.error:raise RuntimeError(self.error)
                self._saved_closed=True
                outputs.source('BRIDGE_CLOSE.json',dict(schema='just-peachy.saved-source-eof.v1',
                    input_sha256=self.input_pin['sha256'],input_samples=self.input_pin['samples'],
                    source_samples=self.sent,complete_input=self.sent==self.input_pin['samples'],
                    file_context_closed=True,physical_microphone=False,child_process_created=False))
            except BaseException as exc:
                self.error=type(exc).__name__+': '+str(exc)[:512]
                request_stop(self.error)
                self.journal.finish(self.error)
                self.callback('fatal',dict(reason=self.error))
            finally:self._saved_done.set()

        def stop(self):
            if self.stop_receipt is not None:return self.stop_receipt
            super().stop()
            joined=self.thread is not None and not self.thread.is_alive()
            okay=joined and self._saved_done.is_set() and self._saved_closed and self.error is None
            self.integrity=dict(ok=okay,reasons=[] if okay else [self.error or 'SAVED_SOURCE_NOT_CLOSED'],
                source_samples=self.sent,journal_samples=self.sent,input_samples=self.input_pin['samples'],
                complete_input=self.sent==self.input_pin['samples'],physical_microphone=False)
            self.stop_receipt=dict(schema='just-peachy.saved-source-closure.v1',source_kind='file',
                input=self.input_pin,file_context_closed=self._saved_closed,thread_joined=joined,
                physical_microphone=False,child_process_created=False,integrity=self.integrity)
            outputs.source('BRIDGE_STOP.json',self.stop_receipt)
            if not okay:
                request_stop('Saved source did not close')
                raise RuntimeError('Saved source did not close: '+str(self.error))
            return self.stop_receipt
    return CheckedSavedSource


def bind_titanet_memory(module, adapter):
    raw=adapter.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='b765ec7cfd725a39f8d1542e76eeb71fcdc083989b421269fea119606afc6caa':
        raise ValueError('Exact original TitaNet adapter required')
    cls=module.TitanetEmbedding
    if Path(cls.__init__.__code__.co_filename).resolve()!=adapter or getattr(cls,'_delivery_memory_bound',False):
        raise ValueError('Original one-time TitaNet constructor required')
    tree=ast.parse(raw)
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='TitanetEmbedding')
    constructor=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    text=ast.unparse(constructor)
    marker='options = ort.SessionOptions()'
    if text.count(marker)!=1:raise ValueError('Exact TitaNet session options site')
    text=text.replace(marker,marker+'\n    options.enable_cpu_mem_arena = False\n    options.enable_mem_pattern = False')
    namespace=dict(module.__dict__)
    exec(compile(text,'<field-runtime:titanet-memory-v1>','exec'),namespace)
    original_init=namespace['__init__'];original_embed=cls.embed
    def initialize(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        options=self._session.get_session_options()
        if options.enable_cpu_mem_arena or options.enable_mem_pattern or options.intra_op_num_threads!=1 or options.inter_op_num_threads!=1:
            raise RuntimeError('Actual TitaNet memory/thread settings differ')
        self.runtime_memory_policy=dict(schema='just-peachy.titanet-memory.v1',
            adapter_sha256=hashlib.sha256(raw).hexdigest(),constructor_sha256=hashlib.sha256(text.encode()).hexdigest(),
            cpu_mem_arena=options.enable_cpu_mem_arena,mem_pattern=options.enable_mem_pattern,
            intra_threads=options.intra_op_num_threads,inter_threads=options.inter_op_num_threads,
            successful_embeddings=0)
    def embed(self,*args,**kwargs):
        result=original_embed(self,*args,**kwargs)
        self.runtime_memory_policy['successful_embeddings']+=1
        return result
    cls.__init__=initialize;cls.embed=embed;cls._delivery_memory_bound=True

import base64
import json
import zlib

def terminal_encode(value, limit):
    if type(limit) is not int or limit != 32768:
        raise ValueError('Exact terminal primary slot')
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode()
    if len(raw) > 262144:
        raise ValueError('Terminal decoded metadata bound')
    if len(raw) <= limit:
        return raw
    packed = dict(schema='just-peachy.terminal-config-zlib.v1', encoding='zlib-base64', decoded_bytes=len(raw), decoded_sha256=hashlib.sha256(raw).hexdigest(), data=base64.b64encode(zlib.compress(raw, 6)).decode())
    encoded = (json.dumps(packed, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if len(encoded) > limit:
        raise ValueError('Terminal physical slot exhausted')
    restored = (json.dumps(decode_terminal(encoded), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False) + '\n').encode()
    if restored != raw:
        raise ValueError('Terminal independent codec readback')
    return encoded

def decode_terminal(raw):
    if type(raw) is not bytes or len(raw) > 32768:
        raise ValueError('Bounded terminal input')

    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError('Duplicate terminal key')
            value[key] = item
        return value

    def bad(value):
        raise ValueError('Nonfinite terminal JSON')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    if type(value) is not dict:
        raise ValueError('Terminal object')
    if value.get('schema') != 'just-peachy.terminal-config-zlib.v1':
        return value
    if set(value) != {'schema', 'encoding', 'decoded_bytes', 'decoded_sha256', 'data'} or value['encoding'] != 'zlib-base64':
        raise ValueError('Exact terminal compressed envelope')
    size = value['decoded_bytes']
    if type(size) is not int or not 32768 < size <= 262144:
        raise ValueError('Decoded terminal bound')
    compressed = base64.b64decode(value['data'], validate=True)
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(compressed, size + 1)
    if len(decoded) != size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        raise ValueError('Exact complete bounded terminal stream')
    if hashlib.sha256(decoded).hexdigest() != value['decoded_sha256']:
        raise ValueError('Terminal digest mismatch')
    result = json.loads(decoded, object_pairs_hook=pairs, parse_constant=bad)
    if type(result) is not dict:
        raise ValueError('Decoded terminal object')
    return result

_MOUNTED_CONFIG_SHA='e17ea820ca7a960d71a6c82b649b7901293574e7771d49fc82c90bb3a3a5eaab'
_MOUNTED_SOURCES={'imu.py': {'bytes': 18555, 'sha256': 'fffb626d199ac0ffaf332745cd10747cce74194dc05893d65b5fc201c2da1b64', 'original_sha256': '8306f82cc88a1f7358109df2e37decff6ccfe421f153a2362d60984ae335ea19', 'compressed': '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'}, 'live_spatial.py': {'bytes': 18268, 'sha256': '1216634ef7642392d952151a788e396c4906ede43f07147e0661f52a88ed34eb', 'original_sha256': '1ca3c5a9384505419c935e2711c8864f38c35b1afba111750a97bfea2eecc4f3', 'compressed': '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'}}

def _bind_mounted_runtime(base, manifest):
    import base64, zlib, hashlib
    from app import imu as imu_module, live_spatial as spatial_module
    from app import seats as seats_module
    for module, relative in ((imu_module,'app/imu.py'),(spatial_module,'app/live_spatial.py'),
                              (seats_module,'app/seats.py')):
        if Path(module.__file__).resolve()!=base/relative or sha(base/relative)!=manifest[relative]['sha256']:
            raise ValueError('Pinned installed motion source required')
    bound={}
    for name, module in (('imu.py',imu_module),('live_spatial.py',spatial_module)):
        item=_MOUNTED_SOURCES[name]
        if sha(base/'app'/name)!=item['original_sha256']:
            raise ValueError('Reviewed motion derivation input changed')
        data=zlib.decompress(base64.b64decode(item['compressed'],validate=True))
        if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise ValueError('Embedded motion derivative changed')
        namespace=dict(module.__dict__)
        exec(compile(data,'<mounted-runtime:'+name+'>','exec'),namespace)
        bound[name]=namespace
    spatial_module.LiveSpatialProvider=bound['live_spatial.py']['LiveSpatialProvider']
    # Seat modes inherit the same display/reference split. Their existing
    # assignment, invalidation and voice rules remain in the installed class.
    # Preserve SeatSpatialProvider.snapshot's seat validity/warning extension.
    seats_module.LiveSpatialProvider.snapshot=spatial_module.LiveSpatialProvider.snapshot
    config_path=Path('/home/peachyprototype/JustPeachy/data/imu_config.json')
    if config_path.is_symlink() or config_path.stat().st_size>4096 or sha(config_path)!=_MOUNTED_CONFIG_SHA:
        raise ValueError('Confirmed mounted sensor configuration changed')
    config=json.loads(config_path.read_bytes())
    library=Path(config['library'])
    if library!=Path('/home/peachyprototype/JustPeachy/tools/bmi270/libpeachy_bmi270.so') or library.is_symlink() or library.stat().st_size!=142264 or sha(library)!='d1eb90a5a4f1f98674e6483bda7711ed7df610fe0fe5bef7845de580b7ce7e28':
        raise ValueError('Existing native BMI270 library changed')
    if not config['fixed_mount'] or not config['rotation_compensation']:
        raise ValueError('Confirmed fixed mount and rotation assistance required')
    class ExistingIMULease:
        def __init__(self,path):
            self.path=Path(path);self.handle=None
        def acquire(self):
            import fcntl,stat
            if self.path!=Path('/home/peachyprototype/JustPeachy/data/imu.lock') or self.path.is_symlink() or not stat.S_ISREG(self.path.stat().st_mode):
                raise ValueError('Existing exact IMU lease required')
            handle=self.path.open('rb')
            try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BaseException:handle.close();raise
            self.handle=handle;return self
        def close(self):
            import fcntl
            if self.handle is not None:
                try:fcntl.flock(self.handle,fcntl.LOCK_UN)
                finally:self.handle.close();self.handle=None
    bound['imu.py']['DeviceLease']=ExistingIMULease
    return bound['imu.py']['BMI270Worker'],config

