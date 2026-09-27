"""Read verified N4 D1 receipts; summarize measurements without loading models."""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import statistics


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def bound_load(binding):
    path = Path(binding['path'])
    if path.stat().st_size != binding['bytes'] or digest(path) != binding['sha256']:
        raise ValueError(f'Changed input: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def summarize(check_path):
    check = json.loads(check_path.read_text(encoding='utf-8'))
    if check['status'] != 'PASS_D1_FULL_BANK_COMPONENTS_ONLY':
        raise ValueError('Expected independently reviewed D1 bank')
    review = bound_load(check['private_review'])
    if len(review['rows']) != 960:
        raise ValueError('Incomplete cell census')
    groups = collections.defaultdict(list)
    seen = set()
    for row in review['rows']:
        cell = bound_load(row['result'])
        key = (cell['encoder'], row['job_id'])
        if key in seen or cell['status'] != 'COMPLETE' or cell['cpu_affinity'] != [4]:
            raise ValueError('Unexpected or duplicate cell')
        seen.add(key)
        b = cell['events']
        path = Path(b['path'])
        if path.stat().st_size != b['bytes'] or digest(path) != b['sha256']:
            raise ValueError(f'Changed events: {path}')
        durations = collections.defaultdict(list)
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                event = json.loads(line)
                typ, payload = event['event_type'], event['payload']
                if typ == 'n2_diarization_binding':
                    if payload['gpu'] or payload['input_buffer_sec'] != 1.04:
                        raise ValueError('Unexpected native device/profile')
                if typ in ('component_d1_dispatch', 'component_d1_embedding_call'):
                    elapsed = payload['actual_finished_elapsed_sec'] - payload['actual_started_elapsed_sec']
                    if elapsed < 0:
                        raise ValueError('Invalid actual call clock')
                    durations[typ].append(elapsed)
        if len(durations['component_d1_embedding_call']) != cell['summary']['embeddings']:
            raise ValueError('Embedding call census mismatch')
        groups[cell['encoder']].append(dict(
            audio_seconds=cell['summary']['input_samples']/16000,
            elapsed_seconds=cell['elapsed_seconds'],
            postcell_rss_bytes=cell['process_rss_bytes'],
            durations=durations))
    rows = []
    for encoder, cells in sorted(groups.items()):
        if len(cells) != 480:
            raise ValueError('Unmatched encoder population')
        audio = sum(c['audio_seconds'] for c in cells)
        elapsed = sum(c['elapsed_seconds'] for c in cells)
        rtfs = [c['elapsed_seconds']/c['audio_seconds'] for c in cells]
        calls = {}
        for kind in ('component_d1_dispatch', 'component_d1_embedding_call'):
            values = [d for c in cells for d in c['durations'][kind]]
            calls[kind] = dict(count=len(values), wall_seconds=sum(values),
                               wall_seconds_per_audio_second=sum(values)/audio,
                               mean_milliseconds=1000*statistics.mean(values),
                               maximum_milliseconds=1000*max(values))
        rows.append(dict(encoder=encoder, cells=len(cells), audio_seconds=audio,
                         collection_wall_seconds=elapsed, collection_wall_rtf=elapsed/audio,
                         median_cell_collection_wall_rtf=statistics.median(rtfs),
                         minimum_cell_collection_wall_rtf=min(rtfs),
                         maximum_cell_collection_wall_rtf=max(rtfs),
                         cells_collection_slower_than_source=sum(x>1 for x in rtfs),
                         maximum_postcell_rss_mib=max(c['postcell_rss_bytes'] for c in cells)/1048576,
                         actual_timed_calls=calls,
                         remaining_collection_wall_seconds=elapsed-sum(x['wall_seconds'] for x in calls.values())))
    return dict(schema='d1-processing-summary-v1', status='VERIFIED_EXISTING_MEASUREMENTS',
                source_check=dict(name=check_path.name, sha256=digest(check_path)),
                source_review_sha256=check['private_review']['sha256'],
                script_sha256=digest(Path(__file__)), verified_cells=len(seen), rows=rows,
                scope='CPU4 affinity, one native thread, Q8 nominal 1.04s; saved audio only. Actual call wall times include preemption. Collection includes observer/log compression and first native load. RSS is post-cell, not a sampled peak. No ASR/GUI, GPU-memory, live-latency or Pi claim. No models run by this summarizer.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', type=Path, default=Path(__file__).parent.parent/'n4/D1_FULL_BANK_REVIEW_V3.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a fresh output path; existing evidence is immutable')
    result = summarize(args.check)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
