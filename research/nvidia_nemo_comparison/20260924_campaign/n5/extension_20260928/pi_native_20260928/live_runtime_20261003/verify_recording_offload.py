"""Read-only PC verification of a selected exported recording ZIP. README_OFFLOAD.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import time
import zipfile


def digest(stream):
    stream.seek(0)
    result=hashlib.sha256()
    while block:=stream.read(65536):result.update(block)
    return result.hexdigest()


def central_bound(stream,size):
    """Bound ZIP directory allocation before ZipFile parses it; support ZIP64."""
    stream.seek(max(0,size-65557));tail=stream.read(65557)
    position=tail.rfind(b'PK\x05\x06')
    if position<0 or len(tail)-position<22:raise ValueError('ZIP end record missing')
    end=struct.unpack('<4s4H2LH',tail[position:position+22])
    if position+22+end[7]!=len(tail) or end[1]!=0 or end[2]!=0:raise ValueError('Single complete ZIP required')
    entries,central_size,central_offset=end[4:7]
    if end[3]!=entries:raise ValueError('Split ZIP rejected')
    end_offset=size-len(tail)+position
    if entries==65535 or central_size==0xffffffff or central_offset==0xffffffff:
        if end_offset<20:raise ValueError('ZIP64 locator missing')
        stream.seek(end_offset-20);locator=struct.unpack('<4sLQL',stream.read(20))
        if locator[0]!=b'PK\x06\x07' or locator[1]!=0 or locator[3]!=1:raise ValueError('ZIP64 disk layout')
        if locator[2]+56>end_offset-20:raise ValueError('ZIP64 extent')
        stream.seek(locator[2]);record=struct.unpack('<4sQ2H2L4Q',stream.read(56))
        if record[0]!=b'PK\x06\x06' or record[1]!=44 or record[4:6]!=(0,0) or record[6]!=record[7]:
            raise ValueError('Unsupported ZIP64 end record')
        entries,central_size,central_offset=record[7:10]
        end_offset=locator[2]
    if not 1<=entries<=16384 or not 0<central_size<=16*1024**2 or central_offset+central_size!=end_offset:
        raise ValueError('ZIP directory count/extent/allocation differs')
    return entries


def verify(path,expected_sha256,expected_bytes,maximum_uncompressed_bytes):
    if re.fullmatch('[0-9a-f]{64}',expected_sha256) is None:raise ValueError('Exact source SHA256 required')
    if type(expected_bytes) is not int or expected_bytes<=0 or type(maximum_uncompressed_bytes) is not int or maximum_uncompressed_bytes<=0:
        raise ValueError('Explicit positive extent bounds required')
    path=Path(path).resolve(strict=True)
    if not path.is_file():raise ValueError('Regular copied ZIP required')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        if before.st_size!=expected_bytes or digest(stream)!=expected_sha256:raise ValueError('Copied ZIP does not match Pi size/SHA256')
        count=central_bound(stream,before.st_size)
        names=set();total=0;files=0
        with zipfile.ZipFile(stream,'r') as archive:
            if len(archive.infolist())!=count:raise ValueError('ZIP member count differs')
            for member in archive.infolist():
                name=member.filename;p=PurePosixPath(name)
                if (len(name.encode('utf-8'))>512 or not name or p.is_absolute() or '..' in p.parts
                        or '\\' in name or ':' in name or p.as_posix()!=name.rstrip('/') or name.casefold() in names):
                    raise ValueError('Duplicate/unsafe ZIP member')
                names.add(name.casefold())
                mode=stat.S_IFMT(member.external_attr>>16)
                if mode not in (0,stat.S_IFREG,stat.S_IFDIR) or member.flag_bits&1 or member.compress_type!=zipfile.ZIP_STORED:
                    raise ValueError('Expected unencrypted stored regular export members')
                total+=member.file_size
                if total>maximum_uncompressed_bytes:raise ValueError('Uncompressed copy bound exceeded')
                copied=0
                with archive.open(member) as source:
                    while block:=source.read(65536):copied+=len(block)
                if copied!=member.file_size:raise ValueError('Member extent mismatch')
                files+=not member.is_dir()
        after=os.fstat(stream.fileno());current=path.stat()
        identity=lambda value:(value.st_dev,value.st_ino,value.st_size,value.st_mtime_ns)
        if identity(before)!=identity(after) or identity(after)!=identity(current) or digest(stream)!=expected_sha256:
            raise ValueError('Copied ZIP changed during complete readback')
    return dict(schema='just-peachy.recording-pc-readback.v1',status='VERIFIED_COMPLETE_COPY',
        zip_sha256=expected_sha256,zip_bytes=expected_bytes,entries=count,regular_files=files,
        uncompressed_bytes=total,all_member_crc_readbacks=True,source_expected_digest_supplied=True,
        audio_quality_evaluated=False,source_deleted=False,extracted=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zip',required=True);parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--source-bytes',type=int,required=True)
    parser.add_argument('--maximum-uncompressed-bytes',type=int,required=True)
    parser.add_argument('--output',required=True,help='Fresh private receipt directory')
    args=parser.parse_args()
    import psutil
    process=psutil.Process();process.cpu_affinity([14])
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        data=json.dumps(value,sort_keys=True,allow_nan=False).encode()+b'\n'
        if len(data)>16384:raise ValueError('Receipt bound')
        with (output/name).open('xb') as sink:sink.write(data);sink.flush();os.fsync(sink.fileno())
        if (output/name).read_bytes()!=data:raise OSError('Receipt readback')
    save('REGISTERED_OWNER.json',dict(pid=os.getpid(),create_time=process.create_time(),cpu=14))
    try:
        result=verify(args.zip,args.source_sha256,args.source_bytes,args.maximum_uncompressed_bytes)
        result['verified_utc_epoch']=time.time();save('VERIFY.json',result)
        print(json.dumps(result,sort_keys=True))
    except BaseException as exc:
        save('FAILURE.json',dict(error=type(exc).__name__,detail=str(exc)[:4096]));raise


if __name__=='__main__':main()
