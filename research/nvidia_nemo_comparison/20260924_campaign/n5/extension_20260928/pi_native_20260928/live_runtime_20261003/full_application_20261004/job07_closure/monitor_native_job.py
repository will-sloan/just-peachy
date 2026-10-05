"""Bounded strict-SSH job monitor and complete closed mirror. README_JOB_MONITOR.md."""
import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time

PRIVATE=Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
SSH=['ssh.exe','-T','-i','C:/Users/amiri/.ssh/just_peachy_cm5_ed25519',
    '-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','HostKeyAlias=192.168.2.57',
    '-o','Hostname=192.168.2.57','-o','ConnectTimeout=10','-o','ServerAliveInterval=5',
    '-o','ServerAliveCountMax=2','peachyprototype@raspberrypi.local']


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def write(path,raw):
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    if path.read_bytes()!=raw: raise OSError('Independent PC readback failed')


def save(path,value): write(path,encoded(value))


def floors(additional=0):
    for drive,gib in (('C:/',50),('G:/',75)):
        if shutil.disk_usage(drive).free<gib*1024**3+additional:
            raise OSError('Existing host free-space floor')


def process_creation(handle):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    times=[ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    return times[0].value


def bootstrap(output):
    if os.name!='nt': raise RuntimeError('Monitor is the Windows CPU14 host action')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    handle=kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384): raise ctypes.WinError(ctypes.get_last_error())
    creation=process_creation(handle)
    output=Path(output).absolute()
    if not output.is_relative_to(PRIVATE) or output.parent.resolve(strict=True)!=output.parent:
        raise ValueError('Fresh canonical private output directory required')
    output.mkdir(exist_ok=False)
    save(output/'REGISTERED_OWNER.json',dict(schema='just-peachy.host-registered-owner.v1',
        pid=os.getpid(),creation_filetime=creation,create_time=(creation-116444736000000000)/10000000,
        affinity_mask=16384,cpu=14))
    threading.stack_size(1024**2)
    return output


def job_limits(job):
    """Larger mirrors require exact named GUI/hour workflow contracts."""
    # Only the already issued build20 manual-Stop job has this larger copy reservation.
    if job.get('output_root') == '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/classic-ui-check-07':
        if (job.get('unit') != 'jp-v29-classic-ui-check-07.service'
                or job.get('package_manifest_sha256') != 'f42216e8169aa2b0be0b40c7fd0d9cf45542e2bf04b0e4405a95cc2189437659'
                or job.get('helper_source_sha256') != '4d0bef169c54d90769d50bb0f9a1becb6ae7ff80d438892e6dc7c57d59754b87'
                or type(job.get('maximum_output_bytes')) is not int
                or job['maximum_output_bytes'] != 512*1024**2
                or not 0 < job['deadline_unix']-job['issued_unix'] <= 581):
            raise ValueError('Exact issued job07 manual-Stop closure/copy contract required')
        return 512*1024**2,256
    base='/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'
    root=job.get('output_root','')
    optional=re.fullmatch(re.escape(base)+r'(optional-followup-[0-9]{2})',job.get('output_root',''))
    if optional:
        plan=job.get('output_plan',{});mode=plan.get('mode')
        metadata=16*1024**2+300*256*1024
        audio=4800000*6+30*(44+3*4096)+1024**2+metadata
        if mode=='raw_processed':audio+=4800000*4*4+30*2*4096
        primary=metadata+1024**2+10*1024**2
        complete=audio+primary+4*1024**2+16*1024**2
        maximum=max(256*1024**2,complete)
        expected=dict(schema='just-peachy.optional-output-plan.v1',stage='followup_policy',
            source_kind='live',session_seconds=300,mode=mode,audio_and_metadata_bytes=audio,
            additional_primary_allocation_bytes=primary,optional_output_bytes=4*1024**2,
            outer_unit_trace_bytes=16*1024**2,computed_output_bytes=complete,
            native_maximum_output_bytes=maximum,maximum_files=256)
        if (mode not in ('processed','raw_processed') or encoded(plan)!=encoded(expected)
                or job.get('unit')!='jp-v29-'+optional[1]+'.service'
                or job.get('workflow')!='optional-followup-live-policy'
                or type(job.get('duration_seconds')) is not int or job['duration_seconds']!=300
                or type(job.get('runtime_seconds')) is not int or job['runtime_seconds']!=840
                or job.get('maximum_output_files')!=256 or job.get('maximum_output_bytes')!=maximum
                or job.get('independent_pc_copy_bytes')!=maximum
                or not 0<job['deadline_unix']-job['issued_unix']<=885):
            raise ValueError('Exact computed optional live300 output and lifetime scope required')
        return 512*1024**2,256
    hour=re.fullmatch(re.escape(base)+r'(full-app-hour-[0-9]+)',root)
    if hour:
        if (job.get('unit')!='jp-v29-'+hour[1]+'.service'
                or job.get('workflow')!='continuous-full-application-repeated-wav'
                or job.get('duration_seconds')!=3600 or job.get('repeat_input_seconds')!=3600
                or job.get('maximum_output_files')!=2048
                or not 0<job['deadline_unix']-job['issued_unix']<=4725):
            raise ValueError('Exact finite full-application hour scope required')
        return 3*1024**3,2048
    match=re.fullmatch(re.escape(base)+r'(gui-qualification-[0-9]+)',root)
    if match:
        if job.get('unit')!='jp-v29-'+match[1]+'.service':
            raise ValueError('Exact GUI output/unit pair required')
        if not 0<job['deadline_unix']-job['issued_unix']<=1545:
            raise ValueError('Finite two-session GUI lifetime required')
        return 1024**3,1024
    return 256*1024**2,256


