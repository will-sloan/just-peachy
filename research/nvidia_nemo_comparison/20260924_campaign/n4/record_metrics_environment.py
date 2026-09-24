"""Freeze evaluator dependencies, code hashes and notices. README_METRICS.md."""
import argparse
import importlib.metadata as metadata
from pathlib import Path
import json
import sys
from common import bind, freeze, fingerprint
from metrics import require_versions


def main(args):
    require_versions()
    args.output.mkdir(parents=True,exist_ok=False)
    packages=[]
    notices=[]
    for dist in sorted(metadata.distributions(),key=lambda d:d.metadata['Name'].lower()):
        name=dist.metadata['Name']
        files=[]
        license_paths=[]
        for entry in dist.files or []:
            path=Path(dist.locate_file(entry)).resolve()
            if path.is_file() and path.suffix not in ('.pyc','.pyo'):
                if path.suffix in ('.py','.pyd','.dll','.json','.yaml','.yml') or path.name in ('METADATA','RECORD'):
                    files.append(dict(relative_path=str(entry).replace('\\','/'),**bind(path)))
                if any(part.lower() in ('licenses','license','copying','license.txt','license.md','notice','notice.txt')
                       for part in Path(entry).parts):
                    try:
                        text=path.read_text(encoding='utf-8')
                    except UnicodeError:
                        continue
                    license_paths.append(bind(path))
                    notices.append(f'## {name} {dist.version}: {entry}\n\n{text}\n')
        packages.append(dict(name=name,version=dist.version,
            license_expression=dist.metadata.get('License-Expression'),
            declared_license=dist.metadata.get('License'),licenses=license_paths,
            code_manifest_sha256=fingerprint(files),files=files))
    freeze(args.output/'ENVIRONMENT.json',dict(schema='n4-evaluator-environment-v1',
        python=bind(sys.executable),python_version=sys.version,packages=packages,
        metric_versions=require_versions(),scope='isolated evaluator, no neural models'))
    # Exact package versions reproduce the resolver; pip receipts additionally bind downloads.
    (args.output/'requirements.txt').write_text('\n'.join(p['name']+'=='+p['version'] for p in packages)+'\n',encoding='utf-8')
    (args.output/'THIRD_PARTY_NOTICES.md').write_text('# Evaluator dependency notices\n\n'+ '\n'.join(notices),encoding='utf-8')
    summary=dict(status='ACTUALLY_RECORDED',packages=len(packages),
        metric_versions=require_versions(),environment=bind(args.output/'ENVIRONMENT.json'),
        requirements=bind(args.output/'requirements.txt'),notices=bind(args.output/'THIRD_PARTY_NOTICES.md'),
        packages_without_license_file=[p['name'] for p in packages if not p['licenses']])
    freeze(args.output/'SUMMARY.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
