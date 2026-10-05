"""Build21 restoration over exact build17, retaining packaging caps. See README.md."""
import ast
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BASE = PRIVATE/'audit-preparation/classic-package-repair-3b5aac854f7b454686eb770ffe218054/package'
BASE_SHA = '35cd64d5d92e6f2d19dc753b889000dc68428563fa7ce6e4da8590f27b3e6494'
OLD_TARGET = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-17'
NEW_TARGET = OLD_TARGET[:-2]+'21'
REPLACEMENTS = ('launcher.py','worker.py','classic_frontend.py','installed_engine.py','profiles.py',
    'storage.py','native_scope.py','release_authorization.py','application_contract.py',
    'application_controller.py','mature_frontend.py','personal_gallery.py','gallery_service.py',
    'gallery_worker.py','retained_seats.py','retained_caption_projection.py','spatial_archive.py',
    'runtime_ui_channel.py','retained_ui_data.py','README_FULL_APPLICATION.md')
ALLOWED_CHANGED = {
    'launcher.py': {'Manager.start'},
    'worker.py': {'main'},
    'classic_frontend.py': {'caption_row','frontend_type','show','choose'},
    'installed_engine.py': {'InstalledSession.__init__','InstalledSession.run','InstalledSession._caption','InstalledSession.close'},
    'profiles.py': {'SessionPolicy.validate'},
    'storage.py': {'SessionStore.export'},
    'native_scope.py': {'outside'},
    'release_authorization.py': {'validate_acceptance','authorize_session','require_service_room'},
    'runtime_ui_channel.py': {'SpatialViews.display_snapshot','spatial_message'},
}


def definitions(raw):
    result = {}
    def visit(nodes, prefix=''):
        for node in nodes:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                result[prefix+node.name] = ast.dump(node,include_attributes=False)
            elif isinstance(node,ast.ClassDef):
                visit(node.body,prefix+node.name+'.')
    visit(ast.parse(raw).body)
    return result


def bootstrap():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,1<<14):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root=PRIVATE/'audit-preparation'/('full-application-package-'+uuid.uuid4().hex)
    root.mkdir()
    owner=dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    (root/'REGISTERED_OWNER.json').write_text(json.dumps(owner,sort_keys=True))
    return root


