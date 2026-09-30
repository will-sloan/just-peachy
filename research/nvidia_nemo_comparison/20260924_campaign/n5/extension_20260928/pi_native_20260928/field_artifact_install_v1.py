"""Installed artifact binding, no inference/capture; README_FIELD_ARTIFACT_INSTALL_V1.md."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import threading


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)


def build(root,a):
    prior=Path(a['installed_release']);source=root/'source'
    assert {p.relative_to(prior).as_posix():sha(p) for p in prior.rglob('*') if p.is_file()}==a['installed_files']
    shutil.copytree(prior,source,ignore=shutil.ignore_patterns('__pycache__'))
    mapping={**{f'artifact_limits_v1/app/{name}':f'app/{name}' for name in
                ['bounded_live_artifacts_v1.py','app_bounded_artifacts_v1.py','sessions.py','pipeline.py']},
             'controller_artifact_v1.py':'app/controller.py',
             'field_entry_artifact_v1.py':'native/field_entry_v5.py',
             'field_archive_v3.py':'native/field_archive_v3.py',
             'field_artifact_limits_v1.py':'native/field_artifact_limits_v1.py',
             'field_artifact_binding_v1.py':'native/field_artifact_binding_v1.py',
             'ARTIFACT_LIMITS_V1.json':'config/artifact_limits.json',
             'README_FIELD_ARTIFACT_INSTALL_V1.md':'docs/README_FIELD_ARTIFACT_INSTALL_V1.md',
             'README_FIELD_ARTIFACT_LIMITS_V2.md':'docs/README_FIELD_ARTIFACT_LIMITS_V2.md'}
    for original,destination in mapping.items():shutil.copyfile(root/original,source/destination)
    from field_artifact_limits_v1 import load,digest,planned_bytes
    limits=load(source/'config/artifact_limits.json',sha(root/'ARTIFACT_LIMITS_V1.json'))
    contract=json.loads((source/'config/field_contract.json').read_text())
    assert 'artifact_limits' not in contract and contract['session_reservation_bytes']==64*1024**2
    contract['artifact_limits']=dict(file='config/artifact_limits.json',sha256=sha(source/'config/artifact_limits.json'),
                                   canonical_sha256=digest(limits),maximum_artifact_bytes=planned_bytes(limits))
    (source/'config/field_contract.json').write_text(json.dumps(contract,indent=2))
    sys.path.insert(0,str(source))
    from release_tools import release
    built=release.build(source,root/'archives','b01-offline-20260930-v11')
    staged=release.stage(built['archive'],root/'deployment',built['sha256'])
    selected=Path(staged['path']);manifest=release.verify_release(selected)
    assert manifest['version']=='b01-offline-20260930-v11'
    for original,destination in mapping.items():assert sha(root/original)==sha(selected/destination)
    changed={p.relative_to(selected).as_posix():sha(p) for p in selected.rglob('*') if p.is_file() and
             (not (prior/p.relative_to(selected)).is_file() or sha(p)!=sha(prior/p.relative_to(selected)))}
    save(root/'CANDIDATE_BUILD.json',dict(built=built,staged=staged,manifest_sha256=sha(selected/'RELEASE_MANIFEST.json'),
         mapping=mapping,changed=changed,contract=contract,pointer_activated=False,assets_copied=False))
    sys.path.remove(str(source))
    for name in list(sys.modules):
        if name=='release_tools' or name.startswith('release_tools.') or name=='field_artifact_limits_v1':del sys.modules[name]
    return selected


def run(root,a):
    selected=build(root,a)
    sys.path[:0]=[str(selected),str(selected/'vendor'),str(selected/'native')]
    from native import field_entry_v5 as entry
    from field_artifact_limits_v1 import digest,resolved,planned_bytes
    from release_tools.runtime_lock import RuntimeLock
    from app import paths
    assert entry.ROOT.resolve()==selected.resolve()==paths.ROOT.resolve()
    import field_artifact_limits_v1 as limits_module
    assert Path(limits_module.__file__).resolve()==selected/'native/field_artifact_limits_v1.py'
    data=root/'data';preserved={p.name:sha(p) for p in data.iterdir() if p.is_file()}
    owner=RuntimeLock(data,'installed_artifact_binding');original=paths.RuntimeLock
    raw=(data/'runtime.lock').read_bytes();borrowed=dict(opened=0,closed=0)
    class Borrow:
        def __init__(self,path,purpose):
            if Path(path).resolve()!=data.resolve() or purpose!='application' or borrowed['opened']:
                raise RuntimeError('Invalid single application lease borrower')
            assert (data/'runtime.lock').read_bytes()==raw
            self.token=owner.token;self.closed=False;borrowed['opened']+=1
        def close(self):
            if not self.closed:self.closed=True;borrowed['closed']+=1
    paths.RuntimeLock=Borrow
    controller=None;archive=None;writer=None;cases=[]
    def reject(name,function):
        try:function()
        except (ValueError,FileNotFoundError,RuntimeError,KeyError) as exc:
            row=dict(name=name,error=type(exc).__name__+': '+str(exc),rejected=True)
            save(root/(name+'.json'),row);cases.append(row)
        else:raise AssertionError('Expected rejection: '+name)
    try:
        contract,limits=entry.artifact_contract()
        # Small config-only fixtures enter the real installed create_controller preflight.
        # They are deliberately not complete valid release trees and do not exercise asset health.
        for label in ['missing-binding','missing-file','wrong-file-hash','wrong-canonical-hash','short-frame-bound','small-reservation','wrong-path']:
            fixture=root/label;(fixture/'config').mkdir(parents=True)
            doc=json.loads(json.dumps(contract));cfg=dict(limits)
            if label=='missing-binding':doc.pop('artifact_limits')
            if label=='wrong-file-hash':doc['artifact_limits']['sha256']='0'*64
            if label=='wrong-canonical-hash':doc['artifact_limits']['canonical_sha256']='0'*64
            if label=='wrong-path':doc['artifact_limits']['file']='../artifact_limits.json'
            if label=='small-reservation':doc['session_reservation_bytes']=1
            if label=='short-frame-bound':cfg['pcm_max_frames']=960000
            if label!='missing-file':
                save(fixture/'config/artifact_limits.json',cfg)
                if label not in ('missing-binding','wrong-file-hash'):
                    doc['artifact_limits']['sha256']=sha(fixture/'config/artifact_limits.json')
                if label=='short-frame-bound':
                    doc['artifact_limits']['canonical_sha256']=digest(cfg)
                    doc['artifact_limits']['maximum_artifact_bytes']=planned_bytes(cfg)
            save(fixture/'config/field_contract.json',doc)
            entry.ROOT=fixture
            try:reject(label,lambda:entry.create_controller(fixture/'must-not-create-data'))
            finally:entry.ROOT=selected
            assert not (fixture/'must-not-create-data').exists() and borrowed['opened']==0
        health=entry.health();save(root/'INSTALLED_HEALTH.json',health)
        assert health['artifact_limits']==limits and not health['models_loaded'] and not health['capture_opened']
        controller=entry.create_controller(data)
        assert controller.engine is None and controller.state=='IDLE'
        assert controller.models.asr_loads==controller.models.speaker_loads==0
        assert controller.session_store.policy['artifact_limits']==limits
        assert (data/'runtime.lock').read_bytes()==raw and borrowed==dict(opened=1,closed=0)
        from app.pipeline import effective_profile
        profile=effective_profile(controller.recipe,controller.mode,controller.tap,controller._effective_identity_overrides(),controller.seats.strength)
        gallery=controller.store.gallery(controller.route(),None,alternate_advisory=False)
        original_policy=controller.session_store.policy['artifact_limits']
        controller.session_store.policy['artifact_limits']=resolved()
        try:
            reject('conflicting-store-before-engine',lambda:controller._create_epoch_engine(profile,gallery,None))
            assert controller.engine is None and not (data/'sessions').exists()
        finally:controller.session_store.policy['artifact_limits']=original_policy
        engine=controller._create_epoch_engine(profile,gallery,None)
        assert type(engine).__name__=='N2Engine' and engine.artifact_limits==limits
        assert engine.archive is None and controller.models.asr_loads==controller.models.speaker_loads==0
        # Actual factory used by production _start_session, no start_xvf/start_file/begin calls.
        writer=engine._open_journal_text(root/'native-factory/events.jsonl')
        assert writer.artifact_limits==limits and writer.byte_limit==16*1024**2
        writer.write(json.dumps(dict(kind='installed_artifact_binding',synthetic_no_capture=True)))
        writer.close();native=writer.closure_receipt();assert native['clean'] and native['accepted']==native['completed']==1
        identifier=controller.session_store.new(audio=True,consent=True,title='Empty artifact binding fixture; no recording')
        archive=controller.session_store.begin(identifier,dict(synthetic_no_capture=True))
        engine.archive=archive  # Same attachment order as production controller, after explicit constructor binding.
        assert archive.artifact_limits==engine.artifact_limits==limits
        assert archive.offer('events',json.dumps(dict(kind='installed_artifact_binding',synthetic_no_capture=True)).encode())
        receipt=controller.session_store.ended(identifier,archive)
        meta=json.loads((archive.path/'epoch.json').read_text())
        assert not receipt['worker_alive'] and meta['state']=='CLOSED' and not meta['archive_error']
        assert meta['artifact_metrics']['events']['byte_limit']==16*1024**2
        assert meta['artifact_metrics']['audio']['max_frames']==2080000 and meta['recorded_samples']==0
        assert (archive.path/'model_input.wav').stat().st_size==44 and (archive.path/'model_input.f32le').stat().st_size==0
        assert not (data/'source_receipts').exists() and not (data/'sessions').exists()
        assert controller.models.asr_loads==controller.models.speaker_loads==0
        result=dict(status='PASS_INSTALLED_ARTIFACT_CONTRACT_AND_NATIVE_FACTORY_ONLY',rejections=cases,
                    installed_release=str(selected),manifest_sha256=sha(selected/'RELEASE_MANIFEST.json'),
                    contract_sha256=sha(selected/'config/field_contract.json'),artifact_limits=limits,
                    store_policy=controller.session_store.policy,native_factory=native,archive_metadata=meta,
                    archive_path=str(archive.path),engine_type=type(engine).__name__,constructor_received_before_archive=True,
                    health_status=health['status'],model_loads=0,capture=False,GUI=False,empty_wav_is_recording=False,
                    pipeline_start_called=False,source_boundaries_executed=False,pointer_activated=False,lease_token=owner.token)
    finally:
        entry.ROOT=selected
        if writer is not None and not writer.closed:writer.close()
        if archive is not None and archive.thread.is_alive():archive.close()
        if controller is not None:
            if not controller.closed:controller.close()
            controller.commands.join();controller.worker.join(10)
            assert controller.closed and not controller.worker.is_alive()
        assert (data/'runtime.lock').read_bytes()==raw
        paths.RuntimeLock=original;owner.close()
        assert not (data/'runtime.lock').exists()
        save(root/'OWNERSHIP_CLOSURE.json',dict(borrowed=borrowed,outer_released=True,controller_closed=bool(controller and controller.closed),
            worker_joined=bool(controller and not controller.worker.is_alive()),pending_commands=controller.commands.unfinished_tasks if controller else None))
    assert borrowed==dict(opened=1,closed=1)
    for name,h in preserved.items():assert sha(data/name)==h
    assert all(sha(Path(a['installed_release'])/name)==h for name,h in a['installed_files'].items())
    assert not any(t.name in ('bounded-event-journal','proto-session-archive','proto-controller') for t in threading.enumerate())
    result.update(original_release_unchanged=True,private_configs_unchanged=True,ownership_closed=True)
    return result
