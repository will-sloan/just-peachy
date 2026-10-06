"""Prepare exact closed-job finalization only. README_FINALIZE_PAYLOAD_V5.md."""
import argparse
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import time
import uuid

HERE = Path(__file__).parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
BOOT = '0561d730-3cad-48e0-940a-fe3930c89665'
PIN = '6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
HELPER_SHA = '0690f255b0fc8fef4ee76b6c32aefc2297de9751d18508ac0a29a7e89a5e1dce'
PACKAGE = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-25'
DATA = '/home/peachyprototype/JustPeachy/data/runtime-v29'
HOST_PACKAGE = PRIVATE/'audit-preparation/stabilization-package-41186a7a33004f1f8656e7be91e54e12/package'
LIMIT = 1024**2


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate finalize input field')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path, maximum=262144):
    path = Path(path); before = path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
        or before.st_size > maximum or any(parent.is_symlink() for parent in path.parents)):
        raise ValueError('Bounded independent real input required')
    raw = path.read_bytes(); after = path.stat()
    if len(raw) != before.st_size or (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('Finalize input changed during read')
    return raw


def bootstrap(label):
    if os.name != 'nt': raise RuntimeError('Windows host-only preparation')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle, 16384): raise ctypes.WinError(ctypes.get_last_error())
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    root = PRIVATE/'audit-preparation'/('finalize-payload-'+label+'-'+uuid.uuid4().hex)
    root.mkdir()
    raw = encoded(dict(schema='just-peachy.host-registered-owner.v1', pid=os.getpid(), cpu=14,
        affinity_mask=16384, creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000))
    with (root/'REGISTERED_OWNER.json').open('xb') as stream:
        if stream.write(raw) != len(raw): raise OSError('Short early owner write')
        stream.flush(); os.fsync(stream.fileno())
    if (root/'REGISTERED_OWNER.json').read_bytes() != raw: raise OSError('Early owner readback')
    return root


class Output:
    def __init__(self, root):
        self.root = root; self.bytes = (root/'REGISTERED_OWNER.json').stat().st_size
        self.started = time.monotonic()
    def write(self, name, raw):
        if self.bytes+len(raw) > LIMIT or time.monotonic()-self.started > 600:
            raise RuntimeError('Finite600s/1MiB finalize preparation exceeded')
        for drive, floor in (('C:/', 50*1024**3), ('G:/', 75*1024**3)):
            if shutil.disk_usage(drive).free < floor+len(raw): raise OSError('Host free-space floor')
        path = self.root/name
        with path.open('xb') as stream:
            if stream.write(raw) != len(raw): raise OSError('Short finalize preparation write')
            stream.flush(); os.fsync(stream.fileno())
        self.bytes += len(raw)
        if read(path, LIMIT) != raw: raise OSError('Independent finalize readback differs')
    def triple(self, name, raw):
        for suffix in ('', '.backup', '.restore'): self.write(name+suffix, raw)


