"""Changed PC subprocess protocol checks; README_FIELD_LOCAL_RECEIVER_V1.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
import json
from pathlib import Path
import sys
import time

FIXTURE = r'''
import psutil
psutil.Process().cpu_affinity([14])
import sys,json,struct,time
from pathlib import Path
p=psutil.Process()
Path(sys.argv[1]).open('x').write(json.dumps(dict(pid=p.pid,create_time=p.create_time(),affinity=[14])))
mode=sys.argv[2]
owner=dict(pid=123,start_ticks=456,boot_id='11111111-1111-1111-1111-111111111111')
def send(value):
 raw=json.dumps(value,separators=(',',':')).encode()
 sys.stdout.buffer.write(struct.pack('!I',len(raw))+raw);sys.stdout.buffer.flush()
def exact(n):
 out=b''
 while len(out)<n:
  x=sys.stdin.buffer.read(n-len(out))
  if not x:raise EOFError()
  out+=x
 return out
if mode=='hang':
 time.sleep(60);sys.exit(0)
if mode=='bad_early':owner['pid']=True
send(dict(early_owner=owner))
size=struct.unpack('!I',exact(4))[0]
payload=exact(size)
if mode=='wrong_hello':owner['start_ticks']=457
send(dict(type='HELLO',owner=owner))
if mode=='export':
 send(dict(type='READY',owner=owner))
 n=struct.unpack('!I',exact(4))[0]
 assert json.loads(exact(n))==dict(ack=owner)
 send(dict(type='FIXTURE_EXPORT_END'))
else:send(dict(type='CENSUS',owner=owner))
if mode=='stderr':
 sys.stderr.buffer.write(b'x'*65537);sys.stderr.buffer.flush()
if mode=='trailing':
 sys.stdout.buffer.write(b'x');sys.stdout.buffer.flush()
sys.exit(2 if mode=='nonzero' else 0)
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(exist_ok=False)
    p=psutil.Process()
    (args.output/'REGISTERED_OWNER.json').open('x').write(json.dumps(
        dict(pid=p.pid,create_time=p.create_time(),affinity=[14])))
    sys.dont_write_bytecode=True
    from field_local_manager_transport_v1 import run,TransportFailure
    cases=[]
    counter=0

    def trial(mode, failure=False):
        nonlocal counter
        counter+=1
        path=args.output/('CHILD_OWNER_%02d.json'%counter)
        stages=[]
        stopped=[]
        def persist(owner):
            stages.append('persisted-before-payload')
            (args.output/('SYNTHETIC_EARLY_%02d.json'%counter)).open('x').write(json.dumps(owner))
            return mode!='persist_false'
        def closure(owner):
            stages.append('independent-closure-callback')
            return mode!='closure_false'
        def consume(channel, owner, close):
            value=channel.json()
            assert value['owner']==owner
            stages.append('matching-consumer-owner')
            if mode=='export':
                assert value['type']=='READY'
                channel.send_json(dict(ack=owner))
                assert channel.json()==dict(type='FIXTURE_EXPORT_END')
            if mode!='missing_closure':
                close()
            return value['type']
        caught=False
        try:
            result,receipt=run([sys.executable,'-u','-B','-c',FIXTURE,str(path),mode],
                b'{"fixture":true}',persist_early=persist,consume=consume,
                verify_closed=closure,stop_owned=lambda:stopped.append(True),
                guard=lambda:None,timeout=2 if mode=='hang' else 10)
        except TransportFailure as exc:
            caught=True;receipt=exc.receipt
        assert caught==failure,(mode,caught)
        assert receipt['process_reaped'] and receipt['io_joined'],mode
        if not failure:
            assert receipt['closure_verified'] and not receipt['stopped'] and receipt['returncode']==0
            assert stages==['persisted-before-payload','matching-consumer-owner','independent-closure-callback']
        else:assert receipt['stopped'] and len(stopped)==1
        owner=json.loads(path.read_bytes())
        try:actual=psutil.Process(owner['pid']).create_time()
        except psutil.NoSuchProcess:actual=None
        assert actual is None or abs(actual-owner['create_time'])>.001
        cases.append(dict(mode=mode,expected_failure=failure,
            child_owner=owner,child_exact_alive=False,receipt=dict(receipt,stderr_bytes=len(receipt['stderr']),stderr=receipt['stderr'].decode('ascii'))))

    trial('census')
    trial('export')
    for mode in ('bad_early','wrong_hello','persist_false','missing_closure',
                 'closure_false','trailing','nonzero','stderr','hang'):
        trial(mode,True)
    result=dict(status='PASS_CHANGED_HOST_MANAGER_TRANSPORT',positive_groups=2,
        rejects=9,cases=cases,remote_owners_synthetic=True,closure_callback_synthetic=True,
        actual_pc_subprocesses=True,native_execution=False,backup_certified=False)
    (args.output/'RESULT.json').open('x').write(json.dumps(result))
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}))


if __name__=='__main__':
    main()
