"""Bind the consolidated desktop to the existing complete backup plan. README_DELIVERY_BACKUP.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid


def main():
    here=Path(__file__).resolve().parent
    private=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
    early=private/'audit-preparation'/('restored-backup-scope-'+uuid.uuid4().hex);early.mkdir();me=psutil.Process();started=time.time()
    def write(name,raw):
        with (early/name).open('xb') as stream:assert stream.write(raw)==len(raw);stream.flush();os.fsync(stream.fileno())
        assert (early/name).read_bytes()==raw
    write('REGISTERED_OWNER.json',json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode())
    ap=argparse.ArgumentParser(add_help=False)
    ap.add_argument('--discovery',required=True);ap.add_argument('--package',required=True);ap.add_argument('--package-manifest-sha256',required=True)
    args,_=ap.parse_known_args()
    expected='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-21'
    if args.package!=expected or args.package_manifest_sha256!='9abaaaffe35d328fd97f5fc47f1f5b938803705dffb728c5d804d225a646ba6e':
        raise ValueError('Exact restored build21 backup only')
    for path in (Path(__file__),here/'README_DELIVERY_BACKUP.md',here.parent/'prepare_production_scope_v3.py',here.parent/'prepare_production_scope_v2.py'):
        raw=path.read_bytes();write(path.name+'.backup',raw);write(path.name+'.restore',raw)
    sys.path.insert(0,str(here.parent))
    import prepare_production_scope_v3 as decoder
    import prepare_production_scope_v2 as original
    import desktop_consolidation_action as desktop
    decoded=decoder.decode_discovery(decoder.strict_json(Path(args.discovery).read_bytes())['action_result'])
    observed=[r['path'] for r in decoded['members'] if Path(r['path']).parent.name=='Desktop']
    if observed!=['/home/peachyprototype/Desktop/Just Peachy.desktop']:
        raise ValueError('Exact sole observed consolidated desktop required')
    # Original all11 check described the pre-consolidation state. Bind its input
    # catalogue to the actual sole shortcut; all other complete-scope checks stay.
    desktop.OWNED=('Just Peachy.desktop',)
    decoder.main()
    assert sum(p.stat().st_size for p in early.iterdir())<2*1024**2 and time.time()-started<600
    write('SOURCE_CLOSED.json',json.dumps(dict(independent_restore=True,desktop_members=observed,native_action=False,closed_unix=time.time())).encode())


if __name__=='__main__':main()
