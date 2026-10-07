"""Read-only build30 hour review. See README_CORE_BUILD30_HELPERS.md.

Derivative of review_full_app_hour.py SHA1b9e4f4ede3b3c4af60790fe79511ec90f4d61068f4afaf3b99392a1b0324f51.
"""
import argparse
import ast
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid


class Stats:
    """Constant-memory descriptive totals from the retained numeric reviewer."""
    def __init__(self):
        self.count=0;self.total=0.;self.minimum=self.maximum=self.first=self.last=None
    def add(self,value):
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Finite exact numeric measurement required')
        if not self.count:self.first=self.minimum=self.maximum=value
        self.count+=1;self.total+=value;self.last=value
        self.minimum=min(self.minimum,value);self.maximum=max(self.maximum,value)
    def result(self):
        return dict(count=self.count,first=self.first,last=self.last,min=self.minimum,max=self.maximum,
            mean=self.total/self.count if self.count else None)


def early(root):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p;handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    values=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in values)):raise ctypes.WinError(ctypes.get_last_error())
    output=Path(root)/('full-app-hour-review-'+uuid.uuid4().hex);output.mkdir(parents=True,exist_ok=False)
    save(output/'REGISTERED_OWNER.json',dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),
        cpu=14,affinity_mask=16384,creation_filetime=values[0].value,
        create_time=(values[0].value-116444736000000000)/10000000))
    return output


def save(path,value):
    raw=json.dumps(value,sort_keys=True,allow_nan=False,indent=2).encode()
    if len(raw)>2*1024**2:raise ValueError('Finite numeric review output')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    if path.read_bytes()!=raw:raise OSError('Review readback differs')


