"""Register retained Chunk52 geometry; README_RUNTIME_CHUNK52_V2.md."""
import base64
import hashlib
import json

INPUT_SHA='5b394bec8877866ebe4e7c063ab9f7d946ab5a7cc5dc1b4eb00a5187c24d1484'


def derive(raw):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:raise ValueError('Exact terminal-config capsule')
    value=json.loads(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    if value['manifest']['files']!=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]:raise ValueError('Exact complete capsule')
    name='code/field_live_d1_v1.py';old=files[name];text=old.decode()
    marker='    selected = modes.select(MODE)'
    if text.count(marker)!=1:raise ValueError('Exact selected-mode boundary')
    text=text.replace(marker,marker+'''
    if MODE=='chunk52':
        expected=dict(chunk_frames=52,right_context_frames=1,left_context_frames=0,fifo_frames=80,
            spkcache_frames=264,update_period_frames=40,preset='v3-streaming',gpu=-1)
        if selected['profile']!=PROFILE or selected['geometry']!=expected or PROFILE in native.PROFILES:
            raise ValueError('Exact retained Chunk52 profile registration required')
        geometry={key:expected[key] for key in modes.GEOMETRY_FIELDS}
        native.PROFILES[PROFILE]=native.StreamingProfile(PROFILE,**geometry)
        if vars(native.PROFILES[PROFILE])!=dict(name=PROFILE,**geometry):
            raise ValueError('Installed Chunk52 descriptor differs from retained recipe')
''')
    files[name]=text.encode();compile(text,name,'exec')
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):raise ValueError('Original capsule bounds')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':')).encode()
    if len(packed)>1048576:raise ValueError('Packed capsule cap')
    return packed,dict(status='PREPARED_RETAINED_CHUNK52_DESCRIPTOR',bundle_sha256=sha(packed),
        changed_member=name,before_sha256=sha(old),sha256=sha(files[name]),
        original_constructor_push_finish_close_unchanged=True,actual_c_abi_check_retained=True)
