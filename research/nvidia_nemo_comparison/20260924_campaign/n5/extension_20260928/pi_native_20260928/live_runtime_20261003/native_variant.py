"""Explicit measured-component thread2 variant. See README_NATIVE_VARIANT.md."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re

try:
    from .profiles import MODEL_SHA256, RuntimeSelection
    from .runtime_support import encoded, strict
except ImportError:
    from profiles import MODEL_SHA256, RuntimeSelection
    from runtime_support import encoded, strict

CAMPAIGN = Path('/home/peachyprototype/JustPeachy/research/nemotron-20260928')
JOB_PARENT = CAMPAIGN / 'live-runtime-tests-20261003'
MODEL_PATH = CAMPAIGN / 'd1-geometry-chunk52-a76-v1/D1.gguf'
SOURCE_SHA256 = '9d83b3c063f7cd0c56362648f0b8f8b5a9962e884f9a533631074c59f47c895c'
METADATA_SHA256 = '679ce2e01202723e7f94233df362ad38751f5380882a6e0964db63270dac4726'
INPUT_MANIFEST_SHA256 = 'c1fab2b4a3041412add0a1243919600b442785e4a76be9e65aa9b5397f090066'
WRAPPER_SHA256 = '9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f'
MEASURED_CORE_SHA256 = '210fee955c8728935e28598bffaf618868a9b9d57b76ac124c753f594a6e0f4d'
MEASURED_DESCRIPTOR_SHA256 = '3fdb0a0699e06a0608ca6cf5676676e3416bf291398271ebd3fd9a5bca41bc57'
COMPONENT_REVIEW_SHA256 = '8ef69dd6333c2a1432cb08fd34a905c60c49044cce869b89b43fc7cb3a926ef6'
COMPONENT_REVIEW = Path(__file__).resolve().parent / 'component_evidence/chunk52_threads2_review.json'
DEPENDENCIES = {}
for _stem, _pin, _suffixes in (
        ('libggml-base.so', 'aab12d9b5aac8e4a23c54f9fc1c24cd95d20c62ad8f7db44e918170ea28bf48b', ('', '.0', '.0.12.0')),
        ('libggml.so', '91e7e842bd2839bbd0b8a03ecdf9e8d9a3c4e278661915d8094b2a6cd81fc3bd', ('', '.0', '.0.12.0')),
        ('libggml-cpu.so', 'f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557', ('', '.0', '.0.12.0')),
        ('libnemo_speech_asr_c.so', WRAPPER_SHA256, ('', '.1'))):
    DEPENDENCIES.update({_stem + suffix: _pin for suffix in _suffixes})
_SEAL = object()


def _pin(value):
    if type(value) is not str or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Exact SHA256 required for native variant')
    return value


def _file(path, expected=None, maximum=8*1024**2):
    path = Path(path)
    if not path.is_absolute() or path.resolve(strict=True) != path or path.is_symlink() or not path.is_file():
        raise ValueError('Canonical regular isolated native variant file required')
    before = path.stat()
    if not 0 < before.st_size <= maximum:
        raise ValueError('Native variant file size bound')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    after = path.stat()
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
    if identity(before) != identity(after):
        raise ValueError('Native variant file changed while verifying')
    result = digest.hexdigest()
    if expected is not None and result != _pin(expected):
        raise ValueError('Native variant file pin mismatch: ' + path.name)
    return result, after.st_size


def _receipt(path, expected=None):
    digest, _ = _file(path, expected, maximum=262144)
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError('Native receipt changed while reading')
    value = strict(raw)
    if type(value) is not dict:
        raise ValueError('Native receipt must be an object')
    return value, digest


def require_selection(selection):
    if not isinstance(selection, RuntimeSelection):
        raise ValueError('RuntimeSelection required')
    selection.validate()
    if (selection.diarizer == 'nemotron' and selection.nemotron_profile == 'chunk52_threads2'
            and selection.allow_experimental and not selection.provisional_correction):
        return  # Distinct opt-in; exact measured core/evidence checks follow.
    if (selection.diarizer, selection.embedding, selection.input_source, selection.nemotron_profile,
            selection.allow_experimental) != ('nemotron', 'anonymous', 'saved', 'chunk52', True):
        raise ValueError('Thread2 variant is only admitted for explicit experimental saved anonymous Chunk52')
    if selection.provisional_correction or selection.embedding_schedule != 'continuous' or selection.speaker_attribution != 'retained':
        raise ValueError('Native variant component comparison cannot enable presentation/refinement changes')


@dataclass(frozen=True)
class VerifiedNativeVariant:
    descriptor_path: str
    descriptor_sha256: str
    build_result_sha256: str
    source_variant_sha256: str
    core_sha256: str
    component_review_sha256: str | None
    _document: bytes = field(repr=False)
    _seal: object = field(repr=False, compare=False)

    def document(self):
        return strict(self._document)

    def receipt(self):
        return dict(id='chunk52-native-threads2', descriptor_path=self.descriptor_path,
                    descriptor_sha256=self.descriptor_sha256, build_result_sha256=self.build_result_sha256,
                    source_variant_sha256=self.source_variant_sha256, core_sha256=self.core_sha256,
                    component_review_sha256=self.component_review_sha256,
                    source_sha256=SOURCE_SHA256, configured_graph_threads=2, observed_graph_threads=None,
                    quality_evaluated=False, native_qualified=False)


def verify_component_evidence(core_pin, descriptor_pin):
    """Exact completed 44.695 s comparison; never whole-pipeline authorization."""
    if core_pin != MEASURED_CORE_SHA256 or descriptor_pin != MEASURED_DESCRIPTOR_SHA256:
        raise ValueError('Integrated thread2 option requires the exact measured core and descriptor')
    review, pin = _receipt(COMPONENT_REVIEW, COMPONENT_REVIEW_SHA256)
    result, comparison = review.get('result', {}), review.get('reference_comparison', {})
    variant = result.get('native_variant', {})
    if (review.get('schema') != 'just-peachy.native-benchmark-review.v1' or
            result.get('status') != 'MEASURED_COMPONENT_COMPLETED' or result.get('native_execution') is not True or
            result.get('complete_eof') is not True or result.get('failure') is not None or
            result.get('delivered_samples') != 715127 or result.get('output_frames') != 4470 or
            result.get('closure') != dict(attempted=True, model_closed=True, pointers_empty=True) or
            result.get('input_sha256') != '0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8' or
            variant.get('core_sha256') != core_pin or variant.get('descriptor_sha256') != descriptor_pin or
            comparison.get('max_abs') != 0. or comparison.get('rows') != 4470 or comparison.get('columns') != 8 or
            comparison.get('reference_sha256') != '99c291b1e0f8a89e4ce3d196012a3d31fade1e4b252c6a0ce9a9976c5f3ed388' or
            result.get('sustained_realtime_qualified') is not False or review.get('quality_evaluated') is not False):
        raise ValueError('Exact completed component/numerical evidence required')
    return pin


def verify_measured_variant(selection):
    """Resolve only the explicitly selected measured thread2 profile's pinned build."""
    if selection.nemotron_profile != 'chunk52_threads2':
        raise ValueError('Explicit chunk52_threads2 profile required')
    review, _ = _receipt(COMPONENT_REVIEW, COMPONENT_REVIEW_SHA256)
    path = review['result']['native_variant']['descriptor_path']
    return verify_native_variant(path, MEASURED_DESCRIPTOR_SHA256, selection)


