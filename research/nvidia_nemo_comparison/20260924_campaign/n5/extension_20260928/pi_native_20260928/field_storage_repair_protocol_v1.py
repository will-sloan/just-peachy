"""Changed native storage checks only; README_FIELD_STORAGE_REPAIR_V1.md."""
import base64
import hashlib
import json
import os
from pathlib import Path
from copy import deepcopy
import field_archive_budget_v3 as archive
import field_metadata_budget_v2 as metadata
from field_sidecar_budget_v1 import GroupWriter


def run(root, admission):
    fixtures=root/'fixtures'; receipts=root/'storage_receipts'
    fixtures.mkdir(); receipts.mkdir()
    writer=GroupWriter(receipts,admission['case_receipt_limits'])
    rows=[]; original_os=archive.os; original_write=archive._write_block
    old=b'{"previous":"retained"}\n'; limit=1024
    for name in ['short-write','file-fsync','replace','directory-fsync','success','existing-pending','oversize']:
        d=fixtures/name; d.mkdir(); path=d/'epoch.json'
        path.write_bytes(old)
        value={'case':name,'new':'bounded control'}
        if name=='oversize':value['new']='x'*2048
        raw=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
        pending=d/'.epoch.json.pending'
        if name=='existing-pending':pending.write_bytes(b'prior partial')
        calls={'fsync':0,'replace':0,'write':0}
        class FaultOS:
            def __getattr__(self,key):return getattr(original_os,key)
            def fsync(self,fd):
                calls['fsync']+=1
                if name=='file-fsync' or name=='directory-fsync' and calls['fsync']==2:
                    raise OSError('injected '+name)
                return original_os.fsync(fd)
            def replace(self,src,dest):
                calls['replace']+=1
                if name=='replace':raise OSError('injected replace')
                return original_os.replace(src,dest)
        def fault_write(stream,payload):
            calls['write']+=1
            return original_write(stream,payload[:3] if name=='short-write' else payload)
        archive.os=FaultOS(); archive._write_block=fault_write
        error=None; replaced=None
        try:archive.publish(path,value,limit)
        except archive.PublicationFailure as exc:
            error=type(exc).__name__;replaced=exc.replaced
        except ValueError as exc:error=type(exc).__name__
        finally:archive.os=original_os;archive._write_block=original_write
        committed=name in ['success','directory-fsync']
        assert path.read_bytes()==(raw if committed else old)
        expected_pending=(raw[:3] if name=='short-write' else raw) if name in ['short-write','file-fsync','replace'] else b'prior partial' if name=='existing-pending' else None
        assert (pending.read_bytes() if pending.exists() else None)==expected_pending
        if name in ['short-write','file-fsync','replace','directory-fsync']:
            assert error=='PublicationFailure' and replaced==committed
        elif name=='success':assert error is None
        else:assert error=='ValueError' and not any(calls.values())
        rows.append(dict(case=name,error=error,replaced=replaced,committed=committed,calls=calls,
                         expected_raw_b64=base64.b64encode(raw).decode(),old_b64=base64.b64encode(old).decode(),
                         control_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         pending_b64=base64.b64encode(expected_pending).decode() if expected_pending is not None else None))
    finite=b'{"finite":1.25,"large":1e308,"underflow":1e-999}\n'
    tokens={'positive-overflow':b'{"n":1e999}', 'nested-negative-overflow':b'{"x":[-1e999]}',
            'hidden-duplicate-overflow':b'{"n":1e999,"n":0}', 'finite-bytes':finite}
    for name,raw in tokens.items():
        destination=fixtures/name
        batch={'code':{'a.py':b'# tiny native staging fixture\n'},
               'control':{'CONFIG.json':raw,'ADMISSION.json':b'{"admitted":true}\n'}}
        error=None; result=None
        try:result=metadata.publish_batch(destination,batch,deepcopy(admission['metadata_limits']))
        except ValueError as exc:error=str(exc)
        if name=='finite-bytes':
            assert result['admission_last'] and (destination/'control/CONFIG.json').read_bytes()==raw
        else:assert error=='Nonfinite decoded control number' and not destination.exists()
        rows.append(dict(case=name,input_b64=base64.b64encode(raw).decode(),error=error,
                         directory_created=destination.exists(),publication=result))
    files=[p for p in fixtures.rglob('*') if p.is_file()]
    directories=[fixtures]+[p for p in fixtures.rglob('*') if p.is_dir()]+[receipts]
    assert len(directories)<=admission['fixture_directory_maximum']
    assert len(files)<=admission['fixture_limits']['maximum_files']
    assert sum(p.stat().st_size for p in files)<=admission['fixture_limits']['maximum_bytes']
    assert all(p.stat().st_size<=admission['fixture_limits']['maximum_file_bytes'] for p in files)
    assert sum(max(p.stat().st_size,p.stat().st_blocks*512) for p in directories)<=admission['fixture_directory_reserve_bytes']
    writer.json('STORAGE_CASES.json',rows)
    result=dict(status='PASS_NATIVE_STORAGE_REPAIR_COMPONENTS_ONLY',cases=len(rows),archive_cases=7,
                injected_io_failures=4,prewrite_slot_rejections=2,overflow_rejections=3,
                exact_finite_staging=True,fixture_files=len(files),fixture_bytes=sum(p.stat().st_size for p in files),
                fixture_directories=len(directories),models=False,capture=False,GUI=False,
                child_processes=0,source_audio_samples=0,whole_run_integrated=False)
    writer.json('STORAGE_CLOSURE.json',result)
    return result
