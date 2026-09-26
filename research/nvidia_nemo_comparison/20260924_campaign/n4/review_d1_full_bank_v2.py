"""Review all full-bank D1 cells. See README_D1_FRAME_CLOCK_V2.md."""
import argparse
import gzip
import json
from pathlib import Path
import sys
from common import bind,verify,load,freeze,fingerprint
from d1_full_bank import verify_admission,require_predecessor,component_key,event_digest,supervisor
from review_d1_frame_clock_v2 import scan_events


OWN=('review_d1_frame_clock_v2.py','review_d1_full_bank_v2.py','test_d1_frame_clock_v2.py','test_review_d1_full_bank_v2.py','README_D1_FRAME_CLOCK_V2.md')

def code_bindings():
    here=Path(__file__).resolve().parent
    return [bind(here/n) for n in OWN+('review_d1_components.py','review_d1_full_bank.py','test_review_d1_components.py','test_review_d1_full_bank.py','test_d1_lane_components.py')]

def review(args):
    code=code_bindings()
    import soundfile as sf
    contract = verify_admission(args.run/'ADMISSION.json')
    result = load(args.run/'RESULT.json')
    if (Path(contract['output']).resolve() != args.run.resolve()
            or result['status'] != 'FULL_BANK_COLLECTED_REQUIRES_REVIEW' or result['completed'] != 960
            or result['total'] != 960 or result['child'] is not None or supervisor.same_process(result['owner'])
            or result['admission'] != bind(args.run/'ADMISSION.json')):
        raise ValueError('Require terminal 960-cell D1 evidence and exited exact coordinator')
    if contract['total']!=960 or len(contract['jobs'])!=480 or contract['encoders']!=['E0','E1']:
        raise ValueError('Full D1 admission census differs')
    if result['predecessor_review']!=require_predecessor(contract):raise ValueError('ASR predecessor review differs')
    initial=[bind(args.run/'ADMISSION.json'),bind(args.run/'RESULT.json')]
    source = Path(contract['source'])
    sys.path[:0] = [str(source), str(source/'vendor')]
    from app.n2_pipeline import ActivityTimeline
    from app.n2_models import redim_namespace
    from app.pipeline import effective_profile
    from app.paths import pipeline_config
    runtime = load(contract['component_contract']['runtime']['path'])
    rows, pairs = [], {}
    bindings=[];expanded_bytes=0
    for encoder in contract['encoders']:
        terminal = load(args.run/encoder/'RESULT.json')
        index = load(args.run/encoder/'RESULT_INDEX.json')
        if (bind(args.run/encoder/'RESULT.json') not in result['encoders'] or terminal['status'] != 'COMPLETE'
                or terminal['completed'] != 480 or terminal['total'] != 480 or terminal['cpu_affinity'] != [4]
                or index['completed'] != 480 or index['total'] != 480 or index['cells'] != terminal['cells']
                or set(index['cells']) != {j['job_id'] for j in contract['jobs']}):
            raise ValueError('Per-encoder terminal census differs')
        bindings.extend([bind(args.run/encoder/'RESULT.json'),bind(args.run/encoder/'RESULT_INDEX.json')])
        for job in contract['jobs']:
            cell = args.run/encoder/job['job_id']
            binding = bind(cell/'RESULT.json')
            if binding != index['cells'][job['job_id']]: raise ValueError('Indexed cell binding differs')
            bindings.append(binding)
            data = load(cell/'RESULT.json')
            profile = effective_profile('balanced', 'anonymous_conversation', job['tap'])
            config = profile.apply(pipeline_config(args.run/'unused-private-root', Path(contract['models_root'])))
            namespace = runtime['embedding_namespace'] if encoder == 'E1' else redim_namespace(config)
            if (data['status'] != 'COMPLETE' or data['job'] != job or data['encoder'] != encoder
                    or data['admission_sha256'] != bind(args.run/'ADMISSION.json')['sha256']
                    or data['profile_sha256'] != fingerprint(profile.to_dict())
                    or profile.to_dict() != contract['profiles'][job['tap']]
                    or data['cache_key'] != component_key(contract, job, encoder, profile.to_dict())
                    or data['namespace'] != namespace or data['cpu_affinity'] != [4]
                    or data['actual_neural_inference'] is not True or data['integrated_N4_cells'] != 0
                    or data['events'] != bind(cell/'D1_EVENTS.jsonl.gz')
                    or data['events_expanded'] != event_digest(cell/'D1_EVENTS.jsonl.gz')):
                raise ValueError('Cell cache/source/asset/evidence contract differs')
            if bind(job['audio_path'])['sha256'] != job['audio_sha256']: raise ValueError('Waveform hash differs')
            wave, rate = sf.read(job['audio_path'], dtype='float32')
            if rate != 16000 or wave.ndim != 1 or len(wave) != job['frames']: raise ValueError('Waveform format differs')
            with gzip.open(cell/'D1_EVENTS.jsonl.gz', 'rt', encoding='utf-8') as stream:
                events = [json.loads(line) for line in stream]
            expected_tracks=[f"{job['job_id']}:nemotron-slot-{s}" for s in range(8)]
            if any(e['payload']['track_ids']!=expected_tracks for e in events if e['event_type']=='n2_diarization_frames'):
                raise ValueError('Native track IDs do not belong to this independent scene')
            native = next(e['payload'] for e in events if e['event_type'] == 'n2_diarization_binding')
            if (native['model_sha256'] != bind(runtime['nemotron_model'])['sha256']
                    or native['library_sha256'] != runtime['nemotron_library_sha256']
                    or native['gpu'] is not False or native['profile']['name'] != 'low_latency'):
                raise ValueError('Actual native model/runtime binding differs')
            scan = scan_events(events, wave, data['summary'], namespace, ActivityTimeline)
            paired = pairs.setdefault(job['job_id'], scan)
            if paired != scan: raise ValueError('E0/E1 native frame or query geometry differs')
            rows.append(dict(encoder=encoder, job_id=job['job_id'], result=binding, **scan))
            expanded_bytes+=data['events_expanded']['uncompressed_bytes']
    for binding in initial+bindings+code:verify(binding)
    if args.output.exists(): raise ValueError('Preserve previous review; choose a new output')
    args.output.mkdir(parents=True)
    receipt = dict(status='PASS_D1_FULL_BANK_COMPONENTS_ONLY', reviewed_utc=supervisor.now(),
        admission=bind(args.run/'ADMISSION.json'), terminal=bind(args.run/'RESULT.json'),
        reviewer=bind(Path(__file__)), code=code, native_frame_interval='EXACT_MANIFEST_VALUE_FOR_ENDPOINTS_AND_ACTIVITY_TIMELINE', component_cells=960, paired_files=480, rows=rows,
        integrated_N4_cells=0, full_bank_component_coverage=True, Controller_widget_parity=False)
    freeze(args.output/'REVIEW.json', receipt)
    redacted={k:v for k,v in receipt.items() if k!='rows'}
    redacted.update(private_review=bind(args.output/'REVIEW.json'),expanded_bytes_verified=expanded_bytes,
        matched_query_windows_per_encoder=sum(r['embeddings'] for r in pairs.values()),
        native_frames_per_encoder=sum(r['native_frames'] for r in pairs.values()),
        short_runs_per_encoder=sum(r['short_runs'] for r in pairs.values()),
        files_without_queries_per_encoder=sum(r['embeddings']==0 for r in pairs.values()))
    freeze(args.output/'REDACTED_REVIEW.json',redacted)
    print(json.dumps(dict(status=receipt['status'],review=bind(args.output/'REVIEW.json'))))
    return redacted


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    import psutil
    psutil.Process().cpu_affinity([14])
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    review(parser.parse_args())
