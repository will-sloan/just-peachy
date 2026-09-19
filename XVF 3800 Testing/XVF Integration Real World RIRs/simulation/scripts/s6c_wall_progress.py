"""One-shot external native wall progress observer. See README_S6C_WALL_PROGRESS.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time
import psutil

MAX_BYTES=2*2**20
MAX_HISTORY=12
WINDOW_SEC=300.
MAX_SOURCE_AGE_SEC=90.


def utc():return datetime.now(timezone.utc).isoformat()


def digest(raw):return hashlib.sha256(raw).hexdigest()


def binding(path,raw):return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=digest(raw))


def finite(value):return type(value) in (int,float) and math.isfinite(value)


def positive_identity(pid,created):
    if type(pid) is not int or pid<=0 or not finite(created) or created<=0:raise ValueError('Positive finite non-boolean PID/creation identity required')


def aware(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:raise ValueError('Aware UTC source/observation time required')
    return result.timestamp()


def parse(raw):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('Duplicate JSON key')
            result[k]=v
        return result
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))


def small_buffer(path):
    with Path(path).open('rb') as f:raw=f.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('Explicit progress metadata exceeds 2 MiB')
    return raw,binding(path,raw)


def process_state(pid,created):
    positive_identity(pid,created)
    try:
        p=psutil.Process(pid);actual=p.create_time()
        return dict(alive=actual==created,status='LIVE_EXPECTED_OWNER' if actual==created else 'PID_REUSED_EXPECTED_OWNER_CLOSED',observed_creation_time=actual)
    except psutil.NoSuchProcess:return dict(alive=False,status='EXPECTED_OWNER_CLOSED',observed_creation_time=None)
    except psutil.Error as exc:return dict(alive=None,status='OWNER_INSPECTION_UNAVAILABLE',error=type(exc).__name__+': '+str(exc))


def point(value,source,pid,created,observed_utc,monotonic_sec,boot_time,owner_state):
    positive_identity(pid,created);owner=value['owner']
    positive_identity(owner['pid'],owner['creation_time'])
    if owner['pid']!=pid or owner['creation_time']!=created:raise ValueError('SOURCE_OWNER_IDENTITY_CHANGED')
    if value['status']!='RUNNING':raise ValueError('Expected RUNNING progress schema; durable closure is separate')
    counters={k:value[k] for k in ('requested','completed','new_native_jobs','reused','pending')}
    if any(type(v) is not int or v<0 for v in counters.values()) or counters['requested']==0:raise ValueError('Invalid integer progress counter')
    if not isinstance(value['active'],list):raise ValueError('Active job list required')
    if not finite(value['elapsed_sec']) or value['elapsed_sec']<0 or not finite(monotonic_sec) or not finite(boot_time):raise ValueError('Invalid progress/observer clock')
    source_time=aware(value['utc']);observed_time=aware(observed_utc)
    original=value.get('eta_range_sec')
    if original is not None and (not isinstance(original,list) or len(original)!=2 or any(not finite(x) or x<0 for x in original) or original[1]<original[0]):raise ValueError('Malformed original ETA')
    consistent=counters['completed']==counters['new_native_jobs']+counters['reused'] and counters['completed']+counters['pending']+len(value['active'])==counters['requested']
    return dict(source_path=str(Path(source).resolve()),pid=pid,creation_time=created,epoch=value['epoch'],phase=value['phase'],source_utc=value['utc'],observed_utc=observed_utc,
        observer_monotonic_sec=monotonic_sec,boot_time=boot_time,source_elapsed_sec=value['elapsed_sec'],source_age_sec=observed_time-source_time,
        owner_state=owner_state,counters=counters,active_count=len(value['active']),counter_snapshot_consistent=consistent,original_eta_range_sec=original)


def compare(previous,current):
    for k in ('source_path','pid','creation_time','epoch','phase','boot_time'):
        if previous[k]!=current[k]:raise ValueError('SOURCE_OR_OWNER_EPOCH_PHASE_CHANGED: '+k)
    if previous['counters']['requested']!=current['counters']['requested']:raise ValueError('REQUESTED_GRID_CHANGED')
    if current['observer_monotonic_sec']<=previous['observer_monotonic_sec'] or aware(current['observed_utc'])<=aware(previous['observed_utc']):raise ValueError('NONMONOTONIC_OBSERVER_CLOCK')
    if current['source_elapsed_sec']<previous['source_elapsed_sec'] or aware(current['source_utc'])<aware(previous['source_utc']):raise ValueError('SOURCE_CLOCK_RESET_OR_REORDER')
    for k in ('completed','new_native_jobs','reused'):
        if current['counters'][k]<previous['counters'][k]:raise ValueError('SOURCE_COUNTER_RESET: '+k)


def estimate(history):
    if not history:raise ValueError('At least one observation required')
    last=history[-1];counts=last['counters'];remaining=max(0,counts['requested']-counts['completed'])
    result=dict(status='INITIAL_OBSERVATION',observed_wall_sec=None,new_native_completions=None,reported_reused_delta=None,
        new_completions_per_observed_wall_sec=None,heuristic_remaining_wall_sec=None,heuristic_eta_range_sec=None,remaining_reported_jobs_including_active=remaining,
        original_worker_cost_eta_range_sec=last['original_eta_range_sec'],original_eta_scope='Source runner pending-only mean returned COMPLETE-job elapsed divided by configured workers; not coordinator wall ETA.',
        source_age_sec=last['source_age_sec'],recent_window_target_sec=WINDOW_SEC,
        basis='External observed wall between sampled new_native_jobs counter values. Reported reused completions never enter new throughput. Includes stalls/scans/admission within the observed interval; no attribution to a model/profile and no durable native-count certification.',
        limits='Counter publications lag work and are not atomic native receipts. Current phases and future jobs may differ. Range is a cautious heuristic, not a confidence interval or completion guarantee. End-of-run validation/drain is not independently timed here.')
    for old,new in zip(history,history[1:]):compare(old,new)
    if last['owner_state']['alive'] is not True:result['status']='OWNER_CLOSED_OR_UNVERIFIED';return result
    if not last['counter_snapshot_consistent']:result['status']='INCONSISTENT_OPTIONAL_COUNTER_SNAPSHOT';return result
    if last['source_age_sec']< -2 or last['source_age_sec']>MAX_SOURCE_AGE_SEC:result['status']='STALE_OR_FUTURE_SOURCE_CLOCK';return result
    if len(history)<2:return result
    previous=history[-2];delta=counts['new_native_jobs']-previous['counters']['new_native_jobs'];reused=counts['reused']-previous['counters']['reused']
    if delta==0:
        result.update(status='NO_NEW_COMPLETIONS_LOAD_VALIDATION_OR_FLAT',new_native_completions=0,reported_reused_delta=reused)
        return result
    recent=[p for p in history if last['observer_monotonic_sec']-p['observer_monotonic_sec']<=WINDOW_SEC and p['counter_snapshot_consistent'] and p['owner_state']['alive'] is True and -2<=p['source_age_sec']<=MAX_SOURCE_AGE_SEC]
    if len(recent)<2:result['status']='INSUFFICIENT_RECENT_OBSERVATIONS';return result
    first=recent[0];wall=last['observer_monotonic_sec']-first['observer_monotonic_sec'];new=counts['new_native_jobs']-first['counters']['new_native_jobs']
    if wall<=0 or new<=0:raise ValueError('Invalid positive observed throughput interval')
    rate=new/wall;prediction=remaining/rate if remaining else None
    result.update(status='OBSERVED_NEW_COMPLETION_PROGRESS' if remaining else 'REPORTED_JOBS_ACCOUNTED_CLOSURE_PENDING',observed_wall_sec=wall,new_native_completions=new,
        reported_reused_delta=counts['reused']-first['counters']['reused'],new_completions_per_observed_wall_sec=rate,
        heuristic_remaining_wall_sec=prediction,heuristic_eta_range_sec=None if prediction is None else [prediction*.5,prediction*2.],
        oldest_used_observation_utc=first['observed_utc'],observations_used=len(recent))
    return result


def save(path,value):
    raw=(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode('utf-8');path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw)
    return binding(path,raw)


def snapshot(args):
    positive_identity(args.pid,args.creation_time)
    if not args.source.is_absolute() or not args.output.is_absolute():raise ValueError('Explicit absolute source/output paths required')
    if args.output.exists():raise ValueError('Fresh explicit observation directory required')
    code=Path(__file__);readme=code.with_name('README_S6C_WALL_PROGRESS.md');sources=[binding(p,p.read_bytes()) for p in (code,readme)]
    history=[];prior=None
    if args.previous:
        raw,prior=small_buffer(args.previous)
        if prior['sha256']!=args.previous_sha256:raise ValueError('Pinned previous observation differs')
        previous=parse(raw)
        if previous['schema']!='s6c-observed-wall-progress.v1' or previous['status']!='OBSERVATION_RECORDED':raise ValueError('Valid previous observation required')
        if previous['sources']!=sources:raise ValueError('Observer code/README changed; use a separately reviewed observation chain')
        history=previous['history']
    started=time.perf_counter();raw,source=small_buffer(args.source);now=utc();mono=time.perf_counter();value=parse(raw)
    owner=process_state(args.pid,args.creation_time);observation=point(value,args.source,args.pid,args.creation_time,now,mono,psutil.boot_time(),owner)
    history=(history+[observation])[-MAX_HISTORY:];prediction=estimate(history)
    args.output.mkdir(parents=True)
    retained=args.output/'PROGRESS_SOURCE.json'
    with retained.open('xb') as f:f.write(raw)
    result=dict(schema='s6c-observed-wall-progress.v1',status='OBSERVATION_RECORDED',observed_utc=now,source=source,retained_source=binding(retained,raw),expected_owner=dict(pid=args.pid,creation_time=args.creation_time),
        previous=prior,history=history,estimate=prediction,observer=dict(pid=os.getpid(),creation_time=psutil.Process().create_time(),read_parse_inspection_elapsed_sec=time.perf_counter()-started),
        sources=sources,model_calls=0,raw_log_reads=0,payload_scans=0,
        scope='One explicit optional-progress JSON observation. No native/receipt mutation, process termination, sleep loop, scheduler, automation, or model work. Original runner ETA is retained separately.')
    return save(args.output/'OBSERVATION.json',result)


def checks():
    count=0
    def reject(call):
        try:call()
        except (ValueError,KeyError):return 1
        raise AssertionError('Invalid observation admitted')
    def make(t,new=0,reused=0,completed=None):
        completed=new+reused if completed is None else completed
        stamp=datetime.fromtimestamp(1789050000+t,timezone.utc).isoformat()
        value=dict(owner=dict(pid=10,creation_time=100.),status='RUNNING',requested=100,completed=completed,new_native_jobs=new,reused=reused,pending=100-completed-2,active=[{},{}],epoch='epoch2',phase='native',utc=stamp,elapsed_sec=t,eta_range_sec=[1.,2.])
        return point(value,Path('C:/explicit/progress.json'),10,100.,stamp,t,1000.,{'alive':True})
    first=make(1);assert estimate([first])['heuristic_eta_range_sec'] is None;count+=1
    second=make(101,new=10,reused=20);result=estimate([first,second]);assert result['new_completions_per_observed_wall_sec']==.1 and result['heuristic_eta_range_sec']==[350.,1400.] and result['reported_reused_delta']==20;count+=1
    assert result['original_worker_cost_eta_range_sec']==[1.,2.] and result['remaining_reported_jobs_including_active']==70;count+=1
    third=make(151,new=10,reused=30);assert estimate([first,second,third])['heuristic_eta_range_sec'] is None;count+=1
    stale=make(201,new=20);stale['source_age_sec']=91;assert estimate([first,stale])['status']=='STALE_OR_FUTURE_SOURCE_CLOCK';count+=1
    stale_first=make(1);stale_first['source_age_sec']=300;assert estimate([stale_first,second])['heuristic_eta_range_sec'] is None;count+=1
    for alive in (False,None):
        p=make(201,new=20);p['owner_state']['alive']=alive;assert estimate([first,p])['heuristic_eta_range_sec'] is None;count+=1
    for key,value in (('source_path','C:/different.json'),('pid',11),('creation_time',101.),('epoch','epoch3'),('phase','other'),('boot_time',1001.),('source_elapsed_sec',0.),('observer_monotonic_sec',0.)):
        p=make(101,new=10);p[key]=value;count+=reject(lambda:estimate([first,p]))
    old=make(101,new=10,reused=2);new=make(151,new=9,reused=2);count+=reject(lambda:estimate([old,new]))
    new=make(151,new=11,reused=1);count+=reject(lambda:estimate([old,new]))
    new=make(151,new=11,reused=2);new['counters']['requested']=101;count+=reject(lambda:estimate([old,new]))
    torn=make(151,new=11,reused=2,completed=20);assert estimate([old,torn])['status']=='INCONSISTENT_OPTIONAL_COUNTER_SNAPSHOT';count+=1
    assert estimate([first,make(401,new=20)])['heuristic_eta_range_sec'] is None;count+=1
    for pid,created in ((True,1.),(1,True),(1,float('nan')),(1,float('inf')),(0,1.)):
        count+=reject(lambda:positive_identity(pid,created))
    count+=reject(lambda:parse(b'{"x":1,"x":2}'));count+=reject(lambda:parse(b'{"x":NaN}'))
    count+=reject(lambda:aware('2026-09-10T00:00:00'))
    assert estimate([make(1,new=0),make(101,new=20)])['new_native_completions']==20;count+=1
    return dict(status='PASS_MODEL_FREE',checks=count,native_calls=0,actual_progress_reads=0,scope='Pure parser/identity/reset/flat/reuse/wall-formula fixtures only.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);parser.add_argument('action',choices=('checks','snapshot'));parser.add_argument('--source',type=Path);parser.add_argument('--pid',type=int);parser.add_argument('--creation-time',type=float);parser.add_argument('--output',type=Path);parser.add_argument('--previous',type=Path);parser.add_argument('--previous-sha256');args=parser.parse_args()
    if args.action=='snapshot':
        if any(getattr(args,k) is None for k in ('source','pid','creation_time','output')):parser.error('Explicit source, PID/creation and fresh output are required')
        if bool(args.previous)!=bool(args.previous_sha256):parser.error('Previous observation and its exact SHA256 are a pair')
        result=snapshot(args)
    else:result=checks()
    print(json.dumps(result,indent=2))
