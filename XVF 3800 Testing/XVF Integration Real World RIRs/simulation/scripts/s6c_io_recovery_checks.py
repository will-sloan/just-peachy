"""Fault-inject actual atomic writer recovery; README_S6C_IO_RECOVERY_CHECKS.md."""
from pathlib import Path
from unittest.mock import patch
import ast
import json
import s6c_common as c

def run():
    folder=c.REPORT/'io_recovery_checks/v1';folder.mkdir(parents=True,exist_ok=False)
    original=c.os.replace;calls=[]
    def transient(a,b):
        calls.append((a,b))
        if len(calls)<=3:raise PermissionError('injected transient destination lock')
        return original(a,b)
    with patch.object(c.os,'replace',transient),patch.object(c.time,'sleep') as sleep:
        result=c.save(folder/'transient.json',dict(expected='complete'))
        assert len(calls)==4 and sleep.call_count==3 and c.verified(result)==dict(expected='complete')
    target=folder/'persistent.json';c.save(target,dict(expected='old'))
    with patch.object(c.os,'replace',side_effect=PermissionError('injected persistent lock')) as replace,patch.object(c.time,'sleep') as sleep:
        try:c.save(target,dict(expected='new'))
        except PermissionError:pass
        else:raise AssertionError('Persistent lock must remain fatal')
        assert replace.call_count==21 and sleep.call_count==20
    assert c.read(target)==dict(expected='old')
    partial=list(folder.glob('.persistent.json.*.tmp'))
    assert len(partial)==1 and c.read(partial[0])==dict(expected='new')
    with patch.object(c.os,'replace',side_effect=OSError('non-permission error')) as replace:
        try:c.save(folder/'other_error.json',dict(expected='fatal'))
        except OSError:pass
        else:raise AssertionError('Other OS error must remain fatal')
        assert replace.call_count==1
    source=c.SIM/'scripts/s6c_execution.py';tree=ast.parse(source.read_text(encoding='utf-8'))
    worker=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker_job')
    guard=next(n for n in worker.body if isinstance(n,ast.Try))
    assert [ast.unparse(n) for n in guard.body[:2]]==["save(folder / 'attempt_receipt.json', receipt)","save(w['status'], dict(receipt, phase='INPUT_ADMISSION'))"]
    receipt=dict(status='PASS',checks=8,transient_retries=3,persistent_attempts=21,persistent_old_bytes_preserved=True,temporary_new_payload_retained=True,
        non_permission_errors_retried=False,initial_worker_status_inside_failure_guard=True,
        source=[c.bind(c.__file__),c.bind(source),c.bind(__file__)],test_outputs=[c.bind(p) for p in folder.iterdir() if p.is_file()],utc=c.utc())
    print(json.dumps(c.save(folder/'CHECK_RECEIPT.json',receipt),indent=2))

if __name__=='__main__':run()
