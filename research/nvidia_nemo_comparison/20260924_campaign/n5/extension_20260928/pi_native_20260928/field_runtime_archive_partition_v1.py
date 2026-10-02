"""Archive initial/runtime partition; README_RUNTIME_ARCHIVE_PARTITION_V1.md."""
import ast,base64,hashlib,json
INPUT_SHA='8151e9c553ebd332d94546cbd911c6930d699ce533e266a235e17b9b063e9fea'
MEMBER_SHA='1f0e1ac380529013d2cfec078dce759e217def842a58258a352fdbf628e3f9e1'

def derive(raw):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:raise ValueError('Exact backed common capsule')
    value=json.loads(raw);files={n:base64.b64decode(s,validate=True) for n,s in value['files'].items()}
    if [dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]!=value['manifest']['files']:raise ValueError('Complete member hashes')
    path='code/field_archive_budget_v4.py';prior=files[path]
    if sha(prior)!=MEMBER_SHA:raise ValueError('Exact compact archive budget source')
    old='initial_control_bytes=32768';new='initial_control_bytes=39936'
    if prior.decode().count(old)!=1:raise ValueError('Exact initial partition')
    changed=prior.decode().replace(old,new)
    before=ast.parse(prior);after=ast.parse(changed)
    bodies=lambda t:[ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
    if bodies(before)!=bodies(after) or changed.replace(new,old)!=prior.decode():raise ValueError('All validators/writers and other source unchanged')
    compile(changed,path,'exec');files[path]=changed.encode()
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):raise ValueError('Original member allocation')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(packed)>1048576:raise ValueError('Original packed capsule cap')
    return packed,dict(status='PREPARED_EXPLICIT_CONTROL_PARTITION',changed_member=path,bundle_sha256=sha(packed),old_member_sha256=sha(prior),new_member_sha256=sha(files[path]),
        old_initial_bytes=32768,initial_bytes=39936,runtime_reserved_bytes=24576,join_reserve_bytes=1024,complete_file_bytes=65536,
        original_file_and_pending_bounds_unchanged=True,fields_dropped=False,native_executed=False)
