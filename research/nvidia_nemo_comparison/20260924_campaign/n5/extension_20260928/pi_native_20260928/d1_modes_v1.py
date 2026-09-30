"""Pinned D1-only mode selection. See README_D1_MODES_V1.md."""
import os
if os.name == 'nt':
    import psutil
    psutil.Process().cpu_affinity([14])
    assert psutil.Process().cpu_affinity() == [14]
import argparse
import copy
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

HERE = Path(__file__).resolve().parent
CATALOG_SHA256 = 'ff431b358c7140addcddd95c313f2ec82272289dce2a9815e8d63b60f6bde7c5'
GEOMETRY_FIELDS = ('chunk_frames', 'right_context_frames', 'left_context_frames',
                   'fifo_frames', 'spkcache_frames', 'update_period_frames')


def catalog():
    raw = (HERE/'D1_MODE_CATALOG_V1.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOG_SHA256:
        raise ValueError('D1 catalog identity changed')
    return json.loads(raw)


def select(mode_id):
    """Return an isolated exact selection, with no fallback or implicit default."""
    if type(mode_id) is not str:
        raise ValueError('Explicit D1 mode name required')
    for mode in catalog()['modes']:
        if mode['id'] == mode_id:
            return copy.deepcopy(mode)
    raise ValueError('D1 mode unavailable: '+mode_id)


def check_inventory(mode_id, observed):
    expected = {x['name']: {'bytes': x['bytes'], 'sha256': x['sha256']}
                for x in select(mode_id)['assets']}
    if type(observed) is not dict or observed != expected:
        raise ValueError('D1 asset set/hash mismatch, including native runtime and CPU kernel')
    return True


def verify_assets(mode_id, campaign_root):
    mode = select(mode_id)
    root = Path(campaign_root).resolve()/mode['retained_run']
    observed = {}; identities = {}
    for item in mode['assets']:
        path = root/item['name']; real = path.resolve(strict=True)
        if not real.is_relative_to(root.resolve()):
            raise ValueError('D1 asset escapes selected retained run')
        stat = real.stat(); identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if identity not in identities:
            with real.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            after = real.stat()
            if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != identity:
                raise ValueError('D1 asset changed during verification')
            identities[identity] = {'bytes': stat.st_size, 'sha256': digest}
        observed[item['name']] = dict(identities[identity])
    check_inventory(mode_id, observed)
    return dict(mode=mode, root=str(root), assets=observed)


def check_geometry(mode_id, observed):
    expected = select(mode_id)['geometry']
    if type(observed) is not dict or set(observed) != set(expected):
        raise ValueError('Exact D1 C-ABI geometry fields required')
    if any(type(observed[k]) is not type(v) or observed[k] != v for k, v in expected.items()):
        raise ValueError('D1 geometry/preset mismatch')
    return True


def require_fresh_runtime(mapped_paths):
    # Equal C-wrapper hashes do not identify the linked main runtime or its LRU.
    for path in mapped_paths:
        if Path(path).name.startswith(('libnemo_speech_', 'libggml')):
            raise RuntimeError('D1 mode requires a fresh process; native runtime already mapped')


def check_loaded_paths(mode_id, campaign_root, mapped_paths):
    mode = select(mode_id); root = Path(campaign_root).resolve()/mode['retained_run']
    allowed = {(root/x['name']).resolve() for x in mode['assets'] if x['name'].startswith('nemo-arm64/lib/')}
    selected = [Path(p) for p in mapped_paths if Path(p).name.startswith(('libnemo_speech_', 'libggml'))]
    if any(p.resolve() not in allowed for p in selected):
        raise RuntimeError('Loaded D1 dependency belongs to another runtime')
    names = [p.name for p in selected]
    if not any(n.startswith('libnemo_speech_asr_c.so') for n in names) or not any(n == 'libnemo_speech_asr.so' for n in names):
        raise RuntimeError('Loaded D1 wrapper/main runtime not observed')
    return True


def mapped_paths():
    return [line.split(maxsplit=5)[5] for line in Path('/proc/self/maps').read_text().splitlines()
            if len(line.split(maxsplit=5)) == 6 and line.split(maxsplit=5)[5].startswith('/')]


def guarded_factory(mode_id, campaign_root):
    """Prepared integration API; caller must hold current admitted research lease.

    Does not acquire authority, schedule work, launch a process, or capture audio.
    Native execution through this NEW factory is not yet qualified by V85.
    """
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise RuntimeError('D1 native factory requires admitted aarch64 Linux process')
    import resource
    hard_as = resource.getrlimit(resource.RLIMIT_AS)[1]
    hard_stack = resource.getrlimit(resource.RLIMIT_STACK)[1]
    if not 0 < hard_as <= 768*1024**2 or not 0 < hard_stack <= 1024**2:
        raise RuntimeError('Required D1 AS/stack envelope absent')
    if os.sched_getaffinity(0) != {2, 3}:
        raise RuntimeError('Required D1 CPU affinity absent')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        if os.environ.get(key) != '1':
            raise RuntimeError('Required one-thread environment absent')
    require_fresh_runtime(mapped_paths())
    checked = verify_assets(mode_id, campaign_root); mode = checked['mode']; root = Path(checked['root'])
    module_name = '_jp_checked_d1_'+mode_id
    if module_name in sys.modules:
        raise RuntimeError('D1 module already imported in this process')
    spec = importlib.util.spec_from_file_location(module_name, root/'nemotron_diarization.py')
    module = importlib.util.module_from_spec(spec); sys.modules[module_name] = module
    spec.loader.exec_module(module)

    class SelectedDiarizer(module.NemotronDiarizer):
        def _bind(self):
            super()._bind()
            native_create = self._api.nemo_speech_diar_create
            def checked_create(pointer, output):
                config = ctypes.cast(pointer, ctypes.POINTER(module._ModelConfig)).contents
                observed = {key: int(getattr(config, key)) for key in GEOMETRY_FIELDS}
                observed.update(preset=config.preset.decode(), gpu=int(config.gpu))
                check_geometry(mode_id, observed)
                check_loaded_paths(mode_id, campaign_root, mapped_paths())
                return native_create(pointer, output)
            self._api.nemo_speech_diar_create = checked_create

    wrapper = root/'nemo-arm64/lib/libnemo_speech_asr_c.so.1'
    model = SelectedDiarizer(root/'D1.gguf', wrapper, profile=mode['profile'], gpu=-1,
                            expected_library_sha256=checked['assets']['nemo-arm64/lib/libnemo_speech_asr_c.so.1']['sha256'])
    try:
        check_loaded_paths(mode_id, campaign_root, mapped_paths())
    except BaseException:
        model.close()
        raise
    return model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', required=True)
    parser.add_argument('--verify-assets', type=Path, metavar='PI_CAMPAIGN_ROOT')
    args = parser.parse_args()
    if args.verify_assets:
        print(json.dumps(verify_assets(args.mode, args.verify_assets), indent=2, allow_nan=False))
    else:
        mode = select(args.mode)
        print(json.dumps({k:v for k,v in mode.items() if k not in ('assets','evidence')}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
