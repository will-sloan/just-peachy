"""Encoder-separated writable galleries; no GUI vectors. See README_IDENTITY_MODES.md."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import uuid

from runtime_support import digest, strict, DiskBudget, resource_snapshot


def snapshot_used_gallery(root, directory, budget, guard):
    """Pin encoder-specific reference bytes for later matched replay."""
    directory.mkdir()
    from gallery_snapshot_io import copy_gallery_tree
    return copy_gallery_tree(root, directory, directory/'GALLERY_MANIFEST.json', budget, guard,
        dict(schema='just-peachy.used-personal-gallery.v1',
            scope='selected encoder references; no cross-encoder conversion; private session data'))


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


def iter_summaries(root, *, guard=None):
    """One bounded person record at a time; no logical roster-count quota."""
    root = Path(root)
    def check():
        if guard is not None:
            guard()
        elif resource_snapshot()['available_ram'] < 192*1024**2:
            raise MemoryError('Available RAM crossed 192 MiB personal metadata floor')
    for path in root.glob('*/person.json'):
        check()
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size > 128*1024:
            raise ValueError('Bounded real personal gallery metadata required')
        info = path.stat()
        import stat
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Owned regular personal metadata required')
        row = strict(path.read_bytes())
        if str(uuid.UUID(row['id'])) != row['id'] or path.parent.name != row['id']:
            raise ValueError('Personal metadata UUID/path mismatch')
        yield dict(id=row['id'], name=row['name'], references=len(row['references']),
            compatible_references=sum(ref.get('route', {}).get('tap') == 'O0' for ref in row['references']))


def summaries(binding, selection, data_root):
    if selection.embedding == 'anonymous':
        return []
    root, legacy, namespace = layout(binding, selection, data_root)
    if not root.exists():
        root = Path(legacy['root'])
    if root.is_symlink():
        raise ValueError('Personal gallery must be a real directory')
    result = list(iter_summaries(root))
    result.sort(key=lambda row:row['id'])
    return result


def open_store(binding, selection, data_root, config, people, n2_people, compat, guard, *, budget=None):
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
        from gallery_snapshot_io import copy_gallery_tree
        copy_gallery_tree(legacy['root'], temporary, root.parent/'SEED.json',
            budget if budget is not None else DiskBudget(1), guard,
            dict(legacy=legacy, namespace=namespace))
        temporary.rename(root)
    if namespace is None:
        from app.n2_models import redim_namespace
        model_namespace = redim_namespace(config)
        class ReDimStore(people.PersonalStore):
            def gallery(self, route, person_ids=None, *, alternate_advisory=False):
                result = super().gallery(route, person_ids, alternate_advisory=alternate_advisory)
                # Explicit representation metadata does not invent a C gate.
                # The retained baseline resolver still uses its original C088
                # settings; N2 verification remains calibration-blocked.
                result.namespace = deepcopy(model_namespace)
                result.calibration = dict(status='UNCALIBRATED_PERSONAL_DOMAIN')
                result.receipt.update(namespace=deepcopy(model_namespace),
                    calibration=deepcopy(result.calibration))
                return result
        return ReDimStore(root, config.asset('redimnet2_b2_fp32').sha256)
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
