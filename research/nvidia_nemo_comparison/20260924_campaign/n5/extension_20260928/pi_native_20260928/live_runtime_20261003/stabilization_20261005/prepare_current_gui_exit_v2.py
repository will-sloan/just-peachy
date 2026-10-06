"""Freeze a normal Exit payload from fresh closed inspection. README_CURRENT_GUI_EXIT_V2.md."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import time
import uuid

PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PACKAGE = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-26'
DATA = '/home/peachyprototype/JustPeachy/data/runtime-v29'
PIN = 'f4c9cc2fd841e3b240b8c16799858ec87839e265cc9f6f6dfbd0db6c772c55a0'
MAXIMUM_BYTES = 2 * 1024**2


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate normal Exit preparation field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def identity(value):
    if (type(value) is not dict or set(value) != {'pid', 'start_ticks', 'boot_id'}
            or any(type(value[key]) is not int or value[key] <= 0 for key in ('pid', 'start_ticks'))
            or type(value['boot_id']) is not str
            or re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value['boot_id']) is None):
        raise ValueError('Exact inspected native identity required')
    return value


def main():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 16384):
        raise ctypes.WinError(ctypes.get_last_error())
    times = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in times)):
        raise ctypes.WinError(ctypes.get_last_error())
    began = time.monotonic()
    out = PRIVATE / 'audit-preparation' / ('current-gui-exit-v2-' + uuid.uuid4().hex)
    out.mkdir()
    used = 0

    def check_time():
        if time.monotonic() - began >= 30:
            raise TimeoutError('Normal Exit preparation exceeded its 30-second scope')

    def put(name, raw):
        nonlocal used
        check_time()
        if used + len(raw) > MAXIMUM_BYTES:
            raise ValueError('Normal Exit preparation exceeds its cumulative 2 MiB allocation')
        used += len(raw)
        with (out / name).open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short normal Exit preparation write')
            stream.flush()
            os.fsync(stream.fileno())
        if (out / name).read_bytes() != raw:
            raise OSError('Independent normal Exit preparation readback differs')

    def encoded(value):
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

    owner = dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
        affinity_mask=16384, creation_filetime=times[0].value,
        create_time=(times[0].value - 116444736000000000) / 10000000)
    put('REGISTERED_OWNER.json', encoded(owner))
    for drive, gib in (('C:/', 50), ('G:/', 75)):
        if shutil.disk_usage(drive).free < gib * 1024**3 + MAXIMUM_BYTES:
            raise OSError('Host floor prevents normal Exit preparation')
    put('HOST_SCOPE.json', encoded(dict(maximum_output_bytes=MAXIMUM_BYTES,
        maximum_seconds=30, issued_unix=time.time(), native_action=False)))

    def read(path, maximum):
        check_time()
        path = Path(path)
        before = path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1 or before.st_size > maximum):
            raise ValueError('Bounded single-link normal Exit preparation input required')
        raw = path.read_bytes()
        after = path.lstat()
        if (len(raw) != before.st_size
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError('Normal Exit preparation input changed during read')
        return raw

    parser = argparse.ArgumentParser(description='Prepare one normal Exit from an actual closed read-only inspection')
    parser.add_argument('--snapshot', required=True, help='Explicit private dispatch/RESULT.json from the latest closed inspection')
    args = parser.parse_args()
    snapshot = Path(args.snapshot).absolute()
    if (snapshot.name != 'RESULT.json' or snapshot.parent.name != 'dispatch'
            or not snapshot.parent.parent.name.startswith('operation-')
            or not snapshot.is_relative_to(PRIVATE)
            or snapshot.resolve(strict=True) != snapshot):
        raise ValueError('Explicit real private operation dispatch/RESULT.json required')
    blobs = {name: read(snapshot.parent / name, 262144 if name == 'RESULT.json' else 65536)
             for name in ('RESULT.json', 'NATIVE_CLOSURE.json', 'PHASE.json')}
    result, closure, phase = (strict(blobs[name]) for name in ('RESULT.json', 'NATIVE_CLOSURE.json', 'PHASE.json'))
    action = result.get('action_result')
    utility = identity(result.get('utility_owner'))
    if (result.get('schema') != 'just-peachy.runtime-install-inspection.v1'
            or result.get('status') != 'CURRENT_OPERATION_INSPECTED'
            or result.get('native_writes') is not False or result.get('capture_started') is not False
            or result.get('utility_pid_absent_after_ssh') is not True
            or type(action) is not dict or action.get('status') != 'CLOSED_RECOVERY_TREE_READ'
            or action.get('native_writes') is not False or action.get('device_commands') is not False
            or result.get('boot_id') != utility['boot_id'] or action.get('boot_id') != utility['boot_id']
            or set(closure) != {'owner', 'exact_pid_absent', 'natural_returncode'}
            or identity(closure['owner']) != utility or closure.get('exact_pid_absent') is not True
            or type(closure.get('natural_returncode')) is not int or closure['natural_returncode'] != 0
            or type(phase.get('returncode')) is not int or phase['returncode'] != 0
            or phase.get('fault') is not None or phase.get('overflow') is not False
            or phase.get('readers_joined') is not True or phase.get('ssh_reaped') is not True
            or phase.get('reader_error') != [] or phase.get('writer_error') != []):
        raise ValueError('Actual read-only inspection and independent natural native closure must both pass')
    capture = result.get('capture')
    if type(capture) is not dict or not capture or any(value != 'closed' for value in capture.values()):
        raise ValueError('Inspected capture must be closed before normal Exit')
    if set(result.get('free_leases', [])) != {
            '/home/peachyprototype/JustPeachy/research/nemotron-20260928/B05_PREVIEW_DISPATCH.lock',
            '/home/peachyprototype/JustPeachy/data/xvf-hardware.lock'}:
        raise ValueError('Inspected research and hardware leases must both be free')
    rows = result.get('current_project_processes')
    if type(rows) is not list or len(rows) != 2:
        raise ValueError('Exactly the inspected idle portrait GUI and its supervisor required')
    candidates = []
    for row in rows:
        if type(row) is not dict or set(row) != {'boot_id', 'pid', 'start_ticks', 'cmdline'}:
            raise ValueError('Exact inspected process command/identity fields required')
        process_owner = identity({key: row[key] for key in ('boot_id', 'pid', 'start_ticks')})
        if process_owner['boot_id'] != utility['boot_id'] or type(row['cmdline']) is not str or len(row['cmdline']) > 8192:
            raise ValueError('Current inspected GUI boot and bounded actual command required')
        command = shlex.split(row['cmdline'])
        if PACKAGE + '/native_scope.py' not in command:
            raise ValueError('Only the existing build26 native scope may receive normal Exit')
        def argument(flag, command=command):
            if command.count(flag) != 1 or command.index(flag) + 1 >= len(command):
                raise ValueError('One exact inspected native scope argument required: ' + flag)
            return command[command.index(flag) + 1]
        if argument('--binding') != PACKAGE + '/BINDING.json' or argument('--manifest-sha256') != PIN or argument('--data-root') != DATA:
            raise ValueError('Inspected existing runtime binding/manifest/data root differs')
        candidates.append((process_owner, command, argument))
    inner = [item for item in candidates if '--inside' in item[1]]
    outer = [item for item in candidates if '--inside' not in item[1]]
    if len(inner) != 1 or len(outer) != 1 or inner[0][0]['pid'] == outer[0][0]['pid']:
        raise ValueError('One distinct inspected GUI owner and supervisor required')
    gui, _, gui_argument = inner[0]
    unit, inside = gui_argument('--unit'), gui_argument('--inside')
    if (re.fullmatch(r'jp-v29-[0-9a-f]{32}\.service', unit) is None
            or re.fullmatch(re.escape(DATA) + r'/unit-owners/[0-9a-f]{32}', inside) is None
            or gui_argument('--entrypoint') != 'launcher.py'):
        raise ValueError('Exact inspected owned portrait GUI unit/path required')
    payload = dict(package_manifest_sha256=PIN, owner=gui, supervisor=outer[0][0],
        unit=unit, unit_ownership=inside + '/UNIT_OWNERSHIP.json')
    pins = {}
    here = Path(__file__).resolve().parent
    for name in ('prepare_current_gui_exit_v2.py', 'README_CURRENT_GUI_EXIT_V2.md',
                 'normal_current_gui_exit.py', 'host_current_gui_exit.py'):
        raw = read(here / name, 65536)
        for suffix in ('', '.backup', '.restore'):
            put(name + suffix, raw)
        if name.endswith('.py'):
            compile(raw, name, 'exec')
        pins[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    for name, raw in blobs.items():
        for suffix in ('', '.backup', '.restore'):
            put('INSPECTION_' + name + suffix, raw)
    payload_raw = encoded(payload)
    for suffix in ('', '.backup', '.restore'):
        put('PAYLOAD.json' + suffix, payload_raw)
    put('SOURCE_CLOSED.json', encoded(dict(status='NORMAL_EXIT_PREPARED_ONLY',
        sources=pins, input_snapshot=str(snapshot),
        input_pins={name: dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) for name, raw in blobs.items()},
        payload_sha256=hashlib.sha256(payload_raw).hexdigest(), independent_restores=True,
        native_action=False, closed_unix=time.time(), cumulative_bytes_before_receipt=used)))
    check_time()
    print(str(out))


if __name__ == '__main__':
    main()
