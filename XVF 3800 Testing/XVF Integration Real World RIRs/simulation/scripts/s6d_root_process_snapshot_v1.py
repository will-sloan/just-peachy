"""Read one root control-process snapshot; see README_S6D_ROOT_PROCESS_SNAPSHOT_V1.md."""
import argparse, importlib.util, json
from pathlib import Path

SIM=Path(__file__).resolve().parents[1]
R=SIM/'reports/S6D/20260913T195357Z'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    source=SIM/'scripts/s6d_closed_telemetry_restore_v5.py'
    import hashlib
    if hashlib.sha256(source.read_bytes()).hexdigest()!='af89c6df108f6b0deaa780736c90cd6311ba95a9a1b566e45fc54da2fe120017':
        raise ValueError('Unchanged accepted process scanner required')
    spec=importlib.util.spec_from_file_location('root_snapshot_scanner_v5',source)
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    metadata=h.bind(R/'qa_recovery_preparation_v1/INACTIVE_REVIEW_METADATA.json')
    h.need(metadata['sha256']=='0785aaf3d37edbbbc263eb9189da0f510a984bbb7295276e02c17fdfee81244c','Exact new QA identity metadata')
    known=h.verify(metadata)['known_process_identities']
    h.need(known==[dict(role='capture_owner',pid=639888,creation_time=1789415369.4817412),dict(role='supervisor',pid=638164,creation_time=1789415331.064818),dict(role='native_telemetry',pid=602832,creation_time=1789415391.2722838)],'Exact three original owner instances')
    out=a.output.resolve();h.need(out.is_relative_to(R) and not out.exists(),'Fresh contained output required')
    services=h.WindowsServices()
    # These are only process APIs. Never acquire, initialize_control, identify, restore, or query ports.
    snapshot=services.census();decision=h.scan_decision(snapshot,known,services.identity)
    snapshot.update(no_matching_task_control_processes=True,matching_processes=[],query_errors=[],decision=decision,root_reader_identity=services.identity,known_identity_metadata=metadata,source=h.bind(__file__),readme=h.bind(Path(__file__).with_name('README_S6D_ROOT_PROCESS_SNAPSHOT_V1.md')),scanner_source=h.bind(source),hardware_or_control_calls=0)
    out.parent.mkdir(parents=True,exist_ok=True);h.save(out,snapshot)
    print(json.dumps(dict(status=decision['status'],snapshot=h.bind(out),processes_scanned=decision['processes_scanned'],hardware_or_control_calls=0)))

if __name__=='__main__':main()
