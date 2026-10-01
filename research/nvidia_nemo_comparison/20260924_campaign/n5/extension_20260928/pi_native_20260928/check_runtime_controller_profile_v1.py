"""Check changed installed selector/gallery bindings; README_RUNTIME_CONTROLLER_PROFILE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,json,os
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--installed',type=Path,required=True)
    args=ap.parse_args();args.output.mkdir();me=psutil.Process()
    (args.output/'REGISTERED_OWNER.json').write_bytes(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    import ast,hashlib,sys,types,threading
    from copy import deepcopy
    from field_runtime_profiles_v1 import backend_manifest,digest,TITANET_MODEL,TITANET_PREPROCESSING,TITANET_ONNX,TITANET_FRONTEND,REDIMNET
    from field_runtime_controller_profile_v1 import bind_registry,specialize_factory,readonly_store_type
    from field_operator_controller_v6 import derive_field
    base=args.installed.absolute();release=json.loads((base/'RELEASE_MANIFEST.json').read_bytes())
    pins={r['path']:r for r in release['files']}
    def source(name):
        raw=(base/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==pins[name]['sha256'];return raw
    catalog=source('config/backends.json');entry=source('native/field_entry_v5.py')
    sys.path.insert(0,str(base))
    import app,app.backends as backends
    assert Path(backends.__file__).resolve()==base/'app/backends.py'
    assert hashlib.sha256(Path(backends.__file__).read_bytes()).hexdigest()==pins['app/backends.py']['sha256']
    original=deepcopy(backends._BACKENDS)
    pipeline=types.ModuleType('app.pipeline');sys.modules['app.pipeline']=pipeline;app.pipeline=pipeline
    class Base:
        def _do_select_backend(self,value):return value
        def _do_switch(self,*args):return args
        def snapshot(self):return dict(backends=backends.backend_catalog(),backend={})
    fake_source=types.SimpleNamespace(IsolatedLiveConfig=object,bind_pipeline=lambda p:None)
    rejections=[];cases=[]
    def reject(name,fn):
        try:fn()
        except ValueError:rejections.append(name)
        else:raise AssertionError(name)
    for profile in ('d1-delayed-titanet','baseline-titanet','d1-anonymous'):
        backends._BACKENDS=deepcopy(original)
        definition=backend_manifest(catalog,profile);identifier=bind_registry(backends,catalog,definition)
        old,node=derive_field(entry);node=specialize_factory(node,definition)
        namespace={}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-installed-field-factory','exec'),namespace)
        Field,supported=namespace['controller_type'](Base,fake_source,object)
        view=Field();view.mode=definition['selection']['ui_mode'];view.recipe='balanced';view.tap='O0'
        assert supported==identifier and view._do_select_backend(identifier)==identifier
        assert view._do_switch(view.mode,'balanced','O0',None,None)[0]==view.mode
        assert view.snapshot()['backend']['label']==definition['label']
        cases.append(dict(profile=profile,actual_composition=backends.backend_manifest(identifier)['composition']['n2']['embedding'],
                          label=view.snapshot()['backend']['label']))
        if profile=='d1-delayed-titanet':
            reject('different-backend-before-base',lambda:view._do_select_backend('sha256:'+'0'*64))
            reject('different-tap-before-base',lambda:view._do_switch(view.mode,'balanced','O1',None,None))
    backends._BACKENDS=original
    # Compile the actual PersonalStore class without importing neural/device modules.
    people_source=source('app/people.py');tree=ast.parse(people_source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PersonalStore')
    module=types.ModuleType('actual_people_fixture')
    module.__file__=str(base/'app/people.py')
    module.__dict__.update(Path=Path,threading=threading,PREPROCESSING='mono-float32-16k-redimnet2-native-l2-v1',AdaptationStore=type('AdaptationStore',(),{}))
    exec(compile(ast.Module(body=[cls],type_ignores=[]),'actual-personal-store','exec'),module.__dict__)
    e0=dict(model_sha256=REDIMNET,preprocessing=module.PREPROCESSING,dimension=192,normalization='L2',minimum_samples=8000)
    e1=dict(model_sha256=TITANET_MODEL,preprocessing=TITANET_PREPROCESSING,dimension=192,normalization='L2',minimum_samples=8000,
            onnx_sha256=TITANET_ONNX,frontend_sha256=TITANET_FRONTEND)
    galleries={}
    for key,namespace in [('E0',e0),('E1',e1)]:
        root=args.output/key;root.mkdir()
        manifest=dict(schema='just-peachy.runtime-gallery-snapshot.v1',namespace=namespace,files={},directories=[''],reserved_bytes=65536)
        raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
        path=args.output/(key+'-MANIFEST.json');path.write_bytes(raw)
        galleries[key]=dict(root=str(root),manifest_path=str(path),manifest_sha256=hashlib.sha256(raw).hexdigest())
    data=args.output/'not-created-recording-data'
    def guard():pass
    Bound=readonly_store_type(module,data,galleries,e1,guard)
    redim=Bound(data/'people',REDIMNET)
    assert redim.root==Path(galleries['E0']['root']).absolute() and not data.exists()
    # Reuse the actual previous TitaNet factory and namespace hash function.
    node=next(n for n in ast.parse(source('app/n2_identity.py')).body if isinstance(n,ast.FunctionDef) and n.name=='binding')
    scope=dict(json=json,hashlib=hashlib)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-namespace-binding','exec'),scope)
    node=next(n for n in ast.parse(source('app/n2_people.py')).body if isinstance(n,ast.FunctionDef) and n.name=='titanet_store')
    scope.update(PersonalStore=Bound,deepcopy=deepcopy)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'actual-titanet-store','exec'),scope)
    titan=scope['titanet_store'](data,e1)
    assert titan.root==Path(galleries['E1']['root']).absolute() and titan.root!=redim.root and not data.exists()
    assert titan.preprocessing=='titanet:'+scope['binding'](e1) and titan.backend==TITANET_MODEL
    reject('cross-embedding-root',lambda:Bound(data/'people',TITANET_MODEL))
    changed=deepcopy(galleries);changed['E1']=galleries['E0']
    reject('wrong-gallery-namespace',lambda:readonly_store_type(module,data,changed,e1,guard))
    # ReDimNet selection has no E1 gallery or model-file dependency.
    only=readonly_store_type(module,data,{'E0':galleries['E0']},None,guard)
    assert only(data/'people',REDIMNET).root==redim.root
    result=dict(status='PASS_CHANGED_INSTALLED_CONTROLLER_AND_GALLERY_BINDING',profile_guards=cases,rejections=rejections,
        actual_installed_factory_methods=True,actual_personal_store_initializer_and_titanet_factory=True,
        empty_private_gallery_fixtures=True,neural_model_loaded=False,native_executed=False,
        full_controller_constructed=False,physical_io_guard_claimed=False)
    (args.output/'RESULT.json').write_bytes(json.dumps(result,indent=2).encode())
    print(json.dumps(dict(status=result['status'],profiles=len(cases),rejections=rejections)))
if __name__=='__main__':main()