def validate_job(job):
    if job.get('schema')!='just-peachy.native-component-job.v1': raise ValueError('Job schema')
    if not re.fullmatch(r'jp-v29-[a-z0-9-]+\.service',job['unit']): raise ValueError('Exact job unit')
    if not re.fullmatch(r'[0-9a-f-]{36}',job['boot_id']): raise ValueError('Actual job boot')
    if job.get('invocation_id') is not None and not re.fullmatch(r'[0-9a-f]{32}',job['invocation_id']):
        raise ValueError('Actual systemd InvocationID')
    maximum,_=job_limits(job)
    if type(job['maximum_output_bytes']) is not int or not 1<=job['maximum_output_bytes']<=maximum:
        raise ValueError('Finite complete-output reservation')
    if not 0<job['deadline_unix']-job['issued_unix']<=86400:
        raise ValueError('Finite native job interval')
    if not re.fullmatch(r'[0-9a-f]{64}',job['package_manifest_sha256']): raise ValueError('Package manifest pin')
    return job


class Receiver:
    def __init__(self,root,maximum,mirror=False,owner_path=None,catalog=False,maximum_files=256):
        self.root=root;self.maximum=maximum;self.mirror=mirror
        self.owner=None;self.status=None;self.utilities=[];self.rows=[]
        self.manifest=None;self.complete=None;self.stream=None;self.current=None
        self.offset=0;self.digest=None;self.completed=set();self.copied=0
        self.owner_path=owner_path
        self.catalog=catalog;self.catalog_complete=None
        if maximum_files not in (256,1024,2048):raise ValueError('Explicit bounded file inventory')
        self.maximum_files=maximum_files

    def feed(self,row):
        kind=row.get('kind')
        if self.owner is None:
            if kind!='OWNER': raise ValueError('Actual native early owner must be first')
            self.owner=row['owner']
            if self.owner_path is not None:
                save(self.owner_path,self.owner)
            return
        if kind=='UTILITY':
            receipt=row['receipt']
            if (not receipt['reaped'] or receipt['forced'] or not receipt['exact_owner_gone']
                or len(self.utilities)>=8): raise ValueError('Natural exact utility closure required')
            self.utilities.append(receipt)
        elif kind=='STATUS':
            if self.status is not None: raise ValueError('Duplicate status')
            self.status=row
        elif kind=='MANIFEST':
            if not self.mirror or not self.status or not self.status['closed'] or self.manifest:
                raise ValueError('Closed output required before manifest')
            if not 0<=row['files']<=self.maximum_files or not 0<=row['bytes']<=self.maximum:
                raise ValueError('Complete output reservation exceeded')
            hash_mode=row.get('hash_mode','whole_file')
            if hash_mode not in ('whole_file','streamed_segments') or hash_mode=='streamed_segments' and (not self.catalog or self.maximum_files!=2048):
                raise ValueError('Segment-only catalog requires explicit full-app-hour scope')
            self.manifest=row
        elif kind=='MANIFEST_ENTRY':
            name=row['path'];path=PurePosixPath(name)
            if (not self.manifest or len(self.rows)>=self.manifest['files'] or path.is_absolute()
                or path.as_posix()!=name or '..' in path.parts or '\\' in name or len(name)>512
                or any(prior['path']==name for prior in self.rows)):
                raise ValueError('Unsafe/duplicate source member')
            identity=row['identity']
            if type(identity['bytes']) is not int or not 0<=identity['bytes']<=self.maximum:
                raise ValueError('Source extent cap')
            if self.manifest.get('hash_mode')=='streamed_segments':
                if row['sha256'] is not None:raise ValueError('Identity catalog cannot claim whole-file hash')
            elif not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256']):
                raise ValueError('Whole-file SHA required')
            self.rows.append(dict(path=name,identity=identity,sha256=row['sha256']))
        elif kind=='CATALOG_END':
            if (not self.catalog or self.catalog_complete or not self.manifest
                or len(self.rows)!=self.manifest['files'] or row['files']!=len(self.rows)
                or row['bytes']!=self.manifest['bytes']
                or sum(entry['identity']['bytes'] for entry in self.rows)!=row['bytes']
                or hashlib.sha256(encoded(self.rows)).hexdigest()!=row['manifest_sha256']
                or not row['closure']['closed']):raise ValueError('Closed catalog proof failed')
            self.catalog_complete=row
        elif kind=='FILE':
            if (not self.manifest or len(self.rows)!=self.manifest['files'] or self.stream is not None
                or row['path'] in self.completed): raise ValueError('Exact sequential file framing')
            self.current=next((entry for entry in self.rows if entry['path']==row['path']),None)
            if self.current is None: raise ValueError('Unlisted output file')
            destination=self.root.joinpath(*PurePosixPath(row['path']).parts)
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.parent.resolve()!=destination.parent: raise ValueError('PC output parent changed')
            self.stream=destination.open('xb');self.offset=0;self.digest=hashlib.sha256()
        elif kind=='CHUNK':
            if self.stream is None or row['path']!=self.current['path'] or row['offset']!=self.offset:
                raise ValueError('Source chunk cursor changed')
            raw=base64.b64decode(row['data'],validate=True)
            if not 1<=len(raw)<=16384 or self.offset+len(raw)>self.current['identity']['bytes']:
                raise ValueError('16 KiB bounded source chunk required')
            if self.copied+len(raw)>self.maximum: raise ValueError('Full mirror reservation exhausted')
            if self.stream.write(raw)!=len(raw): raise OSError('Short PC mirror write')
            self.digest.update(raw);self.offset+=len(raw);self.copied+=len(raw)
        elif kind=='FILE_END':
            if (self.stream is None or row['path']!=self.current['path']
                or self.offset!=self.current['identity']['bytes'] or row['bytes']!=self.offset
                or row['sha256']!=self.current['sha256'] or self.digest.hexdigest()!=row['sha256']):
                raise ValueError('Source file digest/extent differs')
            self.stream.flush();os.fsync(self.stream.fileno());self.stream.close();self.stream=None
            path=self.root/self.current['path']
            with path.open('rb') as verify:
                if hashlib.file_digest(verify,'sha256').hexdigest()!=row['sha256']:
                    raise OSError('Independent PC mirror digest mismatch')
            self.completed.add(self.current['path']);self.current=None
        elif kind=='COMPLETE':
            if (self.complete or not self.manifest or self.stream is not None
                or len(self.completed)!=self.manifest['files'] or row['files']!=len(self.completed)
                or self.copied!=self.manifest['bytes'] or row['bytes']!=self.copied
                or hashlib.sha256(encoded(self.rows)).hexdigest()!=row['manifest_sha256']
                or not row['closure']['closed']): raise ValueError('Full closed mirror proof failed')
            self.complete=row
        else: raise ValueError('Unexpected native job protocol message')

    def close(self):
        if self.stream:
            self.stream.close();self.stream=None


