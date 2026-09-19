"""Exact enumerated-size admission candidate; README_S6C_ADMISSION_FAST_V1.md."""
from __future__ import annotations
import argparse
from pathlib import Path
import os
import tempfile
import time
import json
from s6c_common import REPORT,STAGING,PAYLOAD,bind,save,utc,tree_bytes as original_tree_bytes


def scan_details(root):
    """Sum current traversal's file metadata without a per-file Path.stat call.

    No file list/size is retained across calls. Directory symlinks are skipped,
    matching os.walk(followlinks=False); file symlinks use target stat size.
    Unreadable directories fail closed (os.walk's default can silently skip).
    """
    root=Path(root)
    if not root.exists():return dict(bytes=0,files=0,directories=0)
    pending=[str(root)];total=files=directories=0
    while pending:
        current=pending.pop()
        with os.scandir(current) as entries:
            directories+=1
            for entry in entries:
                if entry.is_dir(follow_symlinks=True):
                    if not entry.is_symlink():pending.append(entry.path)
                else:
                    total+=entry.stat(follow_symlinks=True).st_size
                    files+=1
    return dict(bytes=total,files=files,directories=directories)


def tree_bytes(root):
    """Drop-in callable for a separately bound coordinator admission overlay."""
    return scan_details(root)['bytes']


def sources():
    return [bind(Path(__file__)),bind(Path(__file__).with_name('README_S6C_ADMISSION_FAST_V1.md')),
        bind(Path(__file__).with_name('s6c_common.py'))]


def fixtures():
    checks=[];unavailable=[]
    def same(root,label):
        old=original_tree_bytes(root);new=tree_bytes(root)
        if old!=new:raise AssertionError(label+': old/new bytes differ')
        checks.append(dict(name=label,bytes=old))
    with tempfile.TemporaryDirectory(prefix='s6c_admission_scandir_') as folder:
        root=Path(folder);same(root/'absent','missing root zero')
        same(root,'empty directory')
        (root/'nested/deep').mkdir(parents=True)
        (root/'empty').write_bytes(b'')
        (root/'nested/deep/unicode_é.txt').write_bytes(b'x'*257)
        (root/'.hidden').write_bytes(bytes(range(256)))
        same(root,'nested hidden unicode and empty files')
        target=root/'changing';target.write_bytes(b'a'*1024);same(root,'new file appears on next call')
        target.write_bytes(b'b'*4097);same(root,'growth is reread without time cache')
        target.write_bytes(b'c');same(root,'shrink is reread without time cache')
        target.unlink();same(root,'deleted file absent on next call')
        os.link(root/'.hidden',root/'hardlink');same(root,'hardlink counted per directory entry like original')
        for name,target,is_directory in (('file_link',root/'.hidden',False),('dir_link',root/'nested',True)):
            try:os.symlink(target,root/name,target_is_directory=is_directory)
            except OSError as exc:unavailable.append(dict(name=name,error=repr(exc)))
            else:same(root,name+' preserves original follow policy')
        broken=root/'broken_link'
        try:os.symlink(root/'not_present',broken)
        except OSError as exc:unavailable.append(dict(name='broken_link',error=repr(exc)))
        else:
            for scan in (original_tree_bytes,tree_bytes):
                try:scan(root)
                except FileNotFoundError:pass
                else:raise AssertionError('Broken file link did not fail closed')
            checks.append(dict(name='broken file link rejects both',bytes=None))
            broken.unlink()
    return dict(status='PASS',checks=checks,unavailable_optional_link_fixtures=unavailable,
        scope='Stable-tree byte parity and between-call mutations. No model calls. A recursive scan is not an atomic filesystem snapshot under concurrent writers.')


def benchmark(version):
    import psutil
    process=psutil.Process();cpu0=process.cpu_times();start=time.perf_counter()
    rows=[]
    for root in (REPORT,STAGING,PAYLOAD):
        t=time.perf_counter();detail=scan_details(root)
        rows.append(dict(root=str(root),**detail,elapsed_sec=time.perf_counter()-t))
    elapsed=time.perf_counter()-start;cpu1=process.cpu_times()
    result=dict(schema='s6c_exact_scandir_admission_benchmark.v1',utc=utc(),sources=sources(),
        rows=rows,total_bytes=sum(r['bytes'] for r in rows),elapsed_sec=elapsed,
        process_cpu_sec=cpu1.user+cpu1.system-cpu0.user-cpu0.system,
        prior_original_scan=bind(REPORT/'orchestration_review/READ_ONLY_ADMISSION_SCAN_V1.json'),
        scope='One read-only current-tree scan. Source trees may grow between earlier reference scan and this scan; byte totals are not an atomic paired measurement. The same reservation/free-space/RAM/input hashing would remain unchanged in a future overlay. No live coordinator or worker patched.')
    path=REPORT/'orchestration_review'/('SCANDIR_BENCHMARK_'+version+'.json')
    save(path,result,immutable=True);return bind(path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--test',action='store_true');p.add_argument('--benchmark',action='store_true');p.add_argument('--version',default='v1')
    a=p.parse_args()
    if a.test==a.benchmark:p.error('Choose exactly one of --test or --benchmark')
    if not a.version.replace('_','').isalnum():p.error('Simple version name required')
    if a.test:
        path=REPORT/'orchestration_review'/('SCANDIR_FIXTURES_'+a.version+'.json')
        result=dict(**fixtures(),sources=sources(),utc=utc());save(path,result,immutable=True);value=bind(path)
    else:value=benchmark(a.version)
    print(json.dumps(value,indent=2),flush=True)


if __name__=='__main__':main()