def verify_native_variant(descriptor_path, descriptor_sha256, selection):
    """Read a caller-pinned isolated build; never infer trust from a supplied flag."""
    require_selection(selection)
    descriptor_path = Path(descriptor_path)
    root = descriptor_path.parent
    if (descriptor_path.name != 'RUNTIME_VARIANT.json' or root.parent != JOB_PARENT or
            re.fullmatch('[a-z0-9-]{4,48}', root.name) is None):
        raise ValueError('Known isolated thread-build job root required')
    document, descriptor_pin = _receipt(descriptor_path, _pin(descriptor_sha256))
    build, build_pin = _receipt(root / 'BUILD_RESULT.json')
    source, source_pin = _receipt(root / 'SOURCE_VARIANT.json', _pin(build.get('source_variant_sha256')))
    owner, _ = _receipt(root / 'OWNER.json')
    exit_receipt, _ = _receipt(root / 'JOB_EXIT.json')
    if (set(owner) != {'pid', 'start_ticks', 'boot_id'} or
            any(type(owner[key]) is not int or owner[key] <= 0 for key in ('pid', 'start_ticks')) or
            type(owner['boot_id']) is not str or re.fullmatch('[0-9a-f-]{36}', owner['boot_id']) is None):
        raise ValueError('Exact build owner identity required')
    if (build.get('owner') != owner or exit_receipt.get('owner') != owner or
            exit_receipt.get('unit') != 'jp-v29-' + root.name + '.service' or
            type(exit_receipt.get('natural_returncode')) is not int or exit_receipt['natural_returncode'] != 0 or
            exit_receipt.get('error') is not None or exit_receipt.get('leases_released') is not True):
        raise ValueError('Successful closed build receipt required')
    if (build.get('status') != 'NATIVE_BUILD_COLLECTED_NOT_INFERENCE' or
            build.get('source_sha256') != SOURCE_SHA256 or
            build.get('input_manifest_sha256') != INPUT_MANIFEST_SHA256 or
            build.get('runtime_variant_sha256') != descriptor_pin or
            build.get('configured_native_graph_threads') != 2 or build.get('retained_lru_entries') != 8 or
            type(build.get('input_files_verified')) is not int or build['input_files_verified'] != 2436 or
            build.get('native_execution') is not False or build.get('models_loaded') is not False):
        raise ValueError('Exact successful thread2 build provenance required')
    if source != dict(schema='just-peachy.native-thread-source-variant.v1', source_sha256=SOURCE_SHA256,
                      retained_metadata_sha256=METADATA_SHA256, native_graph_threads_requested=2,
                      change='one graph-helper argument: 1 to 2', input_manifest_sha256=INPUT_MANIFEST_SHA256):
        raise ValueError('Exact thread2 source variant receipt required')
    _file(root / 'session.cpp', SOURCE_SHA256, maximum=65536)
    core_pin = _pin(build.get('core_sha256'))
    variant = document.get('native_variant')
    if variant != dict(id='chunk52-native-threads2', configured_graph_threads=2, source_sha256=SOURCE_SHA256,
                       core_sha256=core_pin, geometry=[52, 1, 0, 80, 264, 40], graph_cache_entries=8,
                       native_qualified=False, numerical_comparison_required=True):
        raise ValueError('Exact isolated Chunk52 thread2 variant required')
    runtime = root / 'runtime'
    if (document.get('schema') != 'just-peachy.n2.runtime.v1' or
            document.get('native_device') != {'kind': 'cpu', 'gpu_index': -1} or
            document.get('streaming_profile') != 'native_cm5_chunk52' or
            document.get('nemotron_model') != str(MODEL_PATH) or
            document.get('nemotron_model_sha256') != MODEL_SHA256 or
            document.get('nemotron_library') != str(runtime / 'libnemo_speech_asr_c.so.1') or
            document.get('nemotron_library_sha256') != WRAPPER_SHA256):
        raise ValueError('Variant must retain the exact model, CPU device and wrapper')
    rows = document.get('native_runtime_files')
    expected = dict(DEPENDENCIES, **{'libnemo_speech_asr.so': core_pin})
    if type(rows) is not list or len(rows) != len(expected) or rows != build.get('native_runtime_files'):
        raise ValueError('Complete build/descriptor library inventory must agree')
    seen = set()
    for row in rows:
        path = Path(row['path'])
        if (set(row) != {'path', 'sha256', 'bytes'} or path.parent != runtime or
                path.name in seen or path.name not in expected or row['sha256'] != expected[path.name]):
            raise ValueError('Isolated dependency path/name/pin differs')
        _, size = _file(path, expected[path.name])
        if type(row['bytes']) is not int or row['bytes'] != size:
            raise ValueError('Dependency size changed')
        seen.add(path.name)
    if {path.name for path in runtime.iterdir()} != set(expected):
        raise ValueError('Unexpected isolated runtime member')
    _file(root / 'build/libnemo_speech_asr.so', core_pin)
    # Adapter initialization also verifies the existing GGUF; no weights move.
    _file(MODEL_PATH.resolve(strict=True), MODEL_SHA256, maximum=512*1024**2)
    component_pin = verify_component_evidence(core_pin, descriptor_pin) if selection.nemotron_profile == 'chunk52_threads2' else None
    return VerifiedNativeVariant(str(descriptor_path), descriptor_pin, build_pin, source_pin,
                                 core_pin, component_pin, encoded(document), _SEAL)


