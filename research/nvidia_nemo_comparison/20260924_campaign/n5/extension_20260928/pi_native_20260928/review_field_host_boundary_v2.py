"""Review only changed host boundaries. README_REVIEW_HOST_BOUNDARY_V2.md."""
import psutil
psutil.Process().cpu_affinity([14])
assert psutil.Process().cpu_affinity()==[14]
import json
from pathlib import Path
import field_host_finite_v1 as h


def main():
    root=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-host-boundary-v1-evidence')
    s=h.HostStore(root/'host')
    a=json.loads((s.root/'metadata/ADMISSION.json').read_bytes())
    for b in a['bindings']:
        assert h.digest(Path(b['path']).read_bytes())==b['sha256']
    o=json.loads((s.root/'metadata/REGISTERED_OWNER.json').read_bytes())['owner']
    try: observed=psutil.Process(o['pid']).create_time()
    except psutil.NoSuchProcess: observed=None
    assert observed is None or abs(observed-o['create_time'])>.001
    r=json.loads((s.root/'metadata/RESULT.json').read_bytes())
    launch=json.loads((s.root/'metadata/LAUNCH.json').read_bytes())
    env=json.loads((s.root/'metadata/JOB_ENVELOPE.json').read_bytes())
    assert r['status']=='PASS_CHANGED_HOST_AFFINITY_AND_FINITE_BOUNDARY' and r['case_count']==5
    assert r['early_affinity']==r['end_affinity']==env['suspended_process_affinity']==[14]
    assert env['job_affinity_mask']==1<<14 and env['job_commit_bytes']==512*h.MIB
    assert all(x['affinity']==[14] for x in launch['samples'])
    assert launch['logical_success'] and launch['lifetime']['root_exit_code']==0
    life=launch['lifetime']
    assert life['job_empty_verified'] and life['observed_members_exited'] and life['forced']
    members=[m for event in life['events'] if event['kind']=='job_members_observed' for m in event['members']]
    assert len(members)==1 and Path(members[0]['executable']).name.lower()=='conhost.exe'
    assert members[0]['affinity']==[14] and members[0]['parent_pid']==o['pid']
    for member in members:
        try: observed_member=psutil.Process(member['pid']).create_time()
        except psutil.NoSuchProcess: observed_member=None
        assert observed_member is None or abs(observed_member-member['create_time'])>.001
    assert life['final_job']['active']==0 and life['final_job']['total']==2
    review_note={'review_v1_assertion_failed_before_publication':True,'root_exit_code':0,
        'forced_auxiliary_closure':True,'whole_job_natural_exit':False,'members':members}
    s.failure('review',h.encoded(review_note),AssertionError('V1 no-force assumption rejected actual helper closure'))
    assert launch['lifetime']['input_desktop_before']==launch['lifetime']['input_desktop_after']
    assert not any((root/'fixtures'/n).exists() for n in ('positive','negative-nested','overwritten-key'))
    fixture=root/'fixtures/first-write/metadata/RESULT.json'
    assert fixture.exists() and not fixture.with_suffix('.json.pending').exists()
    backup=h.publish_backup(s,root/'verified-boundary-backup',{
        'finite-fixture.json':fixture.read_bytes(),
        'RESULT.json':(s.root/'metadata/RESULT.json').read_bytes(),
        'JOB_ENVELOPE.json':(s.root/'metadata/JOB_ENVELOPE.json').read_bytes()})
    review=dict(status=r['status'],forced_auxiliary_closure=True,whole_job_natural_exit=False,auxiliary_members=members,review_v1_failure_preserved=True,case_count=5,exact_owner_dead=True,owner=o,natural_exit=0,
        job_affinity=[14],early_and_end_affinity=[14],sampled_rows=len(launch['samples']),
        sampled_peak_rss_bytes=max((x['rss_bytes'] for x in launch['samples']),default=None),
        protocol_seconds=r['seconds'],process_rss_bytes=r['rss_bytes'],backup_files=len(backup['files']),
        backup_bytes=backup['bytes'],original_V82_failure_unchanged=True,old_19_cases_rerun=False,
        limits='Changed Windows host envelope and JSON boundary only; not live integration')
    s.json('REVIEW.json',review)
    s.json('review-closure.json',dict(logical_success=True,exact_owner_dead=True,backup_verified=True,forced_auxiliary_closure=True,whole_job_natural_exit=False))
    print(json.dumps(review))


if __name__=='__main__':main()
