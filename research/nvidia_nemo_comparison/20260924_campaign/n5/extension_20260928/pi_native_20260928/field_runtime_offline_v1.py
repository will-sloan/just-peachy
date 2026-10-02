"""Bind OS network-denied runtime composition; README_RUNTIME_OFFLINE_V1.md."""
import base64
import hashlib
import json

INPUT_SHA='b8e55d2673971b0d22d5eef9d5cf2a6ed964d317976677556fd4006098ca4ab3'
GUARD="def offline_socket_check():\n    \"\"\"Verify this process has no inherited Internet socket and cannot create one.\"\"\"\n    import errno\n    import socket\n    from pathlib import Path\n    import os\n    status = {}\n    for line in Path('/proc/self/status').read_text().splitlines():\n        if ':' in line:\n            k, v = line.split(':', 1)\n            status[k] = v.strip()\n    if status.get('NoNewPrivs') != '1' or status.get('Seccomp') != '2':\n        raise RuntimeError('Actual kernel socket restriction missing')\n    local = set()\n    for name, column in (('unix', 6), ('netlink', 9)):\n        raw = Path('/proc/net', name).read_bytes()\n        if len(raw) > 262144:\n            raise ValueError('Bounded inherited-socket census')\n        for line in raw.decode().splitlines()[1:]:\n            parts = line.split()\n            if len(parts) > column:\n                local.add(parts[column])\n    inherited = 0\n    for fd in Path('/proc/self/fd').iterdir():\n        try:\n            target = os.readlink(fd)\n        except FileNotFoundError:\n            continue\n        if target.startswith('socket:['):\n            if target[8:-1] not in local:\n                raise RuntimeError('Inherited nonlocal socket rejected')\n            inherited += 1\n    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n    probe.close()\n    denied = {}\n    for family, kind in ((socket.AF_INET, socket.SOCK_STREAM), (socket.AF_INET6, socket.SOCK_DGRAM)):\n        try:\n            probe = socket.socket(family, kind)\n        except OSError as exc:\n            if exc.errno not in (errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES):\n                raise\n            denied[str(int(family))] = exc.errno\n        else:\n            probe.close()\n            raise RuntimeError('Internet socket creation was not denied')\n    return dict(schema='just-peachy.offline-sockets.v1',pid=os.getpid(),\n        seccomp=2,no_new_privileges=True,ipv4_ipv6_socket_denied=denied,\n        inherited_local_sockets=inherited,physical_disconnect_tested=False)\n"

def derive(raw):
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if type(raw) is not bytes or len(raw)>1048576 or sha(raw)!=INPUT_SHA:
        raise ValueError('Exact qualified Chunk52/terminal2 capsule')
    value=json.loads(raw);files={n:base64.b64decode(v,validate=True) for n,v in value['files'].items()}
    if value['manifest']['files']!=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())]:
        raise ValueError('Complete pinned input capsule')
    old=dict(files)
    def change(name,before,after):
        text=files[name].decode()
        if text.count(before)!=1:raise ValueError('Exact offline derivation boundary: '+name)
        files[name]=text.replace(before,after).encode()
    name='code/field_operator_broker_gate_v8.py'
    change(name,"'LimitCORE=0','Nice=10'","'LimitCORE=0','RestrictAddressFamilies=AF_UNIX AF_NETLINK','NoNewPrivileges=yes','SystemCallArchitectures=native','Nice=10'")
    change(name,"'-p','RuntimeMaxUSec','-p','TimeoutStopUSec'],text=True",
        "'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','RestrictAddressFamilies','-p','NoNewPrivileges'],text=True")
    change(name,"                    files.json('ENVELOPE.json',",
        "                    if set(actual['RestrictAddressFamilies'].split())!={'AF_UNIX','AF_NETLINK'} or actual['NoNewPrivileges']!='yes':raise RuntimeError('Actual broker network restriction')\n                    files.json('ENVELOPE.json',")
    name='code/field_operator_broker_entry_v6.py'
    change(name,"    try:\n        # Owner ACK","    try:\n        network_proof=offline_socket_check()\n        # Owner ACK")
    change(name,"result=dict(status='BROKER_CLOSED',owner=owner,","result=dict(status='BROKER_CLOSED',offline_network=network_proof,owner=owner,")
    text=files[name].decode();marker="if __name__=='__main__':"
    if text.count(marker)!=1:raise ValueError('Broker main boundary')
    files[name]=text.replace(marker,GUARD+'\n'+marker).encode()
    name='code/field_operator_entry_v11.py'
    change(name,"        result['owner_ack_before_constructor']=True",
        "        result['owner_ack_before_constructor']=True\n        result['offline_socket_proof']=offline_socket_check()\n        result['offline_network_tested']=True")
    text=files[name].decode();marker="if __name__=='__main__':"
    if text.count(marker)!=1:raise ValueError('Worker main boundary')
    files[name]=text.replace(marker,GUARD+'\n'+marker).encode()
    code={n:b for n,b in files.items() if n.startswith('code/')}
    if len(code)!=64 or sum(map(len,code.values()))>2097152 or any(len(b)>131072 for b in files.values()):
        raise ValueError('Original capsule bounds')
    for n,b in code.items():
        if n.endswith('.py'):compile(b,n,'exec')
    manifest=dict(schema='just-peachy.broker-capsule.v1',files=[dict(path=n,bytes=len(b),sha256=sha(b)) for n,b in sorted(files.items())])
    packed=json.dumps(dict(manifest=manifest,files={n:base64.b64encode(b).decode() for n,b in files.items()}),sort_keys=True,separators=(',',':')).encode()
    if len(packed)>1048576:raise ValueError('Original packed cap')
    return packed,dict(status='PREPARED_OS_SOCKET_DENIAL',bundle_sha256=sha(packed),
        changed={n:dict(before_sha256=sha(old[n]),sha256=sha(b),bytes=len(b)) for n,b in files.items() if b!=old[n]},
        hardware_interface_unchanged=True,physical_disconnect_tested=False,native_executed=False)
