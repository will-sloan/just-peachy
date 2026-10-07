"""Prepare an exact finite optional request; no models/SSH. README_OPTIONAL_QUALIFICATION.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--request',type=Path,required=True)
    ap.add_argument('--permit',type=Path)
    ap.add_argument('--native-permit-path')
    ap.add_argument('--print-context',action='store_true')
    ap.add_argument('--permit-sha256')
    ap.add_argument('--output',type=Path)
    ap.add_argument('--host-owner-directory',type=Path)
    args=ap.parse_args()
    if platform.system()=='Windows':
        import psutil
        process=psutil.Process();process.cpu_affinity([14])
        if args.host_owner_directory is None:raise ValueError('Private fresh host owner directory required')
        args.host_owner_directory.mkdir(exist_ok=False)
        with (args.host_owner_directory/'REGISTERED_OWNER.json').open('x') as stream:
            json.dump(dict(pid=os.getpid(),create_time=process.create_time(),affinity=process.cpu_affinity()),stream)
            stream.flush();os.fsync(stream.fileno())
    elif platform.system()=='Linux':
        if set(os.sched_getaffinity(0))!={2,3}:raise ValueError('Use the exact admitted native unit on CPU2/3')
    else:raise ValueError('Unsupported host')
    from optional_refiner_qualification import read_json,strict,launch_context_sha256,encoded,pin,SCHEMA
    from profiles import RuntimeSelection,SessionPolicy
    if args.request.is_symlink() or args.request.stat().st_size>262144:raise ValueError('Bounded regular launch request required')
    request=strict(args.request.read_bytes())
    if args.print_context:
        print(json.dumps(dict(launch_context_sha256=launch_context_sha256(request),native_execution=False)));return
    if args.permit is None or args.permit_sha256 is None or args.output is None:
        raise ValueError('Permit, exact pin and fresh output required')
    permit,_=read_json(args.permit,args.permit_sha256)
    selection=RuntimeSelection(**request['selection']);policy=SessionPolicy(**request['policy'])
    selection.validate();policy.validate()
    if (permit.get('schema')!=SCHEMA or permit.get('selection')!=selection.validate() or permit.get('policy')!=policy.validate() or
        permit.get('launch_context_sha256')!=launch_context_sha256(request) or request.get('optional_refiner_admission') is not None):
        raise ValueError('Reviewed permit must cover exact complete request; never a measured GUI receipt')
    native_path=args.native_permit_path or str(args.permit)
    from pathlib import PurePosixPath
    if not native_path.startswith('/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/') or '..' in PurePosixPath(native_path).parts:
        raise ValueError('Exact isolated native permit path required; host path is only a mirror')
    request['optional_refiner_qualification']={'path':native_path,'sha256':pin(args.permit_sha256)}
    raw=encoded(request)+b'\n'
    if len(raw)>262144:raise ValueError('Request capacity')
    with args.output.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps(dict(output=str(args.output),sha256=hashlib.sha256(raw).hexdigest(),native_execution=False,
        requires_live_unit_admission=True,production_eligible=False)))

if __name__=='__main__':main()
