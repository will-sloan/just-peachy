"""Pinned, bounded official N3 payload fetch; see README.md for commands."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import time
import urllib.request

MODELS = {
    'A1': ('nvidia/parakeet_realtime_eou_120m-v1', 'a7e2b4629593dce0ec19f600e00e9904353fda2d', 'NVIDIA Open Model License', [
        ('parakeet_realtime_eou_120m-v1.nemo', 460062720, '6603a22a53b7c1a4bac4736cb24628fb568a7102ba931a28c799e2e72f109893')]),
    'A2': ('nvidia/nemotron-speech-streaming-en-0.6b', 'ebe59e5a817142986528bbbee5dba8db7b38ed50', 'NVIDIA Open Model License', [
        ('nemotron-speech-streaming-en-0.6b.q8_0.gguf', 699872960, 'd9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d'),
        ('nemotron-speech-streaming-en-0.6b.nemo', 2473041920, '283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd')]),
    'A3': ('nvidia/nemotron-3.5-asr-streaming-0.6b', 'ea30d66debe3740a08b573244286791d423d6b3e', 'OpenMDW-1.1', [
        ('nemotron-3.5-asr-streaming-0.6b.q8_0.gguf', 742090464, '3fc991d3badad7277c11030a7519832cddaf2057aafed6d4b25147e953a070b1'),
        ('nemotron-3.5-asr-streaming-0.6b.nemo', 2368284501, '210214ed94039bf6bfbb9a047c7fa289628db75b103e2bf6381fa78285436a74')]),
}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    for attempt in range(20):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.1)


def reserve(root, remaining=0):
    # Includes all outstanding downloads and a 16-GiB N2 run allowance.
    if shutil.disk_usage(root).free - remaining < 91 * 2**30:
        raise RuntimeError('Work disk reserve would be breached (75 GiB + 16 GiB N2 allowance)')
    if Path('C:/').exists() and shutil.disk_usage('C:/').free < 50 * 2**30:
        raise RuntimeError('C: reserve below 50 GiB')


def fetch(url, path, size=None, digest=None):
    if path.exists():
        actual = sha(path)
        if (size is not None and path.stat().st_size != size) or (digest and actual != digest):
            raise RuntimeError('Existing payload does not match immutable binding: ' + str(path))
        return actual
    partial = path.with_suffix(path.suffix + '.part')
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={'User-Agent': 'JustPeachy-N3-pinned-fetch/1',
        **({'Range': f'bytes={offset}-'} if offset else {})})
    with urllib.request.urlopen(request, timeout=90) as response:
        if offset and response.status != 206:
            raise RuntimeError('Server did not honor resume range; preserve partial for review')
        if offset and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
            raise RuntimeError('Unexpected resume range')
        with partial.open('ab' if offset else 'xb') as output:
            while chunk := response.read(1024 * 1024):
                reserve(path.parent)
                output.write(chunk)
                if size is not None and output.tell() > size:
                    raise RuntimeError('Download exceeded pinned size')
    actual = sha(partial)
    if (size is not None and partial.stat().st_size != size) or (digest and actual != digest):
        raise RuntimeError('Downloaded payload failed size/hash binding')
    partial.replace(path)
    return actual


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        import psutil
        process = psutil.Process()
        process.cpu_affinity([4])
        if hasattr(psutil, 'BELOW_NORMAL_PRIORITY_CLASS'):
            process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except ImportError:
        pass
    result = dict(schema='just-peachy.n3.assets.v1', status='RUNNING',
                  started_utc=datetime.now(timezone.utc).isoformat(), assets=[])
    receipt = args.output / 'FETCH_RESULT.json'
    atomic(receipt, result)
    try:
        remaining = sum(size for _, _, _, assets in MODELS.values() for name, size, _ in assets
                        if not (args.output / name).exists())
        reserve(args.output, remaining)
        for variant, (repo, revision, license_name, assets) in MODELS.items():
            card = args.output / (variant + '_MODEL_CARD.md')
            card_sha = fetch(f'https://huggingface.co/{repo}/resolve/{revision}/README.md', card)
            for name, size, digest in assets:
                url = f'https://huggingface.co/{repo}/resolve/{revision}/{name}'
                actual = fetch(url, args.output / name, size, digest)
                result['assets'].append(dict(variant=variant, repository=repo, revision=revision,
                    filename=name, path=str((args.output / name).resolve()), bytes=size,
                    sha256=actual, url=url, license=license_name, card_sha256=card_sha,
                    status='DOWNLOADED_HASH_VERIFIED_NOT_EXECUTED'))
                atomic(receipt, result)
                print(variant, name, 'verified', flush=True)
        result['status'] = 'COMPLETE'
    except Exception as exc:
        result.update(status='FAILED', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        result['updated_utc'] = datetime.now(timezone.utc).isoformat()
        atomic(receipt, result)


if __name__ == '__main__':
    main()
