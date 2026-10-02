"""Pinned TitaNet allocator derivation; see README_RUNTIME_TITANET_MEMORY_V1.md."""
import ast
import base64
import hashlib
import json

INPUT_SHA='b0422b395e4dedb01342c514a9d1ca23e5bb681c857dc125a97097aff4102b2a'
ADAPTER_SHA='b765ec7cfd725a39f8d1542e76eeb71fcdc083989b421269fea119606afc6caa'

HELPER='''

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
    text=text.replace(marker,marker+'\\n    options.enable_cpu_mem_arena = False\\n    options.enable_mem_pattern = False')
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
'''


def derive(raw):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:
        raise ValueError('Exact saved-modes3 capsule required')
    value=json.loads(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    if value['manifest']['files']!=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]:
        raise ValueError('Complete original capsule hashes')
    old=dict(files)
    name='code/field_operator_controller_v6.py';s=files[name].decode()
    marker="            raise ValueError('Original installed TitaNet adapter origin/pin')"
    if s.count(marker)!=1:raise ValueError('Exact controller adapter binding')
    s=s.replace(marker,marker+'\n        bind_titanet_memory(titanet_embedding,adapter)')+HELPER
    files[name]=s.encode()
    name='code/field_operator_entry_v11.py';s=files[name].decode()
    marker="        receipts.json('MODEL_CLOSURE.json',state)"
    if s.count(marker)!=1:raise ValueError('Exact actual model receipt site')
    s=s.replace(marker,"""        if context['runtime_profile']['selection']['embedding']=='E1':
            speaker=getattr(controller.models,'speakers',None)
            encoder=getattr(speaker,'encoder',None)
            result['embedding_runtime']=None if encoder is None else dict(encoder.runtime_memory_policy)
        receipts.json('MODEL_CLOSURE.json',state)""")
    files[name]=s.encode()
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule bounds')
    for n,b in code.items():
        if n.endswith('.py'):compile(b,n,'exec')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(packed)>1048576:raise ValueError('Original packed cap')
    return packed,dict(status='PREPARED_TITANET_ORT_ARENA_DISABLED',bundle_sha256=sha(packed),
        changed={n:dict(before_sha256=sha(old[n]),sha256=sha(b),bytes=len(b)) for n,b in files.items() if b!=old[n]},
        original_model_frontend_embed_unchanged=True,hard_address_space_bytes=805306368,native_executed=False)
