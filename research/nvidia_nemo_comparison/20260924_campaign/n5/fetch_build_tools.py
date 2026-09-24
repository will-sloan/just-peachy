"""Fetch verified, isolated Linux cross-build tools. See README_ARM64.md."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

ARM_FILE = 'arm-gnu-toolchain-12.3.rel1-x86_64-aarch64-none-linux-gnu.tar.xz'
ARM_URL = 'https://developer.arm.com/-/media/Files/downloads/gnu/12.3.rel1/binrel/' + ARM_FILE
ARM_SHA = '960ec0bce309528f603639d8228ef39e6fb9185289ff42b01aa3b4de315accef'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def fetch(url, target, expected):
    if not target.exists():
        if shutil.disk_usage(target.parent).free < 75 * 1024**3:
            raise RuntimeError('Work disk reserve reached')
        part = target.with_suffix(target.suffix + '.part')
        with urllib.request.urlopen(url, timeout=60) as src, part.open('wb') as dst:
            shutil.copyfileobj(src, dst, 1024**2)
        if sha(part) != expected:
            raise ValueError('Publisher hash mismatch: ' + target.name)
        part.replace(target)
    if sha(target) != expected:
        raise ValueError('Existing file hash mismatch: ' + target.name)
    return dict(filename=target.name, bytes=target.stat().st_size, sha256=expected, url=url)


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    # Official HTTPS checksum is pinned as well as fetched; upstream changes fail closed.
    checksum = urllib.request.urlopen(ARM_URL + '.sha256asc', timeout=30).read().decode()
    if checksum.split()[0] != ARM_SHA:
        raise ValueError('Arm published checksum changed')
    rows = [fetch(ARM_URL, output / ARM_FILE, ARM_SHA)]
    for name, version in [('cmake', '3.30.5'), ('ninja', '1.11.1.1')]:
        url = f'https://pypi.org/pypi/{name}/{version}/json'
        data = json.load(urllib.request.urlopen(url, timeout=30))
        candidates = [x for x in data['urls'] if x['filename'].endswith('.whl')
                      and 'manylinux' in x['filename'] and 'x86_64' in x['filename']]
        if name == 'cmake':
            candidates = [x for x in candidates if 'manylinux2014_x86_64' in x['filename']]
        if len(candidates) != 1:
            raise ValueError('Ambiguous host wheel: ' + name)
        row = candidates[0]
        result = fetch(row['url'], output / row['filename'], row['digests']['sha256'])
        result.update(name=name, version=version, publisher_manifest=url)
        rows.append(result)
    receipt = dict(status='VERIFIED_DOWNLOADS_ONLY', host='Linux x86_64', target='Linux aarch64', files=rows)
    (output / 'TOOLS.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args().output)
