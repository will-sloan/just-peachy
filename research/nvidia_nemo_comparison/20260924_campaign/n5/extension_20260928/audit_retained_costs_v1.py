"""Audit retained lifecycle timing-event coverage. See README_RETAINED_COSTS_V1.md."""
from collections import Counter
from datetime import datetime,timezone
import argparse,json,math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'n4'))
from common import bind,freeze,load,verify
from metric_process import pin
from window_guard import window


def audit(name,base):
    review_path=base/(name+'-REVIEW.json');review=load(review_path)
    if review['status']!='PASS_PREPI_ONE_FILE_WINDOWS_LIFECYCLE_ONLY':raise ValueError('Unreviewed source run')
    phase=review['phases'][0]['result'];verify(phase);result=load(phase['path'])
    session=Path(result['telemetry']['session_dir'])
    if not session.resolve().is_relative_to(base/name):raise ValueError('Unexpected session path')
    files=sorted(session.glob('events.jsonl*'))
    if not files:raise ValueError('No retained events')
    sequence=[];counts=Counter();costs=Counter();cost_counts=Counter();events=0
    mapping={'n2_diarization_frames':('D1','compute_sec',1.),
             'research_embedding':('E0','compute_ms',.001),
             'research_asr_full_dispatch_cost':('ASR_dispatch','full_dispatch_elapsed_ms',.001)}
    for file in files:
        with file.open(encoding='utf-8') as f:
            for line in f:
                event=json.loads(line);payload=event.get('payload',{});kind=event['event_type']
                events+=1;counts[kind]+=1
                serial=payload.get('publication_sequence')
                if isinstance(serial,int):sequence.append(serial)
                if kind in mapping:
                    label,key,scale=mapping[kind];value=payload.get(key)
                    if isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value) and value>=0:
                        costs[label]+=value*scale;cost_counts[label]+=1
    unique=sorted(set(sequence))
    if not unique:raise ValueError('Publication sequence unavailable')
    minimum,maximum=unique[0],unique[-1]
    gaps=maximum-minimum+1-len(unique)
    return dict(run=name,review=bind(review_path),phase=phase,logs=[bind(p) for p in files],
        source_seconds=result['telemetry']['source_duration_sec'],
        observed_session_elapsed_seconds=result['telemetry']['elapsed_wall_sec'],
        observed_session_elapsed_includes_load_pacing_drain=True,retained_events=events,
        publication_sequence=dict(minimum=minimum,maximum=maximum,unique_count=len(unique),
                                  interior_missing=gaps,duplicate_count=len(sequence)-len(unique)),
        initial_publications_missing=minimum>1,
        retained_cost_event_counts=dict(cost_counts),retained_cost_seconds=dict(costs),
        lifecycle_embedding_calls=result['telemetry']['n2_embedding_calls'],
        complete_component_totals_available=False,component_compute_RTF=None,
        note='Retained costs cover only recorded events, not whole-run totals. Full-run timing coverage and zero-output native calls are not established.')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    pin();window();local=HERE.parent.parents[4]/'local'
    if args.output.exists() or not args.output.resolve().is_relative_to(local/'n5/research-extension-20260928'):
        raise ValueError('Fresh private extension receipt required')
    rows=[audit(name,local/'n5/prepi-20260928') for name in ('a0-d1-e0-v2','a2-d1-e0-v1')]
    result=dict(status='RETAINED_TIMING_COVERAGE_AUDIT_ONLY',utc=datetime.now(timezone.utc).isoformat(),
        code=[bind(HERE/name) for name in ('audit_retained_costs_v1.py','README_RETAINED_COSTS_V1.md')],rows=rows,
        new_inference=False,CM5_tested=False,
        recommendation='Persist bounded cumulative ASR/D1/E0 counters independently of rotating event logs; validate accounting before performance comparisons.')
    freeze(args.output,result)
    print(json.dumps(dict(status=result['status'],rows=[{k:r[k] for k in ('run','publication_sequence','retained_cost_event_counts','lifecycle_embedding_calls')} for r in rows]),indent=2))


if __name__=='__main__':main()
