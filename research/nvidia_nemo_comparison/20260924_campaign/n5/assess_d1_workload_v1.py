"""Saved-bank workload bounds, not a deployed gate; README_D1_WORKLOAD_V1.md."""
import argparse
from collections import defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import sys
import time
import wave

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'n4'))
from common import bind, freeze, load, verify
from metric_process import pin

RATE = 16000
FRAME = 320


def union(intervals):
    result = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def length(intervals):
    return sum(b-a for a, b in union(intervals))


def intersection(left, right):
    left, right = union(left), union(right)
    i = j = total = 0
    while i < len(left) and j < len(right):
        a, b = left[i]
        c, d = right[j]
        total += max(0, min(b, d)-max(a, c))
        if b <= d:
            i += 1
        else:
            j += 1
    return total


def pad(intervals, samples, before=3200, after=6400):
    return union((max(0, a-before), min(samples, b+after)) for a, b in intervals)


def energy_intervals(audio, threshold_db):
    # Frame RMS is a deliberately simple acoustic-energy cue, NOT speech VAD.
    import numpy as np
    n = len(audio)
    padded = np.pad(audio.astype(np.float64), (0, (-n) % FRAME))
    sums = (padded.reshape(-1, FRAME)**2).sum(axis=1)
    counts = np.full(len(sums), FRAME)
    counts[-1] = n-(len(sums)-1)*FRAME
    active = np.flatnonzero(sums/counts >= 10**(threshold_db/10))
    return pad([(int(i)*FRAME, min(n, (int(i)+1)*FRAME)) for i in active], n)


def queue_bound(intervals, samples, rtf, release_delay=.22):
    """Ideal FIFO service of retained 20ms work; no resets/cache/context costs."""
    finish = peak = 0.0
    for a, b in union(intervals):
        cursor = a
        while cursor < b:
            end = min(cursor+FRAME, b)
            available = end/RATE+release_delay
            finish = max(finish, available)+(end-cursor)/RATE*rtf
            peak = max(peak, finish-available)
            cursor = end
    return dict(peak_work_backlog_seconds=peak,
                after_eof_drain_seconds=max(0.0, finish-samples/RATE),
                longest_retained_run_seconds=max((b-a for a, b in union(intervals)), default=0)/RATE)


def overlap_intervals(turns):
    # Merge by identity first: overlapping turns by the same identity count once.
    speakers = defaultdict(list)
    for turn in turns:
        speakers[turn['identity']].extend(turn['activity_ranges_samples_estimated'])
    edges = defaultdict(int)
    for intervals in speakers.values():
        for a, b in union(intervals):
            edges[a] += 1
            edges[b] -= 1
    result, count, previous = [], 0, 0
    for position, delta in sorted(edges.items()):
        if count >= 2:
            result.append((previous, position))
        count += delta
        previous = position
    return union(result)