class SegmentReceiver(Receiver):
    def __init__(self,root,maximum,entry,offset,count,owner_path=None):
        super().__init__(root,maximum,owner_path=owner_path)
        self.entry=entry;self.start=offset;self.count=count;self.offset=offset
        self.segment_complete=None;self.started=False;self.digest=hashlib.sha256()

    def _permit_segment(self,status):
        return bool(status and status['closed'])

    def _permit_end(self,row):
        return bool(row['closure']['closed'])

    def feed(self,row):
        kind=row.get('kind')
        if kind in ('OWNER','UTILITY','STATUS'):
            return super().feed(row)
        if kind=='SEGMENT':
            if (not self._permit_segment(self.status) or self.started or row['entry']!=self.entry
                or row['offset']!=self.start or row['count']!=self.count or not 0<=self.count<=1024**2):
                raise ValueError('Exact bounded closed segment framing')
            name=self.entry['path'];relative=PurePosixPath(name)
            if relative.is_absolute() or relative.as_posix()!=name or '..' in relative.parts or '\\' in name:
                raise ValueError('Unsafe segment destination')
            path=self.root.joinpath(*relative.parts);path.parent.mkdir(parents=True,exist_ok=True)
            if path.parent.resolve()!=path.parent:raise ValueError('Segment destination parent changed')
            if self.start:
                if path.is_symlink() or path.stat().st_size!=self.start:raise ValueError('PC segment prefix changed')
                self.stream=path.open('r+b');self.stream.seek(self.start)
            else:self.stream=path.open('xb')
            self.started=True
        elif kind=='CHUNK':
            if self.stream is None or row['path']!=self.entry['path'] or row['offset']!=self.offset:
                raise ValueError('Exact segment cursor required')
            raw=base64.b64decode(row['data'],validate=True)
            if not 1<=len(raw)<=16384 or self.offset+len(raw)>self.start+self.count:
                raise ValueError('16 KiB bounded segment frame required')
            if self.stream.write(raw)!=len(raw):raise OSError('Short segment write')
            self.digest.update(raw);self.offset+=len(raw)
        elif kind=='SEGMENT_END':
            if (self.stream is None or self.segment_complete or row['path']!=self.entry['path']
                or row['offset']!=self.start or row['bytes']!=self.count or self.offset!=self.start+self.count
                or row['sha256']!=self.digest.hexdigest() or not self._permit_end(row)):
                raise ValueError('Closed segment extent/hash proof failed')
            self.stream.flush();os.fsync(self.stream.fileno());self.stream.close();self.stream=None
            with (self.root/self.entry['path']).open('rb') as stream:
                stream.seek(self.start);remaining=self.count;digest=hashlib.sha256()
                while remaining:
                    raw=stream.read(min(16384,remaining))
                    if not raw:raise OSError('PC segment readback truncated')
                    digest.update(raw);remaining-=len(raw)
            if digest.hexdigest()!=row['sha256']:raise OSError('Independent PC segment readback failed')
            self.segment_complete=row
        else:raise ValueError('Unexpected segment protocol frame')


