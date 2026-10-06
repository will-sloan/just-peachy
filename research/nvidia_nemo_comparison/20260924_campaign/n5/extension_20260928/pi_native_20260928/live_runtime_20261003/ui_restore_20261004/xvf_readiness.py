"""Fault-bound XVF readiness before a new live Start. README_XVF_READINESS.md."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

RESERVE_BYTES = 16 * 1024**2
TOOL = '/home/peachyprototype/JustPeachy/tools/native_xvf_usb/bin/xvf_host'
TOOL_SHA256 = '8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982'
TOOL_BYTES = 1773304


def qualifying_fault(value):
    """Retain the documented exact closed-source AEC255 recovery trigger."""
    commands = value.get('receipt', {}).get('commands', [])
    return bool(value.get('kind') == 'CLOSED' and value.get('stream_closed') is True and
        value.get('lease_released') is True and type(value.get('sent_samples')) is int and
        value['sent_samples'] == 0 and type(value.get('processed_acknowledgements')) is int and
        value['processed_acknowledgements'] == 0 and value.get('integrity', {}).get('route') is None and
        value.get('integrity', {}).get('restoration_ok') is True and
        value.get('receipt', {}).get('metadata', {}).get('stream_start_return_perf_counter_ns', 0) > 0 and
        value.get('status', {}).get('converted_samples') == 0 and len(commands) == 3 and
        [row.get('command') for row in commands] == ['VERSION', 'BLD_MSG', 'AEC_MIC_ARRAY_TYPE'] and
        [row.get('exit_code') for row in commands] == [0, 0, 255] and
        commands[0].get('stdout', '').split() == ['VERSION', '3', '2', '1'] and
        'intdev-lr48-lin-i2c' in commands[1].get('stdout', '') and
        'Resource could not respond' in commands[2].get('stderr', ''))


def qualifying_unsent_manual_failure(records, binding, owner_probe):
    """Pure acknowledgment of the exact completed old unsent manual-lifetime bug."""
    expected = {
        'CHILD_LAUNCH.json': (188, '705b3b2aa93e892f9884039b23d7fca28e692f300f29440335e7461bcdd156ac'),
        'HELPER.stderr': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
        'HELPER.stdout': (0, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
        'HOST_CLOSURE.json': (181, 'cae806bc3cfd9ce0bbd4d509357dbb23dd37d848961dff25ecc825c3876b39e0'),
        'RECOVERY.json': (487, '265c1b463f7309d955b6f3e2013e4a71b41f373770cdf4877abd9e14468a0fed'),
        'REGISTERED_OWNER.json': (81, 'b4d31f526946a805bb4817c28fb348be8e1121bbee997d4e94f3327dbdcc4b61'),
        'REQUEST.json': (1375, 'e2bd6f9ba222d605a6608c1fc301a95a7ad8f49cd3709ffc27c5e29df8292576')}
    if (type(records) is not dict or set(records) != set(expected) or type(binding) is not dict
            or set(binding) != {'fault_sha256','fault_path','closed_path','closed_sha256','boot_id',
                                'module_sha256','helper_sha256'}):
        return False
    for name, (size, pin) in expected.items():
        raw = records[name]
        if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != pin:
            return False
    def strict(raw):
        def pairs(items):
            value={}
            for key,item in items:
                if key in value:raise ValueError('Duplicate preserved recovery field')
                value[key]=item
            return value
        return json.loads(raw,object_pairs_hook=pairs,
            parse_constant=lambda item:(_ for _ in ()).throw(ValueError(item)))
    request=strict(records['REQUEST.json']);child=strict(records['CHILD_LAUNCH.json'])
    host=strict(records['HOST_CLOSURE.json']);result=strict(records['RECOVERY.json'])
    helper=strict(records['REGISTERED_OWNER.json'])
    if any(request.get(key) != binding[key] for key in
           ('fault_sha256','fault_path','closed_path','closed_sha256','module_sha256','helper_sha256')):
        return False
    if (binding['module_sha256'] != '593587891bbdba33619f60e1aafef7888c5b247122e59505cd44917fe12326bd'
            or binding['helper_sha256'] != '8947bf981ce46aebd4b9623a5f621a1d55e4f1f024df91cfd1ddc34c29ebe659'
            or binding['fault_sha256'] != '01beda380170956338c66b1489689e7c725cb0f74a6014b6793a96eb389f133a'
            or type(host.get('natural_returncode')) is not int or host['natural_returncode'] != 1
            or host.get('timeout') is not False or host.get('direct_child_reaped') is not True
            or host.get('exact_owner_gone') is not True or host.get('owner') != helper
            or child.get('owner') != helper or child.get('manager_owner') != request.get('manager_owner')
            or result.get('owner') != helper or result.get('fault_sha256') != binding['fault_sha256']
            or result.get('status') != 'FAILED_PRESERVED' or result.get('commands') != []
            or result.get('error') != {'type':'TypeError', 'message':"unsupported operand type(s) for -: 'NoneType' and 'float'"}
            or any(result.get(key) is not False for key in ('audio_qualified','capture_opened','models_loaded','readiness_verified'))
            or result.get('leases_released') is not True
            or any(type(result.get(key)) is not int or result[key] != 0 for key in ('maintenance_sends','maintenance_sends_attempted'))):
        return False
    for owner in (helper, request['manager_owner'], request['worker_owner'], request['source_owner']):
        if (type(owner) is not dict or set(owner) != {'pid','start_ticks','boot_id'}
                or type(owner['pid']) is not int or owner['pid'] <= 0
                or type(owner['start_ticks']) is not int or owner['start_ticks'] <= 0
                or owner['boot_id'] != binding['boot_id']):
            return False
        observed=owner_probe(owner)
        if type(observed) is not dict or observed.get('closed') is not True:return False
    return True


def preserved_unsent_manual_failure(manager, closure):
    """Read unchanged seven-member evidence; never reopen or retry its old helper."""
    from runtime_support import strict, current_owner
    import stat
    if os.name != 'posix':return False
    pointer=strict((manager.data_root/'CURRENT_LAUNCH.json').read_bytes())
    identifier=pointer.get('launch_id')
    if type(identifier) is not str or re.fullmatch('[0-9a-f]{32}',identifier) is None:return False
    origin=manager.launches/identifier
    session=strict((origin/'worker/SESSION.json').read_bytes())['session_id']
    fault=manager.store._artifact_path(session,'work/source/SOURCE_CLOSE.json')
    closed=origin/'HOST_CLOSURE.json'
    def read(path,maximum):
        before=path.lstat()
        if path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum:
            raise ValueError('Stable bounded real unsent recovery input required')
        raw=path.read_bytes();after=path.lstat()
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('Unsent recovery input changed')
        return raw
    fault_raw=read(fault,65536);closed_raw=read(closed,262144)
    if strict(closed_raw)!=closure or strict(fault_raw)!=closure.get('nested_source',{}).get('physical_receipt'):
        return False
    fault_sha=hashlib.sha256(fault_raw).hexdigest()
    if fault_sha!='01beda380170956338c66b1489689e7c725cb0f74a6014b6793a96eb389f133a':return False
    out=manager.data_root/'recovery'/fault_sha
    if not out.exists():return False
    before=out.lstat()
    if out.is_symlink() or not stat.S_ISDIR(before.st_mode) or out.resolve(strict=True)!=out:return False
    names=sorted(path.name for path in out.iterdir())
    if names!=['CHILD_LAUNCH.json','HELPER.stderr','HELPER.stdout','HOST_CLOSURE.json',
               'RECOVERY.json','REGISTERED_OWNER.json','REQUEST.json']:return False
    records={name:read(out/name,16384) for name in names}
    after=out.lstat()
    if names!=sorted(path.name for path in out.iterdir()) or (before.st_dev,before.st_ino,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_mtime_ns):
        return False
    # Verify the actual retained old source files, not only self-declared pins.
    old=Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-26')
    if hashlib.sha256(read(old/'PACKAGE_MANIFEST.json',262144)).hexdigest()!='f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0':
        return False
    binding=dict(fault_sha256=fault_sha,fault_path=str(fault),closed_path=str(closed),
        closed_sha256=hashlib.sha256(closed_raw).hexdigest(),boot_id=current_owner()['boot_id'],
        module_sha256=hashlib.sha256(read(old/'xvf_readiness.py',65536)).hexdigest(),
        helper_sha256=hashlib.sha256(read(old/'xvf_readiness_helper.py',65536)).hexdigest())
    return qualifying_unsent_manual_failure(records,binding,manager.owner_probe)


def recovery_sequence(command, save, sleep, fault_sha):
    """Pure retained sequence; one literal TEST_CORE_BURN 0, never a retry."""
    def firmware():
        version = command('VERSION'); build = command('BLD_MSG')
        if (version['timeout'] or build['timeout'] or version['exit_code'] != 0 or build['exit_code'] != 0
            or version['stdout'].split() != ['VERSION', '3', '2', '1'] or 'intdev-lr48-lin-i2c' not in build['stdout']):
            raise ValueError('Expected retained firmware readback unavailable')
        return dict(version=version['stdout'], build=build['stdout'])
    before = firmware(); probe = command('AEC_MIC_ARRAY_TYPE')
    if not probe['timeout'] and probe['exit_code'] == 0:
        return dict(status='NO_SEND_CURRENT_AEC_READABLE', before=before, current_aec=probe, maintenance_sends=0)
    if probe['timeout'] or probe['exit_code'] != 255 or 'Resource could not respond' not in probe['stderr']:
        raise ValueError('Fresh exact AEC255 required; no maintenance command sent')
    save('RESTART_INTENT.json', dict(fault_sha256=fault_sha, maximum_sends=1,
        command=['TEST_CORE_BURN', '0'], before=before, current_aec=probe, volatile_state_restorable=False))
    reply = command('TEST_CORE_BURN', ('0',))
    if reply['timeout'] or reply['exit_code'] != 0:
        raise RuntimeError('Maintenance send failed or uncertain; never retry this fault')
    sleep(2)
    after = firmware()
    if after != before:
        raise ValueError('Post-maintenance firmware differs')
    post = command('AEC_MIC_ARRAY_TYPE')
    if post['timeout']:
        raise RuntimeError('Post-maintenance AEC read timed out; no retry')
    return dict(status='SINGLE_SEND_POST_READBACK', before=before, after=after, current_aec=probe,
        maintenance_reply=reply, post_aec=post, post_aec_readable=post['exit_code'] == 0,
        maintenance_sends=1, audio_qualified=False, volatile_state_restored=False)


def recover_previous_source(manager):
    """Repair only an exact previous closed AEC255 fault before the next Start.

    Call after ordinary selection authorization and service-room checks. This
    function starts no microphone/model and never retries an uncertain intent.
    """
    from runtime_support import strict, publish, digest, current_owner, owner_status
    if manager.process is not None or manager.closed or manager.export_task is not None:
        raise RuntimeError('Close the previous worker/export before microphone readiness repair')
    pointer = manager.data_root/'CURRENT_LAUNCH.json'
    if not pointer.exists():
        return None
    identifier = strict(pointer.read_bytes()).get('launch_id')
    if not isinstance(identifier, str) or re.fullmatch('[0-9a-f]{32}', identifier) is None:
        raise RuntimeError('Previous launch identifier is invalid; evidence preserved')
    closed_path = manager.launches/identifier/'HOST_CLOSURE.json'
    if not closed_path.exists():
        return None  # The ordinary Manager previous-launch guard remains authoritative.
    raw = closed_path.read_bytes()
    if len(raw) > 262144:
        raise RuntimeError('Previous source closure exceeds its receipt bound')
    closed = strict(raw)
    physical = closed.get('nested_source', {}).get('physical_receipt')
    if not isinstance(physical, dict) or not qualifying_fault(physical):
        return None
    if (closed.get('direct_child_reaped') is not True or closed.get('stdout_reader_joined') is not True
        or closed.get('nested_source', {}).get('closed') is not True or closed.get('receipt_errors')):
        raise RuntimeError('Microphone fault lacks complete worker/source closure; evidence preserved')
    worker_owner = closed.get('registered_owner'); source_owner = physical.get('owner')
    if os.name == 'posix' and isinstance(source_owner, dict) and source_owner.get('boot_id') != current_owner()['boot_id']:
        return None  # A new boot is not a request to reset a historical DSP fault.
    if not all(owner_status(owner).get('closed') is True for owner in (worker_owner, source_owner)):
        raise RuntimeError('Previous worker/source is live or unverifiable; microphone repair refused')
    session = strict((manager.launches/identifier/'worker/SESSION.json').read_bytes())['session_id']
    fault_path = manager.store._artifact_path(session, 'work/source/SOURCE_CLOSE.json')
    fault_raw = fault_path.read_bytes()
    if len(fault_raw) > 65536 or strict(fault_raw) != physical:
        raise RuntimeError('Original source failure differs from its closed worker receipt')
    fault_sha = hashlib.sha256(fault_raw).hexdigest()
    recovery_root = manager.data_root/'recovery'
    out = recovery_root/fault_sha
    if out.exists():
        host = out/'HOST_CLOSURE.json'
        result_path = out/'RECOVERY.json'
        if host.exists() and result_path.exists():
            prior = strict(host.read_bytes()); result = strict(result_path.read_bytes())
            if (type(prior.get('natural_returncode')) is int and prior['natural_returncode'] == 0 and
                prior.get('timeout') is False and prior.get('direct_child_reaped') is True and
                prior.get('exact_owner_gone') is True and owner_status(prior.get('owner')).get('closed') is True and
                prior.get('owner', {}).get('boot_id') == source_owner.get('boot_id') and
                result.get('owner') == prior.get('owner') and
                result.get('fault_sha256') == fault_sha and result.get('readiness_verified') is True and not result.get('error')):
                return dict(status='PREVIOUS_READINESS_REUSED', fault_sha256=fault_sha, output_root=str(out))
        raise RuntimeError('The prior microphone repair is failed/incomplete; its one-use evidence is preserved. '
                           'No automatic retry will be sent. See Settings diagnostics.')
    if manager.unit_ownership is None or os.name != 'posix':
        raise RuntimeError('Microphone readiness repair requires the owned native Pi service')
    module = Path(__file__).resolve(strict=True)
    helper = module.with_name('xvf_readiness_helper.py')
    package = Path(manager.binding['target'])
    manifest = strict((package/'PACKAGE_MANIFEST.json').read_bytes())
    for path in (module, helper):
        rows = [row for row in manifest['files'] if row['path'] == path.relative_to(package).as_posix()]
        if len(rows) != 1 or rows[0]['bytes'] != path.stat().st_size or rows[0]['sha256'] != digest(path):
            raise RuntimeError('Microphone readiness helper is not in the pinned runtime package')
    usage = shutil.disk_usage(manager.data_root)
    floor = max(5*1024**3, int(manager.store.policy.reserve(usage.total)))
    if usage.free < floor + RESERVE_BYTES:
        raise RuntimeError('Storage safety floor prevents microphone readiness repair')
    recovery_root.mkdir(exist_ok=True)
    if recovery_root.is_symlink() or recovery_root.resolve(strict=True) != recovery_root:
        raise RuntimeError('Microphone recovery directory must be a real owned path')
    out.mkdir()
    request = dict(schema='just-peachy.xvf-readiness.v1', fault_path=str(fault_path), fault_sha256=fault_sha,
        closed_path=str(closed_path), closed_sha256=hashlib.sha256(raw).hexdigest(), data_root=str(manager.data_root),
        module_sha256=digest(module), helper_sha256=digest(helper), manager_owner=current_owner(),
        worker_owner=worker_owner, source_owner=source_owner, unit=manager.unit,
        unit_ownership=str(manager.unit_ownership), unit_ownership_sha256=digest(manager.unit_ownership),
        maximum_output_bytes=RESERVE_BYTES, reserve_bytes=floor, expires_monotonic=time.monotonic()+55)
    publish(out/'REQUEST.json', request, cap=65536)
    # An inherited descriptor barrier records the exact helper owner before it
    # reads this request or any project module, even if the helper exits quickly.
    read_gate, write_gate = os.pipe()
    child = None; owned = None; timed_out = False
    try:
        with (out/'HELPER.stdout').open('xb') as stdout, (out/'HELPER.stderr').open('xb') as stderr:
            child = subprocess.Popen([manager.binding['python'], '-B', str(helper), '--output', str(out),
                '--gate', str(read_gate)], stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                pass_fds=(read_gate,), env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            os.close(read_gate); read_gate = None
            owned = dict(pid=child.pid, start_ticks=int(Path('/proc', str(child.pid), 'stat').read_text().rsplit(')', 1)[1].split()[19]),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
            publish(out/'CHILD_LAUNCH.json', dict(owner=owned, manager_owner=request['manager_owner']), cap=65536)
            os.write(write_gate, b'1'); os.close(write_gate); write_gate = None
            try:
                child.wait(timeout=50)
            except subprocess.TimeoutExpired:
                timed_out = True
                if owner_status(owned).get('closed') is not False:
                    raise RuntimeError('Microphone helper identity changed before timeout cleanup')
                child.kill(); child.wait(timeout=5)
            stdout.flush(); stderr.flush(); os.fsync(stdout.fileno()); os.fsync(stderr.fileno())
    finally:
        if read_gate is not None: os.close(read_gate)
        if write_gate is not None: os.close(write_gate)
        if child is not None and child.poll() is None:
            child.kill(); child.wait(timeout=5)
    if owned is None:
        raise RuntimeError('Microphone helper identity could not be registered; no retry')
    gone = owner_status(owned).get('closed') is True
    publish(out/'HOST_CLOSURE.json', dict(owner=owned, natural_returncode=child.returncode,
        timeout=timed_out, direct_child_reaped=True, exact_owner_gone=gone), cap=65536)
    result_path = out/'RECOVERY.json'
    result = strict(result_path.read_bytes()) if result_path.exists() else {}
    if child.returncode != 0 or timed_out or not gone or result.get('readiness_verified') is not True:
        detail = result.get('error', {}).get('message', 'Readiness helper did not close successfully')
        raise RuntimeError('Microphone recovery stopped safely: '+str(detail)+'. Evidence preserved; no automatic retry.')
    return dict(status=result['status'], fault_sha256=fault_sha, output_root=str(out), audio_qualified=False)
