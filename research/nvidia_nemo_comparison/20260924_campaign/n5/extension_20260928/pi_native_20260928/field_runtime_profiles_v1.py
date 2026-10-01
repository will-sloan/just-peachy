"""Backend/embedding selection reused from the application; README_FIELD_RUNTIME_PROFILES_V1.md."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import time

SCHEMA = 'just-peachy.runtime-profile.v1'
TITANET_MODEL = 'e838520693f269e7984f55bc8eb3c2d60ccf246bf4b896d4be9bcabe3e4b0fe3'
TITANET_ONNX = '86b64bc03a7b151231f59745a8d36619fbc68b739a4abb253bd0d9ce0c350610'
TITANET_FRONTEND = '582f92d2fa2a29be70f6fdc13d67fc1376083ca66cb35401f8335ed85c4115b6'
TITANET_PREPROCESSING = 'nemo-cf724ac3-mel80-16k-eval-v1'
REDIMNET = '5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609'
ROOT = '/home/peachyprototype/JustPeachy/research/nemotron-20260928'
# Explicit retained routes. This is a configuration table, not a test sweep.
ROUTES = {
    'baseline': ('baseline', 'D0', 'E0', 'baseline', 'microphone', 'open_with_names'),
    'baseline-titanet': ('titanet', 'D0', 'E1', 'baseline', 'microphone', 'open_with_names'),
    'd1-delayed': ('nemotron_hybrid', 'D1', 'E0', 'delayed', 'microphone', 'open_with_names'),
    'd1-delayed-titanet': ('nemotron_titanet', 'D1', 'E1', 'delayed', 'microphone', 'open_with_names'),
    'd1-streaming-saved': ('nemotron_hybrid', 'D1', 'E0', 'streaming', 'saved', 'open_with_names'),
    'd1-streaming-titanet-saved': ('nemotron_titanet', 'D1', 'E1', 'streaming', 'saved', 'open_with_names'),
    'd1-chunk52-saved': ('nemotron_hybrid', 'D1', 'E0', 'chunk52', 'saved', 'open_with_names'),
    'd1-chunk52-titanet-saved': ('nemotron_titanet', 'D1', 'E1', 'chunk52', 'saved', 'open_with_names'),
    'd1-anonymous': ('nemotron_hybrid', 'D1', 'E0', 'delayed', 'microphone', 'anonymous_conversation'),
    'baseline-anonymous': ('baseline', 'D0', 'E0', 'baseline', 'microphone', 'anonymous_conversation'),
}
NATIVE_PROFILES = dict(delayed='native_v3_delayed', streaming='native_v3_streaming', chunk52='native_cm5_chunk52')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def select(name):
    if type(name) is not str or name not in ROUTES:
        raise ValueError('Unknown profile; no backend or embedding fallback')
    backend, diarizer, embedding, mode, source, ui_mode = ROUTES[name]
    return dict(profile=name, backend_key=backend, diarization=diarizer, embedding=embedding,
                engine_mode=mode, input_kind=source, ui_mode=ui_mode)


def strict_json(raw, maximum=131072):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        raise ValueError('Bounded metadata bytes required')
    def pairs(rows):
        value = {}
        for key, item in rows:
            if key in value:
                raise ValueError('Duplicate JSON key')
            value[key] = item
        return value
    def bad(value):
        raise ValueError('Nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)


def titanet_namespace(manifest):
    expected = dict(backend_id='titanet_large_fp32', dimension=192,
                    source_model_sha256=TITANET_MODEL, preprocessing_version=TITANET_PREPROCESSING,
                    normalization='l2', minimum_samples=8000)
    for key, value in expected.items():
        if type(manifest.get(key)) is not type(value) or manifest[key] != value:
            raise ValueError('Previous pinned TitaNet representation changed: ' + key)
    for key, name, pin in (('onnx', 'titanet_embedding.onnx', TITANET_ONNX),
                           ('frontend', 'titanet_frontend.npz', TITANET_FRONTEND)):
        if manifest.get(key) != dict(filename=name, sha256=pin):
            raise ValueError('Exact previous TitaNet artifact required: ' + key)
    return dict(model_sha256=TITANET_MODEL, preprocessing=TITANET_PREPROCESSING,
                dimension=192, normalization='L2', minimum_samples=8000,
                onnx_sha256=TITANET_ONNX, frontend_sha256=TITANET_FRONTEND)


def verify_titanet(directory, *, deadline, guard):
    """Read existing artifacts only. No model import, download, conversion or copy."""
    if not callable(guard) or not isinstance(deadline, (int, float)) or isinstance(deadline, bool):
        raise ValueError('Caller resource guard and monotonic deadline required')
    remaining = deadline - time.monotonic()
    if not 0 < remaining <= 600:
        raise ValueError('Bounded current verification deadline required')
    root = Path(directory).absolute()
    for parent in (root, *root.parents):
        if parent.is_symlink() or not parent.is_dir():
            raise ValueError('Existing real asset directory required')
    def read(name, maximum, expected=None):
        guard()
        path = root/name
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum or before.st_nlink != 1:
            raise ValueError('Bounded real artifact')
        h = hashlib.sha256()
        raw = bytearray() if name.endswith('.json') else None
        count = 0
        with path.open('rb') as stream:
            while True:
                guard()
                if time.monotonic() >= deadline:
                    raise TimeoutError('Asset verification deadline')
                block = stream.read(16384)
                if not block:
                    break
                count += len(block); h.update(block)
                if raw is not None:
                    raw.extend(block)
                if count > before.st_size:
                    raise ValueError('Asset grew while read')
        after = path.lstat()
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
        if any(getattr(before, k) != getattr(after, k) for k in fields) or count != before.st_size:
            raise ValueError('Asset identity changed while read')
        if expected is not None and h.hexdigest() != expected:
            raise ValueError('Existing TitaNet artifact hash mismatch')
        return dict(name=name, bytes=count, sha256=h.hexdigest()), bytes(raw) if raw is not None else None
    manifest_row, raw = read('titanet_manifest.json', 16384)
    manifest = strict_json(raw, 16384)
    namespace = titanet_namespace(manifest)
    onnx, _ = read('titanet_embedding.onnx', 88610787, TITANET_ONNX)
    frontend, _ = read('titanet_frontend.npz', 84358, TITANET_FRONTEND)
    if onnx['bytes'] != 88610787 or frontend['bytes'] != 84358:
        raise ValueError('Pinned prior export sizes changed')
    guard()
    return dict(schema='just-peachy.titanet-local-assets.v1', directory=str(root),
                namespace=namespace, files=[manifest_row, onnx, frontend],
                model_loaded=False, native_execution=False)


def backend_manifest(catalog_raw, profile):
    """Select the old implementation and derive a new mode-specific immutable ID."""
    route = select(profile)
    catalog = strict_json(catalog_raw, 1024*1024)
    if catalog.get('schema') != 'just-peachy.backend-catalog.v1':
        raise ValueError('Existing backend catalogue required')
    rows = catalog.get('backends')
    if type(rows) is not list or not 1 <= len(rows) <= 64:
        raise ValueError('Bounded backend catalogue')
    if len({r['key'] for r in rows}) != len(rows):
        raise ValueError('Duplicate backend key')
    for row in rows:
        if row['manifest_id'] != 'sha256:' + digest(row['composition']):
            raise ValueError('Original backend composition digest changed')
    matches = [r for r in rows if r['key'] == route['backend_key']]
    if len(matches) != 1:
        raise ValueError('Previous backend implementation missing')
    old = matches[0]
    comp = deepcopy(old['composition'])
    if 'n3' in comp or 'Nemotron' in comp['components']['asr']['name']:
        raise ValueError('Sherpa ASR must be retained')
    enrollment = comp['components']['enrollment']
    expected_model = TITANET_MODEL if route['embedding'] == 'E1' else REDIMNET
    if route['embedding'] == 'E1':
        if (enrollment.get('artifact_sha256') != expected_model
                or enrollment.get('onnx_sha256') != TITANET_ONNX
                or enrollment.get('frontend_sha256') != TITANET_FRONTEND):
            raise ValueError('Original TitaNet model/export pins differ')
    elif not any(a['sha256'] == expected_model for a in enrollment['assets']):
        raise ValueError('Original ReDimNet model pin differs')
    if route['backend_key'] == 'baseline':
        if comp.get('n2'):
            raise ValueError('Original baseline path changed')
    else:
        if comp['n2']['diarization'] != route['diarization'] or comp['n2']['embedding'] != route['embedding']:
            raise ValueError('Previous actual resident-model route differs')
    if route['diarization'] == 'D1':
        comp['n2']['streaming_profile'] = NATIVE_PROFILES[route['engine_mode']]
    encoder = 'TitaNet' if route['embedding'] == 'E1' else 'ReDimNet'
    diarizer = 'Nemotron' if route['diarization'] == 'D1' else 'Pyannote'
    label = 'Sherpa + ' + diarizer + ' + ' + encoder
    if route['diarization'] == 'D1':
        label += ' · ' + route['engine_mode'].capitalize()
    if route['ui_mode'] == 'anonymous_conversation':
        label += ' · Anonymous'
    if route['input_kind'] == 'saved':
        label += ' · Saved audio'
    return dict(schema=SCHEMA, selection=route, label=label,
                source_manifest_id=old['manifest_id'], backend_manifest_id='sha256:' + digest(comp),
                composition=comp, native_availability='NOT_YET_QUALIFIED',
                automatic_capture=False, silent_fallback=False)


def runtime_document(original, profile, *, d1_catalog_raw=None, native_titanet_manifest=None, titanet_manifest_raw=None):
    """Pure configuration; the caller must hash-verify deployed artifacts independently."""
    route = select(profile)
    if type(original) is not dict or original.get('schema') != 'just-peachy.n2.runtime.v1':
        raise ValueError('Existing N2 runtime document required')
    result = deepcopy(original)
    if result.get('native_device') != dict(kind='cpu', gpu_index=-1):
        raise ValueError('Existing CPU-only runtime required')
    if route['diarization'] == 'D1':
        if (type(d1_catalog_raw) is not bytes or hashlib.sha256(d1_catalog_raw).hexdigest()
                != 'ff431b358c7140addcddd95c313f2ec82272289dce2a9815e8d63b60f6bde7c5'):
            raise ValueError('Retained complete D1 mode catalogue pin required')
        modes = strict_json(d1_catalog_raw)['modes']
        selected = next(row for row in modes if row['id'] == route['engine_mode'])
        if selected['profile'] != NATIVE_PROFILES[route['engine_mode']]:
            raise ValueError('Exact retained D1 native profile required')
        native_root = PurePosixPath(ROOT)/selected['retained_run']
        assets = {row['name']: row for row in selected['assets']}
        library = 'nemo-arm64/lib/libnemo_speech_asr_c.so.1'
        result.update(streaming_profile=selected['profile'], nemotron_model=str(native_root/'D1.gguf'),
            nemotron_library=str(native_root/library), nemotron_library_sha256=assets[library]['sha256'],
            native_runtime_files=[dict(path=str(native_root/name), sha256=row['sha256'])
                for name, row in sorted(assets.items()) if name.startswith('nemo-arm64/lib/')])
        if not result['native_runtime_files']:
            raise ValueError('Complete retained native library set required')
    keys = ('titanet_manifest', 'titanet_manifest_sha256', 'embedding_namespace')
    for key in keys:
        result.pop(key, None)
    if route['embedding'] == 'E1':
        if type(native_titanet_manifest) is not str:
            raise ValueError('Explicit installed TitaNet manifest required')
        path = PurePosixPath(native_titanet_manifest)
        if (str(path) != native_titanet_manifest or not path.is_relative_to(ROOT)
                or path.name != 'titanet_manifest.json' or '..' in path.parts):
            raise ValueError('Canonical local deployed TitaNet asset path required')
        manifest = strict_json(titanet_manifest_raw, 16384)
        result.update(titanet_manifest=native_titanet_manifest,
                      titanet_manifest_sha256=hashlib.sha256(titanet_manifest_raw).hexdigest(),
                      embedding_namespace=titanet_namespace(manifest))
    elif native_titanet_manifest is not None or titanet_manifest_raw is not None:
        raise ValueError('ReDimNet must not acquire a TitaNet dependency')
    return result


def desktop_entry(profile, release_id, label):
    """Prepared .desktop content only; launcher must enforce the installed profile pin."""
    select(profile)
    if type(release_id) is not str or not re.fullmatch('field-runtime-v[1-9][0-9]*', release_id):
        raise ValueError('Exact versioned release required')
    if type(label) is not str or not 1 <= len(label) <= 150 or any(c in label for c in '\r\n\\'):
        raise ValueError('Single-line desktop label required')
    executable = ROOT + '/' + release_id + '/bin/launch-profile'
    return ('[Desktop Entry]\nType=Application\nVersion=1.0\nName=Just Peachy · ' + label +
            '\nComment=Open idle; Start recording explicitly.\nExec=' + executable +
            ' --profile ' + profile + '\nTerminal=false\nCategories=AudioVideo;Audio;\n'
            'StartupNotify=true\nX-JustPeachy-CaptureOnLaunch=false\n').encode()
