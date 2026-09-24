"""Resume the unchanged native numerical contract with IO-only retries; see README_IO.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import io_utils
import run_fixed_screen as original


def binding(path):
    path=Path(path).resolve(strict=True)
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    return dict(path=str(path),sha256=digest,bytes=path.stat().st_size)


def main():
    import psutil
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    output=args.output.resolve(strict=True)
    if not output.is_relative_to(original.LOCAL.resolve()):
        raise ValueError('Resume only an existing private local/n2 output')
    admission=original.load(output/'ADMISSION.json')
    contract=admission['contract']
    if original.stable_hash(contract)!=admission['contract_sha256']:
        raise ValueError('Numerical admission contract integrity failed')
    source=binding(original.__file__)
    if source['sha256']!=contract['frozen_runner']['sha256']:
        raise ValueError('Original runner differs from the frozen numerical runner')
    for item in (contract['frozen_runner'],contract['frozen_adapter'],contract['python_executable']):
        original.verify(item)
    if binding(sys.executable)['sha256']!=contract['python_executable']['sha256']:
        raise ValueError('Resume must use the same admitted interpreter')
    owner=original.load(output/'RUNNER_OWNER.json')
    for identity in (owner,owner.get('worker')):
        if not identity:continue
        try:
            process=psutil.Process(identity['pid'])
            if abs(process.create_time()-identity['create_time'])<.01 and process.is_running():
                raise RuntimeError('Previous native coordinator/worker is still live; no resume was started')
        except psutil.NoSuchProcess:pass
    folder=output/'io_resumes'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    prior=[]
    for path in [output/'PROGRESS.json',output/'RESULT_INDEX.json',output/'RUNNER_OWNER.json',
                 *sorted(output.glob('COORDINATOR_ERROR_*.json'))]:
        if not path.exists():continue
        snapshot=folder/path.name
        snapshot.write_bytes(path.read_bytes())
        prior.append(dict(original=binding(path),preserved_snapshot=binding(snapshot)))
    checkpoint_statuses={}
    for path in output.glob('cells/*/*/CHECKPOINT.json'):
        checkpoint=original.load(path)
        checkpoint_statuses[checkpoint['status']]=checkpoint_statuses.get(checkpoint['status'],0)+1
    amendment=dict(schema='n2-native-io-resume-amendment-v1',io_version=io_utils.IO_VERSION,
        reason='Transient Windows WinError5 while replacing PROGRESS.json; no numerical failures or changed model inputs',
        numerical_contract_sha256=admission['contract_sha256'],admission=binding(output/'ADMISSION.json'),
        original_runner=source,frozen_runner=contract['frozen_runner'],frozen_adapter=contract['frozen_adapter'],
        helper=binding(io_utils.__file__),wrapper=binding(__file__),prior_state=prior,
        prior_checkpoint_statuses=checkpoint_statuses,changed_scope='Parent atomic JSON replacement only',
        numerical_worker='Original frozen runner unchanged, including its original IO behavior',
        retries=dict(winerror=[5,32,33],maximum_seconds=2.0),created_utc=datetime.now(timezone.utc).isoformat())
    # Exclusive creation preserves the amendment before original main writes
    # ownership/progress. Original main retains its existing OS writer lock.
    with (folder/'IO_RESUME_AMENDMENT.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(amendment,stream,indent=2);stream.write('\n');stream.flush();original.os.fsync(stream.fileno())
    original.atomic=io_utils.atomic
    selected=SimpleNamespace(output=output,manifest=Path(contract['manifest']['path']),
        build_receipt=Path(contract['native_build_receipt']['path']),profiles=list(contract['profiles']),
        prepare_only=args.prepare_only,limit=0,retry_failed=False,
        timeout_sec=contract['cell_timeout_sec'],load_timeout_sec=contract['model_load_timeout_sec'],
        reserve_gib=contract['reserve_gib'],cpu=contract['cpu_affinity'],
        device=contract['native_device']['kind'],gpu_index=max(0,contract['gpu_device']),gpu=contract['gpu_device'])
    print(json.dumps(dict(status='IO_ONLY_RESUME_ADMITTED',amendment=str(folder/'IO_RESUME_AMENDMENT.json'),
                          prior_checkpoint_statuses=checkpoint_statuses)),flush=True)
    try:
        code=original.main(selected)
    except BaseException as exc:
        io_utils.atomic(folder/'IO_RESUME_RESULT.json',dict(status='FAILED',error=repr(exc)))
        raise
    io_utils.atomic(folder/'IO_RESUME_RESULT.json',dict(status='RETURNED',exit_code=code,
        final_index=binding(output/'RESULT_INDEX.json'),final_progress=binding(output/'PROGRESS.json')))
    return code


if __name__=='__main__':raise SystemExit(main())
