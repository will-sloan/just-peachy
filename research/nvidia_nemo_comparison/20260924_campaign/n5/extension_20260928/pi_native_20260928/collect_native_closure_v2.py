"""Read-only closure census. See README_COLLECT_NATIVE_CLOSURE_V2.md."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import psutil
from dispatch_geometry_v2 import remote, PRIVATE, LOCAL, REMOTE


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--version', type=int, required=True)
    args = p.parse_args()
    assert args.version > 0
    psutil.Process().cpu_affinity([14])
    paths = [PRIVATE/f'NATIVE_{kind}_V{args.version}.json' for kind in ('CLOSURE', 'RESOURCES')]
    assert not any(path.exists() for path in paths), 'Preserve existing receipts'
    worker = json.loads((LOCAL/'supervision/worker.json').read_text())
    assert worker['status'] == 'COMPLETED'
    host_owners = []
    for pid_key, time_key in [('pid', 'create_time'), ('child_pid', 'child_create_time')]:
        try:
            observed = psutil.Process(worker[pid_key]).create_time()
        except psutil.NoSuchProcess:
            observed = None
        assert observed is None or abs(observed-worker[time_key]) > .001
        host_owners.append(dict(pid=worker[pid_key], create_time=worker[time_key], observed_create_time=observed, exact_alive=False))
    x = remote('ROOT='+repr(REMOTE)+'\n'+r'''
import os,json,hashlib,subprocess,shutil,fcntl
from pathlib import Path
from datetime import datetime,timezone
os.sched_setaffinity(0,{3});r=Path(ROOT)
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='af9c6c63-3c54-42c5-8f79-6fbce3fe7d43'
assert 'Compute Module 5' in Path('/proc/device-tree/model').read_text()
def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
owners=[]
for p in sorted(r.rglob('*OWNER*.json')):
 o=json.loads(p.read_text());t=ticks(o['pid']);assert not(o['boot_id']==boot and t==o['start_ticks'])
 owners.append(dict(path=str(p),owner=o,observed_start_ticks=t,exact_alive=False))
units=subprocess.check_output(['systemctl','--user','list-units','--state=active,activating,deactivating','--no-legend','jp-*'],text=True)
assert not units.strip() and ticks(1013)==569 and ticks(1130)==607
install=sha(Path.home()/'JustPeachy/install/current.json');config=sha(Path.home()/'JustPeachy/data/live_config.json')
assert install=='fbf4f9847cacac4e061523476a3c9567909e88a17177d3166161ffc1e89461c3'
assert config=='568dd48e4dbb189f643014eb46d58d7f3e91e185081a2d8a7a6fe112d798d395'
capture=Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip();assert capture=='closed'
for lock in [r/'B05_PREVIEW_DISPATCH.lock',Path.home()/'JustPeachy/data/xvf-hardware.lock']:
 with lock.open('r+b') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(f,fcntl.LOCK_UN)
available=next(int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
swap={k:int(v) for k,v in (l.split() for l in Path('/proc/vmstat').read_text().splitlines()) if k in ['pswpin','pswpout']}
print(json.dumps(dict(checked_utc=datetime.now(timezone.utc).isoformat(),boot_id=boot,owners=owners,units=units,original_app=[dict(pid=1013,start_ticks=569),dict(pid=1130,start_ticks=607)],install_sha256=install,live_config_sha256=config,capture=capture,hardware_lease_free=True,research_lease_free=True,available_ram_bytes=available,target_free_bytes=shutil.disk_usage(r).free,target_bytes=int(subprocess.check_output(['du','-sb',str(r)],text=True).split()[0]),swap=swap,page_size=os.sysconf('SC_PAGE_SIZE'),temperature_c=int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000,throttle=subprocess.check_output(['vcgencmd','get_throttled'],text=True).strip())))
''')
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from window_guard import payload_inventory
    used = 0
    for relative in ['n5/prepi-20260928', 'releases/prepi-shutdown-v1', 'n5/listening-examples-v1', 'n5/research-extension-20260928']:
        inv = payload_inventory(LOCAL/relative)
        assert not inv['errors'] and not inv['reparse_not_traversed']
        used += inv['total_logical_bytes']
    free = {drive: shutil.disk_usage(drive+'/').free for drive in ['C:', 'G:']}
    resources = dict(checked_utc=x['checked_utc'],host_window_bytes=used,target_bytes=x['target_bytes'],combined_bytes=used+x['target_bytes'],cap_bytes=json.loads((Path(__file__).parent.parent/'WINDOW_V2.json').read_text())['maximum_new_output_bytes'],host_free_bytes=free,all_owned_native_identities_closed=len(x['owners']),host_supervisor_closed=True,host_owners=host_owners)
    assert free['C:'] >= 50*1024**3 and free['G:'] >= 75*1024**3
    assert resources['combined_bytes'] < resources['cap_bytes']
    for path, data in zip(paths, [x, resources]):
        with path.open('x', encoding='utf-8') as f: json.dump(data, f, indent=2)
    print(json.dumps(resources))


if __name__ == '__main__':
    main()
