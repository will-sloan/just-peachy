"""Native continuation allowance authorized September 29. See README_WINDOW_V2.md."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind, load, verify
from metric_process import exact_process
from guarded_execution_v1 import classify_dispatch
from reservation_census_v1 import admission_paths, epoch, validate_live, validate_supervision
from reservation_census_v2 import read_fixtures
from asr_full_bank import payload_inventory

GIB=1024**3


def window():
    w=load(HERE/'WINDOW_V2.json')
    now=datetime.now(timezone.utc)
    if not datetime.fromisoformat(w['started_utc']) <= now < datetime.fromisoformat(w['checkpoint_utc']):
        raise TimeoutError('User-authorized research window is not active')
    if w['logical_cpus_total']!=2 or w['GPU']!='OFF' or w['Pi_access'] is not True:
        raise ValueError('Window constraints changed')
    return w


def budget(total, window_used, requested, free, allowance):
    if not all(type(x) is int and x>=0 for x in (total,window_used,requested)):
        raise ValueError('Invalid byte counts')
    cap=window()['maximum_new_output_bytes']
    if requested<=0 or window_used+requested>cap:
        raise ValueError('Current authorized window output allowance exceeded')
    if total+requested+int(2.5*GIB)>min(50,allowance)*GIB:
        raise ValueError('Campaign payload allowance/reservations exceeded')
    for drive,floor in (('C:',50),('G:',75)):
        if free[drive]<floor*GIB+requested:
            raise ValueError('Drive floor and output headroom unavailable: '+drive)
    return dict(existing_bytes=total,requested_bytes=requested,retained_reservations_bytes=int(2.5*GIB),
                projected_bytes=total+requested+int(2.5*GIB),window_used_bytes=window_used,
                window_maximum_bytes=cap,physical_bytes_credited=0)


def snapshot(local, requested):
    w=window();local=Path(local);n4=HERE.parent.parent/'n4'
    worker=load(local/'supervision/worker.json');spec=load(local/'supervision/worker_spec.json')
    before=epoch(worker,spec)
    fixture=load(n4/'RESERVATION_CENSUS_FIXTURES_V2.json')['manifest']
    fixtures=read_fixtures(fixture,local);paths=admission_paths(local/'n4')
    if not set(fixtures).issubset(paths):raise ValueError('A preserved fixture disappeared')
    records=[fixtures[p] if p in fixtures else classify_dispatch(p,local) for p in paths]
    active=[validate_live(r,local) for r in records if r['state']=='ACTIVE']
    if active:raise RuntimeError('Active allocation exists; do not duplicate it')
    supervision=validate_supervision(worker,spec,active)
    inventory=payload_inventory(local)
    if inventory['errors']:raise RuntimeError('Incomplete physical inventory')
    # The unchanged physical inventory deliberately does not traverse existing
    # WSL venv links. Match the previously admitted six paths; no new link may
    # obtain this exemption by merely appearing under a similarly named folder.
    prior=load(local/'n5/d1-anonymous-lifecycle-parent-v4/ADMISSION.json')['census']
    verify(prior)
    retained_links=load(prior['path'])['inventory']['reparse_not_traversed']
    if set(inventory['reparse_not_traversed'])!=set(retained_links):
        raise RuntimeError('Shared reparse inventory changed; explicit review required')
    used=0
    for root in (local/'n5/prepi-20260928',local/'releases/prepi-shutdown-v1',
                 local/'n5/listening-examples-v1',local/'n5/research-extension-20260928'):
        if root.exists():
            item=payload_inventory(root)
            if item['errors'] or item['reparse_not_traversed']:
                raise RuntimeError('New-window output contains unadmitted links')
            used+=item['total_logical_bytes']
    policy=bind(local/'supervision/campaign.json');old=load(policy['path'])
    free={d:shutil.disk_usage(d+'/').free for d in ('C:','G:')}
    calculation=budget(inventory['total_logical_bytes'],used,requested,free,old['resource_policy']['new_payload_allowance_gib'])
    for record in records:
        for b in record['dependencies']:verify(b)
        if record['state']=='CLOSED_OWNER' and exact_process(record['owner']) is not None:
            raise RuntimeError('Previously closed owner changed')
        if record['state']=='NON_EXECUTION_FIXTURE' and exact_process(record['parent_owner']) is not None:
            raise RuntimeError('Fixture parent is active')
    if epoch(load(local/'supervision/worker.json'),load(local/'supervision/worker_spec.json'))!=before:
        raise RuntimeError('Supervisor changed during census')
    if admission_paths(local/'n4')!=paths:raise RuntimeError('Admission set changed')
    verify(policy);window()
    return dict(scope='USER_AUTHORIZED_NATIVE_CONTINUATION_V2',window=bind(HERE/'WINDOW_V2.json'),
        original_campaign_policy_preserved=policy,inventory=inventory,calculation=calculation,
        prior_reparse_inventory=prior,retained_reparse_paths=retained_links,
        free_bytes=free,records=records,active_allocations=active,supervisor=supervision,
        original_deadline_extended=False,new_window_checkpoint=w['checkpoint_utc'],
        worker_execution_authorized=False,whole_host_idle_proved=False)
