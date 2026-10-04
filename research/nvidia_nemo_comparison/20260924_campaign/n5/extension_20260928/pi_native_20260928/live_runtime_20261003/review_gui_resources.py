"""Private numeric review of a closed two-session GUI mirror; README_GUI_RESOURCES.md."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mirror',type=Path,required=True)
    parser.add_argument('--output-root',type=Path,required=True)
    parser.add_argument('--pipeline-only',action='store_true',help='One explicitly named closed saved-input qualification instead of the two-session GUI')
    args=parser.parse_args()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess();kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    times=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in times)):raise ctypes.WinError(ctypes.get_last_error())
    output=args.output_root/('gui-resource-review-'+uuid.uuid4().hex);output.mkdir(parents=True,exist_ok=False)
    with (output/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,affinity_mask=16384,
            creation_filetime=times[0].value,create_time=(times[0].value-116444736000000000)/10000000),stream)
        stream.flush();os.fsync(stream.fileno())
    sys.dont_write_bytecode=True
    import sqlite3
    from storage import _unpack_event
    from runtime_support import encoded,strict,publish,digest
    def bounded(path,cap):
        if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('Bounded regular private review input')
        return path.read_bytes()
    complete=strict(bounded(args.mirror/'MIRROR_COMPLETE.json',65536))
    manifest=strict(bounded(args.mirror/'MIRROR_MANIFEST.json',2*1024**2))
    if (len(manifest)>1024 or sha(encoded(manifest))!=complete['manifest_sha256']
            or not all(complete['closure'].get(key) is True for key in ('closed','exact_owner_gone','cgroup_empty'))
            or complete['closure']['job_exit']['natural_returncode']!=0):raise ValueError('Full natural closed GUI mirror required')
    rows={row['path']:row for row in manifest};root=args.mirror/'closed-output'
    def verified(name,cap=1024**2):
        row=rows[name];path=root/name;raw=bounded(path,cap)
        if len(raw)!=row['identity']['bytes'] or sha(raw)!=row['sha256']:raise ValueError('Mirrored selected metadata changed')
        return raw
    if args.pipeline_only:
        names=[name for name in rows if name.endswith('/worker/RESULT.json')]
        if len(names)!=1:raise ValueError('Exactly one saved qualification worker required')
        gui=dict(sessions=[strict(verified(names[0]))['session_id']])
    else:
        gui=strict(verified('gui/GUI_RESULT.json'))
        if gui['status']!='GUI_PROGRAMMATIC_CHECK_PASSED' or len(gui['sessions'])!=2:raise ValueError('Exact passed two-session workflow required')
    database=root/'data/recordings/history.sqlite3';row=rows['data/recordings/history.sqlite3']
    if database.stat().st_size!=row['identity']['bytes'] or digest(database)!=row['sha256']:raise ValueError('Closed SQLite hash changed')
    keys=('rss','pss_bytes','virtual_bytes','vm_peak_bytes','available_ram','backlog_seconds','temperature_millicelsius','elapsed')
    def ranges(values,names):
        return {key:dict(minimum=min(found),maximum=max(found)) for key in names
                if (found:=[row[key] for row in values if type(row.get(key)) in (int,float)])}
    sessions=[]
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
        for identifier in gui['sessions']:
            worker_name=next(name for name in rows if name.endswith('/worker/RESULT.json') and strict(verified(name))['session_id']==identifier)
            worker=strict(verified(worker_name));closure_name=worker_name.removesuffix('worker/RESULT.json')+'HOST_CLOSURE.json'
            closure=strict(verified(closure_name))
            if (worker['failure'] is not None or worker['logical_cleanup_complete'] is not True
                    or closure.get('returncode')!=0 or closure.get('direct_child_reaped') is not True
                    or closure.get('stdout_reader_joined') is not True or closure['nested_source'].get('closed') is not True):
                raise ValueError('Worker/source closure is incomplete')
            health=[]
            for event in db.execute("SELECT * FROM events WHERE session_id=? AND event_type='health' ORDER BY seq",(identifier,)):
                if len(health)>=1500:raise ValueError('Finite two-session health review')
                health.append(_unpack_event(dict(event)))
            ledger=db.execute('SELECT * FROM metadata_usage WHERE session_id=?',(identifier,)).fetchone()
            stored=dict(db.execute('SELECT * FROM sessions WHERE id=?',(identifier,)).fetchone())
            prefix='data/recordings/sessions/'+identifier+'/';summaries=[name for name in rows if name.startswith(prefix) and name.endswith('/session_summary.json')]
            terminal={}
            if summaries:
                summary=strict(verified(summaries[0]));terminal={key:value for key,value in summary.get('telemetry',{}).items() if type(value) in (int,float,bool)}
            bins=[]
            for start in range(0,360,60):
                values=[row for row in health if type(row.get('elapsed')) in (int,float) and start<=row['elapsed']<start+60]
                if values:bins.append(dict(start_seconds=start,samples=len(values),ranges=ranges(values,keys)))
            physical=closure['nested_source'].get('physical_receipt',{})
            sessions.append(dict(session_id=identifier,input_source=worker['result']['selection']['input_source'],
                status=stored['status'],source_samples=worker['result']['source_samples'],
                combined_paced_eof_wall_seconds=worker['result']['combined_paced_eof_wall_seconds'],
                costs=worker['result']['costs'],health_samples=len(health),health_ranges=ranges(health,keys),minute_bins=bins,
                metadata_ledger=dict(ledger) if ledger is not None else None,
                retained_work_bytes=sum(row['identity']['bytes'] for name,row in rows.items() if name.startswith(prefix+'work/')),
                numeric_final_telemetry=terminal,logical_cleanup_complete=True,worker_reaped=True,source_closed=True,
                source_lag_max_seconds=physical.get('status',{}).get('maximum_source_lag_seconds'),
                source_dropped_frames=physical.get('status',{}).get('dropped_frames'),
                raw_samples=physical.get('raw_capture',{}).get('samples'),
                route_restored=physical.get('integrity',{}).get('restoration_ok')))
    trace_path=args.mirror/'SAMPLED_MEMORY.jsonl';trace_raw=bounded(trace_path,1024**2)
    samples=[strict(line) for line in trace_raw.splitlines()]
    if len(samples)>1024:raise ValueError('Sample trace record bound')
    active=[row for row in samples if row['complete_process_sample'] and row['observed_processes']>0]
    trace_keys=('rss_bytes','pss_bytes','vm_bytes','swap_bytes','system_swap_used_bytes','available_bytes','temperature_c','sampled_unix','observed_processes')
    result=dict(schema='just-peachy.gui-resource-review.v1',mirror=str(args.mirror),
        mirror_manifest_sha256=complete['manifest_sha256'],mirror_files=complete['files'],mirror_bytes=complete['bytes'],
        selected_metadata_sha256={name:row['sha256'] for name,row in rows.items() if name.endswith(('RESULT.json','HOST_CLOSURE.json','history.sqlite3'))},
        sessions=sessions,gui={key:gui[key] for key in ('actions','stop_mode','stop_button_invocations','kept_audio','policy_boundary_observed',
            'replay_waited_for_natural_eof','physical_touch_tested','visual_quality_qualified','desktop_orientation_preserved','live_direction_orientation_checked') if key in gui},
        memory_trace_sha256=sha(trace_raw),memory_samples=len(samples),complete_active_memory_samples=len(active),
        aggregate_sample_ranges=ranges(active,trace_keys),continuous_peak_claimed=False,
        memory_trace_covers_full_live_phase=False,limitations='Late-start sampled aggregate; worker health sampled separately. No speech/identity accuracy or hour qualification.',
        native_executed_by_review=False,audio_or_transcript_displayed=False)
    publish(output/'REVIEW.json',result,cap=2*1024**2)
    print(encoded(dict(output=str(output),sessions=sessions,aggregate_sample_ranges=result['aggregate_sample_ranges'],memory_samples=len(samples))).decode())


def sha(raw):return hashlib.sha256(raw).hexdigest()


if __name__=='__main__':main()
