"""Identity-bound read-only process-tree measurements. See README_RESOURCES.md."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import time
from common import freeze,bind


def identity(process):
    return dict(pid=process.pid,create_time=process.create_time())


def process_tree(pid,created):
    import psutil
    try:
        root=psutil.Process(pid)
        if abs(root.create_time()-created)>.001:
            return dict(status='PID_REUSED',processes=[])
        processes=[root]+root.children(recursive=True)
    except psutil.NoSuchProcess:
        return dict(status='EXITED',processes=[])
    rows=[]
    for process in processes:
        try:
            info=process.memory_info()._asdict()
            full=process.memory_full_info()._asdict()
            rows.append(dict(**identity(process),ppid=process.ppid(),
                memory_info_bytes=info,unique_set_size_bytes=full.get('uss'),
                proportional_set_size_bytes=full.get('pss'),threads=process.num_threads(),
                cpu_seconds=dict(user=process.cpu_times().user,system=process.cpu_times().system)))
        except psutil.NoSuchProcess:
            rows.append(dict(pid=process.pid,status='EXITED_DURING_SAMPLE'))
        except psutil.AccessDenied:
            rows.append(dict(pid=process.pid,status='UNAVAILABLE_ACCESS_DENIED'))
    valid=[r for r in rows if 'memory_info_bytes' in r]
    return dict(status='ALIVE',processes=rows,
        all_process_samples_complete=len(valid)==len(rows),
        unique_set_size_sum_bytes=sum(r['unique_set_size_bytes'] for r in valid)
            if valid and all(r['unique_set_size_bytes'] is not None for r in valid) else None,
        rss_sum_bytes_not_unique_physical=sum(r['memory_info_bytes']['rss'] for r in valid) if valid else None,
        private_commit_sum_bytes=sum(r['memory_info_bytes']['private'] for r in valid)
            if valid and all('private' in r['memory_info_bytes'] for r in valid) else None)


def gpu_snapshot():
    def query(fields,kind):
        argv=['nvidia-smi','--query-'+kind+'='+fields,'--format=csv,noheader,nounits']
        try:
            result=subprocess.run(argv,capture_output=True,text=True,timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            return dict(exit_code=result.returncode,raw=result.stdout.strip(),error=result.stderr.strip())
        except (OSError,subprocess.TimeoutExpired) as exc:
            return dict(status='UNAVAILABLE',reason=type(exc).__name__)
    return dict(device_wide=query('index,memory.used,memory.total,utilization.gpu','gpu'),
        process_usage=query('pid,used_memory','compute-apps'),
        allocated_bytes=None,reserved_bytes=None,
        limitation='nvidia-smi device usage is not model allocator allocated/reserved; WDDM N/A stays unavailable')


def planning_tier(accounted_application_bytes, *, controlled_whole_stack, cpu_paced_pass):
    if not controlled_whole_stack or accounted_application_bytes is None:
        return dict(tier='UNKNOWN',target_qualified=False,reason='Complete controlled application memory missing')
    if type(accounted_application_bytes) is not int or accounted_application_bytes<0:
        raise ValueError('Expected measured nonnegative byte count')
    gib=1024**3
    envelope=1.5*gib
    tier=('2GB_PLANNING_CANDIDATE' if accounted_application_bytes<=envelope else
          '4GB_PLANNING_CANDIDATE' if accounted_application_bytes<=3.0*gib else
          '8GB_OR_DESKTOP_ONLY')
    return dict(tier=tier,target_qualified=False,application_envelope_2gb_bytes=int(envelope),
        os_display_audio_reserve_2gb_bytes=int(.5*gib),cpu_paced_pass=cpu_paced_pass,
        deployable=False,reason='Host planning only; Pi off. CPU throughput and total physical device RAM unqualified.')


def main(args):
    import psutil
    process=psutil.Process();process.cpu_affinity([4])
    if os.name=='nt':process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    if not 0<args.seconds<=3600 or not .1<=args.interval<=10:
        raise ValueError('Bounded duration and sampling interval required')
    args.output.mkdir(parents=True,exist_ok=False)
    records=[];start=time.perf_counter();deadline=start+args.seconds
    with (args.output/'SAMPLES.jsonl').open('x',encoding='utf-8') as stream:
        while time.perf_counter()<deadline:
            began=time.perf_counter()
            row=dict(elapsed_seconds=began-start,utc=datetime.now(timezone.utc).isoformat(),
                     process_tree=process_tree(args.pid,args.created))
            if args.gpu:row['gpu']=gpu_snapshot()
            row['sample_duration_seconds']=time.perf_counter()-began
            stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush();records.append(row)
            if row['process_tree']['status']!='ALIVE':break
            time.sleep(max(0,args.interval-(time.perf_counter()-began)))
    def peak(field):
        values=[r['process_tree'].get(field) for r in records]
        return max((v for v in values if v is not None),default=None)
    result=dict(status='ACTUALLY_SAMPLED',platform=os.name,target=dict(pid=args.pid,create_time=args.created),
        samples=len(records),scope='HOST_PROCESS_TREE_OBSERVATION_NOT_CONTROLLED_MODEL_BENCHMARK',
        sampled_peak_uss_bytes=peak('unique_set_size_sum_bytes'),
        sampled_peak_rss_sum_not_unique_physical=peak('rss_sum_bytes_not_unique_physical'),
        sampled_peak_private_commit_bytes=peak('private_commit_sum_bytes'),
        target_exit_observed=records[-1]['process_tree']['status']!='ALIVE' if records else False,
        interval_seconds=args.interval,maximum_sample_duration_seconds=max((r['sample_duration_seconds'] for r in records),default=None),
        limitations=['sampling may miss peaks','USS omits shared runtime/weights',
                     'Windows private commit is distinct from resident memory','WSL/cgroup accounting not inferred',
                     'no cold-load attribution or model allocator information inferred'],
        evidence=bind(args.output/'SAMPLES.jsonl'),code=bind(__file__))
    freeze(args.output/'RESULT.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pid',type=int,required=True);p.add_argument('--created',type=float,required=True)
    p.add_argument('--seconds',type=float,default=60);p.add_argument('--interval',type=float,default=1)
    p.add_argument('--gpu',action='store_true');p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
