"""Bind installed D1 to one bounded live run. See README_FIELD_LIVE_D1_V1.md."""
from copy import deepcopy
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import threading

MAX_SAMPLES = 2080000
MAX_FRAMES = 13001
MODE = 'delayed'
PROFILE = 'native_v3_delayed'
_installed = False


def expected_frames(samples):
    """Source-derived endpoint rule, extended bound; not new native EOF evidence."""
    if type(samples) is not int or not 0 <= samples <= MAX_SAMPLES:
        raise ValueError('Live D1 requires an integer count from 0 through 2080000')
    return 0 if samples == 0 else samples // 160 + 1


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def envelope():
    if platform.system() != 'Linux' or platform.machine() != 'aarch64':
        raise RuntimeError('Live D1 requires the admitted aarch64 process')
    import resource
    if os.sched_getaffinity(0) != {2, 3}:
        raise RuntimeError('Live D1 affinity changed')
    if not 0 < resource.getrlimit(resource.RLIMIT_AS)[1] <= 768*1024**2:
        raise RuntimeError('Live D1 address-space limit absent')
    if not 0 < resource.getrlimit(resource.RLIMIT_STACK)[1] <= 1024**2:
        raise RuntimeError('Live D1 stack limit absent')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        if os.environ.get(key) != '1':
            raise RuntimeError('Live D1 thread environment changed')


