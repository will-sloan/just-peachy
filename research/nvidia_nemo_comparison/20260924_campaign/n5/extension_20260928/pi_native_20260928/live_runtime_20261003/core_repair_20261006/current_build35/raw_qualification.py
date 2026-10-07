"""Five-second source-only native raw qualification; README_RAW_CAPTURE.md."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import threading
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--binding-sha256', required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--admission-sha256', required=True)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--unit-ownership', type=Path, required=True)
    parser.add_argument('--owner-directory', type=Path, required=True)
    args = parser.parse_args()
    # The outside native scope gate registers/pins before importing this file;
    # bootstrap records this source-only owner again before any model/source read.
    from worker import bootstrap, file_size_plan
    owner = bootstrap(args.owner_directory)
    from runtime_support import digest, strict, publish, verify_owned_unit, kill_owned_unit, owner_status
    from storage import SessionStore, StoragePolicy
    import installed_source
    import raw_capture
    import source_batch
    from audio_journal import DiskAudioJournal
    from profiles import SessionPolicy
    if digest(args.binding) != args.binding_sha256 or digest(args.admission) != args.admission_sha256:
        raise ValueError('Qualification binding/admission hash changed')
    admitted = strict(args.admission.read_bytes())
    expected = dict(status='RAW_NATIVE_QUALIFICATION_ADMITTED', duration_seconds=5,
        unit=args.unit, binding_sha256=args.binding_sha256,
        installed_source_sha256=digest(Path(installed_source.__file__)),
        raw_capture_sha256=digest(Path(raw_capture.__file__)),
        source_batch_sha256=digest(Path(source_batch.__file__)))
    if any(admitted.get(key) != value for key, value in expected.items()):
        raise ValueError('Fresh exact source-only qualification admission required')
    unit_identity = verify_owned_unit(args.unit, args.unit_ownership)
    if admitted.get('invocation_id') != unit_identity['invocation_id']:
        raise ValueError('Qualification admission belongs to another unit invocation')
    binding = strict(args.binding.read_bytes())
    binding.update(raw_qualification=True, consent=True)
    evidence = dict(qualified=False, qualification_run=True, evidence=str(args.admission),
                    evidence_sha256=args.admission_sha256)
    policy = SessionPolicy(maximum_session_seconds=5, model_load_seconds=30,
                           max_drain_seconds=30, cleanup_seconds=30)
    disk_policy = StoragePolicy(**binding.get('storage_policy', {}))
    spec = dict(duration_seconds=5, sample_rate=16000, mode='raw_processed', raw_qualification=True,
                metadata_reserve_bytes=8*1024**2, metadata_split='text3_sqlite1_v1',
                raw=dict(sample_rate=16000, channels=4, sample_width_bytes=4,
                         encoding='PCM_S32LE', qualification=evidence))
    store_root = args.owner_directory/'recordings'
    store_root.mkdir()
    plan = file_size_plan(store_root, spec['metadata_reserve_bytes'], disk_policy)
    import resource
    _, hard = resource.getrlimit(resource.RLIMIT_FSIZE)
    if plan['file_limit_bytes'] > hard:
        raise ValueError('Qualification allocation exceeds finite inherited file bound')
    resource.setrlimit(resource.RLIMIT_FSIZE, (plan['file_limit_bytes'], plan['file_limit_bytes']))
    publish(args.owner_directory/'FILE_ALLOCATION.json', plan)
    store = SessionStore(store_root, disk_policy)
    spool = store.begin(spec)
    processed_input = hashlib.sha256()
    input_samples = 0
    def processed_observer(start, samples):
        nonlocal input_samples
        if start != input_samples:
            raise ValueError('Qualification processed observer cursor changed')
        processed_input.update(samples.astype('<f4', copy=False).tobytes())
        input_samples += len(samples)
    source = None
    done = threading.Event()
    def watchdog():
        if not done.wait(policy.total_deadline_seconds):
            publish(args.owner_directory/'WATCHDOG_REQUEST.json', dict(reason='raw qualification deadline', closure_claimed=False))
            kill_owned_unit(args.unit, args.unit_ownership)
    watcher = threading.Thread(target=watchdog, name='raw-qualification-watchdog', daemon=True)
    watcher.start()
    failure = None
    proof = dict(expected, status='RAW_NATIVE_QUALIFICATION_FAILED', native_executed=False,
                 owner=owner, session_id=spool.session_id, unit_invocation=unit_identity['invocation_id'])
    try:
        (spool.directory/'work').mkdir()
        journal = DiskAudioJournal(spool, policy=spec, observer=processed_observer,
            fault_receipt=lambda row: store.write_event(spool.session_id, 'journal_fault', row))
        source = installed_source.create_source(journal, binding, lambda *args: None, None, policy, spool)
        proof['native_executed'] = True
        source.start()
        while not source.wait(.1):
            pass  # Independent finite watchdog and service RuntimeMaxSec are armed.
        source.stop()
        if source.error or journal.fatal_error:
            raise RuntimeError(source.error or journal.fatal_error)
        physical = strict((spool.directory/'work/source/SOURCE_CLOSE.json').read_bytes())
        raw = physical.get('raw_capture') or {}
        stop = physical.get('receipt') or {}
        restored = stop.get('route_restoration') or {}
        route_ok = bool(restored) and all(value in ('RESTORED', 'ALREADY_RESTORED') for value in restored.values()) and not stop.get('errors')
        exact_owner = owner_status(physical['owner'])
        readback = spool.raw_receipt()
        expected_samples = 5*16000
        checks = dict(source_clock_checked=(source.sent == source.raw_sent == spool.processed_samples == spool.raw_samples == expected_samples
                                           and raw.get('accepted_transport_frames') == 3*expected_samples
                                           and raw.get('transport_partition_checked') is True
                                           and raw.get('capture_boundary_sample') == expected_samples
                                           and raw.get('capture_boundary_reason') == 'allocated_duration'
                                           and raw.get('shared_sample_clock') is True),
            raw_readback_checked=(readback['sha256'] == raw.get('sha256') and readback['bytes'] == expected_samples*16),
            route_restored=route_ok, stream_closed=physical.get('stream_closed') is True,
            lease_released=physical.get('lease_released') is True, source_owner_closed=exact_owner['closed'])
        if not all(checks.values()) or raw.get('channel_order') != ['MIC0','MIC1','MIC2','MIC3']:
            raise RuntimeError('Native raw qualification check failed: '+json.dumps(checks, sort_keys=True))
        spool.stop(expected_samples)
        processed_readback = hashlib.sha256()
        read_samples = 0
        for start, payload in store.iter_processed(spool.session_id):
            if start != read_samples:
                raise RuntimeError('Qualification processed readback timeline gap')
            processed_readback.update(payload)
            read_samples += len(payload)//4
        checks['processed_readback_checked'] = (input_samples == read_samples == expected_samples
            and processed_readback.digest() == processed_input.digest())
        if not checks['processed_readback_checked']:
            raise RuntimeError('Independent processed spool readback differs')
        for path in (spool.directory/'work').rglob('*'):
            if path.is_file():
                store.register_artifact(spool.session_id, path.relative_to(spool.directory).as_posix(), role='raw_qualification')
        spool.keep(include_raw=True)
        proof.update(checks, status='RAW_NATIVE_QUALIFICATION_PASSED', raw_channels=4,
            raw_samples=spool.raw_samples, processed_samples=spool.processed_samples,
            raw_bytes=readback['bytes'], raw_sha256=readback['sha256'], physical=physical,
            processed_sha256=processed_readback.hexdigest(), processed_bytes=read_samples*4,
            qualification_audio_remains_experimental=True)
    except BaseException as error:
        failure = repr(error)
        proof['failure'] = failure
        try:
            if source is not None:
                source.stop()
        except BaseException as cleanup:
            proof['cleanup_failure'] = repr(cleanup)
        try:
            spool.fail(failure)
        except BaseException as storage_error:
            proof['storage_failure'] = repr(storage_error)
    finally:
        done.set()
        watcher.join(2)
        store.close()
        publish(args.owner_directory/'RAW_QUALIFICATION.json', proof)
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