def verified_core_pin(value, selection, document):
    """Binder gate: a raw descriptor/dict cannot relax the ordinary core pin."""
    require_selection(selection)
    if type(value) is not VerifiedNativeVariant or value._seal is not _SEAL:
        raise ValueError('Native variant must come from the pinned build verifier')
    if selection.nemotron_profile == 'chunk52_threads2' and value.component_review_sha256 != COMPONENT_REVIEW_SHA256:
        raise ValueError('Integrated thread2 profile requires measured component evidence')
    if encoded(document) != value._document or value.core_sha256 != document['native_variant']['core_sha256']:
        raise ValueError('Verified native document changed before binding')
    return value.core_sha256


# These checks describe actual loader state, independently of on-disk pin checks.
def _process_maps():
    with Path('/proc/self/maps').open() as stream:
        raw = stream.read(1024*1024+1)
    if len(raw) > 1024*1024:
        raise ValueError('Native loader map exceeds its explicit bound')
    return raw


def _native_mappings(raw):
    rows = []
    for line in raw.splitlines():
        parts = line.split(None, 5)
        if len(parts) != 6:
            continue
        path = parts[5]
        name = Path(path).name
        if not (name.startswith('libnemo_speech_') or name.startswith('libggml')):
            continue
        if path.endswith(' (deleted)') or '\\' in path:
            raise ValueError('Deleted or escaped native library mapping is not admitted')
        rows.append(dict(path=path, device=parts[3], inode=int(parts[4])))
    return rows


