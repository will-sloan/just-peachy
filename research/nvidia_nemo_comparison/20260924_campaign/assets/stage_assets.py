"""Pin official model metadata and stage selected files without importing model code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import tarfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE = Path('G:/Just_Peachy_N1/20260924_campaign/local/assets')
MODELS = {
    'D1': 'nvidia/Nemotron-3-Diarization',
    'E1': 'nvidia/speakerverification_en_titanet_large',
    'A1': 'nvidia/parakeet_realtime_eou_120m-v1',
    'A2': 'nvidia/nemotron-speech-streaming-en-0.6b',
    'A3': 'nvidia/nemotron-3.5-asr-streaming-0.6b',
    'X1': 'nvidia/multitalker-parakeet-streaming-0.6b-v1',
}
GIB = 1024 ** 3


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'JustPeachy-N1-official-asset-audit/1.0'})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def metadata(cache):
    result = {'checked_at_utc': now(), 'anonymous_access': True, 'models': {}}
    for model_id, repo in MODELS.items():
        api_url = 'https://huggingface.co/api/models/' + repo + '?blobs=true'
        raw = get(api_url)
        model = json.loads(raw)
        revision = model['sha']
        commit_url = 'https://huggingface.co/api/models/' + repo + '/commits/' + revision
        commits = json.loads(get(commit_url))
        snapshots = cache / 'metadata' / model_id
        snapshots.mkdir(parents=True, exist_ok=True)
        (snapshots / 'api.json').write_bytes(raw)
        save(snapshots / 'commits.json', commits)
        small = []
        for item in model['siblings']:
            name = item['rfilename']
            if item.get('size', 0) < 1024 * 1024 and (name.lower().endswith(('.md', '.json', '.txt', '.yaml', '.yml')) or 'license' in name.lower()):
                url = f'https://huggingface.co/{repo}/resolve/{revision}/{urllib.parse.quote(name)}'
                try:
                    content = get(url)
                    target = snapshots / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    small.append({'name': name, 'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content), 'url': url, 'path': str(target)})
                except Exception as error:
                    small.append({'name': name, 'error': type(error).__name__ + ': ' + str(error)})
        result['models'][model_id] = {
            'repo': repo, 'revision': revision, 'created_at': model.get('createdAt'),
            'repo_last_modified': model.get('lastModified'), 'gated': model.get('gated'),
            'license_card_metadata': model.get('cardData', {}).get('license'),
            'siblings': model['siblings'], 'commits': commits, 'snapshots': small,
        }
        save(ROOT / 'official_metadata.json', result)
        print(model_id, revision, 'gated=', model.get('gated'), flush=True)
    return result


def download(cache, model_id, name):
    metadata = json.loads((ROOT / 'official_metadata.json').read_text(encoding='utf-8'))['models'][model_id]
    item = next(x for x in metadata['siblings'] if x['rfilename'] == name)
    expected = item.get('lfs', {}).get('sha256')
    if not expected:
        raise RuntimeError('Only files with official expected LFS SHA256 are staged as weights')
    destination = cache / 'sha256' / expected / Path(name).name
    url = f"https://huggingface.co/{metadata['repo']}/resolve/{metadata['revision']}/{urllib.parse.quote(name)}"
    receipts_path = ROOT / 'download_receipts.json'
    receipts = json.loads(receipts_path.read_text()) if receipts_path.exists() else {'artifacts': []}
    previous = next((x for x in receipts['artifacts'] if x['model_id'] == model_id and x['filename'] == name), None)
    receipt = {'model_id': model_id, 'filename': name, 'repo': metadata['repo'], 'revision': metadata['revision'], 'url': url, 'expected_sha256': expected, 'expected_bytes': item['size'], 'path': str(destination), 'started_at_utc': now(), 'status': 'RUNNING'}
    if previous:
        receipts['artifacts'].remove(previous)
    receipts['artifacts'].append(receipt)
    save(receipts_path, receipts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    def guard(extra):
        used = sum(p.stat().st_size for p in cache.rglob('*') if p.is_file())
        if used + extra > 50 * GIB or shutil.disk_usage('G:/').free - extra < 75 * GIB or shutil.disk_usage('C:/').free < 50 * GIB:
            raise RuntimeError('Disk reserve or 50 GiB campaign assets cap would be exceeded')
    try:
        if not destination.exists():
            guard(item['size'])
            partial = destination.with_suffix(destination.suffix + '.part')
            digest = hashlib.sha256()
            count = 0
            start = time.monotonic()
            request = urllib.request.Request(url, headers={'User-Agent': 'JustPeachy-N1-official-asset-audit/1.0'})
            with urllib.request.urlopen(request, timeout=90) as response, partial.open('wb') as stream:
                while block := response.read(1024 * 1024):
                    if shutil.disk_usage('G:/').free < 75 * GIB:
                        raise RuntimeError('G drive minimum reserve reached')
                    stream.write(block)
                    digest.update(block)
                    count += len(block)
                    # Bound network/disk bandwidth while the owner works on the desktop.
                    delay = count / (40 * 1024 * 1024) - (time.monotonic() - start)
                    if delay > 0:
                        time.sleep(delay)
            if digest.hexdigest() != expected or count != item['size']:
                raise RuntimeError('Downloaded content does not match official hash/size')
            os.replace(partial, destination)
        with destination.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected or destination.stat().st_size != item['size']:
            raise RuntimeError('Existing asset does not match official hash/size')
        receipt.update(status='VERIFIED', sha256=actual, bytes=destination.stat().st_size)
    except Exception as error:
        receipt.update(status='ACCESS_REQUIRED' if getattr(error, 'code', None) in (401, 403) else 'FAILED', error=type(error).__name__ + ': ' + str(error))
    receipt['finished_at_utc'] = now()
    save(receipts_path, receipts)
    print(model_id, name, receipt['status'], flush=True)
    return receipt


def inspect(cache):
    """Read archive listings/configuration and GGUF metadata; never deserialize weights."""
    downloads = json.loads((ROOT / 'download_receipts.json').read_text(encoding='utf-8'))
    records = []
    for artifact in downloads['artifacts']:
        if artifact['status'] != 'VERIFIED':
            continue
        path = Path(artifact['path'])
        record = {'model_id': artifact['model_id'], 'path': str(path), 'sha256': artifact['sha256'],
                  'model_executed': False, 'pickle_deserialized': False}
        if path.suffix == '.nemo':
            with tarfile.open(path, 'r:*') as archive:
                record['members'] = [{'name': m.name, 'bytes': m.size, 'regular_file': m.isfile()} for m in archive.getmembers()]
                configs = []
                for member in archive.getmembers():
                    if member.isfile() and member.name.endswith(('.yaml', '.yml', '.txt')) and member.size < 256 * 1024:
                        raw = archive.extractfile(member).read()
                        output = cache / 'metadata' / artifact['model_id'] / ('archive_' + Path(member.name).name)
                        output.write_bytes(raw)
                        configs.append({'name': member.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'path': str(output)})
                record['configuration_snapshots'] = configs
        elif path.suffix == '.gguf':
            with path.open('rb') as stream:
                def read(fmt):
                    size = struct.calcsize(fmt)
                    raw = stream.read(size)
                    if len(raw) != size:
                        raise ValueError('Truncated GGUF')
                    return struct.unpack(fmt, raw)[0]
                def string(summarize=False):
                    size = read('<Q')
                    if size > 16 * 1024 * 1024:
                        raise ValueError('Oversized GGUF string')
                    raw = stream.read(size)
                    if len(raw) != size:
                        raise ValueError('Truncated GGUF string')
                    if summarize and len(raw) > 1024:
                        return {'string_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'contents_omitted': True}
                    return raw.decode('utf-8', errors='replace')
                scalar_formats = {0:'<B', 1:'<b', 2:'<H', 3:'<h', 4:'<I', 5:'<i', 6:'<f', 7:'<?', 10:'<Q', 11:'<q', 12:'<d'}
                def value(kind, depth=0):
                    if depth > 2:
                        raise ValueError('Unexpected nested GGUF metadata')
                    if kind in scalar_formats:
                        return read(scalar_formats[kind])
                    if kind == 8:
                        return string(summarize=True)
                    if kind == 9:
                        subtype, count = read('<I'), read('<Q')
                        if count > 1_000_000:
                            raise ValueError('Oversized GGUF metadata array')
                        for _ in range(count):
                            value(subtype, depth + 1)
                        return {'array_type': subtype, 'count': count, 'contents_omitted': True}
                    raise ValueError('Unknown GGUF type')
                if stream.read(4) != b'GGUF':
                    raise ValueError('Missing GGUF magic')
                record['gguf_version'] = read('<I')
                record['tensor_count'] = read('<Q')
                count = read('<Q')
                if count > 100_000:
                    raise ValueError('Oversized GGUF metadata count')
                record['metadata'] = {}
                for _ in range(count):
                    key = string()
                    record['metadata'][key] = value(read('<I'))
        records.append(record)
    save(ROOT / 'asset_structure_receipt.json', {'inspected_at_utc': now(), 'artifacts': records})
    print('Metadata-only structure inspection:', len(records), 'artifacts; no model code executed', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['metadata', 'download', 'inspect'])
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--model', choices=MODELS)
    parser.add_argument('--filename')
    parser.add_argument('--refresh', action='store_true', help='Explicitly replace the existing metadata revision pins')
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    if args.action == 'metadata':
        if (ROOT / 'official_metadata.json').exists() and not args.refresh:
            print('Existing metadata pins retained. --refresh explicitly replaces them.', flush=True)
        else:
            metadata(args.cache)
    elif args.action == 'inspect':
        inspect(args.cache)
    elif not args.model or not args.filename:
        parser.error('download requires --model and --filename')
    else:
        result = download(args.cache, args.model, args.filename)
        raise SystemExit(0 if result['status'] == 'VERIFIED' else 1)


if __name__ == '__main__':
    main()
