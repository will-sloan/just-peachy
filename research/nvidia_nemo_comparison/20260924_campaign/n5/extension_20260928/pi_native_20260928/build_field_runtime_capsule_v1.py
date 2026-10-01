"""Build the prepared offline broker template; README_FIELD_RUNTIME_CAPSULE_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse,json,os,shutil
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('source-bundle','policy-source','plan-source','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();args.output.mkdir()
    me=psutil.Process()
    (args.output/'REGISTERED_OWNER.json').write_text(json.dumps(dict(pid=me.pid,
        create_time=me.create_time(),affinity=[14])),encoding='utf-8')
    if shutil.disk_usage('C:/').free<50*1024**3 or shutil.disk_usage('G:/').free<75*1024**3+2097152:
        raise RuntimeError('Original host free floors')
    from field_runtime_capsule_v1 import derive
    def bounded(path,cap):
        if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('Bounded real source')
        raw=path.read_bytes()
        if len(raw)>cap:raise ValueError('Source grew')
        return raw
    raw,review=derive(bounded(args.source_bundle,1048576),bounded(args.policy_source,131072),
        bounded(args.plan_source,131072))
    for name,data in [('BUNDLE.json',raw),('REVIEW.json',(json.dumps(review,indent=2)+'\n').encode())]:
        if len(data)>1048576:raise ValueError('Prepared output cap')
        with (args.output/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        if (args.output/name).read_bytes()!=data:raise IOError('Prepared output readback')
    print(json.dumps({k:v for k,v in review.items() if k not in ('changed','unchanged_members')}))


if __name__=='__main__':main()

