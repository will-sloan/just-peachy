"""One bounded, no-playback restoration recovery. See README_S45_RESTORE_RECOVERY.md."""
import argparse
from s45_common import *


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True)
    args = parser.parse_args()
    folder = (HARDWARE / args.batch).resolve()
    assert folder.parent == HARDWARE.resolve(), 'Batch must be a direct hardware child'
    assert read(REPORT / 'supervisor_postpackage_receipt.json')['status'] == 'SUPERVISOR_CLOSED'
    for name in ['owned_process.json', 'supervisor_process.json']:
        assert read(REPORT / name).get('pid') is None, 'An owned child is still recorded'
    assert not (REPORT / 'UNRESOLVED_SUPERVISOR_CHILD.json').exists()
    assert read(folder / 'restoration.json')['status'] == 'FAIL'
    assert not (folder / 'restoration_recovery.json').exists(), 'Preserve any existing recovery'
    assert not (folder / 'recovery_driver_receipt.json').exists(), 'No blind recovery rerun'
    check_storage()
    import s4_restore
    receipt = {'status': 'STARTED', 'started_utc': now(), 'pid': os.getpid(),
               'batch': args.batch, 'playback_performed': False,
               'wrapper': bind(Path(__file__)), 'existing_restorer': bind(Path(s4_restore.__file__)),
               'original_failure': bind(folder / 'restoration.json'),
               'initial_state': bind(folder / 'initial_state.json'),
               'scope': 'Existing S4 exact getter restorer, unchanged; S4.5 payload root only. No scene recipe, audio, model or source changes.'}
    save(folder / 'recovery_driver_receipt.json', receipt)
    try:
        # The existing function uses REPORT/hardware/batch. Rebind its output root
        # to this run's payload; leave historical S4 evidence and source unchanged.
        s4_restore.REPORT = PAYLOAD
        s4_restore.recover(args.batch)
        from s4_hardware import verified_restoration
        verified_restoration(folder / 'restoration.json')
        receipt['status'] = 'PASS'
    except BaseException as exc:
        receipt.update(status='FAIL', error=repr(exc))
        raise
    finally:
        receipt['ended_utc'] = now()
        receipt['recovery'] = bind(folder / 'restoration_recovery.json') if (folder / 'restoration_recovery.json').exists() else None
        save(folder / 'recovery_driver_receipt.json', receipt)


if __name__ == '__main__':
    main()
