"""Defer broker destruction beyond nested Tk updates; README_RUNTIME_BROKER_CLOSE_V1.md."""
import ast,base64,hashlib,json
INPUT_SHA='4f3bef04b7f3a289a0d431ac3944dc2ed5c493c1df1484e1e5ff3d4b44b69670'
MEMBER_SHA='ae8c108cead759c6036cb0c0c369a6db71c4a4e13c74cd52f0545c849a904105'
def derive(raw):
    if type(raw) is not bytes or len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=INPUT_SHA:
        raise ValueError('Exact prior barrier-corrected runtime capsule required')
    value=json.loads(raw);files={n:base64.b64decode(s,validate=True) for n,s in value['files'].items()}
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if [dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]!=value['manifest']['files']:
        raise ValueError('Complete original member pins')
    path='code/field_operator_chooser_v3.py';prior=files[path]
    if sha(prior)!=MEMBER_SHA:raise ValueError('Exact prior archive writer')
    changes=[('        self.broker.close();self.closed=True;self.root.destroy()\n', '        self.close_requested=True\n'), ('self.closed=False;self.fault=None', 'self.closed=False;self.close_requested=False;self.fault=None'), ('        self.root.update()\n\n    def close(self):', '        self.root.update()\n        if self.close_requested:\n            self.broker.close();self.closed=True;self.root.destroy()\n\n    def close(self):')]
    changed=prior.decode()
    for old,new in changes:
        if changed.count(old)!=1:raise ValueError('Exact broker close boundary')
        changed=changed.replace(old,new)
    before=ast.parse(prior);after=ast.parse(changed)
    def methods(t):
        c=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='Chooser')
        return {n.name:ast.dump(n,include_attributes=False) for n in c.body if isinstance(n,ast.FunctionDef)}
    b,a=methods(before),methods(after)
    if set(b)!=set(a) or {n for n in b if b[n]!=a[n]}!={'__init__','tick','close'}:raise ValueError('Exact close lifecycle methods')
    restored=changed
    for old,new in reversed(changes):restored=restored.replace(new,old)
    if restored!=prior.decode():raise ValueError('Whole-source close derivation')
    compile(changed,path,'exec');files[path]=changed.encode()
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule caps')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if len(packed)>1048576:raise ValueError('Original packed capsule cap')
    return packed,dict(status='PREPARED_DEFERRED_BROKER_CLOSE',changed_member=path,changed_functions=['__init__','tick','close'],bundle_sha256=sha(packed),
        old_member_sha256=sha(prior),new_member_sha256=sha(files[path]),destroy_only_after_event_update_returns=True,
        fields_dropped=False,limits_changed=False,native_executed=False)
