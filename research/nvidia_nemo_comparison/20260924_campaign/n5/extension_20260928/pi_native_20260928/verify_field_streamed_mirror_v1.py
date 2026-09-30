"""Host local-mirror passage; README_FIELD_STREAMED_MIRROR_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from field_host_budget_v1 import HostStore
from field_streamed_mirror_v1 import publish, MAX_MANIFEST


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'manifest', 'output', 'admission'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    if args.admission.stat().st_size > 65536 or args.manifest.stat().st_size > MAX_MANIFEST:
        raise ValueError('Bounded admission/manifest required')
    admission = json.loads(args.admission.read_bytes())
    remaining = (datetime.fromisoformat(admission['expires_utc'])-datetime.now(timezone.utc)).total_seconds()
    if not 0 < remaining <= 600 or admission['host_affinity'] != [14] or admission['pi_dispatch'] is not False:
        raise ValueError('Fresh host-only admission required')
    deadline = time.monotonic()+min(remaining, 60)
    pins = json.loads(args.manifest.read_bytes())['files']
    # This small verifier is separate from the production80MB mirror ceiling.
    if admission['maximum_host_output_bytes'] < 2*1024**2:
        raise ValueError('Two MiB host verification allocation required')
    limits = {'metadata': (65536,65536,12), 'failure': (8192,8192,4), 'closure': (8192,8192,4)}
    store = HostStore(args.output, limits).create({'ADMISSION.json':args.admission.read_bytes()})
    result = publish(store, args.output.with_name(args.output.name+'-mirror'), args.source,
                     pins, deadline=deadline, maximum_bytes=1600000)
    print(json.dumps({k:v for k,v in result.items() if k not in ('files','directories')}))


if __name__ == '__main__':
    main()
