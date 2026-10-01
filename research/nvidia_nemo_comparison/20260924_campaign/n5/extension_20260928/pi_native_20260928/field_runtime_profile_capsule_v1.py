"""One common capsule for existing live backend profiles; README_RUNTIME_PROFILE_CAPSULE_V1.md."""
import ast
import base64
import hashlib
import json
from field_runtime_capsule_v2 import replace_once,encoded

BASE_SHA='984e7402b9b9e901a8fd3c977b2414ac4de06711d9d7b6e1e421c92f3d1056c4'
PINS={'policy':'28d45624e53653787d42f8d032b6712aeaa2e308a9a89c67b7acef3c07b007aa',
      'profiles':'c17368db75cdbfaf0e9738985bf6d111b29a2038a6c50320029c486097501bbb',
      'controller':'0b27860dcfd1a5a43636389bc8574574a30d6c41e21527403b159671b731ea48'}
LIVE_PROFILES=('baseline','baseline-titanet','d1-delayed','d1-delayed-titanet','d1-anonymous','baseline-anonymous')

SETUP=r'''
    runtime_profile=admission.get('runtime_profile')
    if type(runtime_profile) is not dict or set(runtime_profile)!={'definition','galleries'}:
        raise ValueError('Exact admitted runtime profile/gallery binding')
    definition=runtime_profile['definition'];selection=definition['selection']
    if selection['input_kind']!='microphone':
        raise ValueError('Saved-input profiles require their saved source integration')
    broker=admission['session_broker'];broker_root=Path(broker['root'])
    broker_policy=bounded_json(broker_root/'RELEASE.json')
    if (sha(broker_root/'RELEASE.json')!=broker['policy_sha256']
        or broker_policy['profile']!=selection['profile']
        or root!=broker_root/'recordings'/broker['slot']):
        raise ValueError('Actual operation/profile/recording binding')
    from app import backends as runtime_backends,people as runtime_people,n2_people as runtime_n2_people
    catalog_path=base/'config/backends.json'
    if sha(catalog_path)!=manifest['config/backends.json']['sha256']:
        raise ValueError('Actual installed backend catalogue pin')
    selected_id=bind_registry(runtime_backends,catalog_path.read_bytes(),definition)
    gallery_root=Path(broker_policy['runtime_root']).with_name(Path(broker_policy['runtime_root']).name+'-galleries')
    for encoder,descriptor in runtime_profile['galleries'].items():
        if descriptor['root']!=str(gallery_root/encoder/'people') or descriptor['manifest_path']!=str(gallery_root/encoder/'MANIFEST.json'):
            raise ValueError('Versioned independent gallery snapshot path')
    def profile_guard():
        from datetime import datetime,timezone
        import shutil
        if datetime.now(timezone.utc)>=datetime.fromisoformat(admission['expires_utc']):
            raise TimeoutError('Runtime profile binding deadline')
        available=next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))
        if available<192*1024**2 or shutil.disk_usage(root).free<5*1024**3:
            raise RuntimeError('Profile binding RAM/disk floor')
    document=bounded_json(data/'n2_runtime.json')
    namespace=document.get('embedding_namespace') if selection['embedding']=='E1' else None
    if selection['embedding']=='E1':
        from edge_speech_pipeline import titanet_embedding
        adapter=base/'vendor/edge_speech_pipeline/titanet_embedding.py'
        if Path(titanet_embedding.__file__).resolve()!=adapter or sha(adapter)!=manifest['vendor/edge_speech_pipeline/titanet_embedding.py']['sha256']:
            raise ValueError('Original installed TitaNet adapter origin/pin')
    readonly=readonly_store_type(runtime_people,data,runtime_profile['galleries'],namespace,profile_guard)
    cm.PersonalStore=readonly;runtime_n2_people.PersonalStore=readonly
'''


