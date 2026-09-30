"""Fresh bounded sustained-run candidate. README_FIELD_SUSTAINED_V1.md."""
import json
from pathlib import Path
import shutil
import sys
import field_dependencies_v2 as pins
import field_candidate_transaction_v1 as transactions


def build(root, admission):
    pins.configure_output(root,admission['target_output_max_bytes'])
    prior = Path(admission['installed_release'])
    assert {p.relative_to(prior).as_posix():pins.sha(p) for p in prior.rglob('*') if p.is_file()} == admission['installed_files']
    source = root/'source'
    shutil.copytree(prior, source, ignore=shutil.ignore_patterns('__pycache__'))
    for original, relative in [('field_entry_sustained_v1.py','native/field_entry_v5.py'),
                               ('isolated_source_transport_sustained_v1.py','native/isolated_source_transport_v3.py'),
                               ('README_FIELD_SUSTAINED_V1.md','docs/README_FIELD_SUSTAINED_V1.md')]:
        shutil.copyfile(root/original, source/relative)
    contract = pins.read(source/'config/field_contract.json')
    contract.update(maximum_recording_seconds=125,session_reservation_bytes=64*1024**2,
                    sustained_target_seconds=120,archive_interchange_for_extended_recording='UNQUALIFIED',
                    field_release_accepted=False)
    (source/'config/field_contract.json').write_text(json.dumps(contract,indent=2))
    sys.path.insert(0,str(source))
    from release_tools import release
    built=release.build(source,root/'archives','b01-offline-20260930-v8')
    staged=release.stage(built['archive'],root/'deployment',built['sha256'])
    installed=Path(staged['path'])
    pins.exclusive(root/'CANDIDATE_BUILD.json',dict(built=built,staged=staged,manifest_sha256=pins.sha(installed/'RELEASE_MANIFEST.json')))
    sys.path.remove(str(source))
    for name in list(sys.modules):
        if name=='release_tools' or name.startswith('release_tools.'):
            del sys.modules[name]
    return installed


def acquire(root, admission, installed):
    """One outer owner; retain real ApplicationLock validation with a sole borrow."""
    sys.path[:0]=[str(installed),str(installed/'vendor'),str(installed/'native')]
    from release_tools import release
    from release_tools.runtime_lock import RuntimeLock
    from app import paths
    assert paths.ROOT.resolve()==installed.resolve()
    data=root/'data'
    release.write_json(data/'DATA_SCHEMA.json',dict(schema_version=1))
    (data/'private-preservation-canary').write_bytes(b'PRIVATE_SYNTHETIC_CANARY\n')
    candidate=root/'candidate';(candidate/'transactions').mkdir(parents=True);(candidate/'staged').mkdir()
    descriptor=dict(schema='just-peachy.retained-deployment.v1',version='b01-offline-20260930-v8',release=str(installed),
                    resolved_release=str(installed.resolve()),manifest_sha256=pins.sha(installed/'RELEASE_MANIFEST.json'),
                    contract_sha256=pins.sha(installed/'config/field_contract.json'),dependencies=admission['retained_lock'],
                    dependencies_sha256=admission['retained_lock_sha256'],candidate_root=str(candidate),data_root=str(data))
    file=root/'SUSTAINED_DESCRIPTOR.json';pins.exclusive(file,descriptor)
    state,state_sha=transactions.activate(candidate,data,file,pins.sha(file),None,release)
    owner=RuntimeLock(data,'guarded_sustained_gui')
    original=paths.RuntimeLock
    borrowed=dict(opened=0,closed=0)
    raw=(data/'runtime.lock').read_bytes()
    try:
        assert transactions.inspect(candidate)==(state,state_sha)
        pins.check_descriptor(str(file),pins.sha(file),release)
        assert pins.sha(data/'live_config.json')==admission['live_config_sha256']
        assert pins.sha(data/'n2_runtime.json')==admission['n2_runtime_sha256']
    except BaseException:
        owner.close()
        raise
    class Borrow:
        def __init__(self,path,purpose):
            if Path(path).resolve()!=data.resolve() or purpose!='application' or borrowed['opened']:
                raise RuntimeError('Invalid application lease borrower')
            assert (data/'runtime.lock').read_bytes()==raw
            self.closed=False;borrowed['opened']+=1
        def close(self):
            if not self.closed:self.closed=True;borrowed['closed']+=1
    paths.RuntimeLock=Borrow
    def check():
        assert (data/'runtime.lock').read_bytes()==raw
        assert transactions.inspect(candidate)[1]==state_sha
        return dict(token=owner.token,pid=json.loads(raw)['pid'],state_sha256=state_sha,borrowed=dict(borrowed))
    def close():
        final=check()
        paths.RuntimeLock=original
        owner.close()
        assert not (data/'runtime.lock').exists()
        return dict(final,released=True)
    return check,close
