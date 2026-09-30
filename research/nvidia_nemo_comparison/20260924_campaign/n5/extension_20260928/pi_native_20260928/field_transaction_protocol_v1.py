"""Native candidate commit/failure boundaries. See README_FIELD_TRANSACTION_V1.md."""
from pathlib import Path
import shutil
import sys
import field_dependencies_v2 as pins
import field_candidate_transaction_v1 as tx


class InjectedInterruption(RuntimeError):
    pass


def run(root, admission):
    sys.dont_write_bytecode = True
    pins.configure_output(root, admission['target_output_max_bytes'])
    release = Path(admission['installed_release'])
    previous = Path(admission['rollback_release'])
    sys.path.insert(0, str(release))
    from release_tools import release as rt
    deployment = root/'deployment'
    (deployment/'transactions').mkdir(parents=True)
    (deployment/'staged').mkdir()
    data = root/'data'
    data.mkdir()
    rt.write_json(data/'DATA_SCHEMA.json', dict(schema_version=1))
    (data/'private-preservation-canary').write_bytes(b'PRIVATE_SYNTHETIC_CANARY\n')
    shutil.copyfile(root/'LIVE_CONFIG_BACKUP.json', data/'live_config.json')
    preserved = {p.name:pins.sha(p) for p in data.iterdir()}
    descriptors = []
    for candidate in (previous, release):
        manifest = pins.read(candidate/'RELEASE_MANIFEST.json')
        d = dict(schema='just-peachy.retained-deployment.v1', version=manifest['version'],
                 release=str(candidate), resolved_release=str(candidate.resolve()),
                 manifest_sha256=pins.sha(candidate/'RELEASE_MANIFEST.json'),
                 contract_sha256=pins.sha(candidate/'config/field_contract.json'),
                 dependencies=admission['retained_lock'], dependencies_sha256=admission['retained_lock_sha256'],
                 candidate_root=str(deployment), data_root=str(data), original_rc5_activation=False)
        path = root/(manifest['version']+'.deployment.json')
        pins.exclusive(path, d)
        descriptors.append(path)
    def activate(i, expected, **kwargs):
        return tx.activate(deployment, data, descriptors[i], pins.sha(descriptors[i]), expected, rt, **kwargs)
    def tree():
        return {p.relative_to(deployment).as_posix():pins.sha(p) for p in deployment.rglob('*') if p.is_file()}
    results = []
    def rejected(label, fn):
        before = tree()
        try:
            fn()
        except ValueError as exc:
            assert 'quota rejected before publication' in str(exc)
            assert tree() == before
            assert not (data/'runtime.lock').exists()
            results.append(dict(case=label, error=str(exc), before=before, after=tree(), unchanged=True))
        else:
            raise AssertionError('Missing transaction quota rejection')
    first, first_sha = activate(0, None)
    rejected('activation_quota_before_any_candidate_write', lambda:activate(1, first_sha, maximum_additional_bytes=1))
    second, second_sha = activate(1, first_sha)
    rejected('rollback_quota_before_any_candidate_write', lambda:tx.rollback(deployment,data,second_sha,rt,maximum_additional_bytes=1))
    third, third_sha = tx.rollback(deployment, data, second_sha, rt)
    assert third['current'] == first['current'] and third['previous'] == second['current']
    before = tree()
    try:
        activate(1, first_sha)
    except ValueError as exc:
        assert str(exc) == 'Candidate state changed' and tree() == before
        results.append(dict(case='stale_authoritative_state', error=str(exc), unchanged=True))
    else:
        raise AssertionError('Missing stale-state rejection')
    def interrupt(phase):
        def hook(observed, name):
            if observed == phase:
                raise InjectedInterruption(phase+':'+name)
        return hook
    interrupted = []
    for phase in ('before_commit', 'after_commit'):
        before_state, before_sha = tx.inspect(deployment)
        try:
            activate(1, before_sha, fault_hook=interrupt(phase))
        except InjectedInterruption as exc:
            after_state, after_sha = tx.inspect(deployment)
            name = str(exc).split(':')[1]
            assert (deployment/'transactions'/name).is_file()
            if phase == 'before_commit':
                assert after_sha == before_sha and after_state == before_state
                assert (deployment/'staged'/name).is_file()
            else:
                assert after_state['transaction'] == name and after_sha != before_sha
                assert not (deployment/'staged'/name).exists()
            assert not (data/'runtime.lock').exists()
            interrupted.append(dict(phase=phase, transaction=name, prior_sha256=before_sha,
                                    observed_sha256=after_sha, observed_state=after_state,
                                    committed=phase=='after_commit', automatic_retry=False))
        else:
            raise AssertionError('Missing injected interruption')
    # Inspect resolved the committed outcome. A distinct explicit rollback follows;
    # no retry of either interrupted activation is performed.
    recovered, recovered_sha = tx.inspect(deployment)
    final, final_sha = tx.rollback(deployment, data, recovered_sha, rt)
    assert final['current'] == first['current'] and final['previous'] == second['current']
    assert tx.inspect(deployment) == (final, final_sha)
    assert {p.name:pins.sha(p) for p in data.iterdir()} == preserved
    records = list((deployment/'transactions').glob('*.json'))
    staged = list((deployment/'staged').glob('*.json'))
    assert len(records) == 6 and len(staged) == 1
    assert staged[0].name == interrupted[0]['transaction']
    pins.exclusive(root/'TRANSACTION_CASES.json', dict(rejections=results, interruptions=interrupted,
                   first=first, first_sha256=first_sha, second=second, second_sha256=second_sha,
                   third=third, third_sha256=third_sha, final=final, final_sha256=final_sha,
                   immutable_records=len(records), retained_precommit_staged_files=len(staged)))
    return dict(status='PASS_NATIVE_SINGLE_STATE_QUOTA_AND_INJECTED_COMMIT_BOUNDARIES_ONLY',
                dependency_lock_sha256=admission['retained_lock_sha256'], rejections=len(results),
                injected_interruptions=len(interrupted), immutable_records=len(records),
                retained_precommit_staged_files=len(staged), final_state_sha256=final_sha,
                data_unchanged=True, original_baseline_activated=False, assets_copied=False,
                models_loaded=False, capture_opened=False, GUI_opened=False,
                process_kill_test=False, power_loss_test=False, automatic_retry=False)
