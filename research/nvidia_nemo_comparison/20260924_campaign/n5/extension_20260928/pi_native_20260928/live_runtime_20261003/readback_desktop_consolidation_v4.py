"""Host-only consolidation01 result-copy repair; README_CONSOLIDATION_READBACK_V4.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

ACTION_SHA='1a9291504bc94a219a29de4691456bdddd4845c7c1e39ed4b0519c78ebd7d5d0'
PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')


def write_result_copy(path,raw,output,read):
    if path not in {output/'RESULT.json.backup',output/'RESULT.json.restore'} or not 0<len(raw)<=262144:
        raise ValueError('Only the two bounded outer-result copies may use262144bytes')
    with path.open('xb') as stream:
        if stream.write(raw)!=len(raw):raise OSError('Short outer result copy')
        stream.flush();os.fsync(stream.fileno())
    if read(path,262144)!=raw:raise OSError('Independent outer result readback differs')


def main():
    import psutil
    me=psutil.Process();me.cpu_affinity([14]);ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--operation',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    if args.operation!=PRIVATE/'operation-desktop-consolidation-01' or args.output!=PRIVATE/'desktop-consolidation-01-readback-02':raise ValueError('Exact actual01/fresh readback02 paths required')
    output=args.output;output.mkdir()
    raw=json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14])).encode()
    with (output/'REGISTERED_OWNER.json').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    for drive,gib in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<gib*1024**3+16*1024**2:raise OSError('Independent readback floor')
    op=args.operation;source=op/'ACTION.py.backup'
    if source.is_symlink() or source.stat().st_size>131072:raise ValueError('Bounded executed source')
    action=source.read_bytes()
    if hashlib.sha256(action).hexdigest()!=ACTION_SHA:raise ValueError('Exact executed V3 action pin')
    namespace=dict(__name__='_executed_consolidation_readback_only',__file__=str(source))
    exec(compile(action,str(source),'exec'),namespace)
    read,write,strict,encoded=map(namespace.get,('read','write','strict','encoded'))
    if read(op/'ACTION.py.restore',131072)!=action or read(source,131072)!=action:raise ValueError('Independent executed-source copies differ')
    raw=read(op/'dispatch/RESULT.json',262144);outer=strict(raw)
    closure=strict(read(op/'dispatch/NATIVE_CLOSURE.json',16384));owner=strict(read(op/'dispatch/NATIVE_OWNER.json',16384));phase=strict(read(op/'dispatch/PHASE.json',16384))
    if phase!=dict(fault=None,overflow=False,reader_error=[],readers_joined=True,returncode=0,ssh_reaped=True,writer_error=[]):raise ValueError('Exact natural closed transport required')
    metadata,files=namespace['readback_payload'](outer,closure,owner)
    target=output/'archive';target.mkdir()
    for row in metadata['directories']:(target/row['path']).mkdir()
    for name,data in files.items():write(target/name,data)
    for suffix in ('.backup','.restore'):write_result_copy(output/('RESULT.json'+suffix),raw,output,read)
    for suffix in ('.backup','.restore'):write(output/('EXECUTED_ACTION.py'+suffix),action)
    receipt=dict(status='COMPLETE_DESKTOP_ARCHIVE_READBACK',files=len(files),bytes=metadata['bytes'],archive=outer['action_result']['archive'],
        native_inspector=owner,closure=closure,source_result_sha256=hashlib.sha256(raw).hexdigest(),native_actions=False,
        transport_sha256=outer['action_result']['archive_readback']['sha256'],executed_action_sha256=ACTION_SHA,
        host_result_copy_bytes=len(raw),host_result_copy_maximum_bytes=262144,ordinary_archive_write_readback_maximum_bytes=65536,
        all_archive_and_closure_checks_unchanged=True)
    write(output/'VERIFY.json',encoded(receipt));write(output/'VERIFY.restore.json',encoded(receipt))
    print(json.dumps(dict(status=receipt['status'],files=len(files),output=str(output),verify_sha256=hashlib.sha256(encoded(receipt)).hexdigest())))


if __name__=='__main__':main()
