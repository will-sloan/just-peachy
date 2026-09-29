"""Package the reviewed shared application source, without private data/models. See README_B01_V1.md."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile


def main():
    import psutil
    psutil.Process().cpu_affinity([14])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = args.receipt.read_bytes()
    if hashlib.sha256(raw).hexdigest() != 'f28b6f71a9103584605e8cb947643580fda50493ad5694cce690f7ddcda065bc':
        raise ValueError('Unreviewed parent source')
    receipt = json.loads(raw)
    source = Path(receipt['prototype'])
    if len(receipt['files']) != 392 or sum(row['bytes'] for row in receipt['files'].values()) > 5*1024**2:
        raise ValueError('Source size/count changed')
    if args.output.exists() or args.output.with_suffix('.json').exists():
        raise FileExistsError('Fresh output required')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, row in sorted(receipt['files'].items()):
            path = source/name
            if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()):
                raise ValueError('Source escape')
            contents = path.read_bytes()
            if len(contents) != row['bytes'] or hashlib.sha256(contents).hexdigest() != row['sha256']:
                raise ValueError('Source changed: '+name)
            item = tarfile.TarInfo('prototype/'+name)
            item.size = len(contents); item.mode = 0o644; item.mtime = 0
            archive.addfile(item, io.BytesIO(contents))
    manifest = dict(schema='cm5-shared-app-source-bundle.v1', source_receipt_sha256=hashlib.sha256(raw).hexdigest(),
                    bundle_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
                    bundle_bytes=args.output.stat().st_size, files=receipt['files'],
                    application_source_unchanged=True, model_files_included=False, private_data_included=False,
                    stage_accepted=False)
    with args.output.with_suffix('.json').open('x') as f: json.dump(manifest, f, indent=2)
    print(json.dumps({k:v for k,v in manifest.items() if k!='files'}))


if __name__ == '__main__': main()