def phase(command,payload,receiver,maximum_wire):
    proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    creation=process_creation(int(proc._handle))
    errors=[];stderr=bytearray();wire=[0];forced=False
    def output():
        pending=bytearray()
        try:
            while raw:=proc.stdout.read(4096):
                wire[0]+=len(raw)
                if wire[0]>maximum_wire: raise ValueError('Wire output cap')
                pending.extend(raw)
                while b'\n' in pending:
                    line,_,rest=pending.partition(b'\n');pending=bytearray(rest)
                    if len(line)>65536: raise ValueError('Protocol line cap')
                    receiver.feed(strict(line))
                if len(pending)>65536: raise ValueError('Protocol line cap')
            if pending: raise ValueError('Incomplete final native frame')
        except BaseException as error: errors.append(repr(error))
    def diagnostic():
        try:
            while raw:=proc.stderr.read(4096):
                if len(stderr)+len(raw)>65536: raise ValueError('SSH diagnostic cap')
                stderr.extend(raw)
        except BaseException as error: errors.append(repr(error))
    def send():
        try:
            for offset in range(0,len(payload),16384):
                proc.stdin.write(payload[offset:offset+16384])
            proc.stdin.flush()
        except BaseException as error: errors.append(repr(error))
        finally: proc.stdin.close()
    threads=[threading.Thread(target=target,daemon=True) for target in (output,diagnostic,send)]
    for thread in threads:thread.start()
    try:
        proc.wait(timeout=40)
    except subprocess.TimeoutExpired:
        forced=True;proc.kill();proc.wait(timeout=5)
    finally:
        for thread in threads:thread.join(3)
        for pipe in (proc.stdin,proc.stdout,proc.stderr):
            if not pipe.closed:pipe.close()
        receiver.close()
    result=dict(pid=proc.pid,creation_filetime=creation,returncode=proc.returncode,
        natural=not forced,ssh_reaped=proc.poll() is not None,readers_joined=all(not t.is_alive() for t in threads),
        errors=errors,stderr=stderr.decode('utf-8','replace'),wire_bytes=wire[0])
    if forced or proc.returncode or errors or not result['readers_joined']:
        error=RuntimeError('Bounded SSH phase failed: '+str(result));error.receipt=result;raise error
    return result