def main():
    root=bootstrap()  # BEFORE any project/package reads.
    sys.dont_write_bytecode=True
    legacy_path=HERE.parent/'ui_restore_20261004/build_classic_package.py'
    if hashlib.sha256(legacy_path.read_bytes()).hexdigest()!='bc856ba565f5e98f4b5d9878057e8b1653b96be2c19f99b95c4848f83f7a63a5':
        raise ValueError('Exact reviewed bounded packaging implementation required')
    spec=importlib.util.spec_from_file_location('full_packaging_core',legacy_path)
    core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    # Derive only the archive basename; all packaging/check/restore logic stays exact.
    legacy_tree=ast.parse(legacy_path.read_bytes())
    legacy_main=next(node for node in legacy_tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    changed=0
    for node in ast.walk(legacy_main):
        if isinstance(node,ast.Constant) and node.value=='field-runtime-v29-build-17-prepared.tar.gz':
            node.value='field-runtime-v29-build-21-prepared.tar.gz';changed+=1
    if changed!=1:raise ValueError('Exact original archive basename boundary')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[legacy_main],type_ignores=[])),
        '<unchanged-package-main-with-build21-basename>','exec'),core.__dict__)
    core.BASE,core.BASE_SHA=BASE,BASE_SHA
    core.OLD_TARGET,core.NEW_TARGET=OLD_TARGET,NEW_TARGET
    core.ALLOWED_REPLACEMENTS=set(REPLACEMENTS)
    output=core.Output(root)
    output.bytes=(root/'REGISTERED_OWNER.json').stat().st_size
    output.write(root/'HOST_SCOPE.json',core.encoded(dict(maximum_bytes=core.MAX_PREPARATION,
        maximum_seconds=600,issued_unix=time.time(),target=NEW_TARGET,native_action=False)))
    inputs={name: HERE/('README.md' if name=='README_FULL_APPLICATION.md' else name) for name in REPLACEMENTS}
    for name,path in dict(inputs,**{'build_full_package.py':Path(__file__)}).items():
        raw=core.read(path)
        for suffix in ('backup','restore'):
            output.write(root/'prepared-source'/suffix/name,raw)
    output.write(root/'PREPARED_SOURCE_CLOSED.json',core.encoded(dict(closed_unix=time.time(),
        inputs={name:core.sha(core.read(path)) for name,path in inputs.items()},independent_restores=True)))
    core.bootstrap=lambda parent:output
    def review(before,replacements):
        result={}
        for name, allowed in ALLOWED_CHANGED.items():
            old=definitions(before[name]);new=definitions(replacements[name])
            changed={key for key in old if old[key]!=new.get(key)}
            if changed-allowed:
                raise ValueError('Unapproved original function body change: '+name+' '+str(changed-allowed))
            result[name]=dict(changed=sorted(changed),new=sorted(set(new)-set(old)),
                preserved=len(set(old)-changed))
        for name in ('installed_source.py',):
            if core.read(HERE/name)!=before[name]:
                raise ValueError('Original source/telemetry implementation changed')
        # Static definitions remain hash-reviewed; no backend/model substitution.
        old=ast.parse(before['profiles.py']);new=ast.parse(replacements['profiles.py'])
        for node in old.body:
            if isinstance(node,ast.ClassDef) and node.name=='RuntimeSelection':
                counterpart=next(n for n in new.body if isinstance(n,ast.ClassDef) and n.name=='RuntimeSelection')
                if ast.dump(node,include_attributes=False)!=ast.dump(counterpart,include_attributes=False):
                    raise ValueError('Backend/profile selection contract changed')
        return result
    core.validate_repair_scope=review
    original_derive=core.derive
    def derive(parent,files,replacements,reviewer):
        manifest,files,provenance=original_derive(parent,files,replacements,reviewer)
        acceptance=core.strict(files['PRODUCTION_ACCEPTANCE.json'])
        binding=core.strict(files['BINDING.json'])
        acceptance['limits'].update(manual_stop_storage_policy=True,personal_enrollment=True)
        acceptance['limitations']=[
            'Build21 restores the original application on the current v29 backend. Native restoration qualification remains separately reported.',
            'Normal live duration is storage-capacity-driven with manual Stop; load, drain, backlog, ownership and disk/RAM guards remain enforced.',
            'Assigned-seat voice gates remain Pyannote/ReDimNet-specific; other combinations expose the precise compatibility limit.',
            'Representative native checks do not establish all Cartesian combinations or an hour-long whole-application pass.',
            'Old optional-refiner measurements are not reused to admit changed runtime content.']
        provenance.update(schema='just-peachy.full-application-restoration.v1',
            application_modes_restored=12,mode_backend_independent=True,
            personal_gallery_overlay=True,immutable_old_galleries_changed=False,
            manual_stop_storage_policy=True,personal_enrollment=True)
        files['REPAIR_PROVENANCE.json']=files['REPAIR_PROVENANCE.restore.json']=core.encoded(provenance)
        content=core.sha(core.encoded(core.rows({name:raw for name,raw in files.items()
            if name not in core.CONTENT_EXCLUDED and not name.startswith('source-backups/')})))
        acceptance['candidate_content_sha256']=binding['candidate_content_sha256']=content
        acceptance_raw=core.encoded(acceptance)
        binding['production_acceptance_sha256']=core.sha(acceptance_raw)
        files['PRODUCTION_ACCEPTANCE.json']=acceptance_raw
        files['BINDING.json']=core.encoded(binding)
        manifest.update(candidate_content_sha256=content,files=core.rows(files))
        if len(files)+1>512 or sum(map(len,files.values()))>core.MAX_PACKAGE:
            raise ValueError('Original package count/extent bounds exceeded')
        return manifest,files,provenance
    core.derive=derive
    sys.argv=[str(Path(__file__)), '--base',str(BASE),'--base-manifest-sha256',BASE_SHA,
        '--reviewer','Codex reviewed selective mature-application restoration over immutable build17']
    for name,path in inputs.items():
        sys.argv.extend(['--replacement',name+'='+str(path)])
    core.main()


if __name__=='__main__':
    main()
