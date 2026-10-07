"""Injected native lossless c24 staging. See README_CORE_BUILD35_HELPERS.md.

PAYLOAD/BASELINE only; no CLI, SSH, model imports or original-source writes.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import stat
import time
import wave

SCHEMA = 'just-peachy.core-c24-endurance-input.v1'
CAMPAIGN = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
DATA = Path('/home/peachyprototype/JustPeachy/data/runtime-v29')
PACKAGE = CAMPAIGN/'field-runtime-v29-build-35'
PIN = '5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f'
SID = 'c24b685b2bd34d6bb04172965d712c0f'
SOURCE = DATA/'recordings'/'sessions'/SID
TARGET = CAMPAIGN/'live-runtime-tests-20261003'/'core-c24-endurance-input-03'
LOCKS = (CAMPAIGN/'B05_PREVIEW_DISPATCH.lock', DATA.parent/'xvf-hardware.lock',
         DATA/'launcher.lock', DATA/'recordings'/'active.lock')
RESERVATION = 8*1024**2
WAV_SHA = '9a83534025736c2f057f20068f3c0584b45770815289a7842a501fcae52b65c8'
PCM_SHA = '0f13e54972e4140f5797b996bdeb48d802acd4dcbb9407065d46190bda887e97'


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def real(path):
    if any(p.is_symlink() for p in (path,*path.parents)) or path.resolve(strict=True)!=path:
        raise ValueError('Canonical existing non-symlink path required')
    return path


def identity(path):
    real(path);info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
        raise ValueError('Ordinary single-link source or output required')
    return dict(bytes=info.st_size,device=info.st_dev,inode=info.st_ino,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def membership():
    real(SOURCE)
    names = sorted(path.name for path in SOURCE.iterdir())
    return dict(entries=len(names),names_sha256=hashlib.sha256(encoded(names)).hexdigest())


def verify(rows):
    for row in rows:
        path = Path(row['source'])
        if identity(path)!=row['identity'] or digest(path)!=row['sha256'] or identity(path)!=row['identity']:
            raise ValueError('Original c24 source identity/hash changed')


def fsync_directory(path):
    descriptor = os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def stage(payload,baseline):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if (payload.get('schema')!=SCHEMA or payload.get('operation')!='stage_input' or
        payload.get('reviewed') is not True or not isinstance(payload.get('reviewer'),str) or
        not 1<=len(payload['reviewer'])<=128 or
        payload.get('boot_id')!=boot or baseline.get('boot_id')!=boot or
        type(payload.get('expires_unix')) not in (int,float) or
        not time.time()<payload['expires_unix']<=time.time()+600 or
        payload.get('package')!=str(PACKAGE) or payload.get('package_manifest_sha256')!=PIN or
        payload.get('destination')!=str(TARGET/'c24-processed.wav') or
        payload.get('output_copy_reservation_bytes')!=RESERVATION or
        payload.get('maximum_output_bytes')!=RESERVATION or
        payload.get('output_bytes')!=1932844 or payload.get('output_sha256')!=WAV_SHA or
        payload.get('pcm_sha256')!=PCM_SHA or
        payload.get('source_census_sha256')!='c827fad465bb6a1307de9157d13b55d31115476f7354868963cbe5b19a2444ac' or
        payload.get('source_complete_sha256')!='03ffc85b2e2f3046c707879c3059f3c2e1194626f4ece11a7d385975c924bdfb'):
        raise ValueError('Exact fresh current-boot reviewed c24 input staging required')
    if any(baseline.get(key) for key in ('current_project_processes','active_recorded_owners','live_manager_owners')):
        raise ValueError('Project owners must close before retained input staging')
    if set(map(str,LOCKS[:2]))-set(baseline.get('free_leases',[])):
        raise ValueError('Inspected research and hardware leases must be free')
    manifest = PACKAGE/'PACKAGE_MANIFEST.json'
    if identity(manifest)['bytes']>262144 or digest(manifest)!=PIN:
        raise ValueError('Actual frozen build35 manifest differs')
    rows = payload['original_source_pins']
    paths = [str(SOURCE/'session.json')]+[str(SOURCE/('processed-%08d.wav'%i)) for i in range(7)]
    if type(rows) is not list or len(rows)!=8 or [row.get('source') for row in rows]!=paths:
        raise ValueError('Exact kept c24 metadata and seven ordered replay segments required')
    real(TARGET.parent)
    if TARGET.exists() or TARGET.is_symlink():
        raise ValueError('Fresh input destination required; existing evidence is preserved')
    if shutil.disk_usage(TARGET.parent).free<5*1024**3+RESERVATION:
        raise OSError('Native five-GiB reserve plus complete staging allocation required')
    if resource.getrlimit(resource.RLIMIT_FSIZE)[1]<RESERVATION:
        raise ValueError('Inherited finite file allowance cannot fit this input copy')
    streams = []
    signal.alarm(30)
    try:
        for path in (*LOCKS,DATA/'recordings'/'locks'/(SID+'.lock')):
            real(path)
            descriptor = os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            stream = os.fdopen(descriptor,'rb');streams.append(stream)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                raise ValueError('Existing ordinary single-link shared lease required')
            kind = fcntl.LOCK_SH if path.name==SID+'.lock' else fcntl.LOCK_EX
            fcntl.flock(descriptor,kind|fcntl.LOCK_NB)
            current = path.stat()
            if (current.st_dev,current.st_ino)!=(info.st_dev,info.st_ino):
                raise ValueError('Acquired lease identity differs from its current path')
        before_members = membership();verify(rows)
        metadata = json.loads((SOURCE/'session.json').read_bytes())
        if (metadata.get('session_id')!=SID or metadata.get('status')!='kept' or
            metadata.get('processed_samples')!=966400 or metadata.get('spec',{}).get('sample_rate')!=16000):
            raise ValueError('Complete exact kept c24 source required')
        TARGET.mkdir(mode=0o700)
        target = TARGET/'c24-processed.wav';frames=0;pcm=hashlib.sha256()
        with target.open('xb') as output:
            with wave.open(output,'wb') as joined:
                joined.setparams((1,2,16000,966400,'NONE','not compressed'))
                for row in rows[1:]:
                    with wave.open(row['source'],'rb') as source:
                        if (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype())!=(1,2,16000,'NONE'):
                            raise ValueError('Original mono PCM16 16kHz source required')
                        frames += source.getnframes()
                        while block:=source.readframes(8192):
                            pcm.update(block);joined.writeframesraw(block)
            output.flush();os.fsync(output.fileno())
        if frames!=966400 or pcm.hexdigest()!=PCM_SHA or identity(target)['bytes']!=1932844 or digest(target)!=WAV_SHA:
            raise ValueError('Staged full WAV or lossless original PCM differs from accepted host join')
        readback=hashlib.sha256()
        with wave.open(str(target),'rb') as source:
            if (source.getnchannels(),source.getsampwidth(),source.getframerate(),source.getcomptype(),source.getnframes())!=(1,2,16000,'NONE',966400):
                raise ValueError('Independent staged WAV header/sample readback differs')
            while block:=source.readframes(8192):
                readback.update(block)
        if readback.hexdigest()!=PCM_SHA or digest(target)!=WAV_SHA:
            raise ValueError('Independent staged PCM/file readback differs')
        verify(rows)
        if membership()!=before_members:
            raise ValueError('Original retained session directory membership changed')
        result = dict(schema=SCHEMA,status='PASS',boot_id=boot,destination=str(target),
            output_bytes=1932844,output_sha256=WAV_SHA,pcm_sha256=PCM_SHA,frames=frames,
            source_session_id=SID,source_membership=before_members,original_source_unchanged=True,
            independent_wav_readback=True,independent_pcm_readback=True,reencoded=False,
            package_manifest_sha256=PIN,source_census_sha256=payload['source_census_sha256'],
            source_complete_sha256=payload['source_complete_sha256'],
            output_copy_reservation_bytes=RESERVATION,source_shared_lease_held=True,
            exclusive_guard_leases=[str(path) for path in LOCKS],models_started=False)
        body=encoded(result)
        with (TARGET/'SOURCE_JOIN.json').open('xb') as stream:
            if stream.write(body)!=len(body):
                raise OSError('Short staging receipt write')
            stream.flush();os.fsync(stream.fileno())
        fsync_directory(TARGET);fsync_directory(TARGET.parent)
        return result
    finally:
        for stream in reversed(streams):
            stream.close()
        signal.alarm(0)


if 'PAYLOAD' in globals():
    RESULT = stage(PAYLOAD,BASELINE)
