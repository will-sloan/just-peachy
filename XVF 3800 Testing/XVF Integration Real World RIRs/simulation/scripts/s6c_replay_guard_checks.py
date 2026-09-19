"""Verify native-replay failure coverage and semantic resume guards. README_S6C_REPLAY_GUARD_CHECKS.md."""
from copy import deepcopy
from s6c_common import *
from s6c_native_replay_v3 import canonical,differences,run

def checks():
    root=REPORT/'replay_guard_checks/v1';root.mkdir(parents=True,exist_ok=False)
    logical=dict(decisions=[dict(anonymous_label='Speaker_1',available_at_sec=4.2,identity_compute_sec=.001)],
        snapshot=dict(scheduler=dict(policy_total_sec=.01,identity=dict(policy_compute_sec=.02,gallery=dict(loaded_elapsed_sec=.03)))))
    timing=deepcopy(logical);timing['decisions'][0]['identity_compute_sec']=9.
    timing['snapshot']['scheduler']['policy_total_sec']=8.;timing['snapshot']['scheduler']['identity']['policy_compute_sec']=7.
    timing['snapshot']['scheduler']['identity']['gallery']['loaded_elapsed_sec']=6.
    assert not differences(canonical(logical),canonical(timing))
    labels=deepcopy(timing);labels['decisions'][0]['anonymous_label']='Speaker_2'
    assert differences(canonical(logical),canonical(labels))
    clocks=deepcopy(timing);clocks['decisions'][0]['available_at_sec']=4.3
    assert differences(canonical(logical),canonical(clocks))
    source=REPORT/'jobs/epoch1/smoke_v1_RESULTS.json';fixture=deepcopy(read(source))
    fixture.update(status='PARTIAL_RESUMABLE',completed=0,fixture_only=True,original_successful_source=bind(source))
    for row in fixture['rows']:
        row['status']='FAILED';row['error']='MODEL_FREE_SYNTHETIC_FAILURE_COVERAGE_FIXTURE'
    fixture_path=root/'ALL_FAILED_FIXTURE.json';save(fixture_path,fixture,immutable=True)
    first=run('epoch1',[fixture_path],'guard_fixture_all_failed_v1')
    second=run('epoch1',[fixture_path],'guard_fixture_all_failed_v1')
    assert first['status']==second['status']=='PARTIAL_RESUMABLE' and first['requested']==second['requested']==6
    assert first['completed']==second['completed']==0
    index=read(REPORT/'epoch1/guard_fixture_all_failed_v1_PREDICTION_INDEX.json')
    assert len(index['rows'])==6 and all(r['status']=='FAILED' and 'result' not in r for r in index['rows'])
    result=dict(status='PASS',checks=6,actual_new_neural_calls=0,fixture_only=True,
        semantics='Measured duration changes accepted; label/source-availability changes rejected; all six simulated failed rows retained across two resumes',
        helper=bind(SIM/'scripts/s6c_native_replay_v3.py'),test_source=bind(__file__),fixture=bind(fixture_path),utc=utc())
    print(json.dumps(save(root/'CHECK_RECEIPT.json',result),indent=2))

if __name__=='__main__':checks()