def final_asr_support(result):
    verify(result['events'])
    finals = {}
    with gzip.open(result['events']['path'], 'rt', encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            if event['event_type'] == 'research_asr_observation':
                p = event['payload']
                if p['final']:
                    finals[p['utterance_id']] = p
    intervals = [(round(p['source_start_sec']*RATE), round(p['source_end_sec']*RATE))
                 for p in finals.values() if p['text'].strip()]
    return pad(intervals, result['job']['frames'])


def aggregate(rows):
    audio = sum(r['audio_seconds'] for r in rows)
    retained = sum(r['retained_seconds'] for r in rows)
    complete = [r for r in rows if r['complete_reference']]
    known = sum(r['reference_speech_seconds'] for r in complete)
    missed = sum(r['missed_reference_seconds'] for r in complete)
    overlap = sum(r['overlap_seconds'] for r in complete)
    missed_overlap = sum(r['missed_overlap_seconds'] for r in complete)
    return dict(files=len(rows), audio_seconds=audio,
                retained_percent=100*retained/audio,
                ideal_desktop_service_rtf=sum(r['ideal_compute_seconds'] for r in rows)/audio,
                files_ideal_service_rtf_over_one=sum(r['ideal_compute_seconds'] > r['audio_seconds'] for r in rows),
                worst_ideal_after_eof_drain_seconds=max(r['ideal_queue']['after_eof_drain_seconds'] for r in rows),
                worst_ideal_peak_work_backlog_seconds=max(r['ideal_queue']['peak_work_backlog_seconds'] for r in rows),
                complete_reference_files=len(complete), reference_speech_seconds=known,
                missed_reference_seconds=missed, missed_reference_percent=100*missed/known if known else None,
                overlap_seconds=overlap, missed_overlap_percent=100*missed_overlap/overlap if overlap else None,
                short_turns=sum(r['short_turns'] for r in complete),
                entirely_lost_short_turns=sum(r['entirely_lost_short_turns'] for r in complete))


def assess(output_dir, public_output):
    process = pin()
    import numpy as np
    import psutil
    started = time.monotonic()
    if output_dir.exists() or public_output.exists():
        raise ValueError('Fresh output paths required; preserve prior attempts')
    free = {disk: psutil.disk_usage(disk).free/2**30 for disk in ('C:\\', 'G:\\')}
    if free['C:\\'] < 50 or free['G:\\'] < 75:
        raise ValueError('Storage reserve failed')
    local = HERE.parents[4] / 'local'
    worker = load(local/'supervision/worker.json')
    if worker.get('status') not in ('COMPLETED', 'COMPLETE', 'FAILED', 'STOPPED'):
        raise ValueError('Supervisor not terminal; inspect owner before admitting analysis')
    plan_path = local/'n4/integrated-main-plan-v3.json'
    plan = load(plan_path)
    reviews = plan['context']['reviews']
    for key in ('ASR', 'D1'):
        verify(reviews[key])
    truth_path = local/'n2/evaluation/EVALUATOR_TRUTH.json'
    truth = {r['job_id']: r for r in load(truth_path)['cells']}
    catalogue_path = HERE.parent/'data/CORPUS_CATALOGUE_240.csv'
    with catalogue_path.open(encoding='utf-8-sig') as stream:
        catalogue = {r['case_id']: r for r in csv.DictReader(stream)}
    d1 = {r['job_id']: r for r in load(reviews['D1']['path'])['rows'] if r['encoder'] == 'E0'}
    asr = {(r['variant'], Path(r['result']['path']).parent.name): r
           for r in load(reviews['ASR']['path'])['cells'] if r['variant'] in ('A0', 'A2')}
    if len(d1) != 480 or len(asr) != 960 or set(d1) != set(truth):
        raise ValueError('Full-bank join failed')
    inputs = [bind(plan_path), bind(truth_path), bind(catalogue_path), reviews['ASR'], reviews['D1']]
    rows = []
    # Thresholds and padding declared before any results; do not tune to this bank.
    for index, (job_id, dr) in enumerate(sorted(d1.items()), 1):
        if time.monotonic()-started > 600:
            raise TimeoutError('Ten-minute analysis budget exceeded')
        verify(dr['result'])
        d = load(dr['result']['path'])
        if d['status'] != 'COMPLETE':
            raise ValueError('Incomplete D1 evidence')
        job = d['job']
        audio_binding = bind(job['audio_path'])
        if audio_binding['sha256'] != job['audio_sha256'] or job['gain'] != 1:
            raise ValueError('Prepared audio identity or gain changed')
        with wave.open(job['audio_path'], 'rb') as stream:
            if (stream.getnchannels(), stream.getframerate(), stream.getsampwidth(), stream.getnframes()) != (1, RATE, 2, job['frames']):
                raise ValueError('Expected exact prepared mono PCM16 input')
            audio = np.frombuffer(stream.readframes(job['frames']), dtype='<i2').astype(np.float32)/32768
        gates = {f'energy_{db}dB': energy_intervals(audio, db) for db in (-55, -45, -35)}
        inputs.extend((dr['result'], audio_binding))
        for variant in ('A0', 'A2'):
            ab = asr[variant, job_id]['result']
            verify(ab)
            a = load(ab['path'])
            if a['status'] != 'COMPLETE' or a['job'] != job:
                raise ValueError('ASR/D1 source join failed')
            gates[f'{variant}_final_OFFLINE'] = final_asr_support(a)
            gates[f'energy_-45dB_OR_{variant}_final_OFFLINE'] = union(gates['energy_-45dB']+gates[f'{variant}_final_OFFLINE'])
            inputs.extend((ab, a['events']))
        # Evaluation-only oracle is added AFTER audio-only cue construction.
        t = truth[job_id]
        if t['frames'] != job['frames']:
            raise ValueError('Truth duration differs')
        reference = union([x for turn in t['turns'] for x in turn['activity_ranges_samples_estimated']])
        overlap = overlap_intervals(t['turns'])
        gates['estimated_speech_ORACLE'] = reference
        gates['ungated'] = [[0, job['frames']]]
        seconds = job['frames']/RATE
        rtf = d['elapsed_seconds']/seconds
        for name, support in gates.items():
            short = [turn['activity_ranges_samples_estimated'] for turn in t['turns']
                     if 0 < length(turn['activity_ranges_samples_estimated']) <= RATE]
            retained = length(support)/RATE
            rows.append(dict(job_id=job_id, tap=job['tap'], family=catalogue[t['case_id']]['family'],
                method=name, reference_class=t['reference_class'], complete_reference=t['complete_reference'],
                audio_seconds=seconds, retained_seconds=retained,
                reference_speech_seconds=length(reference)/RATE,
                missed_reference_seconds=(length(reference)-intersection(reference, support))/RATE,
                overlap_seconds=length(overlap)/RATE,
                missed_overlap_seconds=(length(overlap)-intersection(overlap, support))/RATE,
                short_turns=len(short), entirely_lost_short_turns=sum(intersection(x, support) == 0 for x in short),
                retained_runs=len(support), observed_ungated_desktop_rtf=rtf,
                ideal_compute_seconds=retained*rtf,
                ideal_queue=queue_bound(support, job['frames'], rtf)))
        if index % 80 == 0:
            print(f'Analyzed {index}/480 saved files', flush=True)
    methods = sorted({r['method'] for r in rows})
    aggregates = {name: aggregate([r for r in rows if r['method'] == name]) for name in methods}
    groups = {name: {tap: aggregate([r for r in rows if r['method'] == name and r['tap'] == tap])
                    for tap in ('O0', 'O1')} for name in methods}
    elapsed = time.monotonic()-started
    summary = dict(schema='d1-workload-assessment-v1', status='DIAGNOSTIC_ONLY_NO_DEPLOYED_GATE',
        files=480, independent_scenarios=240, thresholds_dbfs=[-55, -45, -35],
        energy_frame_seconds=.02, pre_roll_seconds=.2, hangover_seconds=.4,
        analysis_elapsed_seconds=elapsed, cpu_affinity=process.cpu_affinity(),
        aggregate=aggregates, by_tap=groups,
        limitations=['Energy is not a speech classifier; estimated 20ms reference activity is not gold alignment.',
          'Final ASR and oracle methods are noncausal diagnostics, never production decisions or latency measurements.',
          'Queue simulation assumes ideal 20ms dispatch at source end +220ms, including noncausal methods as bounds.',
          'Linear scaling from desktop ungated collection RTF excludes state repair, rewarming, real native chunks, fusion and new gate overhead.',
          'No compressed/discontinuous waveform was passed to Nemotron. Speaker continuity and resulting DER are untested.',
          'Incomplete ambient references excluded from speech-loss denominators, but included in workload totals.',
          'Two taps share scenes; 480 files are not 480 independent conversations. No continuous long-session proof.',
          'No Pi, new neural inference, training, audio device use or new download. No stage acceptance.'])
    freeze(output_dir/'ROWS.json', rows)
    freeze(output_dir/'RECEIPT.json', dict(summary=summary, inputs=inputs,
        rows=bind(output_dir/'ROWS.json'), source=[bind(__file__), bind(HERE/'README_D1_WORKLOAD_V1.md')],
        process=dict(pid=process.pid, create_time=process.create_time()), free_gib=free))
    summary['private_receipt_sha256'] = bind(output_dir/'RECEIPT.json')['sha256']
    summary['script_sha256'] = bind(__file__)['sha256']
    freeze(public_output, summary)
    print(json.dumps(aggregates, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--public-output', type=Path, required=True)
    args = parser.parse_args()
    assess(args.output_dir, args.public_output)
