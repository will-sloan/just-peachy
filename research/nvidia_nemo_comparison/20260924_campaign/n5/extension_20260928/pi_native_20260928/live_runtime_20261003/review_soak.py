"""Streaming review of a fully mirrored continuous component run. README_SOAK_REVIEW.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False, indent=2).encode()
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise OSError('Short review write')
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise OSError('Review readback differs')


class Stats:
    def __init__(self):
        self.count = 0
        self.total = 0.
        self.minimum = self.maximum = self.first = self.last = None

    def add(self, value):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Finite exact numeric measurement required')
        if not self.count:
            self.first = self.minimum = self.maximum = value
        self.count += 1
        self.total += value
        self.last = value
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    def result(self):
        return dict(count=self.count, first=self.first, last=self.last,
                    min=self.minimum, max=self.maximum,
                    mean=self.total/self.count if self.count else None)


def records(root):
    pending = b''
    for path in sorted(root.glob('calls-jsonl-*.bin')):
        if path.stat().st_size > 16*1024**2:
            raise ValueError('Call segment exceeds retained limit')
        with path.open('rb') as stream:
            for raw in iter(lambda: stream.read(65536), b''):
                pending += raw
                while b'\n' in pending:
                    line, pending = pending.split(b'\n', 1)
                    if not 0 < len(line) <= 4096:
                        raise ValueError('Call record bound')
                    yield json.loads(line)
                if len(pending) > 4096:
                    raise ValueError('Unterminated call bound')
    if pending:
        raise ValueError('Truncated final call')


def aggregate(rows, bin_seconds=600):
    bins = {}
    count = 0
    previous_samples = 0
    previous_index = -1
    pss_clock = None
    for row in rows:
        index = row['call_index']
        if type(index) is not int or index != previous_index+1:
            raise ValueError('Continuous unique call sequence required')
        previous_index = index
        samples = row['source_samples']
        if type(samples) is not int or samples < previous_samples:
            raise ValueError('Source clock regressed')
        added = samples-previous_samples
        previous_samples = samples
        bucket = int(max(0, samples-added)/16000)//bin_seconds
        # Finish belongs to the final represented audio interval.
        if not added and samples:
            bucket = int((samples-1)/16000)//bin_seconds
        b = bins.setdefault(bucket, dict(calls=0, samples=0, compute_seconds=0.,
                                         finish_seconds=0., metrics={}))
        b['calls'] += 1
        b['samples'] += added
        elapsed = row['wall_seconds']
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('Finite nonnegative compute time')
        if row['kind'] == 'finish':
            b['finish_seconds'] += elapsed
        else:
            b['compute_seconds'] += elapsed
        def add(key, value):
            b['metrics'].setdefault(key, Stats()).add(value)
        r = row['resources']
        for key in ('rss_bytes', 'virtual_bytes', 'swap_bytes', 'available_ram_bytes',
                    'task_count', 'cpu_seconds'):
            if key in r:
                add(key, r[key])
        if r.get('pss_sampled_monotonic_sec') != pss_clock and r.get('pss_bytes') is not None:
            pss_clock = r['pss_sampled_monotonic_sec']
            add('pss_bytes_distinct_samples', r['pss_bytes'])
        for key, value in r.get('temperatures_celsius', {}).items():
            add('temperature_'+key, value)
        for key in ('input_backlog_seconds', 'speaker_backlog_seconds',
                    'source_elapsed_seconds', 'process_cpu_percent_since_previous_call'):
            if row.get(key) is not None:
                add(key, row[key])
        rolling = row.get('rolling_push_rtf', {})
        if rolling.get('rolling_rtf') is not None:
            add('rolling_push_rtf', rolling['rolling_rtf'])
        for key in ('dropped_samples', 'dropped_refinements'):
            if key in rolling:
                add(key, rolling[key])
        count += 1
        if count > 500000 or len(bins) > 145:
            raise ValueError('Review duration/call capacity')
    output = []
    for number, b in sorted(bins.items()):
        output.append(dict(bin_start_source_seconds=number*bin_seconds,
            bin_end_source_seconds=(number+1)*bin_seconds,
            calls=b['calls'], source_samples=b['samples'],
            audio_seconds=b['samples']/16000, push_compute_seconds=b['compute_seconds'],
            finish_seconds=b['finish_seconds'],
            push_rtf=b['compute_seconds']/(b['samples']/16000) if b['samples'] else None,
            including_finish_rtf=(b['compute_seconds']+b['finish_seconds'])/(b['samples']/16000) if b['samples'] else None,
            metrics={k: v.result() for k, v in sorted(b['metrics'].items())}))
    return dict(call_records=count, source_samples=previous_samples, bins=output)


def trends(bins):
    # Exclude the first ten-minute bin, which includes model/context warmup.
    selected = bins[1:]
    result = {}
    for key in ('rss_bytes', 'pss_bytes_distinct_samples', 'input_backlog_seconds',
                'speaker_backlog_seconds', 'rolling_push_rtf'):
        values = [(b['bin_start_source_seconds']/60, b['metrics'][key]['mean'])
                  for b in selected if key in b['metrics'] and b['metrics'][key]['count']]
        if len(values) < 3:
            result[key] = dict(status='INSUFFICIENT_POST_WARMUP_BINS', points=len(values))
            continue
        mx = sum(x for x, _ in values)/len(values)
        my = sum(y for _, y in values)/len(values)
        slope = sum((x-mx)*(y-my) for x,y in values)/sum((x-mx)**2 for x,_ in values)
        ys = [y for _,y in values]
        result[key] = dict(points=len(values), first_bin_mean=ys[0], last_bin_mean=ys[-1],
            delta=ys[-1]-ys[0], least_squares_per_audio_minute=slope,
            every_successive_bin_mean_strictly_increases=all(a < b for a,b in zip(ys,ys[1:])),
            interpretation='descriptive trend; no leak/steady-state or hardware-upgrade threshold inferred')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--monitor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for path in (args.monitor, args.output):
        if not path.resolve().is_relative_to(PRIVATE.resolve()):
            raise ValueError('Private evidence paths required')
    args.output.mkdir()
    me = psutil.Process()
    save(args.output/'REGISTERED_OWNER.json', dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))
    transport = json.loads((args.monitor/'RESULT.json').read_bytes())
    complete = json.loads((args.monitor/'MIRROR_COMPLETE.json').read_bytes())
    manifest_path = args.monitor/'MIRROR_MANIFEST.json'
    manifest = json.loads(manifest_path.read_bytes())
    if transport['status'] != 'FULL_CLOSED_OUTPUT_MIRRORED':
        raise ValueError('Complete independent mirror required')
    root = args.monitor/'closed-output'
    for item in manifest:
        path = root/item['path']
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError('Mirror member path')
        if path.stat().st_size != item['identity']['bytes'] or sha(path) != item['sha256']:
            raise ValueError('Mirror member changed')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != {r['path'] for r in manifest}:
        raise ValueError('Whole mirror membership changed')
    if not all(complete['closure'].get(k) is True for k in ('closed','cgroup_empty','exact_owner_gone')):
        raise ValueError('Exact closed owner/cgroup receipt required')
    benchmark = root/'benchmark'
    result = json.loads((benchmark/'RESULT.json').read_bytes())
    summary = aggregate(records(benchmark))
    summary.update(schema='just-peachy.component-soak-review.v1',
        native_result=result, mirror_manifest_sha256=sha(manifest_path),
        transport_functional_success=transport['functional_success'],
        closure=complete['closure'], trends_after_first_600_seconds=trends(summary['bins']),
        scope='continuous repeated saved-input diarizer only; no ASR/embedding/capture/GUI',
        larger_ram_measurements=False, diarization_quality_evaluated=False,
        automatic_realtime_qualification=False,
        thermal_throttling_flags='not collected by this benchmark; temperature retained where available')
    save(args.output/'SOAK_REVIEW.json', summary)
    print(json.dumps(dict(output=str(args.output),calls=summary['call_records'],
                          source_samples=summary['source_samples'],bins=len(summary['bins']))))


if __name__ == '__main__':
    main()

