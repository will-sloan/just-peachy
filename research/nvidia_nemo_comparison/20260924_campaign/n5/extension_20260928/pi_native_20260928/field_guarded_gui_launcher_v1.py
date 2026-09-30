"""Exact-state installed entry with continuous ownership. README_FIELD_GUI_LEASE_V1.md."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import sys
import threading
import time
import traceback
import field_dependencies_v2 as pins
import field_candidate_transaction_v1 as transactions


def write(path, value):
    raw = json.dumps(value, indent=2, allow_nan=False).encode('utf-8')
    if len(raw) > 128*1024:
        raise ValueError('Launcher receipt size bound')
    with Path(path).open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())


def ticks():
    return int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])


def execute(spec_path):
    sys.dont_write_bytecode = True
    threading.stack_size(1024**2)
    spec = pins.read(spec_path)
    root = Path(spec_path).resolve().parent
    case = spec['case']
    if not case or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in case):
        raise ValueError('Launcher case identifier')
    owner = dict(pid=os.getpid(),start_ticks=ticks(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    write(root/(case+'-OWNER.json'), owner)
    result = dict(status='FAILED_PRESERVED',entered=False,models_loaded=False,capture_opened=False,
                  case=case,borrowers=0,borrowers_closed=0)
    begun = time.monotonic()
    try:
        a = pins.read(root/'ADMISSION.json')
        assert pins.sha(root/'ADMISSION.json') == spec['run_admission_sha256']
        assert owner['boot_id'] == a['boot_id']
        assert time.time() < spec['expires_unix'] <= time.time()+120
        authority=pins.read(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')
        assert pins.sha(root/'AUTONOMOUS_QUIET_AUTHORIZATION_V1.json')==a['authority_sha256']
        assert authority['pi_gui_testing_authorized'] and authority['questions_requested'] is False
        assert spec['authority_sha256']==a['authority_sha256']
        assert not a['capture'] and spec['command'] == 'gui'
        for row in a['files']:
            assert pins.sha(row['path']) == row['sha256']
        assert sorted(os.sched_getaffinity(0)) == [2,3]
        assert resource.getrlimit(resource.RLIMIT_AS) == (768*1024**2,)*2
        assert resource.getrlimit(resource.RLIMIT_STACK) == (1024**2,)*2
        assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip() == 'closed'
        bootstrap = Path(a['installed_release'])
        for rel, expected in a['installed_files'].items():
            assert pins.sha(bootstrap/rel) == expected
        sys.path.insert(0,str(bootstrap))
        from release_tools import release as release_tools
        from release_tools.runtime_lock import RuntimeLock
        data = Path(spec['data_root']).resolve()
        candidate = Path(spec['candidate_root']).resolve()
        assert data == root/'data' and candidate == root/'deployment'
        # One runtime owner survives dependency preflight, borrowed ApplicationLock
        # validation, the installed main(), and its queue/thread shutdown.
        with contextlib.ExitStack() as stack:
            lease = RuntimeLock(data,'guarded_installed_entry')
            stack.callback(lease.close)
            lock_raw = (data/'runtime.lock').read_bytes()
            lock_record = json.loads(lock_raw)
            assert lock_record['pid'] == os.getpid() and lock_record['token'] == lease.token
            state, state_sha = transactions.inspect(candidate)
            if state_sha != spec['state_sha256']:
                raise ValueError('Launcher candidate state changed')
            pointer = state['current']
            d, manifest, checked = pins.check_descriptor(pointer['descriptor'],pointer['descriptor_sha256'],release_tools)
            if d['candidate_root'] != str(candidate) or d['data_root'] != str(data):
                raise ValueError('Launcher descriptor data binding')
            if set(spec['config_sha256']) != {'DATA_SCHEMA.json','live_config.json','n2_runtime.json'}:
                raise ValueError('Launcher required config set')
            for name, expected in spec['config_sha256'].items():
                path = data/name
                if not path.is_file():
                    raise ValueError('Missing launcher configuration: '+name)
                if pins.sha(path) != expected:
                    raise ValueError('Launcher configuration changed: '+name)
            selected = Path(d['release'])
            entry_path = selected/'native/field_entry_v5.py'
            if pins.sha(entry_path) != spec['entry_sha256']:
                raise ValueError('Installed entry hash changed')
            # The bootstrapped lock/release modules must also be exact selected bytes.
            import release_tools as namespace
            assert namespace.__spec__.origin is None
            assert {Path(x).resolve() for x in namespace.__path__} == {(bootstrap/'release_tools').resolve()}
            assert not (selected/'release_tools/__init__.py').exists() and not (bootstrap/'release_tools/__init__.py').exists()
            for rel in ['release_tools/release.py','release_tools/runtime_lock.py']:
                assert pins.sha(selected/rel) == pins.sha(bootstrap/rel)
            assert Path(release_tools.__file__).resolve() == (bootstrap/'release_tools/release.py').resolve()
            assert Path(sys.modules['release_tools.runtime_lock'].__file__).resolve() == (bootstrap/'release_tools/runtime_lock.py').resolve()
            result.update(version=d['version'],state_sha256=state_sha,entry_sha256=pins.sha(entry_path),
                          dependency_entries=checked['entries'],lease_token=lease.token,
                          lease_owner_pid=os.getpid(),configuration_sha256=spec['config_sha256'])
            def barrier(phase):
                assert (data/'runtime.lock').read_bytes() == lock_raw
                if spec.get('test_barriers'):
                    write(root/(case+'-'+phase+'.json'),dict(phase=phase,owner=owner,lease_token=lease.token,
                          state_sha256=state_sha,borrowers=result['borrowers'],borrowers_closed=result['borrowers_closed']))
                    deadline = time.monotonic()+8
                    gate = root/(case+'-'+phase+'-continue.json')
                    while not gate.exists():
                        if time.monotonic() > deadline:
                            raise TimeoutError('Bounded launcher test barrier')
                        time.sleep(.01)
                    assert pins.read(gate) == dict(continue_phase=phase,owner_pid=os.getpid())
            barrier('before-entry')
            sys.path[:0] = [str(selected),str(selected/'vendor'),str(selected/'native')]
            module_spec = importlib.util.spec_from_file_location('bound_installed_entry',entry_path)
            entry = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(entry)
            paths = None
            original_lock = None
            if spec['command'] == 'gui':
                from app import paths
                assert paths.ROOT.resolve() == selected.resolve()
                original_lock = paths.RuntimeLock
                class BorrowedLease:
                    def __init__(self, requested, purpose):
                        if Path(requested).resolve() != data or purpose != 'application' or result['borrowers']:
                            raise RuntimeError('Unexpected application lease borrower')
                        assert (data/'runtime.lock').read_bytes() == lock_raw
                        self.token = lease.token
                        self.closed = False
                        result['borrowers'] += 1
                    def close(self):
                        if not self.closed:
                            self.closed = True
                            result['borrowers_closed'] += 1
                        # Outer owner releases only after installed main joins threads.
                paths.RuntimeLock = BorrowedLease
            from field_gui_observer_v1 import IdleGUIObserver
            observer = IdleGUIObserver(root,case,owner,lease.token,state_sha,write)
            old_argv = sys.argv
            before_threads = {t.ident for t in threading.enumerate()}
            captured = io.StringIO()
            try:
                sys.argv = [str(entry_path),'gui','--data-root',str(data),'--launch-admission',str(spec_path)]
                result['entered'] = True
                with observer, contextlib.redirect_stdout(captured):
                    code = entry.main()
                if code != 0:
                    raise RuntimeError('Installed entry returned '+str(code))
            finally:
                sys.argv = old_argv
                if paths is not None:
                    paths.RuntimeLock = original_lock
            raw = captured.getvalue()
            if len(raw.encode('utf-8')) > 128*1024:
                raise ValueError('Installed output bound')
            assert not raw.strip()
            output = observer.finish()
            assert not [t for t in threading.enumerate() if t.ident not in before_threads]
            assert result['borrowers'] == result['borrowers_closed'] == 1
            assert (data/'runtime.lock').read_bytes() == lock_raw
            assert transactions.inspect(candidate)[1] == state_sha
            assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip() == 'closed'
            result.update(entry_output=output,threads_closed=True,lease_continuous=True)
            barrier('after-entry')
        assert not (data/'runtime.lock').exists()
        result.update(status='PASS_GUARDED_INSTALLED_GUI_IDLE_ONLY',lease_released=True)
    except Exception as exc:
        result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()[-16000:])
    result.update(elapsed_seconds=time.monotonic()-begun,current_status=Path('/proc/self/status').read_text(),
                  affinity=sorted(os.sched_getaffinity(0)),address_space=list(resource.getrlimit(resource.RLIMIT_AS)),
                  stack=list(resource.getrlimit(resource.RLIMIT_STACK)))
    write(root/(case+'-RESULT.json'),result)
    print(json.dumps({k:result.get(k) for k in ['status','case','entered','error']}))
    return int(result['status']!='PASS_GUARDED_INSTALLED_GUI_IDLE_ONLY')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--launch',required=True,type=Path)
    raise SystemExit(execute(parser.parse_args().launch))
