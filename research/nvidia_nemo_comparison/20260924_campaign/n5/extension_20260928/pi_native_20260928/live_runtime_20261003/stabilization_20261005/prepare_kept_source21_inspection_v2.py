"""Prepare original CHECK21 metadata inspection. README_KEPT_SOURCE21_INSPECTION_V2.md."""
import argparse
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
PRIVATE = Path('G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003')
PIN = '6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8'
BOOT = '0561d730-3cad-48e0-940a-fe3930c89665'
SESSION = 'c24b685b2bd34d6bb04172965d712c0f'
PROOF = '0c4844160ab39d53f140a8cd7a3e192ad6fe1f47308a10a4bc59213b91893423'
MAXIMUM = 2*1024**2


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def read(path, maximum):
    path = Path(path)
    before = path.lstat()
    if path.is_symlink() or before.st_nlink != 1 or not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
        raise ValueError('Bounded independent preparation input required')
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_ino,after.st_size,after.st_mtime_ns) or len(raw) != before.st_size:
        raise ValueError('Preparation input changed')
    return raw


def bootstrap(output):
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    handle = kernel.GetCurrentProcess()
    kernel.SetProcessAffinityMask.argtypes = [ctypes.c_void_p,ctypes.c_size_t]
    if not kernel.SetProcessAffinityMask(handle,16384):
        raise ctypes.WinError(ctypes.get_last_error())
    stamps = [ctypes.c_ulonglong() for _ in range(4)]
    kernel.GetProcessTimes.argtypes = [ctypes.c_void_p]+[ctypes.POINTER(ctypes.c_ulonglong)]*4
    if not kernel.GetProcessTimes(handle,*(ctypes.byref(value) for value in stamps)):
        raise ctypes.WinError(ctypes.get_last_error())
    if output is None:
        output = PRIVATE/'audit-preparation'/('kept-source21-inspection-'+uuid.uuid4().hex)
    if output.parent != PRIVATE/'audit-preparation' or output.is_symlink():
        raise ValueError('Fresh exact private preparation parent required')
    output.mkdir()
    owner = dict(schema='just-peachy.host-registered-owner.v1',pid=os.getpid(),cpu=14,
        affinity=[14],affinity_mask=16384,creation_filetime=stamps[0].value,
        create_time=(stamps[0].value-116444736000000000)/10000000)
    started = time.time()
    def write(name, raw):
        if time.time()-started > 30 or sum(path.stat().st_size for path in output.iterdir() if path.is_file())+len(raw) > MAXIMUM:
            raise ValueError('Finite30second/2MiB source preparation bound')
        with (output/name).open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Short preparation write')
            stream.flush();os.fsync(stream.fileno())
        if (output/name).read_bytes() != raw:
            raise OSError('Preparation readback differs')
    write('REGISTERED_OWNER.json',encoded(owner))
    write('HOST_SCOPE.json',encoded(dict(issued_unix=started,maximum_seconds=30,maximum_output_bytes=MAXIMUM,cpu=14,native_action=False)))
    return output, write, owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    output, write, owner = bootstrap(args.output)
    rows = []
    def copies(name, raw):
        for suffix in ('','.backup','.restore'):
            write(name+suffix,raw)
        rows.append(dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    copies('PREPARER.py',read(Path(__file__),65536))
    copies('README.md',read(HERE/'README_KEPT_SOURCE21_INSPECTION_V2.md',32768))
    action = read(HERE/'inspect_kept_source21_v2.py',65536)
    copies('ACTION.py',action)
    helper = read(HERE/'native_saved_stabilization_check_v4.py',65536)
    copies('SAVED_HELPER_V4.py',helper)
    raw_proof = read(PRIVATE/'classic-ui-check-21-finalized-monitor-01/closed-output/NATIVE_CHECK_V2.json',262144)
    copies('CHECK21_PROOF.json',raw_proof)
    old_action = read(HERE/'inspect_kept_source21_v1.py',65536)
    copies('OLD_ACTION_V1.py',old_action)
    package = PRIVATE/'audit-preparation/stabilization-package-41186a7a33004f1f8656e7be91e54e12/package'
    publish_source = read(package/'storage.py',131072)
    copies('PUBLISH_STORAGE25.py',publish_source)
    package_raw = read(package/'PACKAGE_MANIFEST.json',262144)
    copies('PACKAGE_MANIFEST.json',package_raw)
    write('SOURCE_CLOSED.json',encoded(dict(owner=owner,members=rows,closed_unix=time.time(),
        exact_backup=True,independent_restore=True,before_execution=True,native_action=False)))
    for name, raw in (('ACTION.py',action),('SAVED_HELPER_V4.py',helper),('PREPARER.py',read(Path(__file__),65536))):
        compile(raw,'<backed-'+name+'>','exec')
    trees = [ast.parse(raw) for raw in (action,helper)]
    methods = []
    for tree, wanted in zip(trees,('SourceSnapshot','ClassicDriver')):
        cls = next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name == wanted)
        methods.append(next(node for node in cls.body if isinstance(node,ast.FunctionDef) and node.name == 'source_snapshot'))
    if ast.dump(methods[0],include_attributes=False) != ast.dump(methods[1],include_attributes=False):
        raise ValueError('Original SavedV4 source snapshot guards must remain AST exact')
    old_tree = ast.parse(old_action)
    new_tree = trees[0]
    old_defs = {node.name:node for node in old_tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
    new_defs = {node.name:node for node in new_tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
    if set(old_defs) != set(new_defs):
        raise ValueError('Inspector definitions must remain unchanged')
    for name in old_defs:
        if name != 'inspect' and ast.dump(old_defs[name],include_attributes=False) != ast.dump(new_defs[name],include_attributes=False):
            raise ValueError('Unchanged read-only inspector guard drift: '+name)
    audio = {'processed_encoding':'FLOAT32_LE','processed_channels':1,
        'replay_encoding':'PCM_S16LE','segment_index':'segments.jsonl'}
    storage_tree = ast.parse(publish_source)
    storage_class = next(node for node in storage_tree.body if isinstance(node,ast.ClassDef) and node.name == 'SessionStore')
    publish = next(node for node in storage_class.body if isinstance(node,ast.FunctionDef) and node.name == '_publish')
    assignment = next(node for node in publish.body if isinstance(node,ast.Assign) and
        isinstance(node.targets[0],ast.Subscript) and isinstance(node.targets[0].value,ast.Name) and
        node.targets[0].value.id == 'metadata' and ast.literal_eval(node.targets[0].slice) == 'audio')
    if ast.literal_eval(assignment.value) != audio:
        raise ValueError('Exact actual SessionStore._publish audio descriptor differs')
    class FixPublishedViews(ast.NodeTransformer):
        def __init__(self):
            self.changed = []
        def visit_Compare(self,node):
            self.generic_visit(node)
            if len(node.ops) != 1 or not isinstance(node.ops[0],ast.NotEq) or len(node.comparators) != 1:
                return node
            if isinstance(node.left,ast.Name) and node.left.id == 'metadata' and isinstance(node.comparators[0],ast.Name) and node.comparators[0].id == 'current':
                node.left = ast.parse('encoded(metadata)',mode='eval').body
                node.comparators[0] = ast.parse('encoded(dict(current,audio='+repr(audio)+'))',mode='eval').body
                self.changed.append('published_audio')
            elif ast.dump(node.left,include_attributes=False) == ast.dump(ast.parse('store.read(SESSION)',mode='eval').body,include_attributes=False) and isinstance(node.comparators[0],ast.Name) and node.comparators[0].id == 'metadata':
                node.comparators[0] = ast.Name(id='current',ctx=ast.Load())
                self.changed.append('same_database_view')
            return node
    correction = FixPublishedViews()
    corrected = correction.visit(old_defs['inspect'])
    if correction.changed != ['published_audio','same_database_view'] or ast.dump(corrected,include_attributes=False) != ast.dump(new_defs['inspect'],include_attributes=False):
        raise ValueError('Only exact published/database view comparisons may change')
    manifest = json.loads(package_raw)
    storage_row = next(row for row in manifest['files'] if row['path'] == 'storage.py')
    if hashlib.sha256(package_raw).hexdigest() != PIN or storage_row['bytes'] != len(publish_source) or storage_row['sha256'] != hashlib.sha256(publish_source).hexdigest():
        raise ValueError('Actual package25 storage source pin differs')
    proof = json.loads(raw_proof)
    if (hashlib.sha256(raw_proof).hexdigest() != PROOF or proof.get('status') != 'PASS' or
            proof.get('session_id') != SESSION or proof.get('boot_id') != BOOT or
            proof.get('package_manifest_sha256') != PIN or proof.get('processed_save_passed') is not True or
            proof.get('main_exact_owner_gone') is not True or proof.get('unit_recursively_empty') is not True):
        raise ValueError('Actual closed CHECK21 proof required before payload preparation')
    payload = dict(package_manifest_sha256=PIN,boot_id=BOOT,session_id=SESSION,
        check21_proof_sha256=PROOF,expires_unix=time.time()+590)
    copies('PAYLOAD.json',encoded(payload))
    write('RESULT.json',encoded(dict(status='READONLY_SOURCE_METADATA_PAYLOAD_PREPARED',owner=owner,
        output=str(output),snapshot_method_ast_exact=True,published_audio_ast_bound=True,only_two_metadata_comparisons_changed=True,native_action=False,source_raw_sha_invented=False,
        command_argv=[str(HERE/'host_stabilization_operations_v5.py'),'--label','kept-source21-inspect-03',
            '--action',str(output/'ACTION.py'),'--payload',str(output/'PAYLOAD.json')],
        payload_expires_unix=payload['expires_unix'])))
    write('EXIT_INTENT.json',encoded(dict(owner=owner,at_unix=time.time(),native_action=False,physical_closure_claimed=False)))
    print(str(output))


if __name__ == '__main__':
    main()
