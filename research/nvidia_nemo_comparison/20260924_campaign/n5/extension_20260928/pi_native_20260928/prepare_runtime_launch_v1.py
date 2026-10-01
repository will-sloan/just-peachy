"""Prepare native release launch/profile assets; README_RUNTIME_BOOT_MANAGER_V3.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,ast,base64,copy,hashlib,json,os,re,shlex,shutil
from pathlib import Path
from datetime import datetime,timezone

def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()

def launch_assets(release_id,policy_sha256,profiles,python_path):
    from field_runtime_profiles_v1 import select
    if not re.fullmatch(r'field-runtime-v[1-9][0-9]*',release_id) or not re.fullmatch('[0-9a-f]{64}',policy_sha256):
        raise ValueError('Exact versioned installed policy')
    expected='/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python'
    if python_path!=expected:raise ValueError('Existing native interpreter required')
    if type(profiles) is not list or not profiles or len(set(profiles))!=len(profiles):raise ValueError('Explicit profile names')
    for name in profiles:select(name)
    root='/home/peachyprototype/JustPeachy/research/nemotron-20260928/'+release_id
    wrapper=root+'-profiles/bin/launch-profile'
    slice_name='jpfield'+release_id.replace('-','')+'.slice'
    command=['systemd-run','--user','--quiet','--collect','--unit=jp-'+release_id,'--slice='+slice_name,
        '--property=Description=JustPeachyOfflineRuntime','--property=LimitAS=134217728',
        '--property=LimitSTACK=1048576','--property=LimitFSIZE=33554432','--property=TasksMax=64',
        '--property=RuntimeMaxSec=86400','--property=TimeoutStopSec=45',
        '--setenv=DISPLAY=:0','--setenv=XDG_RUNTIME_DIR=/run/user/1000','--setenv=WAYLAND_DISPLAY=wayland-0',
        '--setenv=HF_HUB_OFFLINE=1','--setenv=TRANSFORMERS_OFFLINE=1','--setenv=PYTHONDONTWRITEBYTECODE=1',
        '--setenv=OMP_NUM_THREADS=1','--setenv=OPENBLAS_NUM_THREADS=1','--setenv=MKL_NUM_THREADS=1',
        python_path,'-B',root+'/code/field_runtime_manager_v3.py','--root',root,'--policy-sha256',policy_sha256]
    shell=("#!/bin/sh\nset -eu\n[ \"$#\" -eq 2 ] && [ \"$1\" = --profile ] || exit 64\n"
           "case \"$2\" in "+'|'.join(profiles)+") ;; *) exit 64 ;; esac\n"
           "exec "+shlex.join(command)+" --profile \"$2\"\n")
    entries={}
    for name in profiles:
        definition=select(name)
        encoder='TitaNet' if definition['embedding']=='E1' else 'ReDimNet'
        diarizer='Nemotron-3' if definition['diarization']=='D1' else 'Baseline'
        label='Sherpa + '+diarizer+' + '+encoder+' ('+definition['engine_mode']+')'
        if definition['ui_mode']=='anonymous_conversation':label+=' - Anonymous'
        entries[name+'.desktop']=('[Desktop Entry]\nType=Application\nName=Just Peachy - '+label+
            '\nComment=Opens idle. Press New and Start to record.\nExec='+wrapper+' --profile '+name+
            '\nIcon=audio-input-microphone\nTerminal=false\nCategories=AudioVideo;Audio;\n'
            'X-JustPeachy-CaptureOnLaunch=false\n').encode()
    return {'bin/launch-profile':shell.encode(),'systemd/'+slice_name:
        ('[Unit]\nDescription=Just Peachy shared runtime resources\n[Slice]\nCPUQuota=200%\nAllowedCPUs=2-3\nTasksMax=64\n').encode(),
        **{'desktop/'+k:v for k,v in entries.items()},
        'autostart/just-peachy.desktop':entries['d1-delayed.desktop']}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('manager-bundle','profile-bundle','sources','catalog','inspection','titanet-manifest','scope','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--release-id',required=True);ap.add_argument('--titanet-version',type=int,required=True)
    a=ap.parse_args();a.output.mkdir();me=psutil.Process()
    def put(path,raw):
        path.parent.mkdir(exist_ok=True,parents=True)
        with path.open('xb') as f:
            if f.write(raw)!=len(raw):raise IOError('Short prepared publication')
            f.flush();os.fsync(f.fileno())
        if path.read_bytes()!=raw:raise IOError('Prepared readback')
    put(a.output/'REGISTERED_OWNER.json',encode(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])))
    scope=json.loads(a.scope.read_bytes())
    def guard(extra=0):
        if datetime.now(timezone.utc)>=datetime.fromisoformat(scope['expires_utc']):raise TimeoutError('Preparation scope')
        if sum(p.stat().st_size for p in a.scope.parent.rglob('*') if p.is_file())+extra>scope['maximum_bytes']:raise RuntimeError('Same cumulative allocation')
        for drive,gib in [('C:/',50),('G:/',75)]:
            if shutil.disk_usage(drive).free<gib*1024**3+extra:raise RuntimeError('Host floor')
    guard()
    from field_runtime_profiles_v1 import ROOT,ROUTES,backend_manifest,titanet_namespace,REDIMNET
    from field_runtime_profiles_v1 import select

    def bundle(path,expected):
        raw=path.read_bytes()
        if len(raw)>1048576 or sha(raw)!=expected:raise ValueError('Previously backed complete capsule pin')
        value=json.loads(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
        if value['manifest']['files']!=[dict(path=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(files.items())]:
            raise ValueError('Complete capsule membership and hashes')
        return raw,files
    old_raw,files=bundle(a.manager_bundle,'a5bdb8cfab798af2e18ed736cf696e7b82e6ce9cc6b3ff6fa5d2123f43451355')
    common_raw,common=bundle(a.profile_bundle,'4ec6d0f422bffbcbf85365b39707b6f0942625aeed2989e697f529b5bb051eae')
    manager=(a.sources/'field_runtime_manager_v3.py').read_bytes()
    backed=json.loads((a.scope.parent/'SOURCE_CLOSED_V30.json').read_bytes())['files']['field_runtime_manager_v3.py']
    if backed!={'bytes':len(manager),'sha256':sha(manager)}:raise ValueError('Backed current manager source')
    old=ast.parse(files.pop('code/field_runtime_manager_v2.py'));new=ast.parse(manager)
    methods=lambda t:{n.name:ast.dump(n,include_attributes=False) for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    previous,current=methods(old),methods(new)
    changed={n for n in previous if previous[n]!=current.get(n)}
    if changed!={'bootstrap_manager','bundle_for_operation'} or set(current)-set(previous)!={'current_activation'}:
        raise ValueError('Only current boot validation/binding may change')
    files['code/field_runtime_manager_v3.py']=manager
    if len(files)!=16 or any(len(r)>131072 for r in files.values()) or sum(map(len,files.values()))>2097152:
        raise ValueError('Original full manager cardinality/byte guards')
    for name,raw in files.items():compile(raw,name,'exec')
    manifest=dict(schema='just-peachy.local-release-manifest.v1',files=[dict(path=n,bytes=len(r),sha256=sha(r)) for n,r in sorted(files.items())])
    manager_bundle=encode(dict(manifest=manifest,files={n:base64.b64encode(r).decode() for n,r in files.items()}))
    if not re.fullmatch('field-runtime-v[1-9][0-9]*',a.release_id) or a.titanet_version<1:raise ValueError('Fresh exact proposed roots')
    root=ROOT+'/'+a.release_id
    observed=json.loads((a.inspection/'RESULT.json').read_bytes())
    existing=[v for v in observed['galleries'] if v['root']=='/home/peachyprototype/JustPeachy/data/people']
    if len(existing)!=1 or existing[0]['exists'] is not True:raise ValueError('Exact existing baseline gallery inventory')
    tm=a.titanet_manifest.read_bytes();namespace=titanet_namespace(json.loads(tm))
    namespaces=dict(E0=dict(model_sha256=REDIMNET,preprocessing='mono-float32-16k-redimnet2-native-l2-v1',dimension=192,normalization='L2',minimum_samples=8000),E1=namespace)
    gallery_manifests={};gallery_descriptors={}
    for key,ns in namespaces.items():
        row=existing[0] if key=='E0' else dict(files={},directories=[''],reserved_bytes=65536)
        document=dict(schema='just-peachy.runtime-gallery-snapshot.v1',namespace=ns,
            files=row['files'],directories=row['directories'],reserved_bytes=row['reserved_bytes'])
        raw=encode(document);gallery_manifests[key]=document
        gallery_descriptors[key]=dict(root=root+'-galleries/'+key+'/people',
            manifest_path=root+'-galleries/'+key+'/MANIFEST.json',manifest_sha256=sha(raw))
    catalog=a.catalog.read_bytes();template=json.loads(common['broker/TEMPLATE.json'])
    descriptors={};availability={}
    native_tm=ROOT+'/runtime-titanet-v'+str(a.titanet_version)+'/titanet_manifest.json'
    for profile in ROUTES:
        route=select(profile)
        if route['input_kind']=='saved':
            availability[profile]=dict(available=False,input_kind='saved',manifest_sha256=None,
                reason='Saved Streaming/Chunk52 entry integration is not yet installed. No fallback to live Delayed.')
            continue
        definition=backend_manifest(catalog,profile);doc=copy.deepcopy(template['data_files']['n2_runtime.json'])
        # Keep the actual qualified common Delayed model/library paths, not a guessed sibling GGUF.
        for key in ('titanet_manifest','titanet_manifest_sha256','embedding_namespace'):doc.pop(key,None)
        keys=['E0']
        if route['embedding']=='E1':
            keys.append('E1');doc.update(titanet_manifest=native_tm,titanet_manifest_sha256=sha(tm),embedding_namespace=namespace)
        descriptor=dict(schema='just-peachy.runtime-profile-descriptor.v1',profile=profile,template_sha256=sha(common_raw),
            runtime_profile=dict(definition=definition,galleries={k:gallery_descriptors[k] for k in keys}),runtime_document=doc)
        raw=encode(descriptor)
        if len(raw)>65536:raise ValueError('Original descriptor cap')
        descriptors[profile]=descriptor
        availability[profile]=dict(available=True,input_kind='microphone',manifest_sha256=sha(raw),reason='')
    from field_local_release_plan_v2 import allocation
    plan=allocation(4,16)
    proposal=dict(schema='just-peachy.runtime-install-inputs.v1',release_id=a.release_id,manager_root=root,
        manager_manifest_sha256=sha(encode(manifest)),manager_bundle_sha256=sha(manager_bundle),
        common_bundle=dict(path=str(a.profile_bundle),bytes=len(common_raw),sha256=sha(common_raw)),
        gallery_manifests=gallery_manifests,gallery_source=existing[0]['root'],
        titanet_manifest=dict(path=native_tm,bytes=len(tm),sha256=sha(tm)),
        profiles=availability,allocation=plan,policy_issued=False,native_qualified=False,
        gallery_target_reserved_bytes=sum(v['reserved_bytes'] for v in gallery_manifests.values())+4*65536,
        gallery_host_reserved_bytes=2*(sum(v['reserved_bytes'] for v in gallery_manifests.values())+4*65536),
        profile_target_reserved_bytes=len(common_raw)+sum(len(encode(v)) for v in descriptors.values())+32*65536,
        actual_current_baseline=observed['current_project_processes'],config_pins={r['path']:r['sha256'] for r in observed['files']})
    # Preview is explicitly non-dispatchable until a real measured policy SHA replaces this placeholder.
    preview=launch_assets(a.release_id,'0'*64,list(descriptors),
        '/home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python')
    total=2*len(manager_bundle)+sum(map(len,files.values()))+len(encode(proposal))+sum(len(encode(v)) for v in descriptors.values())+sum(map(len,preview.values()))
    guard(total+65536)
    put(a.output/'MANAGER_BUNDLE.json',manager_bundle);put(a.output/'MANAGER_BUNDLE_BACKUP.json',manager_bundle)
    for name,raw in files.items():put(a.output/'independent-restore'/name,raw)
    for profile,descriptor in descriptors.items():put(a.output/'profiles'/(profile+'.json'),encode(descriptor))
    for name,raw in preview.items():put(a.output/'non-dispatchable-preview'/name,raw)
    put(a.output/'INSTALL_INPUTS.json',encode(proposal))
    for name,raw in files.items():
        if (a.output/'independent-restore'/name).read_bytes()!=raw:raise IOError('Complete independent manager restore')
    review=dict(status='PREPARED_BOOT_BOUND_MANAGER_AND_SIX_PROFILE_LAUNCH_INPUTS',
        native_dispatched=False,policy_issued=False,manager_modules=len(files),manager_code_bytes=sum(map(len,files.values())),
        manager_bundle_sha256=sha(manager_bundle),manager_manifest_sha256=sha(encode(manifest)),
        profiles=list(descriptors),saved_profiles_unavailable=[p for p,v in availability.items() if not v['available']],
        exact_existing_delayed_model_paths_retained=True,synthetic_launcher_preview_policy_sha=True,
        closed_utc=datetime.now(timezone.utc).isoformat())
    put(a.output/'REVIEW.json',encode(review));guard();print(json.dumps(review))

if __name__=='__main__':main()

