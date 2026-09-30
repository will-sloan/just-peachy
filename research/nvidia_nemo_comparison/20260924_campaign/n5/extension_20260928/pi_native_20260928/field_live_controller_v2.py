"""Compose the actual field controller; README_FIELD_LIVE_D1_V1.md."""
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
COMMANDS = frozenset(('select_backend','switch','start_live','stop','close','session_action'))


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
    from field_live_layout_v3 import finite_json
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
                raw=encode_control(value,32768);finite_json(raw)
                if shutil.disk_usage(data).free<5*1024**3+len(raw):
                    raise OSError('Pi free floor')
                return publish(path,value,32768)
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
    from field_live_source_outputs_v1 import load,bounded_json
    cfg,admission,outputs=load(config_path)
    base=Path(cfg['prototype']);root=Path(cfg['output_root']);data=root/'data'
    if sha(base/'RELEASE_MANIFEST.json')!=BASE_MANIFEST:
        raise ValueError('Exact installed v12 manifest required')
    manifest={r['path']:r for r in bounded_json(base/'RELEASE_MANIFEST.json',1024**2)['files']}
    pins={r['path']:r for r in admission['files']}
    code=Path(__file__).resolve().parent
    required=('field_live_controller_v2.py','field_live_d1_v1.py','d1_modes_v1.py','d1_endpoint_contract_v3.py','d1_method_controls_v1.py','archive_stop_sessions_v1.py','field_controller_stop_v1.py',
              'field_archive_stop_v1.py','field_archive_budget_v4.py','field_native_binding_v1.py',
              'field_native_text_v2.py','isolated_pipeline_source_v5.py')
    for name in required:
        path=code/name
        if str(path) not in pins or sha(path)!=pins[str(path)]['sha256']:
            raise ValueError('Required composition source not admitted: '+name)
    if data.resolve()!=data or data.is_symlink():
        raise ValueError('Real data root required')
    for name in ('people','sessions','conversations'):
        path=data/name
        if not path.is_dir() or path.is_symlink() or any(path.iterdir()):
            raise ValueError('This first live integration requires empty private '+name)
    # Additional private features are excluded before any application constructor.
    if {p.name for p in data.iterdir()}-{'people','sessions','conversations','live_config.json','settings.json','n2_runtime.json','DATA_SCHEMA.json'}:
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
    import isolated_pipeline_source_v5 as source_module
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
    cm.atomic_json=paths.atomic_json=text_assistance.atomic_json=writer
    policy=dict(archive_budget=budget,artifact_limits=limits,quota_mib=512,free_floor_mib=5120,record_bytes=65536)
    Required=controller_class(cm,sessions,outputs,policy,manifest['app/controller.py']['sha256'])
    Store=store_class(installed_store,sessions,outputs,owner,budget)
    sessions.EpochArchive=archive_class(sessions.EpochArchive,outputs,owner.stop)

    def live_config(controller,Config):
        if controller.source_kind!='live' or controller.epoch!=1:
            raise ValueError('Exactly one live epoch is admitted')
        current,_,_=load(config_path)
        if current!=cfg:raise ValueError('Source binding changed before Start')
        return Config(Path(config_path),base)
    original,node=derive_field(Path(entry.__file__).read_bytes())
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
            self._delivery_attempted=False
            super().__init__(*args,**kwargs)

        def _delivery_command(self,action,args,kwargs):
            if action not in COMMANDS:
                raise ValueError('Action unavailable in this bounded live integration')
            if action in ('select_backend','switch') and self._delivery_attempted:
                raise ValueError('Return to a fresh process to change runtime/mode')
            if action=='session_action' and (not args or args[0] not in ('save','open')):
                raise ValueError('Only Save and Open are admitted here; transfer/playback/delete are unavailable')

        def _start_session(self):
            if self._delivery_attempted or self.source_kind!='live':
                raise ValueError('One live recording attempt per fresh process')
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
                save_open_available=True,interchange_available=False,delete_available=False,
                physical_touch_qualified=False,field_release_accepted=False)
            return value

    native=NativeOwner(data/'sessions',outputs,owner.stop)
    bind_native(pipeline,runtime,research_s7,native,
                {key:manifest[rel]['sha256'] for key,rel in
                 (('pipeline','app/pipeline.py'),('runtime','vendor/edge_speech_pipeline/runtime.py'),
                  ('trace','vendor/edge_speech_pipeline/research_s7.py'))})
    from field_live_d1_v1 import bind as bind_d1
    from d1_method_controls_v1 import MethodCatalog
    binding=admission.get('d1_binding',{})
    if set(binding)!={'mode','campaign','method_contract','method_evidence','maximum_samples'}:
        raise ValueError('Explicit admitted live D1 method binding required')
    if binding['mode']!='delayed' or type(binding['maximum_samples']) is not int or binding['maximum_samples']!=2080000:
        raise ValueError('Only the selected bounded delayed live method is admitted')
    if Path(binding['campaign']).resolve()!=root.parent:
        raise ValueError('Live D1 campaign root mismatch')
    if Path(binding['method_contract'])!=code/'D1_METHOD_CONTRACT_V1.json':
        raise ValueError('Method contract must use the admitted code capsule')
    for path in (Path(binding['method_contract']),Path(binding['method_evidence']),
                 code/'D1_MODE_CATALOG_V1.json',code/'D1_ENDPOINT_CONTRACT_V3.json'):
        if str(path) not in pins or sha(path)!=pins[str(path)]['sha256']:
            raise ValueError('D1 method/catalogue/endpoint evidence is not admitted')
    catalog=MethodCatalog(binding['method_contract'],binding['method_evidence'])
    d1_state=bind_d1(base,Path(binding['campaign']),manifest,
                     bounded_json(data/'n2_runtime.json'),catalog,outputs,owner.stop)
    controller=DeliveryController(data,Path(contract['models_root']),saved_audio_only=False)
    try:
        controller.config=replace(controller.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        controller.select_backend(backend);controller.commands.join()
        if controller.error:raise RuntimeError(controller.error)
        controller.switch(mode='open_with_names',recipe='balanced',tap='O0');controller.commands.join()
        if controller.error or owner.early_failure:raise RuntimeError(controller.error or owner.early_failure)
        origins=verify_loaded()
    except BaseException:
        if not controller.closed:controller.close()
        controller.commands.join();controller.worker.join(10)
        if controller.worker.is_alive():raise RuntimeError('Controller construction cleanup remains owned')
        raise
    return controller,dict(native_owner=native,outputs=outputs,configuration=writer,
                           installed_origins=origins,source_binding=cfg,admission=admission,
                           d1_binding=d1_state,runtime_accepted=False)
