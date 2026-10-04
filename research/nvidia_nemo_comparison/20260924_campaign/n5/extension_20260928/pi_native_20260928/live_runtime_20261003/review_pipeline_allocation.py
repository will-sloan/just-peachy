"""Read-only closed pipeline allocation/WER counts; see README_PIPELINE_REVIEW.md."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid


def register(parent):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess();kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):raise ctypes.WinError(ctypes.get_last_error())
    clocks=[ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in clocks)):raise ctypes.WinError(ctypes.get_last_error())
    root=Path(parent)/('pipeline-allocation-review-'+uuid.uuid4().hex);root.mkdir(exist_ok=False)
    with (root/'REGISTERED_OWNER.json').open('x') as f:
        json.dump(dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
            affinity_mask=16384,creation_filetime=clocks[0].value,
            create_time=(clocks[0].value-116444736000000000)/10000000),f);f.flush();os.fsync(f.fileno())
    return root


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mirror',type=Path,required=True);ap.add_argument('--session',required=True)
    ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--output-root',required=True)
    args=ap.parse_args();output=register(args.output_root);sys.dont_write_bytecode=True
    import collections,re,sqlite3,string
    from runtime_support import encoded,strict,digest,publish
    from event_compaction import iter_events
    from storage import _unpack_event
    def bounded(path,limit):
        if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:raise ValueError('Read-only finite review input')
        return path.read_bytes()
    complete=strict(bounded(args.mirror/'MIRROR_COMPLETE.json',65536))
    manifest=strict(bounded(args.mirror/'MIRROR_MANIFEST.json',2*1024**2))
    if (not complete['closure']['closed'] or not complete['closure']['cgroup_empty']
            or not complete['closure']['exact_owner_gone'] or len(manifest)>2048
            or hashlib.sha256(encoded(manifest)).hexdigest()!=complete['manifest_sha256']):
        raise ValueError('Complete pinned closed mirror required')
    rows={row['path']:row for row in manifest}
    root=args.mirror/'closed-output'
    def path(name):
        if name not in rows:raise ValueError('Unlisted review file')
        item=root/name
        if rows[name]['identity']['bytes']!=item.stat().st_size or digest(item)!=rows[name]['sha256']:
            raise ValueError('Mirrored selected file changed')
        return item
    prefix='data/recordings/sessions/'+args.session+'/'
    session=strict(bounded(path(prefix+'session.json'),65536))
    source_seconds=session['processed_samples']/16000
    if not 0<source_seconds<=3600:raise ValueError('Explicit <=hour review bound')
    source_events=next(name for name in rows if name.startswith(prefix) and name.endswith('/events.jsonl.index.json'))
    session_base=source_events.removesuffix('events.jsonl.index.json')
    writers={}
    for name in rows:
        if name.startswith(session_base) and name.endswith('.index.json'):
            index=strict(bounded(path(name),16384))
            if 'accepted_bytes' in index:
                if not index['complete'] or index['accepted_bytes']!=index['completed_bytes']:raise ValueError('Incomplete writer')
                writers[Path(name).name]=index['accepted_bytes']
    # Verify each selected evidence member; no WAV/f32 reads or broad tree walk.
    for name in rows:
        if name.startswith(session_base) and not name.endswith(('.wav','.f32')):path(name)
    counts=collections.Counter();sizes=collections.Counter();maximum=collections.Counter();source_sha=None;coverage=[]
    for event in iter_events(root/(session_base+'events.jsonl'),maximum_bytes=64*1024**2,maximum_records=1000000):
        kind=event.get('event_type',event.get('kind','unknown'));size=len(encoded(event))+1
        counts[kind]+=1;sizes[kind]+=size;maximum[kind]=max(maximum[kind],size)
        if kind=='source_started':source_sha=event['payload']['source_sha256']
        if kind=='n2_exclusive_run_coverage':
            if len(coverage)>=16:raise ValueError('Bounded terminal coverage review')
            coverage.append(event['payload'])
    database=path('data/recordings/history.sqlite3')
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
        ledger=dict(db.execute('SELECT * FROM metadata_usage WHERE session_id=?',(args.session,)).fetchone())
        event_groups=[dict(row) for row in db.execute('SELECT event_type,COUNT(*) AS records,SUM(LENGTH(CAST(payload AS BLOB))) AS stored_bytes,SUM(payload_bytes) AS logical_bytes FROM events WHERE session_id=? GROUP BY event_type',(args.session,))]
        table_counts={table:db.execute('SELECT COUNT(*) FROM '+table+' WHERE session_id=?',(args.session,)).fetchone()[0] for table in ('segments','captions','events','artifacts')}
        segments=[dict(row) for row in db.execute('SELECT kind,SUM(samples) AS samples,COUNT(*) AS segments FROM segments WHERE session_id=? GROUP BY kind',(args.session,))]
        health=[]
        for row in db.execute("SELECT * FROM events WHERE session_id=? AND event_type='health' ORDER BY seq",(args.session,)):
            if len(health)>4000:raise ValueError('Finite health review')
            health.append(_unpack_event(dict(row)))
    compact=strict(bounded(path(session_base+'events.jsonl.compaction.json'),16384))
    finalization=strict(bounded(path(session_base+'session_finalization_v3.json'),65536))
    summary=strict(bounded(path(session_base+'session_summary.json'),1024**2))
    if finalization['source_samples']!=session['processed_samples'] or finalization['identity_samples']!=session['processed_samples']:
        raise ValueError('Exact source/identity sample closure differs')
    text_bytes=sum(row['identity']['bytes'] for name,row in rows.items() if name.startswith(prefix+'work/'))
    meta=session['spec']['metadata_reserve_bytes']
    loads=[strict(raw) for raw in bounded(path(prefix+'work/model_load_memory.jsonl'),1024**2).splitlines()]
    keys=('rss','pss_bytes','virtual_bytes','vm_peak_bytes','available_ram','backlog_seconds','temperature_millicelsius')
    ranges={key:dict(minimum=min(values),maximum=max(values)) for key in keys if (values:=[row[key] for row in health if type(row.get(key)) in (int,float)])}
    bins={}
    for row in health:
        elapsed=row.get('elapsed')
        if type(elapsed) not in (int,float):continue
        bucket=int(elapsed//10)*10;value=bins.setdefault(bucket,dict(samples=0))
        value['samples']+=1
        for key in keys:
            item=row.get(key)
            if type(item) in (int,float):value[key+'_max']=max(value.get(key+'_max',item),item)
    reference=strict(bounded(args.reference,65536))
    if (source_sha!=reference['audio']['sha256'] or reference['reference_words']!=38
            or abs(reference['duration_sec']-source_seconds)>1/16000
            or reference['normalization']['id']!='lowercase_remove_ascii_punctuation_collapse_whitespace_v1'
            or reference.get('transcript_valid') is not True):raise ValueError('Exact existing labeled reference/provenance required')
    normalize=lambda value:' '.join(value.lower().translate(str.maketrans('','',string.punctuation)).split())
    expected=reference['reference_normalized'].split()
    transcript=[strict(raw) for raw in bounded(path(session_base+'latest_labelled_transcript.jsonl'),1024**2).splitlines()]
    hypothesis=normalize(' '.join(row.get('display_text',row['text']) for row in transcript if row['is_final'])).split()
    if len(expected)!=38 or len(hypothesis)>8192:raise ValueError('Bounded full-reference WER')
    prior=[(i,0,0,i) for i in range(len(hypothesis)+1)]
    for i,left in enumerate(expected,1):
        current=[(i,0,i,0)]
        for j,right in enumerate(hypothesis,1):
            if left==right:value=prior[j-1]
            else:
                cost,s,d,ins=prior[j-1];sub=(cost+1,s+1,d,ins)
                cost,s,d,ins=prior[j];delete=(cost+1,s,d+1,ins)
                cost,s,d,ins=current[j-1];insert=(cost+1,s,d,ins+1)
                value=min((sub,delete,insert),key=lambda item:item[0])
            current.append(value)
        prior=current
    errors,substitutions,deletions,insertions=prior[-1]
    review=dict(schema='just-peachy.closed-pipeline-review.v1',mirror_manifest_sha256=complete['manifest_sha256'],
        session_id=args.session,source_samples=session['processed_samples'],source_seconds=source_seconds,source_sha256=source_sha,
        physical_closure=complete['closure'],stored_status=session['status'],exact_segments=segments,
        finalization=finalization,metadata_reserve_bytes=meta,native_budget_bytes=meta*5//6,
        terminal_numeric_telemetry={key:value for key,value in summary['telemetry'].items() if type(value) in (bool,int,float)},
        exclusive_coverage=coverage,
        text_and_work_files_bytes=text_bytes,writers=writers,compaction=compact,
        sqlite_file_bytes=database.stat().st_size,sqlite_ledger=ledger,sqlite_table_counts=table_counts,sqlite_events=event_groups,
        event_counts=dict(counts),event_logical_bytes=dict(sizes),maximum_event_bytes=dict(maximum),
        model_load_stages=loads,health_ranges=ranges,ten_second_health_bins=bins,
        linear_projection_not_qualification=dict(text_work_hour_bytes=text_bytes/source_seconds*3600,
            sqlite_ledger_hour_bytes=ledger['used_bytes']/source_seconds*3600,
            hour_text_budget_5_6=(16*1024**2+3600*256*1024)*5//6,
            hour_sqlite_budget_1_6=1024**2+(16*1024**2+3600*256*1024)//6,
            hour_text_budget_3_4=(16*1024**2+3600*256*1024)*3//4,
            hour_sqlite_budget_1_4=1024**2+(16*1024**2+3600*256*1024)//4),
        wer=dict(reference_sha256=digest(args.reference),normalization=reference['normalization'],reference_words=len(expected),
            hypothesis_words=len(hypothesis),substitutions=substitutions,deletions=deletions,insertions=insertions,
            errors=errors,wer=errors/len(expected),full_input=True,transcript_printed=False,
            tie_break='minimum edit distance; substitution then deletion then insertion',der_evaluated=False),
        native_executed=False,read_only=True)
    publish(output/'REVIEW.json',review)
    print(encoded(dict(output=str(output),samples=review['source_samples'],text_bytes=text_bytes,
        sqlite_ledger=ledger,health_ranges=ranges,wer=review['wer'])).decode())
    return 0


if __name__=='__main__':raise SystemExit(main())
