"""Extract exact action_result for the existing closed-job monitor. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os
import json
import uuid
from pathlib import Path
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
owner=Q/('presets-preparation-optional-job-extract-'+uuid.uuid4().hex);owner.mkdir()
with (owner/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14]),stream)
    stream.flush();os.fsync(stream.fileno())
import argparse
import hashlib
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dispatch-result',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if args.dispatch_result.is_symlink() or args.dispatch_result.stat().st_size>16*1024**2:
    raise ValueError('Bounded exact dispatch result required')
raw=args.dispatch_result.read_bytes();job=json.loads(raw)['action_result']
if (job.get('schema')!='just-peachy.native-component-job.v1' or job.get('workflow')!='optional-first-finite-saved' or
    args.output.parent.resolve()!=Q.resolve() or not args.output.name.endswith('-JOB.json') or
    job.get('maximum_output_bytes')!=256*1024**2):raise ValueError('Exact optional JOB output required')
value=json.dumps(job,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
with args.output.open('xb') as stream:stream.write(value);stream.flush();os.fsync(stream.fileno())
with (owner/'RESULT.json').open('x') as stream:
    json.dump(dict(source_sha256=hashlib.sha256(raw).hexdigest(),job_sha256=hashlib.sha256(value).hexdigest(),output=str(args.output),native_execution=False),stream)
print(args.output)
