"""Repair the completed STARTED reader in the existing capsule; README_RUNTIME_START_BARRIER_V1.md."""
import ast,base64,hashlib,json
INPUT_SHA='4ec6d0f422bffbcbf85365b39707b6f0942625aeed2989e697f529b5bb051eae'
OLD="    while not path.exists():\n        check()\n        if ticks(binding['manager_owner']['pid'])!=binding['manager_owner']['start_ticks']:\n            raise RuntimeError('Manager disappeared before actual STARTED')\n        if time.monotonic()>=end:raise TimeoutError('Manager durable Start acknowledgment')\n        time.sleep(.01)\n    row=read(path,16384)"
NEW="    import stat\n    pending=path.with_name(path.name+'.pending')\n    while True:\n        check()\n        if ticks(binding['manager_owner']['pid'])!=binding['manager_owner']['start_ticks']:\n            raise RuntimeError('Manager disappeared before actual STARTED')\n        if path.exists():\n            observed=path.lstat()\n            if not stat.S_ISREG(observed.st_mode) or observed.st_size>16384:\n                raise ValueError('Bounded regular STARTED publication required')\n            if observed.st_nlink==1 and not pending.exists():break\n            if observed.st_nlink not in (1,2):raise ValueError('Unexpected STARTED link count')\n        if time.monotonic()>=end:raise TimeoutError('Manager durable Start acknowledgment')\n        time.sleep(.01)\n    row=read(path,16384)"

def derive(raw):
    if type(raw) is not bytes or len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=INPUT_SHA:
        raise ValueError('Exact backed existing six-profile capsule required')
    value=json.loads(raw);files={n:base64.b64decode(s,validate=True) for n,s in value['files'].items()}
    sha=lambda b:hashlib.sha256(b).hexdigest()
    rows=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]
    if rows!=value['manifest']['files']:raise ValueError('Complete original pins')
    path='code/field_operator_broker_common_v1.py';source=files[path].decode();prior=ast.parse(source)
    if source.count(OLD)!=1:raise ValueError('Exact original STARTED boundary')
    source=source.replace(OLD,NEW);changed=ast.parse(source)
    before={n.name:ast.dump(n,include_attributes=False) for n in prior.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    after={n.name:ast.dump(n,include_attributes=False) for n in changed.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    if set(before)!=set(after) or [n for n in before if before[n]!=after[n]]!=['runtime_started']:
        raise ValueError('Only the reviewed read barrier may change')
    compile(source,path,'exec');files[path]=source.encode()
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule caps')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(packed)>1048576:raise ValueError('Original packed capsule cap')
    return packed,dict(status='PREPARED_START_BARRIER_CORRECTION',changed_member=path,changed_function='runtime_started',bundle_sha256=sha(packed),code_members=len(code),code_bytes=sum(map(len,code.values())),native_executed=False)
