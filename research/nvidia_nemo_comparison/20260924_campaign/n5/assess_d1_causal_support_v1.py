"""Availability-aware support replay; see README_D1_CAUSAL_SUPPORT_V1.md."""
import argparse
import gzip
import json
from pathlib import Path
import time
from assess_d1_workload_v1 import (HERE, RATE, FRAME, pin, load, bind, verify,
                                 freeze, union, length, intersection, queue_bound, aggregate)


def support_before_deadline(energy_support, observations, samples, decision_delay):
    """20ms conservative support: an ASR observation must exist by the deadline."""
    import numpy as np
    if decision_delay < .22:
        raise ValueError('Energy pre-roll needs at least 220ms decision delay')
    starts = np.arange(0, samples, FRAME)
    ends = np.minimum(starts+FRAME, samples)
    keep = np.zeros(len(starts), dtype=bool)
    for a, b in energy_support:
        keep |= (starts < b) & (ends > a)
    deadlines = ends/RATE+decision_delay
    for observation in observations:
        start, end, available = observation
        if available < end-1e-6 or start > end:
            raise ValueError('ASR observation violates causal source support')
        keep |= ((starts/RATE < end+.4) & (ends/RATE > max(0, start-.2)) & (deadlines >= available))
    return union([(int(a), int(b)) for a, b in zip(starts[keep], ends[keep])])


def assess(output_dir, public_output):
    process = pin()
    import psutil
    start_clock = time.monotonic()
    if output_dir.exists() or public_output.exists():
        raise ValueError('Fresh output required')
    for disk, minimum in [('C:\\', 50), ('G:\\', 75)]:
        if psutil.disk_usage(disk).free < minimum*2**30:
            raise ValueError('Storage reserve failed')
    local = HERE.parents[4]/'local'
    if load(local/'supervision/worker.json').get('status') != 'COMPLETED':
        raise ValueError('Inspect supervisor ownership before admitting replay')
    base = local/'n5/d1-workload-v1'
    receipt = load(base/'RECEIPT.json')
    verify(receipt['rows'])
    # Parent bindings verify the bank, source timing and result identities.
    for binding in receipt['inputs']:
        if not str(binding['path']).lower().endswith('.wav'):
            verify(binding)
    truth = {r['job_id']: r for r in load(local/'n2/evaluation/EVALUATOR_TRUTH.json')['cells']}
    parent_rows = {r['job_id']: r for r in load(base/'ROWS.json') if r['method'] == 'energy_-45dB'}
    plan = load(local/'n4/integrated-main-plan-v3.json')
    review = load(plan['context']['reviews']['ASR']['path'])
    inputs = [bind(base/'RECEIPT.json'), receipt['rows']]
    rows = []
    # Energy intervals are reconstructed from the SAME verified saved waveform.
    import wave
    import numpy as np
    from assess_d1_workload_v1 import energy_intervals
    for index, cell in enumerate([r for r in review['cells'] if r['variant'] in ('A0', 'A2')], 1):
        if time.monotonic()-start_clock > 600:
            raise TimeoutError('Ten-minute analysis budget exceeded')
        verify(cell['result'])
        a = load(cell['result']['path'])
        job = a['job']
        if a['status'] != 'COMPLETE' or bind(job['audio_path'])['sha256'] != job['audio_sha256']:
            raise ValueError('ASR source changed')
        with wave.open(job['audio_path'], 'rb') as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()) != (1, 2, RATE, job['frames']):
                raise ValueError('Audio format changed')
            audio = np.frombuffer(stream.readframes(job['frames']), dtype='<i2').astype(np.float32)/32768
        energy = energy_intervals(audio, -45)
        parent = parent_rows[job['job_id']]
        if abs(length(energy)/RATE-parent['retained_seconds']) > 1e-8:
            raise ValueError('Energy support does not reproduce parent')
        verify(a['events'])
        observations = []
        with gzip.open(a['events']['path'], 'rt', encoding='utf-8') as stream:
            for line in stream:
                event = json.loads(line)
                if event['event_type'] == 'research_asr_observation':
                    p = event['payload']
                    if p['text'].strip():
                        observations.append((p['source_start_sec'], p['source_end_sec'], p['available_at_sec']))
        t = truth[job['job_id']]
        reference = union([x for turn in t['turns'] for x in turn['activity_ranges_samples_estimated']])
        from assess_d1_workload_v1 import overlap_intervals
        overlap = overlap_intervals(t['turns'])
        short = [turn['activity_ranges_samples_estimated'] for turn in t['turns'] if 0 < length(turn['activity_ranges_samples_estimated']) <= RATE]
        for delay in (.22, 1.0, 2.0, 4.0):
            support = support_before_deadline(energy, observations, job['frames'], delay)
            retained = length(support)/RATE
            rows.append({**parent, 'method': f'energy_-45dB_OR_{cell["variant"]}_partial_delay_{delay}',
                'retained_seconds': retained, 'retained_runs': len(support),
                'missed_reference_seconds': (length(reference)-intersection(reference, support))/RATE,
                'missed_overlap_seconds': (length(overlap)-intersection(overlap, support))/RATE,
                'entirely_lost_short_turns': sum(intersection(x, support) == 0 for x in short),
                'ideal_compute_seconds': retained*parent['observed_ungated_desktop_rtf'],
                'ideal_queue': queue_bound(support, job['frames'], parent['observed_ungated_desktop_rtf'], delay)})
        inputs.extend((cell['result'], a['events']))
        if index % 160 == 0:
            print(f'Replayed {index}/960 existing ASR traces', flush=True)
    methods = sorted({r['method'] for r in rows})
    result = dict(schema='d1-causal-support-v1', status='MODELED_AVAILABILITY_REPLAY_ONLY',
        files_per_method=480, independent_scenarios=240, aggregate={m: aggregate([r for r in rows if r['method'] == m]) for m in methods},
        analysis_elapsed_seconds=time.monotonic()-start_clock, cpu_affinity=process.cpu_affinity(),
        limitations=['Recorded availability is the component collector modeled serial ASR clock, not CM5 or integrated runtime arrival.',
          'Use every nonempty partial/final observation as positive evidence only after its recorded availability; later retractions cannot erase retained work.',
          'Gate decisions occur at each 20ms frame end plus fixed delay; late ASR never rescues already discarded frames.',
          'Frames intersecting coarse ASR support are conservatively retained; no exact word boundaries or calibrated confidences.',
          'Same linear desktop cost/queue bounds as parent; real chunk state, gate cost and speaker continuity not measured.',
          'No model/device/Pi access or deployed gate; no new DER, WER, effective RTF or stage acceptance claim.'])
    freeze(output_dir/'ROWS.json', rows)
    freeze(output_dir/'RECEIPT.json', dict(summary=result, inputs=inputs, rows=bind(output_dir/'ROWS.json'),
        code=[bind(__file__), bind(HERE/'assess_d1_workload_v1.py'), bind(HERE/'README_D1_CAUSAL_SUPPORT_V1.md')],
        process=dict(pid=process.pid, create_time=process.create_time())))
    result['private_receipt_sha256'] = bind(output_dir/'RECEIPT.json')['sha256']
    freeze(public_output, result)
    print(json.dumps(result['aggregate'], indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--public-output', type=Path, required=True)
    args = p.parse_args()
    assess(args.output_dir, args.public_output)
