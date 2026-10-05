"""Encoder-separated writable personal galleries; no vectors in GUI. See README.md."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import stat
import uuid

from runtime_support import digest, publish, strict


def snapshot_used_gallery(root, directory, budget, guard):
    """Pin encoder-specific reference bytes for later matched replay."""
    directory.mkdir()
    files, total = [], 0
    for index, source in enumerate(sorted(Path(root).rglob('*')), 1):
        if index > 1024:
            raise ValueError('Used gallery reference membership exceeds reviewed bound')
        guard()
        relative = source.relative_to(root)
        if source.is_symlink() or not source.resolve().is_relative_to(Path(root).resolve()):
            raise ValueError('Used gallery snapshot path escapes its root')
        target = directory/relative
        if source.is_dir():
            target.mkdir()
            continue
        size = source.stat().st_size
        total += size
        if total>16*1024**2 or size>2*1024**2 or source.stat().st_nlink!=1:
            raise ValueError('Used gallery reference snapshot exceeds reviewed bound')
        budget.claim(size)
        with source.open('rb') as original, target.open('xb') as copied:
            while True:
                raw = original.read(16384)
                if not raw: break
                if copied.write(raw)!=len(raw): raise OSError('Short gallery reference copy')
            copied.flush()
            import os
            os.fsync(copied.fileno())
        expected = digest(source)
        if digest(target)!=expected:
            raise OSError('Used gallery independent reference readback differs')
        files.append(dict(path=relative.as_posix(),bytes=size,sha256=expected))
    receipt = dict(schema='just-peachy.used-personal-gallery.v1',files=files,bytes=total,
        scope='selected encoder references; no cross-encoder conversion; private session data')
    budget.claim(len(json.dumps(receipt,sort_keys=True).encode()))
    publish(directory/'GALLERY_MANIFEST.json',receipt)
    return receipt


def descriptor(binding, selection):
    if selection.diarizer == 'pyannote':
        key = 'baseline-titanet' if selection.embedding == 'titanet' else 'baseline'
    else:
        mode = 'delayed' if selection.nemotron_profile == 'current_delayed' else 'streaming'
        key = 'd1-'+mode+('-titanet' if selection.embedding == 'titanet' else '')+('-saved' if mode == 'streaming' else '')
    row = binding['profiles'][key]
    path = Path(row['path'])
    if path.is_symlink() or path.stat().st_size > 65536 or digest(path) != row['sha256']:
        raise ValueError('Pinned backend/gallery descriptor changed')
    return strict(path.read_bytes())


def layout(binding, selection, data_root):
    value = descriptor(binding, selection)
    encoder = 'E1' if selection.embedding == 'titanet' else 'E0'
    legacy = value['runtime_profile']['galleries'][encoder]
    namespace = value['runtime_document'].get('embedding_namespace') if encoder == 'E1' else None
    key = hashlib.sha256(json.dumps(namespace, sort_keys=True, separators=(',', ':')).encode()).hexdigest() if namespace else 'redimnet'
    root = Path(data_root).resolve()/ 'people-spaces'/key/'people'
    return root, legacy, namespace


def summaries(binding, selection, data_root):
    if selection.embedding == 'anonymous':
        return []
    root, legacy, namespace = layout(binding, selection, data_root)
    if not root.exists():
        root = Path(legacy['root'])
    if root.is_symlink():
        raise ValueError('Personal gallery must be a real directory')
    result = []
    for path in sorted(root.glob('*/person.json')):
        if len(result) >= 256 or path.is_symlink() or path.stat().st_size > 128*1024:
            raise ValueError('Bounded personal gallery metadata required')
        row = strict(path.read_bytes())
        if str(uuid.UUID(row['id'])) != row['id'] or path.parent.name != row['id']:
            raise ValueError('Personal metadata UUID/path mismatch')
        result.append(dict(id=row['id'], name=row['name'], references=len(row['references']),
            compatible_references=sum(ref.get('route', {}).get('tap') == 'O0' for ref in row['references'])))
    return result


def open_store(binding, selection, data_root, config, people, n2_people, compat, guard):
    """Seed an independent copy; never edit the old immutable gallery snapshot."""
    root, legacy, namespace = layout(binding, selection, data_root)
    descriptor_value = descriptor(binding, selection)
    # The existing complete manifest/model/preprocessing/extent verifier runs
    # before copying and before constructing the writable original store.
    readonly = compat.readonly_store_type(people, Path(data_root)/'verification',
        descriptor_value['runtime_profile']['galleries'], namespace, guard)
    if namespace is None:
        seeded = readonly(Path(data_root)/'verification/people', config.asset('redimnet2_b2_fp32').sha256)
    else:
        from app.n2_identity import binding as namespace_id
        preprocessing = 'titanet:'+namespace_id(namespace)
        class VerifyTitanet(readonly):
            pass
        VerifyTitanet.preprocessing = preprocessing
        seeded = VerifyTitanet(Path(data_root)/'verification/embedding_spaces'/namespace_id(namespace)/'people', namespace['model_sha256'])
    seeded.list(refresh=True)
    if not root.exists():
        root.parent.mkdir(parents=True, exist_ok=True)
        temporary = root.parent/('seed-'+uuid.uuid4().hex)
        temporary.mkdir()
        copied = []
        total = 0
        for path in sorted(Path(legacy['root']).rglob('*')):
            guard()
            relative = path.relative_to(legacy['root'])
            if path.is_symlink():
                raise ValueError('Gallery seed symlink refused')
            if path.is_dir():
                (temporary/relative).mkdir(exist_ok=False)
                continue
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 2*1024**2:
                raise ValueError('Bounded real gallery seed file required')
            total += info.st_size
            if total > 16*1024**2:
                raise ValueError('Gallery seed exceeds 16 MiB')
            shutil.copyfile(path, temporary/relative)
            if digest(path) != digest(temporary/relative):
                raise OSError('Gallery seed independent readback differs')
            copied.append(dict(path=relative.as_posix(), bytes=info.st_size, sha256=digest(path)))
        publish(root.parent/'SEED.json', dict(legacy=legacy, namespace=namespace, files=copied))
        temporary.rename(root)
    if namespace is None:
        return people.PersonalStore(root, config.asset('redimnet2_b2_fp32').sha256)
    original = people.PersonalStore
    from app.n2_identity import binding as namespace_id
    class TitanetStore(original):
        preprocessing = 'titanet:'+namespace_id(namespace)
        def gallery(self, route, person_ids=None, *, alternate_advisory=False):
            result = super().gallery(route, person_ids, alternate_advisory=alternate_advisory)
            result.namespace = deepcopy(namespace)
            result.calibration = dict(status='UNCALIBRATED_PERSONAL_DOMAIN')
            result.receipt.update(namespace=deepcopy(namespace), calibration=deepcopy(result.calibration))
            return result
    return TitanetStore(root, namespace['model_sha256'])
