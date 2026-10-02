"""Full-pipeline saved inputs; see README_RUNTIME_SAVED_MODES_V3.md."""
import ast
import base64
import hashlib
import json

INPUT_SHA = '53283ec24117bd22c028151786c694ba76de502c62b65a68886f2c35a3bb7373'
ENDPOINT_PINS = {
    'streaming': (1, '74a46898b7c99f920821d763cad29e9fb037cdaa01b6eb4e092d70661a1b4b7d', '34f7971469307436ecb7ffbda3785ed6a4c79720abab777c95ad91fc30fc776c'),
    'chunk52': (2, '01d5d528225d8bef8a734d76945bb03b99bd819339694aa35c5af1b57a4580d5', 'd6aea07355940995d36c81584cd82a0eabd7a95149a94a0eb456cc3269ab3f74'),
    'delayed': (3, 'f7c44e2653b22ed05a9273ab6759d8d51846fd4d146ecc462d32468c5fa3315e', 'd6b4c142c21c32407f0f7bf7ace554d9f33fcfe0ffbf843ca40a85a85637aaea'),
}


def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Exact saved-source boundary changed: '+old[:110])
    return s.replace(old, new)


# Appended to the already pinned controller member; no extra capsule module.
SAVED_HELPERS = r'''

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
'''


def endpoint_members(sources, contracts):
    if set(sources)!=set(ENDPOINT_PINS) or set(contracts)!=set(ENDPOINT_PINS):
        raise ValueError('All three retained endpoint bindings required')
    result='import hashlib\nimport json\nimport base64\nfrom pathlib import Path\n\n'
    raw_contracts={}
    for mode,(version,source_sha,contract_sha) in ENDPOINT_PINS.items():
        source=sources[mode];raw=contracts[mode]
        if hashlib.sha256(source).hexdigest()!=source_sha or hashlib.sha256(raw).hexdigest()!=contract_sha:
            raise ValueError('Retained endpoint source/contract changed')
        raw_contracts[mode]=base64.b64encode(raw).decode()
        text=source.decode();tree=ast.parse(text)
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify_binding')
        body=ast.get_source_segment(text,node)
        body=once(body,'def verify_binding(campaign, mode):','def verify_'+mode+'(campaign, mode):')
        body=once(body,"raw = Path(__file__).with_name('D1_ENDPOINT_CONTRACT_V"+str(version)+".json').read_bytes()",
            "container=json.loads(Path(__file__).with_name('D1_ENDPOINT_CONTRACT_V3.json').read_bytes())\n    if set(container)!={'streaming','chunk52','delayed'}:raise ValueError('Exact endpoint contract set')\n    raw=base64.b64decode(container[mode],validate=True)")
        body=body.replace('CONTRACT_SHA256',repr(contract_sha))
        result+=body+'\n\n'
    result+="def verify_binding(campaign, mode):\n    callbacks={'streaming':verify_streaming,'chunk52':verify_chunk52,'delayed':verify_delayed}\n    if mode not in callbacks:raise ValueError('Exact supported mode')\n    return callbacks[mode](campaign,mode)\n"
    compile(result,'d1_endpoint_contract_v3.py','exec')
    return result.encode(),json.dumps(raw_contracts,sort_keys=True,separators=(',',':')).encode()


