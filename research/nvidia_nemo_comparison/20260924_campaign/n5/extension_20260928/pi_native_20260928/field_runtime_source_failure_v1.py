"""Lossless archive JSON within unchanged caps; README_RUNTIME_SOURCE_FAILURE_V1.md."""
import ast,base64,hashlib,json
INPUT_SHA='999b7716c695597306dbf8ccf796d57f3f25dffaf0c288fb6e2a4d42f423a520'
MEMBER_SHA='2e467272931d29ba9bc2bc67b2b6c1b5ab00c4309732b85e58e46891d9415a75'
def derive(raw):
    if type(raw) is not bytes or len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=INPUT_SHA:
        raise ValueError('Exact prior barrier-corrected runtime capsule required')
    value=json.loads(raw);files={n:base64.b64decode(s,validate=True) for n,s in value['files'].items()}
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if [dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]!=value['manifest']['files']:
        raise ValueError('Complete original member pins')
    path='code/field_operator_entry_v11.py';prior=files[path]
    if sha(prior)!=MEMBER_SHA:raise ValueError('Exact prior archive writer')
    old="source_thread_joined=not source.thread.is_alive(),"
    new="source_thread_created=source.thread is not None,source_thread_joined=source.thread is not None and not source.thread.is_alive(),"
    if prior.decode().count(old)!=1:raise ValueError('Exact single encoding boundary')
    changed=prior.decode().replace(old,new)
    before=ast.parse(prior);after=ast.parse(changed)
    def bodies(t):return {n.name:ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    b,a=bodies(before),bodies(after)
    if set(b)!=set(a) or [n for n in b if b[n]!=a[n]]!=['worker']:
        raise ValueError('Only encoding whitespace may change')
    # Assert the entire source differs solely at the one serializer call.
    if changed.replace(new,old)!=prior.decode():raise ValueError('Whole-source derivation')
    compile(changed,path,'exec');files[path]=changed.encode()
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule caps')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(packed)>1048576:raise ValueError('Original packed capsule cap')
    return packed,dict(status='PREPARED_ABSENT_SOURCE_THREAD_FAILURE_RECEIPT',changed_member=path,changed_function='worker',bundle_sha256=sha(packed),
        old_member_sha256=sha(prior),new_member_sha256=sha(files[path]),source_thread_absence_not_claimed_joined=True,
        fields_dropped=False,limits_changed=False,native_executed=False)
