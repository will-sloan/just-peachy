"""Pure host payload constructor, no SSH/native/model calls. See README.md."""
import psutil
psutil.Process().cpu_affinity([14])
import os
import json
import uuid
from pathlib import Path

# Ownership precedes source/data reads and imports of project modules.
Q=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
OWNER=Q/('presets-preparation-optional-dispatch-'+uuid.uuid4().hex)
OWNER.mkdir()
with (OWNER/'REGISTERED_OWNER.json').open('x') as stream:
    json.dump(dict(pid=os.getpid(),create_time=psutil.Process().create_time(),affinity=[14]),stream)
    stream.flush();os.fsync(stream.fileno())

import argparse
import base64
import hashlib
import importlib.util
import time


def bounded(path,maximum=262144):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>maximum:raise ValueError('Bounded regular reviewed input required')
    return path.read_bytes()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prerequisites',required=True,type=Path)
    parser.add_argument('--primary-review',required=True,type=Path)
    parser.add_argument('--gui-review',required=True,type=Path)
    parser.add_argument('--assets',required=True,type=Path)
    parser.add_argument('--boot-id',required=True)
    parser.add_argument('--label',required=True)
    parser.add_argument('--expiry',required=True,type=float)
    parser.add_argument('--maximum-lag-seconds',type=int,default=30)
    args=parser.parse_args()
    source=Path(__file__).parent
    action_raw=bounded(source/'launch_optional_first_action.py',131072)
    spec=importlib.util.spec_from_file_location('optional_dispatch_action',source/'launch_optional_first_action.py')
    action=importlib.util.module_from_spec(spec);spec.loader.exec_module(action)
    def reference(raw):return dict(sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode('ascii'))
    gate=json.loads(bounded(args.prerequisites));selected=dict(gate['primary_selection'],optional_d1_refiner=True,allow_experimental=True)
    # Both raw reviews are untouched. Their pass/closure interpretation lives in
    # the independently reviewed gate, never inferred from a filename or label.
    evidence=dict(primary=reference(bounded(args.primary_review)),gui=reference(bounded(args.gui_review)))
    for role,row in evidence.items():
        if gate[role+'_review']['sha256']!=row['sha256']:raise ValueError('Actual reviewed prerequisite input hash differs')
    value=dict(schema='just-peachy.optional-first-dispatch.v1',reviewed=True,package=action.TARGET.as_posix(),
        package_manifest_sha256=action.MANIFEST,binding_sha256=action.BINDING,candidate_content_sha256=action.CONTENT,
        boot_id=args.boot_id,expires_unix=args.expiry,label=args.label,maximum_output_bytes=256*1024**2,
        independent_pc_copy_bytes=256*1024**2,runtime_seconds=585,selection=selected,
        policy=dict(maximum_session_seconds=45,developer_soak=False,max_drain_seconds=60,max_backlog_seconds=30,
            model_load_seconds=120,cleanup_seconds=60),source=gate['source'],maximum_lag_seconds=args.maximum_lag_seconds,
        assets=json.loads(bounded(args.assets)),prerequisites=gate,evidence=evidence,
        dispatcher_sha256=hashlib.sha256(action_raw).hexdigest(),receiver=reference(bounded(source/'receiver.py',65536)))
    action.shape(value)
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    path=OWNER/'PAYLOAD.json'
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    with (OWNER/'PREPARATION.json').open('x') as stream:
        json.dump(dict(payload_sha256=hashlib.sha256(raw).hexdigest(),dispatcher_sha256=value['dispatcher_sha256'],
            receiver_sha256=value['receiver']['sha256'],native_execution=False,output=str(path)),stream,sort_keys=True)
    print(path)


if __name__=='__main__':main()
