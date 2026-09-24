"""Fetch the exact official .nemo counterpart using frozen N1 LFS hashes."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
LOCAL = Path('G:/Just_Peachy_N1/20260924_campaign/local/n2/diarization')

def main():
    metadata = json.loads((HERE.parents[1] / 'assets/official_metadata.json').read_text())['models']['D1']
    item = next(x for x in metadata['siblings'] if x['rfilename'] == 'Nemotron-3-Diarization.nemo')
    digest = item['lfs']['sha256']
    target = LOCAL / 'reference' / digest / item['rfilename']
    target.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(target.parent).free < 75 * 1024**3 + item['size']:
        raise RuntimeError('Insufficient disk reserve')
    url = f"https://huggingface.co/{metadata['repo']}/resolve/{metadata['revision']}/{item['rfilename']}"
    if not target.exists():
        temp = target.with_suffix('.download')
        request = urllib.request.Request(url, headers={'User-Agent': 'JustPeachy-N2/1.0'})
        with urllib.request.urlopen(request, timeout=90) as incoming, temp.open('wb') as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        if temp.stat().st_size != item['size'] or hashlib.file_digest(temp.open('rb'), 'sha256').hexdigest() != digest:
            raise RuntimeError('Downloaded reference artifact hash or size mismatch')
        temp.replace(target)
    if hashlib.file_digest(target.open('rb'), 'sha256').hexdigest() != digest:
        raise RuntimeError('Reference checkpoint hash mismatch')
    with tarfile.open(target) as archive:
        members = [{'name': m.name, 'size': m.size, 'regular_file': m.isfile()} for m in archive.getmembers()]
        config_member = next(m for m in archive.getmembers() if m.name.endswith('model_config.yaml'))
        config = archive.extractfile(config_member).read()
    config_path = target.parent / 'model_config.yaml'
    config_path.write_bytes(config)
    result = {'status': 'VERIFIED_NOT_DESERIALIZED', 'path': str(target), 'sha256': digest,
              'bytes': target.stat().st_size, 'url': url, 'revision': metadata['revision'],
              'config_path': str(config_path), 'members': members}
    (HERE / 'REFERENCE_ARTIFACT_RECEIPT.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
