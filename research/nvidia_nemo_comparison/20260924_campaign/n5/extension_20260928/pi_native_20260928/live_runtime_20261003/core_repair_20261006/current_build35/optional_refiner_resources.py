"""One-Hz whole-cgroup physical guard; README_OPTIONAL_REFINER.md."""
import json
from pathlib import Path
import time

MIB=1024**2


def snapshot(unit):
    lines=Path('/proc/self/cgroup').read_text().splitlines()
    if len(lines)!=1 or not lines[0].startswith('0::') or not lines[0].endswith('/'+unit):
        raise RuntimeError('Exact unified owned cgroup required for combined memory')
    root=Path('/sys/fs/cgroup')/lines[0][3:].lstrip('/')
    pids=[int(value) for value in (root/'cgroup.procs').read_text().split()]
    if not 1<=len(pids)<=64:raise RuntimeError('Combined process count exceeds admitted envelope')
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    rss=pss=virtual=swap=0;owners=[]
    for pid in pids:
        try:
            start=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
            status=dict(line.split(':',1) for line in Path('/proc',str(pid),'status').read_text().splitlines() if ':' in line)
            roll=dict(line.split(':',1) for line in Path('/proc',str(pid),'smaps_rollup').read_text().splitlines() if ':' in line)
            one=dict(pid=pid,start_ticks=start,boot_id=boot,
                rss_bytes=int(status.get('VmRSS','0').split()[0])*1024,
                pss_bytes=int(roll['Pss'].split()[0])*1024,
                virtual_bytes=int(status.get('VmSize','0').split()[0])*1024,
                swap_bytes=int(status.get('VmSwap','0').split()[0])*1024)
            rss+=one['rss_bytes'];pss+=one['pss_bytes'];virtual+=one['virtual_bytes'];swap+=one['swap_bytes'];owners.append(one)
        except (FileNotFoundError,ProcessLookupError):continue
    mem=dict(line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
    cpu=dict(line.split() for line in (root/'cpu.stat').read_text().splitlines())
    return dict(at_monotonic=time.monotonic(),scope='whole_owned_cgroup',unit=unit,control_group=lines[0][3:],
        whole_unit_rss_bytes=rss,whole_unit_pss_bytes=pss,whole_unit_virtual_bytes=virtual,whole_unit_swap_bytes=swap,
        physical_ram_bytes=int(mem['MemTotal'].split()[0])*1024,available_ram_bytes=int(mem['MemAvailable'].split()[0])*1024,
        cgroup_cpu_seconds=int(cpu['usage_usec'])/1000000,owners=owners)


class CombinedResourceGuard:
    def __init__(self,unit,path,limits):
        self.unit,self.path,self.limits=unit,Path(path),limits
        self.last=None;self.bytes=0
    def sample(self):
        now=time.monotonic()
        if self.last is not None and now-self.last['at_monotonic']<1:return self.last
        value=snapshot(self.unit)
        raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()+b'\n'
        if len(raw)>16384 or self.bytes+len(raw)>2*MIB:raise RuntimeError('Combined resource evidence2MiB reservation exhausted')
        with self.path.open('ab') as stream:stream.write(raw)
        self.bytes+=len(raw);self.last=value;return value
    def exceeded(self):
        value=self.sample()
        return (value['available_ram_bytes']<self.limits['available_ram_floor_bytes'] or
                value['whole_unit_rss_bytes']>=self.limits['whole_unit_rss_soft_stop_bytes'])
