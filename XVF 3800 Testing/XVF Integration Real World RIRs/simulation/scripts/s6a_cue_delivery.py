"""Sanitize historical physical XVF delivery for app profiles; README_S6A_CUES.md."""
from __future__ import annotations
import bisect
import json
import math
from pathlib import Path
import time
from s6a_cues import read,save,binding,verified,write_csv,DEFAULT_REPORT,PRIOR,BANK,now
from s4_spatial_analysis import ReceiptTimeline,FIELDS
from s4_telemetry import normalize_observation


def sanitize(metadata,capture,raw_rows):
    callbacks=metadata['callback_times'];startup=capture['framing']['startup_frames_excluded']
    times=[r.get('host_copy_complete_monotonic_ns',r['host_callback_monotonic_ns']) for r in callbacks]
    if any(a>b for a,b in zip(times,times[1:])):raise ValueError('nonmonotonic callbacks')
    timeline=ReceiptTimeline(raw_rows);result=[];quantization=[];outside=0;invalid=0
    for raw in raw_rows:
        if raw.get('command')!=FIELDS[2]:continue
        row=normalize_observation(raw);receipt=row['available_monotonic_ns']
        if not isinstance(receipt,int):invalid+=1;continue
        index=bisect.bisect_left(times,receipt)
        if index>=len(callbacks):outside+=1;continue
        callback=callbacks[index]
        available=(callback['first_native_frame']+callback['frames']-startup)/48000.
        if available<0:outside+=1;continue
        # Only fields already delivered at this selected-angle receipt can be
        # attached. Newer energy/directions from the containing callback are
        # not borrowed. DSP observation time is not known and is not invented.
        state=timeline.state('selected_processed',receipt)
        automatic=timeline.state('selected_auto',receipt)
        energy=timeline.state('raw_auto',receipt)['energy']
        disagreement=(abs(state['angle_deg']-automatic['angle_deg'])
                      if state['angle_deg'] is not None and automatic['angle_deg'] is not None else None)
        reliability=1. if disagreement is None else max(.2,1.-disagreement/90.)
        delay=(times[index]-receipt)/1e9
        valid=bool(state['available']) and delay<=.25
        # Conservative loss of confidence for the explicit host-to-callback
        # quantization delay, not a claim of calibrated sensor reliability.
        reliability*=max(0.,1.-delay/.25)
        result.append(dict(angle_deg=state['angle_deg'],available_at_sec=available,
                           energy=energy,reliability=reliability,valid=valid,
                           sequence=int(raw.get('receipt_sequence',raw.get('sequence',len(result))))))
        quantization.append(delay)
    return result,dict(selected_rows=len(result),outside_capture_rows=outside,invalid_host_stamp_rows=invalid,
                        host_to_callback_delay_max_sec=max(quantization,default=None),
                        host_to_callback_delay_mean_sec=sum(quantization)/len(quantization) if quantization else None,
                        native_dsp_observation_time='UNKNOWN_NOT_EXPOSED',source_span_supplied=False)


def generate(report=DEFAULT_REPORT):
    from app.edge_speech_pipeline.research_profiles import JsonSpatialProvider
    report=Path(report);bank=read(BANK);allowed={s['case_id'] for s in bank['scenes']}
    captures=read(PRIOR/'CAPTURE_ANALYSIS.json')['cases']
    if len(allowed)!=240 or len(captures)!=240:raise ValueError('require all240')
    started=time.perf_counter();rows=[]
    for capture in sorted(captures,key=lambda r:r['case_id']):
        cid=capture['case_id']
        if cid not in allowed:raise PermissionError('outside canonicalbank')
        cap_path=verified(capture['case_result']);folder=cap_path.parent
        metadata=folder/'capture_metadata.json';telemetry=folder/'telemetry/received_telemetry.jsonl'
        raw=[json.loads(line) for line in telemetry.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        values,stats=sanitize(read(metadata),read(cap_path),raw)
        destination=report/'cues/delivered'/f'{cid}.jsonl';destination.parent.mkdir(parents=True,exist_ok=True)
        payload=''.join(json.dumps(v,allow_nan=False,separators=(',',':'))+'\n' for v in values)
        if destination.exists():
            if destination.read_text(encoding='utf-8')!=payload:raise ValueError('sanitized output changed; version required')
        else:destination.write_text(payload,encoding='utf-8')
        provider=JsonSpatialProvider(destination)
        if len(provider.rows)!=len(values):raise ValueError('actual app provider did not preserve rows')
        rows.append(dict(case_id=cid,streams=['O0','O1'],sanitized=binding(destination),statistics=stats,
                         capture=capture['case_result'],metadata=binding(metadata),raw_telemetry=binding(telemetry)))
        if len(rows)%40==0:print(json.dumps(dict(phase='SANITIZED_DELIVERY',completed=len(rows),elapsed_sec=time.perf_counter()-started)),flush=True)
    result=dict(schema='jp_s6a_sanitized_delivery_v1',status='COMPLETE',physical_traces=240,rows=rows,
                created_utc=now(),elapsed_sec=time.perf_counter()-started,code=binding(__file__),
                predictor_fields=['angle_deg','available_at_sec','energy','reliability','valid','sequence'],
                mapping='Selected host receipt -> first containing-or-later copy-complete callback -> captured output frame end excluding startup; no source truth/correlation lag',
                energy='Latest independently fresh raw-auto energy at selected-angle receipt; non-atomic and not calibrated VAD',
                omitted_fields='DSP observation timestamp, source receptive span, participant/text/room/seat/source labels',
                limitations=['Callback quantization conservatively delays delivery; exact physical latency unknown',
                             'Observation-source age cannot be established; delivery freshness only',
                             'Historical DSP state or RT60 not available','Raw/focused/selected fields are not atomic DSP frames'])
    save(report/'CUE_DELIVERY_INDEX.json',result);return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,default=DEFAULT_REPORT)
    args=parser.parse_args();result=generate(args.report)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
