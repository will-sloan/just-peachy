"""Independent closed-worker review and small exact backup. See corresponding README."""
import psutil
psutil.Process().cpu_affinity([14])
import json
from pathlib import Path
import field_host_budget_v1 as h


def main():
    root=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-host-budget-v1-evidence')
    s=h.HostStore(root/'host')
    a=json.loads((s.root/'metadata/ADMISSION.json').read_bytes())
    for b in a['bindings']+a['backup_inputs']:
        assert h.digest(Path(b['path']).read_bytes())==b['sha256']
    owner=json.loads((s.root/'metadata/REGISTERED_OWNER.json').read_bytes())['owner']
    try: observed=psutil.Process(owner['pid']).create_time()
    except psutil.NoSuchProcess: observed=None
    assert observed is None or abs(observed-owner['create_time'])>.001
    result=json.loads((s.root/'metadata/RESULT.json').read_bytes())
    launch=json.loads((s.root/'metadata/LAUNCH.json').read_bytes())
    assert result['status']=='PASS_HOST_METADATA_AND_SMALL_BACKUP_ONLY' and result['case_count']==19
    assert result['affinity']==[14] and launch['logical_success']
    life=launch['lifetime']
    assert life['root_exit_code']==0 and life['job_empty_verified'] and life['observed_members_exited'] and not life['forced']
    assert life['input_desktop_before']==life['input_desktop_after']
    partial=root/'fixtures/partial'
    raw=(partial/'failure/worker.raw').read_bytes()
    assert (partial/'metadata/RESULT.json.pending').read_bytes()==raw[:3]
    assert not (partial/'metadata/RESULT.json').exists() and not (partial/'metadata/REVIEW.json').exists()
    # Preserve all small fixture files in an independently hash-verified private copy.
    # This is a closed-run exact batch, not a model/release or target recollection.
    batch={}
    for p in (root/'fixtures').rglob('*'):
        if p.is_file() and p.name!='.host.guard':
            # Raw pending evidence is a payload with an explicit safe backup name.
            name=p.relative_to(root/'fixtures').as_posix().replace('.pending','.partial-evidence')
            batch[name]=p.read_bytes()
    # The small backup interface deliberately has only eight directories; fixture
    # snapshots are flattened with unambiguous separators after collision checks.
    flat={name.replace('/','__'):raw for name,raw in batch.items()}
    assert len(flat)==len(batch)
    backup=h.publish_backup(s,root/'verified-fixture-backup',flat)
    review={'status':result['status'],'case_count':19,'exact_owner_dead':True,'owner':owner,
            'natural_exit':0,'seconds':result['seconds'],'rss_bytes':result['rss_bytes'],
            'backup_files':len(flat),'backup_bytes':backup['bytes'],
            'partial_filename_mapping':{name:name.replace('/','__') for name in batch},
            'limits':'Windows cooperating writers only; no Pi/live/full-capsule qualification',
            'file_inventory':{str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=h.digest(p.read_bytes()))
                              for p in root.rglob('*') if p.is_file()}}
    s.json('REVIEW.json',review)
    s.json('review-closure.json',{'logical_success':True,'exact_owner_dead':True,'backup_verified':True})
    print(json.dumps({k:v for k,v in review.items() if k not in ('file_inventory','partial_filename_mapping')}))


if __name__=='__main__':main()