def verify(job_path, monitor):
    job_path = Path(job_path); monitor = Path(monitor)
    if (job_path.parent != PRIVATE or job_path.resolve(strict=True) != job_path
        or monitor.parent != PRIVATE or monitor.resolve(strict=True) != monitor):
        raise ValueError('Exact canonical private job and monitor required')
    raw_job = read(job_path, 65536); job = strict(raw_job)
    label = job_path.name.removesuffix('-JOB.json')
    native = '/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/'+label
    if (re.fullmatch(r'classic-ui-check-[0-9]{2}', label) is None
        or monitor.name != label+'-monitor-01' or job.get('output_root') != native
        or job.get('schema') != 'just-peachy.native-component-job.v1'
        or job.get('boot_id') != BOOT or job.get('package_manifest_sha256') != PIN
        or job.get('helper_source_sha256') != HELPER_SHA
        or job.get('unit') != 'jp-v29-'+label+'.service'):
        raise ValueError('Actual current-boot/build25/exact-helper job required')
    result = strict(read(monitor/'RESULT.json')); mirrored = strict(read(monitor/'MIRROR_COMPLETE.json'))
    original = strict(read(monitor/'closed-output/JOB.json', 65536))
    backup = read(monitor/'JOB.json.backup', 65536); restore = read(monitor/'JOB.json.restore', 65536)
    observed = result.get('job'); identity = (observed or {}).get('output_identity')
    closure = mirrored.get('closure', {})
    if (original != job or backup != restore or strict(backup) != job
        or type(observed) is not dict or set(observed) != set(job)|{'output_identity'}
        or {key:value for key,value in observed.items() if key != 'output_identity'} != job
        or strict(read(monitor/'EFFECTIVE_JOB.json', 65536)) != observed
        or type(identity) is not dict or set(identity) != {'device','inode'}
        or any(type(identity[key]) is not int or identity[key] <= 0 for key in identity)
        or closure.get('output_identity') != identity
        or result.get('status') != 'FULL_CLOSED_OUTPUT_MIRRORED' or result.get('functional_success') is not True
        or Path(result.get('copied_root', '')) != monitor/'closed-output'
        or result.get('mirror_scope') != 'all_regular_output_files'
        or mirrored.get('mirror_scope') != 'all_regular_output_files'):
        raise ValueError('Complete independently closed exact job mirror required')
    owner = job.get('owner')
    if (type(owner) is not dict or set(owner) != {'boot_id','pid','start_ticks'} or owner['boot_id'] != BOOT
        or any(type(owner[key]) is not int or owner[key] <= 0 for key in ('pid','start_ticks'))
        or closure.get('owner') != owner or closure.get('unit') != job['unit']
        or closure.get('invocation_id') != job['invocation_id'] or closure.get('control_group') != job['control_group']
        or closure.get('kind') != 'STATUS' or closure.get('utility_read_only') is not True
        or any(closure.get(key) is not True for key in ('closed','cgroup_empty','exact_owner_gone','owner_recaptured'))
        or closure.get('observed_owner') is not None
        or closure.get('state',{}).get('ActiveState') != 'inactive'):
        raise ValueError('Actual exact owner and natural service/cgroup closure required')
    manifest_raw = read(monitor/'MIRROR_MANIFEST.json'); rows = strict(manifest_raw)
    if type(rows) is not list or not 1 <= len(rows) <= 4096 or sha(encoded(rows)) != mirrored.get('manifest_sha256'):
        raise ValueError('Complete bounded mirror manifest hash required')
    names = set(); aliases = set(); total = 0; closed = monitor/'closed-output'
    for row in rows:
        name = row['path']; rel = PurePosixPath(name); file_identity = row['identity']
        if (type(name) is not str or rel.is_absolute() or '..' in rel.parts or '\\' in name
            or rel.as_posix() != name or name.casefold() in aliases
            or type(file_identity.get('bytes')) is not int or not 0 <= file_identity['bytes'] <= 32*1024**2):
            raise ValueError('Canonical unique typed mirror member required')
        raw = read(closed.joinpath(*rel.parts), 32*1024**2)
        if len(raw) != file_identity['bytes'] or sha(raw) != row['sha256']:
            raise ValueError('Independent mirror member hash/readback differs')
        names.add(name); aliases.add(name.casefold()); total += len(raw)
    actual = set()
    for count, path in enumerate(closed.rglob('*'), 1):
        if count > 8192 or path.is_symlink(): raise ValueError('Bounded real complete mirror tree required')
        if path.is_file(): actual.add(path.relative_to(closed).as_posix())
    if (actual != names or mirrored.get('files') != len(names) or mirrored.get('bytes') != total
        or type(job.get('maximum_output_bytes')) is not int or total > job['maximum_output_bytes']):
        raise ValueError('Complete mirror membership/count/allocation differs')
    complete = strict(read(closed/'COMPLETE.json')); service = strict(read(closed/'SERVICE_EXIT.json'))
    wrapper = strict(read(closed/'JOB_EXIT.json'))
    if (complete.get('status') != 'FUNCTION_PASS_AWAITING_UNIT_CLOSURE'
        or complete.get('boot_id') != BOOT or complete.get('package_manifest_sha256') != PIN
        or complete.get('owner') != owner or service.get('owner') != owner
        or service.get('exit_code') != 0 or service.get('error') is not None
        or wrapper.get('natural_returncode') != 0 or wrapper.get('error') is not None
        or wrapper.get('output_budget_failure') is not None or wrapper.get('leases_released') is not True
        or wrapper != closure.get('job_exit')):
        raise ValueError('Functional workflow and natural0 exact closure receipts required')
    package_manifest_raw = read(HOST_PACKAGE/'PACKAGE_MANIFEST.json')
    if sha(package_manifest_raw) != PIN: raise ValueError('Current build25 host manifest changed')
    package_manifest = strict(package_manifest_raw)
    driver = read(HOST_PACKAGE/'native_gui_driver.py')
    pins = [row for row in package_manifest['files'] if row['path'] == 'native_gui_driver.py']
    if len(pins) != 1 or (len(driver), sha(driver)) != (pins[0]['bytes'], pins[0]['sha256']):
        raise ValueError('Exact retained worker closure checker changed')
    nodes = [node for node in ast.parse(driver).body if isinstance(node, ast.FunctionDef) and node.name == 'require_closed']
    if len(nodes) != 1: raise ValueError('One retained pure closure checker required')
    space = {}; exec(compile(ast.Module(body=nodes, type_ignores=[]), '<unchanged-closure-check>', 'exec'), space)
    if space['require_closed'](complete['worker_closure']) != complete['session_id']:
        raise ValueError('Actual worker/session closure mismatch')
    return job, dict(job_sha256=sha(raw_job), monitor_manifest_sha256=sha(manifest_raw),
        monitor_complete_sha256=sha(read(monitor/'MIRROR_COMPLETE.json')),
        files=len(names), bytes=total, exact_worker_closure_checked=True,
        native_finalize_pending=True, native_action=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--monitor', type=Path, required=True)
    parser.add_argument('--label', required=True, help='Explicit unused dispatch label, e.g. classic-finalize-15-01')
    args = parser.parse_args()
    if re.fullmatch(r'classic-finalize-[0-9]{2}-[0-9]{2}', args.label) is None:
        raise ValueError('Canonical unique finalize dispatch label required')
    output = Output(bootstrap(args.label))  # BEFORE project/evidence reads.
    sys.dont_write_bytecode = True
    output.write('HOST_SCOPE.json', encoded(dict(maximum_bytes=LIMIT, maximum_seconds=600,
        cpu=14, label=args.label, native_action=False)))
    source = read(Path(__file__)); guide = read(HERE/'README_FINALIZE_PAYLOAD_V5.md')
    output.triple('PREPARER.py', source); output.triple('README.md', guide)
    compile(source, '<backed-finalize-preparer>', 'exec')
    if any(PRIVATE.glob(args.label+'-*')): raise ValueError('Finalize dispatch label already used')
    job, review = verify(args.job, args.monitor)
    if args.label.split('-')[2] != job['output_root'][-2:]: raise ValueError('Finalize label must bind the exact job number')
    helper = read(HERE/'native_stabilization_check_v5.py', 65536)
    if sha(helper) != HELPER_SHA: raise ValueError('Whole original native helper source changed')
    compile(helper, '<unchanged-finalize-action>', 'exec')
    payload = dict(operation='finalize', output_root=job['output_root'], package=PACKAGE,
        package_manifest_sha256=PIN, data_root=DATA)
    output.triple('ACTION.py', helper); output.triple('PAYLOAD.json', encoded(payload))
    output.write('INPUT_BINDING_REVIEW.json', encoded(dict(review, job=str(args.job), monitor=str(args.monitor),
        actual_boot=BOOT, package_manifest_sha256=PIN, helper_source_sha256=HELPER_SHA,
        finalize_ast_unchanged=True, native_success_not_published=True)))
    output.write('SOURCE_CLOSED.json', encoded(dict(closed_unix=time.time(), prepared_bytes=output.bytes,
        independent_restores=True, payload_sha256=sha(encoded(payload)), native_action=False)))
    print(encoded(dict(output=str(output.root), action=str(output.root/'ACTION.py'),
        payload=str(output.root/'PAYLOAD.json'), label=args.label, native_action=False)).decode())


if __name__ == '__main__': main()
