"""Native compact dependency binding boundary; README_FIELD_DEPENDENCY_BINDING_V1.md."""
import copy
import json
from pathlib import Path
import sys
import field_dependencies_v2 as pins
import field_dependency_binding_v1 as binding


def run(root,a):
    sys.dont_write_bytecode=True
    pins.configure_output(root,a['target_output_max_bytes'])
    selected=Path(a['installed_release']);base=Path(a['base_release'])
    sys.path.insert(0,str(selected))
    from release_tools import release
    from release_tools.runtime_lock import RuntimeLock
    before={k:pins.sha(v) for k,v in dict(lock=a['retained_lock'],old=base/'RELEASE_MANIFEST.json',selected=selected/'RELEASE_MANIFEST.json').items()}
    assert before['lock']==a['retained_lock_sha256'] and before['selected']==a['release_manifest_sha256']
    assert before['old']=='b823918b2d8939a9bdb3105109ae6e4b7063461f234a22df37c04fd941aee6c4'
    assert {p.relative_to(selected).as_posix():pins.sha(p) for p in selected.rglob('*') if p.is_file()}==a['installed_files']
    value=binding.describe(a['retained_lock'],base,selected)
    path=root/'CONTRACT_BINDING.json';pins.exclusive(path,value)
    rejections=[]
    def reject(name,fn):
        try:fn()
        except (ValueError,FileNotFoundError) as exc:
            row=dict(case=name,error=type(exc).__name__+': '+str(exc),rejected=True)
            pins.exclusive(root/(name+'.json'),row);rejections.append(row)
        else:raise AssertionError('Missing rejection: '+name)
    reject('wrong-binding-digest',lambda:binding.verify(path,'0'*64,release))
    for name,edit in [
        ('catalogue-override',lambda x:x.update(entries=[])),
        ('wrong-catalogue-sha',lambda x:x['base_lock'].update(sha256='0'*64)),
        ('wrong-release-sha',lambda x:x['selected_release'].update(manifest_sha256='0'*64)),
        ('wrong-contract-sha',lambda x:x['selected_release'].update(contract_sha256='0'*64)),
        ('missing-release',lambda x:x['selected_release'].update(path=str(root/'absent-release'))),
        ('unauthorized-patch',lambda x:x['patch'].update(maximum_recording_seconds=[30,3600])),
        ('missing-patch',lambda x:x['patch'].pop('artifact_limits'))]:
        fixture=copy.deepcopy(value);edit(fixture);f=root/(name+'-fixture.json');pins.exclusive(f,fixture)
        reject(name,lambda f=f:binding.verify(f,pins.sha(f),release))
    data=root/'data';preserved={p.name:pins.sha(p) for p in data.iterdir() if p.is_file()}
    owner=RuntimeLock(data,'compact_dependency_binding');raw=(data/'runtime.lock').read_bytes()
    try:
        checked=binding.verify(path,pins.sha(path),release)
        assert (data/'runtime.lock').read_bytes()==raw
        pins.exclusive(root/'BINDING_VERIFIED.json',checked)
    finally:owner.close()
    assert not (data/'runtime.lock').exists()
    assert before=={k:pins.sha(v) for k,v in dict(lock=a['retained_lock'],old=base/'RELEASE_MANIFEST.json',selected=selected/'RELEASE_MANIFEST.json').items()}
    for name,sha in preserved.items():assert pins.sha(data/name)==sha
    assert not any((root/n).exists() for n in ['source','deployment','archives','DEPENDENCIES.json'])
    assert not any((data/n).exists() for n in ['sessions','source_receipts','conversations'])
    pins.exclusive(root/'LEASE_CLOSED.json',dict(released=True,token=owner.token,private_config_unchanged=True))
    return dict(status='PASS_NATIVE_COMPACT_DEPENDENCY_BINDING_ONLY',rejections=rejections,verification=checked,
                ownership_closed=True,old_catalogue_unchanged=True,old_release_unchanged=True,selected_release_unchanged=True,
                controller_started=False,GUI=False,models=False,capture=False,pointer_activated=False)