def run_probe(source,job,mode,root,index,extra=None):
    directory=root/('probe-'+str(index).zfill(4));directory.mkdir()
    extra=extra or {}
    if mode=='segment':
        receiver=SegmentReceiver(root/'closed-output',job['maximum_output_bytes'],extra['entry'],
            extra['offset'],extra['count'],owner_path=directory/'NATIVE_OWNER.json')
    else:
        receiver=Receiver(root/'closed-output',job['maximum_output_bytes'],mirror=mode in ('mirror','catalog'),
            owner_path=directory/'NATIVE_OWNER.json',catalog=mode=='catalog',maximum_files=job_limits(job)[1])
    payload=encoded(dict(mode=mode,job=job,**extra))
    if len(payload)>65536:raise ValueError('Job request cap')
    bootstrap="import base64;exec(compile(base64.b64decode('"+base64.b64encode(source).decode()+"'),'<read-only-owned-job-probe>','exec'))"
    command=SSH+['exec '+shlex.join(['python3','-B','-c',bootstrap])]
    try:
        wire_max=job['maximum_output_bytes']*2+1024**2 if mode=='mirror' else (3*1024**2 if mode=='segment' else (4*1024**2 if mode=='catalog' and job_limits(job)[1]==2048 else 2*1024**2 if mode=='catalog' and job_limits(job)[1]==1024 else 262144))
        receipt=phase(command,payload,receiver,wire_max)
        if receiver.owner is None:raise ValueError('Native utility early owner missing')
        # Read-only exact PID absence, after natural exec/SSH completion. A reused
        # PID fails conservatively; it is never signaled or treated as ours.
        check=subprocess.Popen(SSH+['exec /usr/bin/test ! -e /proc/'+str(receiver.owner['pid'])],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        check_creation=process_creation(int(check._handle))
        try:
            check_out,check_error=check.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            check.kill();check.communicate(timeout=5)
            raise RuntimeError('Read-only utility absence SSH did not finish naturally')
        if check.returncode or check_out or len(check_error)>4096:
            raise RuntimeError('Native read-only utility did not prove absent after natural SSH exit')
        save(directory/'SSH_CLOSURE.json',dict(receipt,utility_pid_absent_after_ssh=True,
            utilities=receiver.utilities,absence_check=dict(pid=check.pid,creation_filetime=check_creation,
                returncode=check.returncode,naturally_reaped=True,readers_closed=True)))
        save(directory/'STATUS.json',receiver.status)
        if mode=='mirror':
            if receiver.complete is None:raise ValueError('Full output completion frame missing')
            save(root/'MIRROR_MANIFEST.json',receiver.rows)
            save(root/'MIRROR_COMPLETE.json',receiver.complete)
        if mode=='segment':
            if receiver.segment_complete is None:raise ValueError('Segment completion frame missing')
            save(directory/'SEGMENT_COMPLETE.json',receiver.segment_complete)
            return receiver
        if mode=='catalog':
            if receiver.catalog_complete is None:raise ValueError('Catalog completion frame missing')
            save(directory/'CATALOG_COMPLETE.json',receiver.catalog_complete)
            return receiver
        return receiver.status
    except BaseException as error:
        save(directory/'FAILURE.json',dict(error=repr(error),ssh=getattr(error,'receipt',None),
            early_native_owner=receiver.owner,partial_status=receiver.status,certified=False))
        raise


def segmented_mirror(source,job,root,index,deadline):
    first=run_probe(source,job,'catalog',root,index);index+=1
    streamed=first.manifest.get('hash_mode')=='streamed_segments'
    save(root/('SOURCE_IDENTITY_MANIFEST.json' if streamed else 'MIRROR_MANIFEST.json'),first.rows)
    complete_rows=[]
    copied=0;segment_count=0;chunk_size=65536
    for entry in first.rows:
        offset=0;size=entry['identity']['bytes']
        while offset<size or offset==0 and size==0:
            if time.time()>deadline:raise TimeoutError('Finite segmented copy lifetime')
            count=min(chunk_size,size-offset);started=time.monotonic()
            run_probe(source,job,'segment',root,index,dict(entry=entry,offset=offset,count=count))
            elapsed=max(time.monotonic()-started,0.001);index+=1;segment_count+=1
            offset+=count;copied+=count
            # Adapt only from measured successful network/reap throughput. Native
            # alarm stays 15s; each transfer is at most 1MiB in 16KiB frames.
            if count:chunk_size=min(1024**2,max(65536,int(count/elapsed*6)))
            if size==0:break
        path=root/'closed-output'/entry['path']
        with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.stat().st_size!=size or not streamed and digest!=entry['sha256']:raise ValueError('Full independent PC file digest failed')
        complete_rows.append(dict(entry,sha256=digest))
    if time.time()>deadline:raise TimeoutError('Finite final catalog lifetime')
    final=run_probe(source,job,'catalog',root,index)
    if first.rows!=final.rows or copied!=first.manifest['bytes']:
        raise ValueError('Closed source membership or bytes changed across segmented mirror')
    actual=sorted(path.relative_to(root/'closed-output').as_posix()
        for path in (root/'closed-output').rglob('*') if path.is_file())
    if actual!=sorted(entry['path'] for entry in first.rows):raise ValueError('PC mirror membership changed')
    result=dict(final.catalog_complete,kind='COMPLETE',segmented=True,segments=segment_count,
        native_alarm_seconds=15,maximum_segment_bytes=1024**2)
    if streamed:
        save(root/'MIRROR_MANIFEST.json',complete_rows)
        result.update(source_identity_manifest_sha256=final.catalog_complete['manifest_sha256'],
            manifest_sha256=hashlib.sha256(encoded(complete_rows)).hexdigest(),
            hash_provenance='native SHA256 for each exact contiguous segment; independent PC segment readback and complete-file SHA256',
            source_whole_file_hash_claimed=False)
    save(root/'MIRROR_COMPLETE.json',result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--job',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--status-only',action='store_true')
    ap.add_argument('--sample-memory',action='store_true',help='Bounded whole-owned-unit read-only samples; not continuous peaks')
    ap.add_argument('--poll-seconds',type=float,default=5)
    ap.add_argument('--copy-deadline-seconds',type=int,default=1800)
    args=ap.parse_args();root=bootstrap(args.output)
    if not 1<=args.poll_seconds<=30:raise ValueError('Poll interval 1..30 seconds')
    if args.sample_memory:args.poll_seconds=max(15,args.poll_seconds)
    if not 60<=args.copy_deadline_seconds<=7200:raise ValueError('Finite copy allowance 60..7200 seconds')
    floors()
    if args.job.is_symlink() or args.job.stat().st_size>65536:raise ValueError('Bounded real JOB.json')
    raw=args.job.read_bytes();job=validate_job(strict(raw))
    floors(2*job['maximum_output_bytes']+8*1024**2)
    source=Path(__file__).with_name('native_job_probe.py').read_bytes()
    if len(source)>65536:raise ValueError('Native helper source cap')
    compile(source,'<read-only-job-probe>','exec')
    for name,data in (('JOB.json',raw),('MONITOR.py',Path(__file__).read_bytes()),('NATIVE_PROBE.py',source)):
        write(root/(name+'.backup'),data);write(root/(name+'.restore'),data)
    save(root/'SOURCE_CLOSED.json',dict(job_sha256=hashlib.sha256(raw).hexdigest(),
        native_probe_sha256=hashlib.sha256(source).hexdigest(),independent_restore=True))
    # Monitoring after the compute deadline is allowed only for bounded closure
    # and output transfer; it cannot start/renew or signal the native job.
    deadline=max(time.time(),job['deadline_unix'])+args.copy_deadline_seconds
    try:
        for index in range(1024):
            if time.time()>deadline:raise TimeoutError('Finite monitor/closed-copy lifetime')
            status=run_probe(source,job,'status',root,index,dict(sample_memory=True) if args.sample_memory else None)
            if args.sample_memory:
                sample=status['memory_sample']
                # Full per-process rows remain in this probe's bounded STATUS.
                # The compact host trace has its own1MiB finite allowance.
                compact={key:value for key,value in sample.items() if key!='processes'}
                line=encoded(compact)+b'\n';trace=root/'SAMPLED_MEMORY.jsonl'
                if len(line)>4096 or (trace.stat().st_size if trace.exists() else 0)+len(line)>1024**2:
                    raise ValueError('Sampled host memory trace reservation exhausted')
                with trace.open('ab') as stream:
                    if stream.write(line)!=len(line):raise OSError('Short sampled-memory trace write')
                    stream.flush();os.fsync(stream.fileno())
            for key in ('owner','invocation_id','control_group','output_identity'):
                if status.get(key) is not None:job[key]=status[key]
            if args.status_only:
                save(root/'RESULT.json',dict(status=status,mirror_complete=False,native_actions=False))
                print(encoded(dict(output=str(root),status=status)).decode());return 0
            if status['closed']:
                save(root/'EFFECTIVE_JOB.json',job)
                segmented_mirror(source,job,root,index+1,deadline)
                result=dict(status='FULL_CLOSED_OUTPUT_MIRRORED',output=str(root),job=job,
                    copied_root=str(root/'closed-output'),native_actions=False,
                    mirror_scope='all_regular_output_files',empty_directories_copied=False,
                    functional_success=bool(status.get('job_exit') and status['job_exit'].get('natural_returncode')==0
                                            and not status['job_exit'].get('error')))
                save(root/'RESULT.json',result);print(encoded(result).decode());return 0
            time.sleep(args.poll_seconds)
        raise TimeoutError('Maximum bounded status probes reached')
    except BaseException as error:
        save(root/'RESULT.json',dict(status='INCOMPLETE',error=repr(error),native_actions=False,certified=False))
        raise


if __name__=='__main__':raise SystemExit(main())
