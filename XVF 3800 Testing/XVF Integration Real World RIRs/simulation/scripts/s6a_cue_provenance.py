"""Audit and archive cue feature/physical provenance. README_S6A_CUES.md."""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from s6a_cues import read,save,binding,verified,DEFAULT_REPORT,now


def archive_feature_code(report):
    current=Path(__file__).with_name('s6a_cues.py');source=current.read_text(encoding='utf-8')
    # The one smoke version preceded added immutable invocation bookkeeping.
    # Reconstruct only that exact known diff, then require the recorded SHA.
    after="""    invocation=folder/'invocations'/('extract_'+str(os.getpid())+'_'+str(round(created*1000))+'.json')
    initial=dict(pid=os.getpid(),creation_time=created,started_utc=now(),status='RUNNING',threads=2,
                 argv=sys.argv,requested_limit=limit)
    save(folder/'EXTRACT_PROCESS.json',initial);save(invocation,initial)"""
    before="""    save(folder/'EXTRACT_PROCESS.json',dict(pid=os.getpid(),creation_time=created,started_utc=now(),status='RUNNING',threads=2))"""
    old=source.replace(after,before).replace(
        "save(folder/'FEATURE_INDEX.json',result);save(invocation,dict(initial,status='FINISHED',result=result));return result",
        "save(folder/'FEATURE_INDEX.json',result);return result")
    candidates={hashlib.sha256(text.encode()).hexdigest():text for text in (source,old)}
    index=read(report/'cues/FEATURE_INDEX.json');counts=Counter();bindings={}
    for item in index['rows']:
        if item['status']!='COMPLETE':continue
        feature=read(verified(item['result']));row=feature['source_code'];counts[row['sha256']]+=1;bindings[row['sha256']]=row
    rows=[]
    for sha,count in sorted(counts.items()):
        if sha not in candidates:raise ValueError('unavailable historical cue source version: '+sha)
        text=candidates[sha]
        if len(text.encode())!=bindings[sha]['bytes']:raise ValueError('historical code byte count mismatch')
        destination=report/'cues/code_archive'/(sha+'.source.txt');destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            if destination.read_text(encoding='utf-8')!=text:raise ValueError('code archive changed')
        else:destination.write_bytes(text.encode('utf-8'))
        archived=binding(destination,sha)
        rows.append(dict(historical_binding=bindings[sha],immutable_archive=archived,feature_outputs=count))
    def semantics(text):
        parsed=ast.parse(text)
        return {node.name:ast.dump(node,include_attributes=False) for node in parsed.body
                if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in ('feature_identity','extract_vectors','ExactReDim')}
    parity=semantics(source)==semantics(old)
    if not parity:raise ValueError('bookkeeping version changed model semantics')
    result=dict(schema='jp_s6a_feature_code_archive_v1',status='PASS',rows=rows,
                neural_feature_functions_semantically_identical=parity,
                rejected_line_ending_archive_attempts=[binding(p) for p in (report/'cues/code_archive').glob('*.py.txt')],
                scope='One smoke then added invocation bookkeeping; archive verified by recorded SHA256 and exact bytes',created_utc=now())
    save(report/'CUE_CODE_ARCHIVE.json',result);return result


def audit_physical(report):
    from s4_telemetry import normalize_observation
    index=read(report/'CUE_DELIVERY_INDEX.json');rows=[];started=time.perf_counter()
    for item in index['rows']:
        capture=read(verified(item['capture']));metadata=read(verified(item['metadata']))
        path=verified(item['raw_telemetry']);verified(item['sanitized'])
        callbacks=metadata['callback_times'];expected_start=0;previous_time=-1
        for callback in callbacks:
            if callback['first_native_frame']!=expected_start or callback['frames']<=0:
                raise ValueError('noncontiguous physical callback support')
            expected_start+=callback['frames'];stamp=callback.get('host_copy_complete_monotonic_ns',callback['host_callback_monotonic_ns'])
            if stamp<previous_time:raise ValueError('decreasing physical callback availability')
            previous_time=stamp
        if expected_start!=metadata['captured_frames'] or expected_start!=capture['framing']['native_frames']:
            raise ValueError('physical frame counts differ')
        if metadata['callback_flags'] or metadata['callback_errors'] or capture['status']!='PASS':
            raise ValueError('capture not accepted clean callback evidence')
        raw=[json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        stamps=[r['host_line_arrival_monotonic_ns'] for r in raw]
        if any(a>b for a,b in zip(stamps,stamps[1:])):raise ValueError('historical line delivery reordered')
        normalized=[normalize_observation(row) for row in raw]
        invalid=Counter(reason for row in normalized for reason in row['transaction_invalid_reasons'])
        fields=Counter(row['command'] for row in normalized)
        native_receipt=read(path.parent/'result.json')
        if native_receipt['status']!='PASS' or native_receipt['reply_count']!=len(raw):raise ValueError('telemetry receipt/count differs')
        for field,count in fields.items():
            if native_receipt['per_field'][field]['count']!=count:raise ValueError('per-field count differs')
        rows.append(dict(case_id=item['case_id'],native_frames=expected_start,callbacks=len(callbacks),
                         telemetry_rows=len(raw),fields=dict(fields),invalid_transactions=dict(invalid),
                         capture=item['capture'],metadata=item['metadata'],telemetry=item['raw_telemetry'],
                         native_telemetry_receipt=binding(path.parent/'result.json'),status='PASS'))
    result=dict(schema='jp_s6a_physical_cue_integrity_v1',status='PASS',physical_traces=len(rows),rows=rows,
                telemetry_rows=sum(r['telemetry_rows'] for r in rows),created_utc=now(),elapsed_sec=time.perf_counter()-started,
                source_changes_performed=False,device_opened=False,
                scope='Current bound physical files, callback/frame continuity, accepted telemetry counts; no claim DSP observation time known')
    save(report/'CUE_PHYSICAL_INTEGRITY.json',result);return result


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    args=parser.parse_args();code=archive_feature_code(args.report);physical=audit_physical(args.report)
    result=dict(status='PASS',code_versions=len(code['rows']),physical_traces=physical['physical_traces'],
                telemetry_rows=physical['telemetry_rows'],code_archive=binding(args.report/'CUE_CODE_ARCHIVE.json'),
                physical_integrity=binding(args.report/'CUE_PHYSICAL_INTEGRITY.json'),created_utc=now())
    save(args.report/'CUE_PROVENANCE_RECEIPT.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
