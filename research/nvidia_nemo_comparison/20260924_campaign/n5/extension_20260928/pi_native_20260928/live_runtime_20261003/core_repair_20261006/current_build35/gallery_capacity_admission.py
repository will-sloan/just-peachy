"""Capacity admission for normal galleries; README_GALLERY_CAPACITY_STORE.md.

Derive only the inherited profile-count conditions from their exact installed
source. Namespace, backend, receipt integrity, model math and C gates stay intact.
"""
import ast
from copy import deepcopy
import hashlib
import inspect
import os
from pathlib import Path
import stat
import textwrap

from runtime_support import encoded, resource_snapshot

RAM_FLOOR = 192*1024**2
SOURCES = {
    'PipelineEngine': ('vendor/edge_speech_pipeline/runtime.py',
        '64c8021099be59578f1408228bd4dda6b76821f9efd29b2f68172b3f0938f78c'),
    'N2Engine': ('app/n2_pipeline.py',
        '6312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491'),
}


def allocation_bytes(metadata_bytes, vector_bytes):
    """Reserve JSON object copies plus centroid/matrix/advisory working arrays.

    Multipliers bound expected Python/NumPy working allocations from actual
    serialized metadata and vector bytes. They do not limit a roster count.
    """
    if any(type(value) is not int or value < 0 for value in (metadata_bytes, vector_bytes)):
        raise ValueError('Actual nonnegative gallery input byte sizes required')
    return 12*metadata_bytes+4*vector_bytes


def memory_guard(guard, reservation):
    guard()
    measured = resource_snapshot()
    if measured['available_ram'] < RAM_FLOOR+reservation:
        raise MemoryError('Gallery working allocation cannot preserve the 192 MiB RAM floor')
    if os.name != 'nt':
        import resource
        maximum = resource.getrlimit(resource.RLIMIT_AS)[0]
        current = measured.get('virtual_bytes')
        if maximum != resource.RLIM_INFINITY and (current is None or current+reservation > maximum):
            raise MemoryError('Gallery allocation exceeds the existing address-space budget')
    return measured


def _same(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def _derive(raw, owner):
    tree = ast.parse(raw)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == owner]
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef)
               and node.name == '_admit_research_gallery'] if len(classes) == 1 else []
    if len(methods) != 1 or methods[0].decorator_list:
        raise ValueError('Exactly one pinned gallery admission method required')
    original = methods[0]
    changed = deepcopy(original)
    expected = ast.parse('admitted.receipt["loaded_count"] > maximum_profiles', mode='eval').body
    n2_expected = ast.parse("gallery.receipt.get('loaded_count') != len(gallery.ids) or len(gallery.ids) > maximum_profiles", mode='eval').body
    found = 0
    class Counts(ast.NodeTransformer):
        def visit_If(self, node):
            nonlocal found
            if owner == 'PipelineEngine' and _same(node.test, expected):
                if node.orelse:
                    raise ValueError('Unexpected baseline count-gate alternative')
                found += 1
                return None
            if owner == 'N2Engine' and _same(node.test, n2_expected):
                found += 1
                node.test = deepcopy(n2_expected.values[0])
            return self.generic_visit(node)
    changed = Counts().visit(changed)
    if found != 1:
        raise ValueError('Exact inherited gallery count condition differs')
    return original, changed


def bind_capacity_admission(parent, installed_root, manifest, guard):
    """Return an instance method; never monkeypatch the immutable parent class."""
    method = parent._admit_research_gallery
    owner = method.__qualname__.split('.')[0]
    if owner not in SOURCES:
        raise ValueError('Unrecognized ordinary gallery admission owner')
    relative, pin = SOURCES[owner]
    source = Path(installed_root)/relative
    info = source.lstat()
    if (source.is_symlink() or getattr(info, 'st_file_attributes', 0)&0x400
            or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or Path(inspect.getsourcefile(method)).resolve() != source.resolve()
            or manifest[relative]['sha256'] != pin):
        raise ValueError('Exact installed gallery admission source/origin required')
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('Installed gallery admission source changed')
    original, changed = _derive(raw, owner)
    actual = ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]
    if not _same(original, actual):
        raise ValueError('Loaded admission method differs from pinned source')
    namespace = dict(method.__globals__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[changed], type_ignores=[])),
                 str(source)+'#capacity-count', 'exec'), namespace)
    derived = namespace['_admit_research_gallery']

    def admit(engine, gallery, maximum_profiles):
        # Normal product construction has already validated every personal
        # record/vector. Never broaden the research manifest-path parser here.
        from edge_speech_pipeline.research_identity_v3 import ResearchGallery
        from app.n2_identity import N2Gallery
        if not isinstance(gallery, (ResearchGallery, N2Gallery)):
            raise ValueError('Capacity admission requires an actual already-validated gallery object')
        matrix = gallery.matrix
        receipt = gallery.receipt
        dimension = receipt.get('dimension')
        if (dimension not in (192, 384) or matrix.shape != (len(gallery.ids), dimension)
                or str(matrix.dtype) != 'float32' or receipt.get('loaded_count') != len(gallery.ids)):
            raise ValueError('Actual gallery count/vector representation differs')
        metadata_bytes = len(encoded(receipt))
        matrix_bytes = int(matrix.nbytes)
        reservation = allocation_bytes(metadata_bytes, matrix_bytes)
        memory_guard(guard, reservation)
        import numpy as np
        if not np.isfinite(matrix).all():
            raise ValueError('Actual gallery vectors must remain finite')
        result = derived(engine, gallery, maximum_profiles)
        memory_guard(guard, 0)
        engine._gallery_capacity_admission = dict(
            schema='just-peachy.gallery-capacity-admission.v1', loaded_count=len(result.ids),
            dimension=dimension, metadata_bytes=metadata_bytes, matrix_bytes=matrix_bytes,
            reserved_working_bytes=reservation, available_ram_floor_bytes=RAM_FLOOR,
            count_quota_enforced=False, historical_max_gallery_profiles=maximum_profiles,
            source_path=relative, source_sha256=pin, model_namespace_checks_unchanged=True)
        return result
    return admit