def derive(raw_bundle,policy_source,profiles_source,controller_source):
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    if type(raw_bundle) is not bytes or len(raw_bundle)>1048576 or sha(raw_bundle)!=BASE_SHA:
        raise ValueError('Exact prior backed runtime broker capsule')
    for key,source in [('policy',policy_source),('profiles',profiles_source),('controller',controller_source)]:
        if type(source) is not bytes or len(source)>131072 or sha(source)!=PINS[key]:
            raise ValueError('Exact backed profile source '+key)
    value=json.loads(raw_bundle);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    pins={r['path']:r for r in value['manifest']['files']}
    if len(pins)!=len(value['manifest']['files']) or set(pins)!=set(files):raise ValueError('Complete original bundle')
    for n,r in files.items():
        if pins[n]!=dict(path=n,bytes=len(r),sha256=sha(r)):raise ValueError('Original capsule changed')
    old=dict(files)
    for name,raw in list(files.items()):
        if name.endswith('.py'):files[name]=raw.replace(b'field_runtime_policy_v2',b'field_runtime_policy_v3')
    del files['code/field_runtime_policy_v2.py'];files['code/field_runtime_policy_v3.py']=policy_source
    def change(name,fn):
        name='code/'+name;result=fn(files[name].decode()).encode();compile(result,name,'exec');files[name]=result
    def controller(s):
        imports='from field_runtime_profiles_v1 import backend_manifest as profile_definition, digest as profile_digest, TITANET_MODEL, REDIMNET, TITANET_PREPROCESSING, TITANET_ONNX, TITANET_FRONTEND'
        helper=replace_once(controller_source.decode(),imports,'profile_definition=backend_manifest\nprofile_digest=digest')
        # Inline existing reviewed helpers into the existing member; no module cap increase.
        s += '\n'+profiles_source.decode()+'\n'+helper
        s=replace_once(s,'    original,node=derive_field(Path(entry.__file__).read_bytes())',
            SETUP+'\n    original,node=derive_field(Path(entry.__file__).read_bytes())\n    node=specialize_factory(node,definition)')
        start=s.index('    from field_live_d1_v1 import bind as bind_d1')
        terminal='                     bounded_json(data/\'n2_runtime.json\'),catalog,outputs,owner.stop)'
        end=s.index(terminal,start)+len(terminal)
        original=s[start:end]
        s=s[:start]+"    d1_state=None\n    if selection['diarization']=='D1':\n"+''.join('    '+line+'\n' for line in original.splitlines())+s[end:]
        s=replace_once(s,"controller.switch(mode='open_with_names',recipe='balanced',tap='O0')",
            "controller.switch(mode=selection['ui_mode'],recipe='balanced',tap='O0')")
        s=replace_once(s,"        origins=verify_loaded()",
            """        if controller.backend_id!=selected_id:
            raise RuntimeError('Selected backend did not reach actual Controller')
        actual=getattr(controller,'_n2_components',None)
        if selection['backend_key']!='baseline' and (not actual or actual['embedding']!=selection['embedding'] or actual['diarization']!=selection['diarization']):
            raise RuntimeError('Actual resident backend differs from selected encoder/diarizer')
        origins=verify_loaded()""")
        s=replace_once(s,"d1_binding=d1_state,physical_files=outputs.physical_files,actions=actions,transfer=derived,runtime_accepted=False)",
            "d1_binding=d1_state,runtime_profile=definition,physical_files=outputs.physical_files,actions=actions,transfer=derived,runtime_accepted=False)")
        return s
    change('field_operator_controller_v6.py',controller)
    def parent(s):
        start=s.index("    binding=a['operator_parent']")
        end=s.index('    def unmapped():',start)
        old_block=s[start:end]
        prefix="""    profile=a['runtime_profile']['definition']['selection']
    policy=small(Path(broker['root'])/'RELEASE.json')
    if profile['profile']!=policy['profile'] or profile['input_kind']!='microphone':
        raise ValueError('Exact actual live operation profile')
    if profile['diarization']=='D1':
"""
        s=s[:start]+prefix+''.join('    '+line+'\n' for line in old_block.splitlines())+s[end:]
        s=replace_once(s,"text='Delayed mode / one recording\\nStart recording inside the next screen.'",
            "text=a['runtime_profile']['definition']['label']+' / one recording\\nStart recording inside the next screen.'")
        s=replace_once(s,"packet=dict(parent=owner,mode='delayed',","packet=dict(parent=owner,mode=profile['engine_mode'],")
        s=s.replace('method_binding_sha256','profile_binding_sha256').replace("json.dumps(a['d1_binding'],","json.dumps(a['runtime_profile'],")
        return s
    change('field_operator_parent_v13.py',parent)
    def entry(s):
        s=s.replace('method_binding_sha256','profile_binding_sha256').replace("json.dumps(a['d1_binding'],","json.dumps(a['runtime_profile'],")
        s=replace_once(s,"packet['mode']!='delayed'","packet['mode']!=a['runtime_profile']['definition']['selection']['engine_mode']")
        s=replace_once(s,"        state=context['d1_binding']",
            """        state=context['d1_binding']
        if state is None:
            profile=context['runtime_profile']['selection']
            if profile['diarization']!='D0':raise RuntimeError('Missing actual D1 closure state')
            state=dict(schema='just-peachy.process-owned-d0-models.v1',owner=owner,
                profile=profile['profile'],embedding=profile['embedding'],
                asr_loads=controller.models.asr_loads,speaker_loads=controller.models.speaker_loads,
                release_requires_exact_process_exit=True,
                physical_process_death_claimed=False,samples=0 if source is None else source.sent)""")
        s=replace_once(s,"and not(state['closed'] and state['finish_observed'] and state['samples']==result['source_samples']):",
            "and state['schema']=='just-peachy.live-d1-binding.v1' and not(state['closed'] and state['finish_observed'] and state['samples']==result['source_samples']):")
        return s
    change('field_operator_entry_v11.py',entry)
    def ledger(s):
        s=replace_once(s,"dict(root=str(root),mode='delayed',","dict(root=str(root),mode=self.policy['mode'],")
        old_condition="""            if (not stop['source_thread_joined'] or not stop['archive_thread_joined']
                or not model['closed'] or not model['finish_observed']
                or model['samples']!=result['source_samples']):
                raise RuntimeError('Source/model/archive closure incomplete')"""
        new_condition="""            if not stop['source_thread_joined'] or not stop['archive_thread_joined'] or model['samples']!=result['source_samples']:
                raise RuntimeError('Source/archive closure incomplete')
            if self.policy['mode']=='baseline':
                expected_embedding='E1' if self.policy['profile']=='baseline-titanet' else 'E0'
                if (model.get('schema')!='just-peachy.process-owned-d0-models.v1'
                    or model.get('owner')!=parent['child_owner'] or model.get('profile')!=self.policy['profile']
                    or model.get('embedding')!=expected_embedding or type(model.get('asr_loads')) is not int or type(model.get('speaker_loads')) is not int
                    or model['asr_loads']!=1 or model['speaker_loads']!=1
                    or model.get('release_requires_exact_process_exit') is not True
                    or model.get('physical_process_death_claimed') is not False):
                    raise RuntimeError('D0 model route and previously verified exact process exit required')
            elif not model['closed'] or not model['finish_observed']:
                raise RuntimeError('Actual D1 closure/EOF incomplete')"""
        return replace_once(s,old_condition,new_condition)
    change('field_operator_session_ledger_v4.py',ledger)
    change('field_operator_ui_v1.py',lambda s:replace_once(s,
        "self.preview_label.configure(text='Nemotron-3 Diarizer / Delayed')",
        "self.preview_label.configure(text=context['runtime_profile']['label'])"))
    template=json.loads(files['broker/TEMPLATE.json'])
    template['code_names']=[n.replace('field_runtime_policy_v2','field_runtime_policy_v3') for n in template['code_names']]
    files['broker/TEMPLATE.json']=encoded(template)
    code={n:r for n,r in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(r)>131072 for r in code.values()):
        raise ValueError('Original64-member/2MiB/128KiB capsule guards')
    for n,r in code.items():
        if n.endswith('.py'):compile(r,n,'exec')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(files.items())])
    result=encoded(dict(manifest=manifest,files={n:base64.b64encode(r).decode() for n,r in files.items()}))
    if len(result)>1048576:raise ValueError('Original prepared bundle cap')
    changes={n:dict(before_sha256=None if n not in old else sha(old[n]),after_sha256=sha(r),bytes=len(r)) for n,r in files.items() if old.get(n)!=r}
    review=dict(status='PREPARED_COMMON_LIVE_PROFILE_CAPSULE',supported_live_profiles=list(LIVE_PROFILES),
        saved_profiles_integrated=False,native_executed=False,policy_issued=False,code_members=len(code),
        code_bytes=sum(map(len,code.values())),bundle_bytes=len(result),bundle_sha256=sha(result),
        manifest_sha256=sha(encoded(manifest)),changed=changes,
        removed=[n for n in old if n not in files],child_code_members=len(template['code_names']))
    return result,review

