"""Stream private gallery copies and membership receipts. See README_GALLERY_CAPACITY.md."""
import hashlib
import os
from pathlib import Path
import stat

from runtime_support import digest, encoded


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def copy_gallery_tree(source_root, target_root, manifest_path, budget, guard, header):
    """Copy validated files one at a time; keep membership on disk, never in a list.

    Inputs are real source/target directories, actual capacity budget, owner/RAM
    guard and small metadata header. Outputs are original-schema streamed JSON
    membership and a small hash/count descriptor. No reference vectors are read
    into receipts or transformed. The caller creates the new target directory.
    """
    source_root, target_root = Path(source_root), Path(target_root)
    manifest_path = Path(manifest_path)
    source_resolved, target_resolved = source_root.resolve(), target_root.resolve()
    if (source_root.is_symlink() or target_root.is_symlink() or
            not source_root.is_dir() or not target_root.is_dir() or
            target_resolved == source_resolved or target_resolved.is_relative_to(source_resolved)):
        raise ValueError('Separate real gallery directories required')
    if any(p.is_symlink() for p in target_root.parents) or manifest_path.is_symlink():
        raise ValueError('Real owned gallery receipt path required')
    if any(k in header for k in ('files', 'bytes', 'file_count')):
        raise ValueError('Gallery membership fields are stream owned')
    prefix = b'{' + b','.join(encoded(k)+b':'+encoded(v) for k,v in header.items())
    prefix += (b',' if header else b'') + b'"files":['
    if len(prefix) > 256*1024:
        raise ValueError('Bounded individual gallery receipt header required')
    pending = manifest_path.with_name(manifest_path.name+'.pending')
    if pending.exists() or pending.is_symlink() or manifest_path.exists():
        raise FileExistsError('Preserve prior or incomplete gallery membership')
    count, total, receipt_bytes = 0, 0, 0
    expected_manifest = hashlib.sha256()
    with pending.open('xb') as receipt:
        def write(raw):
            nonlocal receipt_bytes
            guard()
            budget.check_free(pending.parent, len(raw))
            budget.claim(len(raw))
            if receipt.write(raw) != len(raw):
                raise OSError('Short gallery membership write')
            expected_manifest.update(raw)
            receipt_bytes += len(raw)
        write(prefix)
        for source in source_root.rglob('*'):
            guard()
            relative = source.relative_to(source_root)
            if source.is_symlink() or not source.resolve().is_relative_to(source_resolved):
                raise ValueError('Gallery copy path escapes its source root')
            target = target_root/relative
            if not target.resolve().is_relative_to(target_resolved):
                raise ValueError('Gallery copy path escapes its destination root')
            if source.is_dir():
                target.mkdir(exist_ok=False)
                continue
            before = source.stat()
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 2*1024**2:
                raise ValueError('Bounded real gallery reference file required')
            budget.check_free(target_root, before.st_size)
            budget.claim(before.st_size)
            source_hash = hashlib.sha256()
            with source.open('rb') as original, target.open('xb') as copied:
                if _identity(os.fstat(original.fileno())) != _identity(before):
                    raise ValueError('Gallery reference changed before copy')
                while True:
                    raw = original.read(16384)
                    if not raw:
                        break
                    guard()
                    budget.check_free(target_root, len(raw))
                    if copied.write(raw) != len(raw):
                        raise OSError('Short gallery reference copy')
                    source_hash.update(raw)
                copied.flush()
                os.fsync(copied.fileno())
                if _identity(os.fstat(original.fileno())) != _identity(before):
                    raise ValueError('Gallery reference changed during copy')
            expected = source_hash.hexdigest()
            if _identity(source.stat()) != _identity(before) or digest(source) != expected or digest(target) != expected:
                raise OSError('Gallery independent reference readback differs')
            record = encoded(dict(path=relative.as_posix(), bytes=before.st_size, sha256=expected))
            if len(record) > 256*1024:
                raise ValueError('Bounded individual gallery member metadata required')
            write((b',' if count else b'')+record)
            count += 1
            total += before.st_size
        write(b'],"bytes":'+str(total).encode()+b',"file_count":'+str(count).encode()+b'}\n')
        receipt.flush()
        os.fsync(receipt.fileno())
    if digest(pending) != expected_manifest.hexdigest():
        raise OSError('Gallery membership independent readback differs')
    os.link(pending, manifest_path)
    pending.unlink()
    if digest(manifest_path) != expected_manifest.hexdigest():
        raise OSError('Published gallery membership readback differs')
    if os.name != 'nt':
        fd = os.open(manifest_path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return dict(header, bytes=total, file_count=count, manifest_path=str(manifest_path),
        manifest_sha256=expected_manifest.hexdigest(), receipt_bytes=receipt_bytes,
        membership_storage='streamed JSON files array; bounded per-file copy and metadata')