def strict(path,cap=1024**2):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('Bounded regular metadata required')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('Duplicate metadata key')
            result[key]=value
        return result
    return json.loads(path.read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def slopes(bins):
    result={}
    for key in sorted({key for b in bins for key in b['metrics']}):
        values=[(b['start_seconds']/60,b['metrics'][key]['mean']) for b in bins
                if b['start_seconds']>=600 and key in b['metrics']]
        if len(values)<3:
            result[key]=dict(points=len(values),status='INSUFFICIENT_POST_WARMUP_BINS');continue
        mx=sum(x for x,y in values)/len(values);my=sum(y for x,y in values)/len(values)
        result[key]=dict(points=len(values),first_mean=values[0][1],last_mean=values[-1][1],
            delta=values[-1][1]-values[0][1],
            least_squares_per_minute=sum((x-mx)*(y-my) for x,y in values)/sum((x-mx)**2 for x,y in values),
            interpretation='Descriptive only; no automatic leak, steady-state, RTF or upgrade verdict')
    return result


def review(mirror):
    import sqlite3
    from storage import _unpack_event
    from event_compaction import iter_events
    transport=strict(mirror/'RESULT.json');complete=strict(mirror/'MIRROR_COMPLETE.json')
    manifest=strict(mirror/'MIRROR_MANIFEST.json',2*1024**2);job=transport['job']
    if (transport.get('status')!='FULL_CLOSED_OUTPUT_MIRRORED' or complete.get('kind')!='COMPLETE'
            or not isinstance(manifest,list) or not 0<len(manifest)<=2048
            or hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()!=complete['manifest_sha256']):
        raise ValueError('Complete pinned bounded mirror required')
    closure=complete['closure']
    if (not all(closure.get(k) is True for k in ('closed','exact_owner_gone','cgroup_empty'))
            or any(closure.get(k)!=job[k] for k in ('owner','unit','invocation_id','control_group'))
            or job.get('workflow')!='continuous-full-application-repeated-wav'):
        raise ValueError('Exact closed application-hour job required')
    root=(mirror/'closed-output').resolve();rows={};total=0
    for row in manifest:
        name=row['path'];path=root/name
        if (name in rows or '\\' in name or any(part in ('','.','..') for part in name.split('/'))
                or not path.resolve().is_relative_to(root) or path.is_symlink() or not path.is_file()
                or path.stat().st_size!=row['identity']['bytes'] or sha(path)!=row['sha256']):
            raise ValueError('Full mirrored member identity/hash differs')
        rows[name]=row;total+=row['identity']['bytes']
        if total>3*1024**3:raise ValueError('Complete hour output bound')
    actual=set();directories=0
    for directory,children,files in os.walk(root):
        directories+=1
        if directories>4096 or len(children)+len(files)>4096:raise ValueError('Bounded mirror traversal')
        for name in files:actual.add((Path(directory)/name).relative_to(root).as_posix())
        if len(actual)>2048:raise ValueError('Mirror membership exceeds scope')
    if actual!=set(rows) or complete['files']!=len(rows) or complete['bytes']!=total:raise ValueError('Full mirror membership differs')
    def document(name,cap=1024**2):
        if name not in rows:return None
        return strict(root/name,cap)
    database_name='data/recordings/history.sqlite3'
    if database_name not in rows:raise ValueError('One indexed hour session required')
    if any(rows.get(database_name+suffix,{}).get('identity',{}).get('bytes',0)>0
            for suffix in ('-journal','-wal','-shm')):
        raise ValueError('Closed mirror has SQLite sidecars; immutable review cannot ignore them')
    aggregate={};health_bins={};unit_bins={};caption_latency=Stats();origin_estimates=Stats()
    def add(bins,clock,values):
        if type(clock) not in (int,float) or not math.isfinite(clock) or not -180<=clock<=5400:raise ValueError('Finite session clock')
        bucket=math.floor(clock/600)*600;b=bins.setdefault(bucket,{})
        for key,value in values.items():
            if type(value) in (int,float) and math.isfinite(value):
                b.setdefault(key,Stats()).add(value);aggregate.setdefault(key,Stats()).add(value)
    def result_bins(bins):return [dict(start_seconds=start,end_seconds=start+600,
        metrics={key:stats.result() for key,stats in sorted(values.items())}) for start,values in sorted(bins.items())]
    with sqlite3.connect((root/database_name).as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-2048')
        deadline=time.monotonic()+30
        db.set_progress_handler(lambda:int(time.monotonic()>deadline),10000)
        quick_check=[row[0] for row in db.execute('PRAGMA quick_check')]
        if quick_check!=['ok']:raise ValueError('Closed indexed hour database failed quick_check')
        db.set_progress_handler(None,0)
        sessions=db.execute('SELECT id,status,spec,processed_samples,raw_samples FROM sessions LIMIT 2').fetchall()
        if len(sessions)!=1:raise ValueError('Exactly one hour session required')
        session=dict(sessions[0]);identifier=session['id'];spec=json.loads(session.pop('spec'))
        health_count=0;origin=None;last_clock=None;last_cpu=None;last_samples=0;last_health={}
        for event in db.execute("SELECT * FROM events WHERE session_id=? AND event_type='health' ORDER BY seq",(identifier,)):
            row=_unpack_event(dict(event));health_count+=1
            if health_count>6000:raise ValueError('Finite 1Hz health review')
            elapsed=row.get('elapsed');clock=row.get('at_monotonic')
            if type(elapsed) not in (int,float) or type(clock) not in (int,float):continue
            if origin is None:origin=clock-elapsed
            if last_clock is not None and clock<=last_clock:raise ValueError('Health clock regressed')
            if row['source_samples']<last_samples:raise ValueError('Source sample clock regressed')
            values={key:row.get(key) for key in ('rss','pss_bytes','virtual_bytes','vm_peak_bytes','available_ram',
                'backlog_seconds','temperature_millicelsius','cpu_seconds','threads','first_caption_latency','first_speaker_latency','dropped_audio')}
            if last_cpu is not None:values['worker_cpu_percent']=100*(row['cpu_seconds']-last_cpu)/(clock-last_clock)
            values['diarizer_push_rolling_rtf']=row.get('diarizer_rolling',{}).get('rolling_rtf')
            values['source_seconds']=row['source_samples']/16000
            origin_estimates.add(event['created']-elapsed)
            add(health_bins,elapsed,values);last_clock=clock;last_cpu=row['cpu_seconds'];last_samples=row['source_samples'];last_health=row
        if not health_count or origin is None:raise ValueError('Actual health/source origin required')
        caption=db.execute('SELECT COUNT(*) AS count,SUM(revision) AS stored_revision_total,MAX(end_sample) AS last_end_sample FROM captions WHERE session_id=?',(identifier,)).fetchone()
        revision_events=0;first_revision_events=0
        for event in db.execute("SELECT * FROM events WHERE session_id=? AND event_type='caption_revision' ORDER BY seq",(identifier,)):
            revision_events+=1
            if revision_events>1000000:raise ValueError('Finite caption revision review')
            row=_unpack_event(dict(event))
            if row['revision']==1:
                first_revision_events+=1;caption_latency.add(event['created']-origin_estimates.first-row['end_sample']/16000)
        ledger=db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(identifier,)).fetchone()
        event_counts={r[0]:r[1] for r in db.execute('SELECT event_type,COUNT(*) FROM events WHERE session_id=? GROUP BY event_type',(identifier,))}
    memory_name='WHOLE_UNIT_MEMORY.jsonl'
    if memory_name not in rows or rows[memory_name]['identity']['bytes']>16*1024**2:raise ValueError('Finite complete whole-unit trace required')
    memory_count=0;incomplete=0;last_time=None;first_time=None;gaps=Stats();physical=set()
    with (root/memory_name).open('rb') as stream:
        for line in stream:
            if not 0<len(line)<=16384:raise ValueError('Whole-unit row bound')
            row=json.loads(line);memory_count+=1
            if memory_count>6000:raise ValueError('Whole-unit sample count bound')
            if any(row.get(k)!=job[k] for k in ('unit','invocation_id','control_group','boot_id')):raise ValueError('Memory sample unit differs')
            clock=row['monotonic_sec'];physical.add(row['physical_ram_bytes'])
            if first_time is None:first_time=clock
            if last_time is not None:
                if clock<=last_time:raise ValueError('Memory clock regressed')
                gaps.add(clock-last_time)
            last_time=clock
            if row.get('complete_process_sample') is not True:incomplete+=1;continue
            owners=row['owners']
            if not 0<len(owners)<=64 or len({(r['pid'],r['start_ticks']) for r in owners})!=len(owners):raise ValueError('Bounded actual unit members required')
            if (sum(r['rss_bytes'] for r in owners)!=row['combined_rss_bytes'] or
                    sum(r['pss_bytes'] for r in owners)!=row['combined_pss_bytes']):raise ValueError('Aggregate process sum differs')
            add(unit_bins,clock-origin,dict(unit_rss_bytes=row['combined_rss_bytes'],unit_pss_bytes=row['combined_pss_bytes'],
                unit_available_ram=row['available_ram'],unit_temperature_millicelsius=row.get('temperature_millicelsius'),
                unit_swap_bytes=sum(r['swap_bytes'] for r in owners),unit_process_count=len(owners)))
    if len(physical)!=1:raise ValueError('Physical RAM changed within the bound job')
    worker_names=[name for name in rows if name.endswith('/worker/RESULT.json')]
    if len(worker_names)>1:raise ValueError('Only one application worker expected')
    worker=document(worker_names[0]) if worker_names else None
    host=document(worker_names[0].removesuffix('worker/RESULT.json')+'HOST_CLOSURE.json') if worker_names else None
    summaries=[name for name in rows if '/sessions/'+identifier+'/' in name and name.endswith('/session_summary.json')]
    if len(summaries)>1:raise ValueError('Unique final engine summary expected')
    summary=document(summaries[0]) if summaries else None
    terminal={key:value for key,value in (summary or {}).get('telemetry',{}).items() if type(value) in (int,float,bool)}
    telemetry=(summary or {}).get('telemetry',{})
    indices=[name for name in rows if name.endswith('/events.jsonl.index.json')]
    if len(indices)!=1:raise ValueError('One complete actual engine event stream required')
    index=document(indices[0],16384);source_start=[];source_stop=[];wraps=[]
    for event in iter_events(root/indices[0].removesuffix('.index.json'),
            maximum_bytes=index['completed_bytes'] or 1,maximum_records=index['completed_bytes'] or 1):
        kind=event.get('event_type',event.get('kind'))
        if kind in ('source_started','source_stopped','source_repeat_boundary'):
            payload=event['payload']
            if kind=='source_started':source_start.append(payload)
            elif kind=='source_stopped':source_stop.append(payload)
            else:wraps.append(payload)
            if len(source_start)>1 or len(source_stop)>1 or len(wraps)>59:
                raise ValueError('Multiple source epochs or unexpected repeated-source wraps')
    start=source_start[0] if len(source_start)==1 else {};stop=source_stop[0] if len(source_stop)==1 else {}
    epoch=start.get('source_epoch_monotonic_sec')
    correct_wraps=len(wraps)==59 and all(row.get('repetition')==number and
        row.get('logical_start_sample')==number*966400 and row.get('input_offset_sample')==0 and
        row.get('source_frames')==966400 and row.get('source_sha256')==start.get('source_sha256') and
        row.get('source_epoch_monotonic_sec')==epoch and row.get('models_reset') is False
        for number,row in enumerate(wraps,1))
    metrics=stop.get('saved_source_metrics',{})
    calls=telemetry.get('component_costs',{}).get('rows',{})
    measured_calls={key:calls.get(key,{}) for key in ('model_setup','diarizer_setup','diarizer_push','embedding','asr_accept')}
    punctuation=telemetry.get('s6d',{}).get('punctuation',{})
    admission=document('ADMISSION.json') or {};budget=admission.get('budget',{})
    maximum=budget.get('file_limit_bytes');reserve=budget.get('physical_file_reserve_bytes')
    filesystem=budget.get('physical_filesystem_total_bytes');free=budget.get('physical_free_at_admission_bytes')
    physical_capacity=(all(type(v) is int and v>0 for v in (maximum,reserve,filesystem,free)) and
        maximum==filesystem-reserve and free>=reserve+budget.get('maximum_output_bytes',0) and
        all(row['identity']['bytes']<=maximum for row in rows.values()) and
        'OUTPUT_BUDGET_FAILURE.json' not in rows)
    needed=57600000;final=(worker or {}).get('result') or {}
    clocks={key:terminal.get(key) for key in ('source_duration_sec','asr_cursor_sec','speaker_cursor_sec','asr_lag_sec','speaker_lag_sec','audio_frames_dropped')}
    job_exit=closure.get('job_exit')
    if job_exit is not None and type(job_exit) is not dict:raise ValueError('Recorded job exit must be an object or null')
    gates=dict(natural_job_exit=bool(job_exit is not None and job_exit.get('natural_returncode')==0),
        leases_released=bool(job_exit is not None and job_exit.get('leases_released') is True),
        exact_3600_source=final.get('source_samples')==needed and session['processed_samples']==needed,
        developer_policy=final.get('source_policy',{}).get('developer_soak') is True and final.get('source_policy',{}).get('maximum_session_seconds')==3600,
        final_clocks=all(clocks[k]==3600 for k in ('source_duration_sec','asr_cursor_sec','speaker_cursor_sec')),
        no_final_lag_or_drops=all(clocks[k]==0 for k in ('asr_lag_sec','speaker_lag_sec','audio_frames_dropped')),
        worker_logical_cleanup=bool(worker and worker.get('failure') is None and worker.get('logical_cleanup_complete') is True),
        worker_reaped=bool(host and host.get('returncode')==0 and host.get('direct_child_reaped') is True and host.get('stdout_reader_joined') is True and host.get('nested_source',{}).get('closed') is True),
        engine_completed=bool(summary and summary.get('state')=='COMPLETED'),
        trace_covers_source_clock=bool(first_time is not None and first_time<=origin+2 and last_time>=origin+3600),
        physical_capacity=physical_capacity,
        metadata_ledger_accounted=bool(ledger and ledger['used_bytes']>=0),database_quick_check=quick_check==['ok'],
        exact_repeated_source=(start.get('mode')=='developer_repeated_file' and start.get('source_frames')==966400
            and start.get('target_samples')==needed and start.get('physical_microphone') is False and
            start.get('motion_applied') is False and stop.get('sent_samples')==needed and
            stop.get('target_samples')==needed and stop.get('repetitions')==59 and stop.get('error') is None),
        exact_59_wraps=correct_wraps,
        source_append_complete=(metrics.get('committed_source_samples')==needed and metrics.get('append_failures')==0),
        nonempty_captions=caption['count']>0,
        measured_layer_calls=all(measured_calls[key].get('completed',0)>0 and
            measured_calls[key].get('errors')==0 and measured_calls[key].get('in_flight')==0
            for key in ('diarizer_push','embedding','asr_accept')),
        single_model_session=(len(worker_names)==1 and len(summaries)==1 and
            measured_calls['model_setup'].get('started')==1 and measured_calls['diarizer_setup'].get('started')==1),
        punctuation_drained=(punctuation.get('accepted',0)>0 and punctuation.get('accepted')==punctuation.get('completed')
            and punctuation.get('error') is None and punctuation.get('closed') is True and punctuation.get('thread_alive') is False))
    hbins=result_bins(health_bins);ubins=result_bins(unit_bins)
    paced=final.get('combined_paced_eof_wall_seconds')
    return dict(schema='just-peachy.full-app-hour-numeric-review.v1',status='COMPLETE_3600_SOURCE_AND_CLOSURE' if all(gates.values()) else 'FAILED_OR_INCOMPLETE_PREFIX',
        completion_gates=gates,mirror_manifest_sha256=complete['manifest_sha256'],mirror_files=len(rows),mirror_bytes=total,
        job_exit_recorded=job_exit is not None,physical_owner_gone=closure['exact_owner_gone'],physical_cgroup_empty=closure['cgroup_empty'],
        closed_service_state=closure.get('state'),
        job_unit=job['unit'],physical_ram_bytes=next(iter(physical)),session=session,source_spec_numeric={k:v for k,v in spec.items() if type(v) in (int,float,bool)},
        final_clocks=clocks,numeric_final_telemetry=terminal,costs=final.get('costs'),
        paced_source_to_eof_seconds=paced,post_3600_paced_drain_seconds=None if paced is None else paced-3600,
        health_samples=health_count,whole_unit_samples=memory_count,incomplete_unit_samples=incomplete,unit_sample_gaps_seconds=gaps.result(),
        whole_unit_first_source_elapsed_seconds=None if first_time is None else first_time-origin,
        whole_unit_last_source_elapsed_seconds=None if last_time is None else last_time-origin,
        aggregate_metrics={key:value.result() for key,value in sorted(aggregate.items())},health_600s_bins=hbins,whole_unit_600s_bins=ubins,
        health_post_warmup_slopes=slopes(hbins),whole_unit_post_warmup_slopes=slopes(ubins),
        captions=dict(caption),caption_revision_events=revision_events,first_revision_events=first_revision_events,
        approximate_first_publication_after_source_end_seconds=caption_latency.result(),wall_source_origin_estimates=origin_estimates.result(),
        metadata_ledger=dict(ledger) if ledger else None,event_counts=event_counts,
        source_epochs=len(source_start),source_stops=len(source_stop),wraps=len(wraps),
        exact_source_wraps=correct_wraps,source_append_metrics=metrics,component_call_rows=measured_calls,
        punctuation_worker=punctuation,physical_capacity_plan=budget,
        database_quick_check=quick_check,
        final_queue_and_scheduler_state={key:telemetry.get(key) for key in ('s6d','s7_observed_policy')},
        limitations=['Bins use capture-origin elapsed time; negative bin is startup, final bin includes drain.',
            'Rolling RTF is diarizer pushes only. Paced whole-application duration is not compute RTF.',
            'Caption publication latency uses SQLite wall time minus health-derived source origin; clock shifts may affect it.',
            'Sampled RSS/PSS are not continuous peaks. Per-process VM/AS are distinct from physical RAM.',
            'Historical metadata limit_bytes is bookkeeping; exceeding it is not a physical capacity failure.',
            'Repeated retained PCM speech is not natural conversation, GUI endurance or saved spatial replay.',
            'Trends do not by themselves prove a leak, thermal throttling, quality, or a hardware upgrade benefit.'],
        automatic_realtime_qualification=False,quality_evaluated=False,native_executed=False,audio_or_words_emitted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mirror',type=Path,required=True)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--output-root',type=Path,required=True);args=parser.parse_args()
    output=early(args.output_root);sys.dont_write_bytecode=True
    for name in ('review_core_full_app_hour30.py','launch_core_full_app_hour30.py','prepare_core_native_validation_v3.py',
                 'README_CORE_BUILD30_HELPERS.md'):
        raw=Path(__file__).with_name(name).read_bytes()
        for suffix in ('.backup','.restore'):
            with (output/(name+suffix)).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        if (output/(name+'.backup')).read_bytes()!=(output/(name+'.restore')).read_bytes():raise OSError('Source restore differs')
    if args.manifest_sha256!='b2eeab82452d5b87515477c4a562ce167cf6d35503a16df6a4febc1b1af25569':
        raise ValueError('Exact frozen build30 pure review dependencies required')
    from prepare_core_native_validation import inventory
    manifest,_=inventory(args.package,args.manifest_sha256)
    tree=ast.parse(Path(__file__).with_name('launch_core_full_app_hour30.py').read_bytes())
    names={'bind_verified_package','hash_file'}
    nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    if len(nodes)!=2:raise ValueError('Exact verified pure import binding required')
    namespace=dict(Path=Path,sys=sys,hashlib=hashlib)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<verified-core-hour-review-imports>','exec'),namespace)
    check=namespace['bind_verified_package'](args.package,manifest)
    result=review(args.mirror);check();save(output/'REVIEW.json',result)
    print(json.dumps(dict(output=str(output),status=result['status'],gates=result['completion_gates'],health_samples=result['health_samples'])))


if __name__=='__main__':main()
