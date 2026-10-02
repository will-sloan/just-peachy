"""Lossless bounded terminal snapshot; README_RUNTIME_TERMINAL_CONFIG_V1.md."""
import ast
import base64
import hashlib
import json
import zlib

INPUT_SHA='118a5d1b44beaaec710ea5cf22cf05e079c1b0d5908a3c328ca08d43b362e97e'


def terminal_encode(value,limit):
    if type(limit) is not int or limit!=32768:raise ValueError('Exact terminal primary slot')
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
    if len(raw)>262144:raise ValueError('Terminal decoded metadata bound')
    if len(raw)<=limit:return raw
    packed=dict(schema='just-peachy.terminal-config-zlib.v1',encoding='zlib-base64',
        decoded_bytes=len(raw),decoded_sha256=hashlib.sha256(raw).hexdigest(),
        data=base64.b64encode(zlib.compress(raw,6)).decode())
    encoded=(json.dumps(packed,sort_keys=True,separators=(',',':'))+'\n').encode()
    if len(encoded)>limit:raise ValueError('Terminal physical slot exhausted')
    if decode_terminal(encoded)!=value:raise ValueError('Terminal independent codec readback')
    return encoded


def decode_terminal(raw):
    if type(raw) is not bytes or len(raw)>32768:raise ValueError('Bounded terminal input')
    def pairs(rows):
        value={}
        for key,item in rows:
            if key in value:raise ValueError('Duplicate terminal key')
            value[key]=item
        return value
    def bad(value):raise ValueError('Nonfinite terminal JSON')
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    if type(value) is not dict:raise ValueError('Terminal object')
    if value.get('schema')!='just-peachy.terminal-config-zlib.v1':return value
    if set(value)!={'schema','encoding','decoded_bytes','decoded_sha256','data'} or value['encoding']!='zlib-base64':
        raise ValueError('Exact terminal compressed envelope')
    size=value['decoded_bytes']
    if type(size) is not int or not 32768<size<=262144:raise ValueError('Decoded terminal bound')
    compressed=base64.b64decode(value['data'],validate=True)
    decoder=zlib.decompressobj();decoded=decoder.decompress(compressed,size+1)
    if len(decoded)!=size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
        raise ValueError('Exact complete bounded terminal stream')
    if hashlib.sha256(decoded).hexdigest()!=value['decoded_sha256']:raise ValueError('Terminal digest mismatch')
    result=json.loads(decoded,object_pairs_hook=pairs,parse_constant=bad)
    if type(result) is not dict:raise ValueError('Decoded terminal object')
    return result


def derive(raw,helper_source):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:raise ValueError('Exact TitaNet-memory capsule')
    value=json.loads(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    if value['manifest']['files']!=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]:raise ValueError('Complete capsule pins')
    old=dict(files)
    functions=[n for n in ast.parse(helper_source).body if isinstance(n,ast.FunctionDef) and n.name in ('terminal_encode','decode_terminal')]
    if len(functions)!=2:raise ValueError('Exact terminal helper definitions')
    # The caller binds this entire source through the immutable source backup.
    helpers='\nimport base64\nimport json\nimport zlib\n\n'+'\n\n'.join(ast.unparse(n) for n in functions)+'\n'
    def once(s,a,b):
        if s.count(a)!=1:raise ValueError('Exact terminal source boundary: '+a)
        return s.replace(a,b)
    name='code/field_operator_controller_v6.py';s=files[name].decode()
    s=once(s,'    from field_archive_budget_v4 import encode_control,publish',
        '    from field_archive_budget_v4 import encode_control,publish\n    import types\n    terminal_publish=types.FunctionType(publish.__code__,dict(publish.__globals__,encode_control=terminal_encode),publish.__name__,publish.__defaults__,publish.__closure__)')
    s=once(s,'                raw=encode_control(value,32768);finite_json(raw)',
        "                serialize=terminal_encode if path.name=='last_application.json' else encode_control\n                raw=serialize(value,32768);finite_json(raw)")
    s=once(s,'                return publish(path,value,32768)',
        "                writer=terminal_publish if path.name=='last_application.json' else publish\n                result=writer(path,value,32768)\n                if path.read_bytes()!=raw:raise IOError('Exact configuration readback')\n                if path.name=='last_application.json' and decode_terminal(raw)!=value:raise IOError('Complete terminal metadata readback')\n                return result")
    files[name]=(s+helpers).encode()
    name='code/field_operator_entry_v11.py';s=files[name].decode()
    s=once(s,"if census['failures'] or census['open_writable_descriptors'] or not capture_closed():", "if census['failures'] or census['open_writable_descriptors'] or context['configuration'].failures or not capture_closed():")
    files[name]=s.encode()
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):raise ValueError('Original code bounds')
    for n,b in code.items():
        if n.endswith('.py'):compile(b,n,'exec')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':')).encode()
    if len(packed)>1048576:raise ValueError('Packed capsule bound')
    return packed,dict(status='PREPARED_LOSSLESS_TERMINAL_CONFIG',bundle_sha256=sha(packed),primary_maximum=32768,pending_maximum=32768,
        decoded_maximum=262144,configuration_failures_block_success=True,publication_code_unchanged=True,
        changed={n:dict(before_sha256=sha(old[n]),sha256=sha(b),bytes=len(b)) for n,b in files.items() if b!=old[n]})
