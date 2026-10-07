"""Nested broker qualification; README_FIELD_OPERATOR_MANUAL_V1.md."""
import argparse
from datetime import datetime,timezone
import os
from pathlib import Path
import resource
import signal
import sys
import time
sys.dont_write_bytecode=True
from field_operator_session_plan_v3 import validate_policy,state
from field_operator_session_ledger_v4 import Ledger,read,file_pin,identity,ticks
from field_operator_broker_files_v2 import Files
from field_operator_broker_common_v1 import bundle,ready,physical

def main(root,policy_sha256):
    root=Path(root).absolute()
    if file_pin(root/'RELEASE.json')['sha256']!=policy_sha256:raise ValueError('Entry policy pin')
    policy,config,manifest=bundle(root);physical(config)
    if resource.getrlimit(resource.RLIMIT_AS)!=(768*1024**2,)*2 or resource.getrlimit(resource.RLIMIT_STACK)!=(1048576,)*2 or os.sched_getaffinity(0)!={2,3}:
        raise ValueError('Actual inherited broker CPU/AS/stack')
    expiry=datetime.fromisoformat(policy['expires_utc'])
    check=lambda:validate_policy(policy)
    files=Files(root,check);owner=identity();files.json('OWNER.json',owner)
    until=time.monotonic()+15
    while not (root/'broker/ACK.json').exists():
        check()
        if time.monotonic()>=until:raise TimeoutError('Outer gate ACK')
        time.sleep(.01)
    ack=ready(root,'ACK.json',check)
    if set(ack)!={'owner','policy_sha256','gate_owner'} or ack['owner']!=owner or ack['policy_sha256']!=policy_sha256:
        raise ValueError('Exact gate ACK')
    gate=ack['gate_owner']
    if gate['boot_id']!=owner['boot_id'] or ticks(gate['pid'])!=gate['start_ticks']:raise RuntimeError('Outer gate missing')
    ledger=broker=ui=None;failure=None;result=None
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise RuntimeError('Existing broker alarm')
    previous={s:signal.getsignal(s) for s in (signal.SIGALRM,signal.SIGTERM)}
    def expired(signum,frame):
        signal.setitimer(signal.ITIMER_REAL,0)
        raise TimeoutError('Broker admission end or supervisor Stop')
    for s in previous:signal.signal(s,expired)
    signal.setitimer(signal.ITIMER_REAL,max(1,(expiry-datetime.now(timezone.utc)).total_seconds()-90))
    try:
        network_proof=offline_socket_check()
        # Owner ACK precedes installed History or Field/Store constructors.
        ledger=Ledger(root,policy_sha256,policy['release_manifest_sha256'],create=True)
        from field_operator_broker_v7 import Broker
        from field_operator_chooser_v3 import Chooser
        from field_operator_broker_stage_v5 import stage
        broker=Broker(ledger,config['installed_release'],config['installed_manifest_sha256'])
        ui=Chooser(broker,lambda recording:stage(broker,recording))
        while not ui.closed:
            check()
            if ticks(gate['pid'])!=gate['start_ticks']:raise RuntimeError('Outer gate ownership lost')
            if (expiry-datetime.now(timezone.utc)).total_seconds()<95:
                if broker.proc is not None:raise TimeoutError('Final broker cleanup reserve')
                ui.close();break
            ui.tick()
            if ui.fault:raise RuntimeError(ui.fault)
            time.sleep(.01)
        result=dict(status='BROKER_CLOSED',offline_network=network_proof,owner=owner,capture_closed=True,automatic_explicit_button_driver=False,
                    accepted_field_runtime=False,repeated_modes_qualified=False)
    except BaseException as exc:
        failure=type(exc).__name__+': '+str(exc)[:1024]
        if broker is not None:broker.abort.set()
        result=dict(status='FAILED_PRESERVED',owner=owner,failure=failure,
                    accepted_field_runtime=False,repeated_modes_qualified=False)
    finally:
        cleanup=[]
        if broker is not None:
            try:broker.close()
            except BaseException as exc:cleanup.append(type(exc).__name__+': '+str(exc)[:512])
        elif ledger is not None:ledger.close()
        if ui is not None and not ui.closed:
            try:ui.root.destroy()
            except Exception as exc:cleanup.append(str(exc)[:512])
        signal.setitimer(signal.ITIMER_REAL,0)
        for s,handler in previous.items():signal.signal(s,handler)
        if result is None:result=dict(status='FAILED_PRESERVED',owner=owner)
        result.update(cleanup_errors=cleanup,capture_closed=Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip()=='closed')
        files.json('RESULT.json',result)
    return int(result['status']!='BROKER_CLOSED' or result['cleanup_errors'] or not result['capture_closed'])
def offline_socket_check():
    """Verify this process has no inherited Internet socket and cannot create one."""
    import errno
    import socket
    from pathlib import Path
    import os
    status = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            status[k] = v.strip()
    if status.get('NoNewPrivs') != '1' or status.get('Seccomp') != '2':
        raise RuntimeError('Actual kernel socket restriction missing')
    local = set()
    for name, column in (('unix', 6), ('netlink', 9)):
        raw = Path('/proc/net', name).read_bytes()
        if len(raw) > 262144:
            raise ValueError('Bounded inherited-socket census')
        for line in raw.decode().splitlines()[1:]:
            parts = line.split()
            if len(parts) > column:
                local.add(parts[column])
    inherited = 0
    for fd in Path('/proc/self/fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith('socket:['):
            if target[8:-1] not in local:
                raise RuntimeError('Inherited nonlocal socket rejected')
            inherited += 1
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.close()
    denied = {}
    for family, kind in ((socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET6, socket.SOCK_DGRAM)):
        try:
            probe = socket.socket(family, kind)
        except OSError as exc:
            if exc.errno not in (errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES):
                raise
            denied[str(int(family))] = exc.errno
        else:
            probe.close()
            raise RuntimeError('Internet socket creation was not denied')
    return dict(schema='just-peachy.offline-sockets.v1',pid=os.getpid(),
        seccomp=2,no_new_privileges=True,ipv4_ipv6_socket_denied=denied,
        inherited_local_sockets=inherited,physical_disconnect_tested=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--policy-sha256',required=True)
    args=parser.parse_args();raise SystemExit(main(args.root,args.policy_sha256))