def bind(base, campaign, manifest, runtime_document, catalog, outputs, request_stop):
    """Patch the exact installed class and resident acquisition in a fresh process.

    Importing/binding does not construct a model. The unchanged installed resident
    acquisition calls the checked subclass only after the live entry owns Start.
    The caller owns admission, source lease, deadline, all output slots and Close.
    """
    global _installed
    if _installed:
        raise RuntimeError('Live D1 binding is permanent for this process')
    envelope()
    import d1_modes_v1 as modes
    import d1_endpoint_contract_v3 as endpoint
    from app import n2_models as resident
    from edge_speech_pipeline import nemotron_diarization as native
    base = Path(base).resolve(); campaign = Path(campaign).resolve()
    for module, relative in ((resident, 'app/n2_models.py'),
                             (native, 'vendor/edge_speech_pipeline/nemotron_diarization.py')):
        path = Path(module.__file__).resolve()
        if path != base/relative or digest(path) != manifest[relative]['sha256']:
            raise ValueError('Installed D1 origin/manifest mismatch')
    modes.require_fresh_runtime(modes.mapped_paths())
    selected = modes.select(MODE)
    method = catalog.validate(MODE, catalog.request(MODE))
    if method['resources']['executable_graph_lru'] != 1 or method['resources']['metadata_arena_mib'] != 2:
        raise ValueError('Wrong delayed resource method')
    document = deepcopy(runtime_document)
    if document.get('streaming_profile') != PROFILE or canonical(document.get('native_device')) != canonical(dict(kind='cpu',gpu_index=-1)):
        raise ValueError('Actual live runtime must select explicit delayed CPU D1')
    model_path = Path(document['nemotron_model']).resolve()
    library_path = Path(document['nemotron_library']).resolve()
    selected_root = campaign/selected['retained_run']
    selected_library = (selected_root/'nemo-arm64/lib/libnemo_speech_asr_c.so.1').resolve()
    if library_path != selected_library or not model_path.is_relative_to(campaign):
        raise ValueError('Unmapped live native model/library path')
    assets = {row['name']:row for row in selected['assets']}
    wrapper_sha = assets['nemo-arm64/lib/libnemo_speech_asr_c.so.1']['sha256']
    if document['nemotron_library_sha256'] != wrapper_sha:
        raise ValueError('Live C wrapper differs from method assets')
    state = dict(schema='just-peachy.live-d1-binding.v1',mode=MODE,profile=PROFILE,
        maximum_samples=MAX_SAMPLES,maximum_frames=MAX_FRAMES,acquisition_attempted=False,
        constructor_attempted=False,constructor_completed=False,initial_reset_attempted=False,
        closed=False,failed=None,samples=0,frames=0,pushes=0,finish_observed=False,
        endpoint=None,observed_c_abi=None,mapped_checks=0,method=method,
        installed_origin=str(native.__file__),installed_sha256=manifest['vendor/edge_speech_pipeline/nemotron_diarization.py']['sha256'],
        native_empty_input_tested=False,accuracy_tested=False,live_runtime_accepted=False)
    lock = threading.RLock()
    original = native.NemotronDiarizer
    acquire = resident.N2ResidentModels.acquire_diarizer

    def failed(exc):
        # The real source Stop callback runs before diagnostic publication.
        request_stop('D1: '+str(exc)[:512])
        with lock:
            if state['failed'] is None:
                state['failed'] = type(exc).__name__+': '+str(exc)[:512]
                outputs.fail('native',exc,lambda:request_stop('D1_FAILURE'))

    class CheckedInstalledDiarizer(original):
        def __init__(self, model, library, *, profile='low_latency', session_id=None,
                     expected_library_sha256=None, gpu=-1):
            with lock:
                if not state['acquisition_attempted'] or state['constructor_attempted'] or state['failed']:
                    raise RuntimeError('One installed D1 construction through resident acquisition only')
                state['constructor_attempted'] = True
            try:
                if (Path(model).resolve()!=model_path or Path(library).resolve()!=library_path or
                    profile!=PROFILE or type(gpu) is not int or gpu!=-1 or
                    expected_library_sha256!=wrapper_sha or type(session_id) is not str or not session_id):
                    raise ValueError('Installed D1 constructor differs from admitted runtime')
                envelope();modes.require_fresh_runtime(modes.mapped_paths())
                modes.verify_assets(MODE,campaign)
                if digest(model_path)!=assets['D1.gguf']['sha256']:
                    raise ValueError('Actual runtime model alias differs from selected Q8 asset')
                state['endpoint']=endpoint.verify_binding(campaign,MODE)
                super().__init__(model,library,profile=profile,session_id=session_id,
                                 expected_library_sha256=expected_library_sha256,gpu=gpu)
                modes.check_loaded_paths(MODE,campaign,modes.mapped_paths())
                state['mapped_checks']+=1
                state['constructor_completed']=True
                state['session_id']=session_id
            except BaseException as exc:
                try:
                    if hasattr(self,'_lock'):self.close()
                finally:failed(exc)
                raise

        def _bind(self):
            super()._bind()
            create_native=self._api.nemo_speech_diar_create
            def checked_create(pointer,result):
                config=ctypes.cast(pointer,ctypes.POINTER(native._ModelConfig)).contents
                observed={key:int(getattr(config,key)) for key in modes.GEOMETRY_FIELDS}
                observed.update(preset=config.preset.decode(),gpu=int(config.gpu))
                modes.check_geometry(MODE,observed)
                if Path(os.fsdecode(config.model_path)).resolve()!=model_path:
                    raise ValueError('C-ABI model pointer changed')
                modes.check_loaded_paths(MODE,campaign,modes.mapped_paths())
                state['mapped_checks']+=1;state['observed_c_abi']=observed
                return create_native(pointer,result)
            self._api.nemo_speech_diar_create=checked_create

        def reset(self, *, session_id=None):
            with lock:
                if state['initial_reset_attempted'] or state['constructor_completed'] or state['failed']:
                    exc=RuntimeError('A new D1 session requires a new admitted process')
                    failed(exc);raise exc
                state['initial_reset_attempted']=True
            return super().reset(session_id=session_id)

        def _update(self,received_at,started,final):
            # Bound native-reported rows before the installed NumPy allocation.
            count=int(self._api.nemo_speech_diar_frame_count(self._stream))
            base_count=int(self._api.nemo_speech_diar_frame_probs_start(self._stream))
            if not 0<=base_count<=count<=MAX_FRAMES:
                raise RuntimeError('Native frame count exceeds live allocation')
            return super()._update(received_at,started,final)

        def push(self,samples, *, received_at_monotonic=None):
            try:
                with self._lock:
                    if state['failed'] or state['finish_observed']:
                        raise RuntimeError('Live D1 is terminal')
                    if state['samples']+len(samples)>MAX_SAMPLES:
                        raise ValueError('Live D1 sample ceiling reached before native push')
                    value=super().push(samples,received_at_monotonic=received_at_monotonic)
                    state.update(samples=int(self._samples_received),frames=int(self._frames_delivered),pushes=state['pushes']+1)
                    return value
            except BaseException as exc:failed(exc);raise

        def finish(self):
            try:
                with self._lock:
                    if state['failed']:raise RuntimeError('Failed D1 cannot retry finish')
                    value=super().finish()
                    if self._frames_delivered!=expected_frames(int(self._samples_received)):
                        raise RuntimeError('Actual live EOF violates source-derived endpoint count')
                    state.update(samples=int(self._samples_received),frames=int(self._frames_delivered),finish_observed=True)
                    return value
            except BaseException as exc:failed(exc);raise

        def close(self):
            try:
                super().close()
                state['closed']=bool(self._closed and not self._stream and not self._model)
            except BaseException as exc:failed(exc);raise

    def once(bundle,session_id):
        try:
            with lock:
                if state['acquisition_attempted'] or state['failed'] or bundle.diarizer is not None:
                    raise RuntimeError('Second resident D1 acquisition is unavailable')
                state['acquisition_attempted']=True
                if bundle.diarization!='D1' or canonical(bundle.document)!=canonical(document):
                    raise ValueError('Resident D1 document changed')
            return acquire(bundle,session_id)
        except BaseException as exc:failed(exc);raise

    _installed=True
    native.NemotronDiarizer=CheckedInstalledDiarizer
    resident.N2ResidentModels.acquire_diarizer=once
    return state