def require_fresh_variant_loader():
    """Call before model imports, and again immediately before variant CDLL."""
    if os.environ.get('LD_PRELOAD') or os.environ.get('LD_LIBRARY_PATH'):
        raise ValueError('Native variant requires unmodified fresh-process library search')
    if _native_mappings(_process_maps()):
        raise ValueError('Native variant requires no already-mapped D1/GGML library')


def verify_loaded_variant_libraries(document, *, require_cpu=True):
    """After CDLL, before C model creation: verify mapped paths, inode and bytes."""
    expected = {str(Path(row['path']).resolve()): row['sha256']
                for row in document['native_runtime_files']}
    rows = _native_mappings(_process_maps())
    seen, verified = set(), set()
    for row in rows:
        path = Path(row['path'])
        canonical = str(path.resolve(strict=True))
        if canonical != row['path'] or canonical not in expected:
            raise ValueError('Mapped native dependency is outside the pinned variant inventory')
        info = path.stat()
        device = '%x:%x' % (os.major(info.st_dev), os.minor(info.st_dev))
        observed_device = ':'.join(format(int(x,16),'x') for x in row['device'].split(':'))
        if row['inode'] != info.st_ino or observed_device != device:
            raise ValueError('Mapped native dependency inode/device differs from pinned file')
        if canonical not in verified:
            _file(path, expected[canonical], maximum=64*1024**2)
            verified.add(canonical)
        name = path.name
        if name.startswith('libnemo_speech_asr_c.so'):seen.add('wrapper')
        elif name == 'libnemo_speech_asr.so':seen.add('core')
        elif name.startswith('libggml-base.so'):seen.add('ggml-base')
        elif name.startswith('libggml-cpu.so'):seen.add('ggml-cpu')
        elif name.startswith('libggml.so'):seen.add('ggml')
    required = {'wrapper','core','ggml-base','ggml'} | ({'ggml-cpu'} if require_cpu else set())
    if not required <= seen:
        raise ValueError('Actual loaded native library set is incomplete')
    return dict(scope='actual_proc_maps_after_model_init' if require_cpu else 'actual_proc_maps_before_model_create', paths=sorted(verified),
                exact_inventory=True)
