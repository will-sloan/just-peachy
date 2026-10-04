"""Private D1-only child; no standalone user launcher. See README_OPTIONAL_REFINER.md."""
# Standard library only until affinity, resource limits and owner are published.
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import socket
import sys
import time


def publish(path, value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode()+b"\n"
    if len(raw) > 65536:
        raise ValueError("Bounded optional-worker receipt required")
    with path.open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def bootstrap(args):
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        raise RuntimeError("Native optional child requires the admitted CM5")
    import resource
    os.sched_setaffinity(0, {2,3})
    if not 256*1024**2 <= args.as_bytes <= 768*1024**2 or not 1 <= args.deadline <= 345600:
        raise ValueError("Bounded native child envelope required")
    for kind, cap in ((resource.RLIMIT_AS,args.as_bytes), (resource.RLIMIT_STACK,1024**2),
                      (resource.RLIMIT_FSIZE,512*1024), (resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(cap,cap))
    signal.alarm(args.deadline)
    for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
        if os.environ.get(key) != "1":
            raise ValueError("Retained single-thread library environment required")
    output = Path(args.output).absolute()
    if any(path.is_symlink() for path in (output,*output.parents)):
        raise ValueError("Real isolated child output required")
    output.mkdir(exist_ok=False)
    owner = dict(pid=os.getpid(), start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
                 boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), affinity=[2,3],
                 parent_pid=args.parent_pid)
    publish(output/'REGISTERED_OWNER.json',owner)
    # A vanished parent must not leave an optional model resident.
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL,0,0,0) != 0 or os.getppid() != args.parent_pid:
        raise RuntimeError("Could not bind optional child lifetime to the exact parent")
    import re, subprocess
    if not re.fullmatch(r'[A-Za-z0-9_.@-]+\.(service|scope)',args.unit):
        raise ValueError("Exact owning shared unit required")
    if not any(line.rstrip().endswith('/'+args.unit) for line in Path('/proc/self/cgroup').read_text().splitlines()):
        raise RuntimeError("Optional child escaped the primary resource unit")
    result = subprocess.run(['systemctl','--user','show',args.unit,
        '--property=ActiveState,AllowedCPUs,CPUQuotaPerSecUSec,TasksMax'],capture_output=True,text=True,timeout=5,check=True)
    props = dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
    if (props.get('ActiveState') != 'active' or props.get('AllowedCPUs') not in ('2-3','2,3') or
            props.get('CPUQuotaPerSecUSec') != '2s' or props.get('TasksMax') != '64'):
        raise RuntimeError("Shared CPU2/3, aggregate200%, Tasks64 required")
    sys.dont_write_bytecode=True
    return output, owner


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('fd','parent-pid','deadline','as-bytes'):
        parser.add_argument('--'+name,type=int,required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--unit',required=True)
    args=parser.parse_args()
    output,owner=bootstrap(args)
    from optional_refiner_protocol import Channel, RATE, BLOCK_SAMPLES, MAX_FRAMES
    channel=Channel(socket.socket(fileno=args.fd))
    channel.send(dict(kind='owner',owner=owner))
    config=None
    while config is None:
        config=channel.receive()
    if config.get('kind') != 'configure':
        raise ValueError('Explicit parent configuration required')
    from profiles import RuntimeSelection,SessionPolicy
    from native_benchmark import load_factory,resource_sample
    from nemotron_binding import expected_frames
    selection=RuntimeSelection('nemotron','anonymous',config['input_source'],'current_delayed')
    policy=SessionPolicy(**config['policy']);policy.validate()
    if policy.total_deadline_seconds != args.deadline:
        raise ValueError('Child policy and wall lifetime differ')
    model=None;failure=None;complete=False;cursor=frames=0;digest=hashlib.sha256();cost=0.
    try:
        before=time.perf_counter()
        np,factory=load_factory(config['binding'],config['binding_sha256'],selection,policy,config['session_id'])
        model=factory()
        channel.send(dict(kind='ready',initialization_seconds=time.perf_counter()-before,resources=resource_sample()))
        def accept(update,final):
            nonlocal frames,cost
            values=update.probabilities
            if (update.frame_start != frames or update.frame_end != frames+len(values) or len(values)>MAX_FRAMES or
                    update.frame_end>expected_frames(cursor,policy.maximum_samples()) or values.shape != (len(values),8) or
                    abs(update.audio_received_sec-cursor/RATE)>1e-9 or update.is_final is not final or
                    abs(update.seconds_per_frame-.01)>1e-6 or not np.isfinite(values).all() or
                    np.any(values<0) or np.any(values>1)):
                raise RuntimeError('Optional native sample/frame/probability contract')
            masks=((values >= .5).astype(np.uint8)*(1 << np.arange(8,dtype=np.uint8))).sum(axis=1).astype(np.uint8).tobytes()
            channel.send(dict(kind='activity',frame_start=frames,frame_end=update.frame_end,
                received_samples=cursor,masks=base64.b64encode(masks).decode(),final=final,
                compute_seconds=update.compute_sec,resources=resource_sample()))
            frames=update.frame_end;cost+=update.compute_sec
        while True:
            channel.send(dict(kind='read',start_sample=cursor,maximum_samples=BLOCK_SAMPLES))
            reply=None
            while reply is None:
                reply=channel.receive()
            if reply.get('kind') == 'stop':
                failure='OPTIONAL_STOPPED_BY_PARENT';break
            if reply.get('kind') != 'audio' or reply.get('start_sample') != cursor:
                raise RuntimeError('Discontinuous optional audio RPC')
            raw=base64.b64decode(reply['audio'],validate=True)
            if len(raw)%4 or len(raw)>BLOCK_SAMPLES*4 or cursor+len(raw)//4>policy.maximum_samples():
                raise ValueError('Optional audio allocation/source policy bound')
            if raw:
                audio=np.frombuffer(raw,dtype='<f4')
                if not np.isfinite(audio).all():raise ValueError('Nonfinite committed audio')
                update=model.push(audio,received_at_monotonic=time.perf_counter())
                cursor+=len(audio);digest.update(raw);accept(update,False)
            if reply.get('finished') and cursor==reply['committed_samples']:
                accept(model.finish(),True)
                if frames!=expected_frames(cursor,policy.maximum_samples()):raise RuntimeError('Incomplete EOF')
                complete=True;break
            if not raw:time.sleep(.025)
    except BaseException as exc:
        failure=type(exc).__name__+': '+str(exc)[:1024]
    finally:
        closed=False
        if model is not None:
            try:
                model.close();closed=bool(model._closed and not model._stream and not model._model)
            except BaseException as exc:
                failure=(failure or '')+';close:'+str(exc)[:512]
        receipt=dict(kind='closed',owner=owner,complete_eof=complete and failure is None,
            failure=failure,delivered_samples=cursor,output_frames=frames,
            delivered_f32_sha256=digest.hexdigest(),model_closed=closed,
            component_compute_seconds=cost,resources=resource_sample(),quality_qualified=False)
        publish(output/'RESULT.json',receipt)
        try:channel.send(receipt)
        finally:channel.close()
    return 0 if complete and closed and failure is None else 1


if __name__=='__main__':
    raise SystemExit(main())