def derive(raw, endpoint_sources, endpoint_contracts):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:
        raise ValueError('Exact optional-recording capsule required')
    value=json.loads(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    if value['manifest']['files']!=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]:
        raise ValueError('Complete original capsule hashes')
    old=dict(files)
    def change(name,fn):
        name='code/'+name;s=fn(files[name].decode());compile(s,name,'exec');files[name]=s.encode()

    def controller(s):
        s=once(s,"'switch','start_live','stop'","'switch','start_live','start_file','stop'")
        s=once(s,"    if selection['input_kind']!='microphone':\n        raise ValueError('Saved-input profiles require their saved source integration')",
            "    if selection['input_kind'] not in ('microphone','saved'):raise ValueError('Exact input route')\n    if selection['input_kind']=='saved' and selection['engine_mode'] not in ('streaming','chunk52'):raise ValueError('Exact saved mode')")
        s=once(s,"            if action in ('select_backend','switch') and self._delivery_attempted:",
            """            if action in ('start_live','start_file'):
                expected='start_file' if selection['input_kind']=='saved' else 'start_live'
                if action!=expected or self._delivery_attempted:raise ValueError('Source route/one Start attempt')
                if action=='start_file':
                    if len(args)!=1 or kwargs:raise ValueError('One explicit prepared input path')
                    if not self._delivery_new_requested:raise ValueError('Choose recording before Start')
                    self._saved_pin=saved_input_pin(args[0],selection['engine_mode'],profile_guard)
                    outputs.source('SOURCE_START.json',dict(schema='just-peachy.saved-source-start.v1',input=self._saved_pin,physical_microphone=False))
            if action in ('select_backend','switch') and self._delivery_attempted:""")
        s=once(s,"            if self._delivery_attempted or self.source_kind!='live':",
            "            expected_kind='file' if selection['input_kind']=='saved' else 'live'\n            if self._delivery_attempted or self.source_kind!=expected_kind:")
        s=once(s,"if binding['mode']!='delayed' or type(binding['maximum_samples'])",
            "if binding['mode']!=selection['engine_mode'] or type(binding['maximum_samples'])")
        s=once(s,"bounded_json(data/'n2_runtime.json'),catalog,outputs,owner.stop)",
            "bounded_json(data/'n2_runtime.json'),catalog,outputs,owner.stop,mode=selection['engine_mode'])")
        s=once(s,"    controller=DeliveryController(data,Path(contract['models_root']),saved_audio_only=False)",
            """    if selection['input_kind']=='saved':
        pipeline.FileSource=saved_source_type(pipeline,lambda:getattr(owner.controller,'_saved_pin',None),
            selection['engine_mode'],profile_guard,outputs,owner.stop)
    controller=DeliveryController(data,Path(contract['models_root']),saved_audio_only=selection['input_kind']=='saved')""")
        s=once(s,"save_open_available=True,interchange_available=True,delete_available=True,",
            "save_open_available=True,interchange_available=True,delete_available=True,\n                input_kind=selection['input_kind'],maximum_input_seconds=30 if selection['engine_mode']=='streaming' else 120,")
        return s+SAVED_HELPERS
    change('field_operator_controller_v6.py',controller)

    def d1(s):
        s=once(s,'def bind(base, campaign, manifest, runtime_document, catalog, outputs, request_stop):',
            "def bind(base, campaign, manifest, runtime_document, catalog, outputs, request_stop, *, mode='delayed'):")
        s=once(s,'    global _installed',
            "    global _installed\n    if mode not in ('streaming','chunk52','delayed'):raise ValueError('Explicit supported D1 mode')\n    MODE=mode\n    PROFILE={'delayed':'native_v3_delayed','streaming':'native_v3_streaming','chunk52':'native_cm5_chunk52'}[mode]")
        s=once(s,"if method['resources']['executable_graph_lru'] != 1 or method['resources']['metadata_arena_mib'] != 2:",
            "if method['resources']['executable_graph_lru'] != (1 if MODE=='delayed' else 8) or (MODE=='delayed' and method['resources']['metadata_arena_mib'] != 2):")
        return s
    change('field_live_d1_v1.py',d1)
    files['code/d1_endpoint_contract_v3.py'],files['code/D1_ENDPOINT_CONTRACT_V3.json']=endpoint_members(endpoint_sources,endpoint_contracts)

    def parent(s):
        s=once(s,"a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION' or a['capture'] is not True:",
            "a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION' or a['capture'] is not (a['runtime_profile']['definition']['selection']['input_kind']=='microphone'):")
        s=once(s,"profile['input_kind']!='microphone'","profile['input_kind'] not in ('microphone','saved')")
        s=once(s,"binding['mode']!='delayed'","binding['mode']!=profile['engine_mode']")
        s=once(s,"registry.request('delayed',Path(broker['root']).name+'-'+broker['slot'])['mode']!='delayed'",
            "registry.request(profile['engine_mode'],Path(broker['root']).name+'-'+broker['slot'])['mode']!=profile['engine_mode']")
        return s
    change('field_operator_parent_v13.py',parent)

    def stage(s):
        s=once(s,"cfg=dict(schema='just-peachy.live-source.v1',capture=True,",
            "cfg=dict(schema='just-peachy.live-source.v1',capture=a['capture'],")
        return s
    change('field_operator_broker_stage_v5.py',stage)

    def outputs(s):
        s=once(s,"if cfg['capture'] is not True or cfg['quiet_only'] is not False:",
            "if type(cfg['capture']) is not bool or cfg['quiet_only'] is not False:")
        s=once(s,"    admission = bounded_json(cfg['admission_path'])",
            """    admission = bounded_json(cfg['admission_path'])
    selection=admission['runtime_profile']['definition']['selection']
    expected_capture=selection['input_kind']=='microphone'
    if selection['input_kind'] not in ('microphone','saved') or cfg['capture'] is not expected_capture or admission['capture'] is not expected_capture:
        raise ValueError('Actual input route/capture flag differs')
    if not expected_capture and role in ('child','source'):raise ValueError('Saved inputs cannot spawn microphone transport')""")
        s=once(s,"if admission['capture'] is not True or type(admission['maximum_active_children'])",
            "if type(admission['capture']) is not bool or type(admission['maximum_active_children'])")
        return s
    change('field_live_source_outputs_v6.py',outputs)

    def entry(s):
        s=once(s,"a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION' or a['capture'] is not True:",
            "a['scope']!='OPERATOR_LIVE_DATA_COMPOSITION' or a['capture'] is not (a['runtime_profile']['definition']['selection']['input_kind']=='microphone'):")
        s=once(s,"actual_capture_started=observed_start,actions=context['actions'].completed,",
            "actual_source_started=observed_start,actual_capture_started=observed_start and a['capture'],source_kind='live' if a['capture'] else 'file',actions=context['actions'].completed,")
        s=once(s,"result.get('actual_capture_started') and state['schema']",
            "result.get('actual_source_started') and state['schema']")
        return s
    change('field_operator_entry_v11.py',entry)

    def ledger(s):
        oldblock="""        if result.get('actual_capture_started'):
            source=read(root/'source/CHILD_OWNER.json')
            if source['boot_id']==self.policy['boot_id'] and ticks(source['pid'])==source['start_ticks']:
                raise RuntimeError('Source remains alive')
            stop=read(root/'receipts/GUI_STOP.json');model=read(root/'receipts/MODEL_CLOSURE.json')"""
        newblock="""        if result.get('actual_source_started'):
            if result.get('actual_capture_started'):
                source=read(root/'source/CHILD_OWNER.json')
                if source['boot_id']==self.policy['boot_id'] and ticks(source['pid'])==source['start_ticks']:
                    raise RuntimeError('Source remains alive')
            elif result.get('source_kind')!='file' or not self.policy['profile'].endswith('-saved'):
                raise RuntimeError('Exact saved source identity required')
            stop=read(root/'receipts/GUI_STOP.json');model=read(root/'receipts/MODEL_CLOSURE.json')
            if not result.get('actual_capture_started'):
                receipt=stop['stop_receipt']
                if (receipt.get('schema')!='just-peachy.saved-source-closure.v1' or receipt.get('physical_microphone') is not False
                    or receipt.get('child_process_created') is not False or not receipt['file_context_closed']
                    or not receipt['thread_joined'] or not receipt['integrity']['ok']):
                    raise RuntimeError('Actual saved file closure required')"""
        s=once(s,oldblock,newblock)
        s=once(s,"        if result.get('actual_capture_started'):\n            names+=['source/CHILD_OWNER.json','receipts/GUI_STOP.json','receipts/MODEL_CLOSURE.json']",
            "        if result.get('actual_source_started'):\n            names+=['receipts/GUI_STOP.json','receipts/MODEL_CLOSURE.json']\n            if result.get('actual_capture_started'):names+=['source/CHILD_OWNER.json']\n            else:names+=['source/SOURCE_START.json','source/BRIDGE_STOP.json']")
        return s
    change('field_operator_session_ledger_v4.py',ledger)

    def ui(s):
        s=once(s,"'session_action','start_live','stop'","'session_action','start_live','start_file','stop'")
        s=once(s,'            return super().toggle_listening()',"""            if context['runtime_profile']['selection']['input_kind']=='saved':
                if self._running():return self._call('stop')
                maximum=30 if context['runtime_profile']['selection']['engine_mode']=='streaming' else 120
                return self.keyboard('Prepared mono16k PCM16 WAV (up to '+str(maximum)+'s)',
                    str(Path.home()/'JustPeachy/data/'),self._start_saved_file,cancel=self.home)
            return super().toggle_listening()""")
        s=once(s,'        def toggle_listening(self):',"        def _start_saved_file(self,path):\n            if self._call('start_file',path):self.home()\n\n        def toggle_listening(self):")
        return s
    change('field_operator_ui_v1.py',ui)
    def chooser(s):
        s=once(s,"        tk.Label(self.root,text='Nemotron-3 Diarizer'","        profile=broker.ledger.policy['profile']\n        mode='Streaming' if 'streaming' in profile else 'Chunk52' if 'chunk52' in profile else 'Delayed'\n        diarizer='Nemotron-3 '+mode if profile.startswith('d1-') else 'Baseline diarization'\n        embedding='TitaNet' if 'titanet' in profile else 'Anonymous' if profile.endswith('-anonymous') else 'ReDimNet'\n        self.input_kind='WAV' if profile.endswith('-saved') else 'microphone'\n        tk.Label(self.root,text=diarizer+' / '+embedding")
        s=once(s,"text='New recording / Delayed'","text='Open '+mode+' / WAV' if self.input_kind=='WAV' else 'New microphone recording'")
        s=once(s,"for label in ('Streaming / live unavailable','Chunk 52 / live unavailable'):","for label in ('Input: prepared WAV only; microphone stays off',) if self.input_kind=='WAV' else ('Input: processed microphone',):")
        return s
    change('field_operator_chooser_v3.py',chooser)
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule size/allocation')
    for n,b in code.items():
        if n.endswith('.py'):compile(b,n,'exec')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(packed)>1048576:raise ValueError('Original packed capsule cap')
    return packed,dict(status='PREPARED_FULL_PIPELINE_SAVED_MODES',bundle_sha256=sha(packed),
        changed={n:dict(before_sha256=sha(old[n]),sha256=sha(b),bytes=len(b)) for n,b in files.items() if b!=old[n]},
        modes=['streaming','chunk52'],embeddings=['E0','E1'],maximum_seconds=dict(streaming=30,chunk52=120),
        original_allocations_unchanged=True,native_executed=False)

