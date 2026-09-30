"""Installed application saved-input D1 controls; README_D1_PROCESS_LAUNCH_V1.md."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import threading
import time

import d1_modes_v1 as modes
from d1_model_binding_v1 import bind_request, REASON



def request(mode_id):
    mode = modes.select(mode_id)
    return dict(schema='d1-saved-mode-selection.v1', selection=dict(id=mode_id,
        catalog_sha256=modes.CATALOG_SHA256, geometry=mode['geometry'], retained_run=mode['retained_run']),
        requires_fresh_process=True, requires_independent_session=True, source_scope='saved-input-only',
        live_start_available=False)


def adapter_request(selected):
    """Translate a validated public saved selection into the immutable adapter schema."""
    if type(selected) is not dict or type(selected.get('selection')) is not dict:
        raise ValueError('Explicit saved mode selection required')
    expected = request(selected['selection'].get('id'))
    encode = lambda value:json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    if encode(selected) != encode(expected):
        raise ValueError('Changed saved selection contract')
    return dict(schema='d1-application-selection.v1', selection=deepcopy(expected['selection']),
        requires_fresh_process=True, requires_independent_session=True, launchable=False, reason=REASON)


def controller_class(Base, root, spec, writer, closer, failure, *, endpoint):
    """Single admitted saved test per process; original live pipeline is unavailable."""
    root = Path(root)
    spec = deepcopy(spec)
    expected_frames = endpoint.expected_frames
    verify_binding = endpoint.verify_binding

    class D1SavedController(Base):
        def __init__(self, *args, **kwargs):
            self.d1_lock = threading.RLock()
            self.d1_cancel = threading.Event()
            self.d1_thread = None
            self.d1_selected = None
            self.d1_used = self.d1_owned = False
            self.d1_phase = 'SELECT_MODE'
            self.d1_error = None
            self.d1_samples = self.d1_frames = 0
            self.d1_outcome = self.d1_closure = None
            self.d1_transitions = []
            super().__init__(*args, **kwargs)

        def _d1_transition(self, phase):
            with self.d1_lock:
                labels = {'STARTING':'Loading saved diarizer.', 'RUNNING':'Processing saved audio. Microphone is off.',
                    'STOPPING':'Stopping saved diarizer; source/model still owned.',
                    'AWAITING_JOIN':'Saved worker drained; waiting for ownership closure.',
                    'STOPPED':'Saved diarizer stopped; source/model released.', 'ERROR':'Saved diarizer failed; inspect closure.'}
                if phase not in labels or len(self.d1_transitions) >= 32:
                    raise RuntimeError('Invalid or excessive D1 state transition')
                self.d1_phase = self.state = phase
                self.status = self.d1_error if phase == 'ERROR' and self.d1_error else labels[phase]
                if phase == 'ERROR':self.error = self.d1_error or self.status
                self.d1_transitions.append(dict(phase=phase, application_state=self.state,
                    owned=self.d1_owned, samples=self.d1_samples, frames=self.d1_frames))

        def _enqueue(self, action, *args, **kwargs):
            if action not in ('d1_select', 'd1_start', 'd1_stop', 'close'):
                raise RuntimeError('This admitted page supports saved diarizer tests only.')
            return super()._enqueue(action, *args, **kwargs)

        def d1_select(self, mode):
            self._enqueue('d1_select', mode=mode)

        def _do_d1_select(self, mode):
            with self.d1_lock:
                if self.d1_owned or self.d1_used or self.closed:
                    raise RuntimeError('Start a fresh application process before changing the diarizer.')
                value = request(mode)
                self.d1_selected = value
                self.d1_phase = 'READY' if mode == spec['mode'] else 'NOT_ADMITTED'

        def d1_start(self):
            self._enqueue('d1_start')

        def _do_d1_start(self):
            with self.d1_lock:
                if self.d1_owned or self.d1_used or self.d1_selected is None:
                    raise RuntimeError('Choose a mode in a fresh application process.')
                if self.d1_selected['selection']['id'] != spec['mode']:
                    raise RuntimeError('This saved passage admission does not cover the selected mode.')
                if self.engine is not None or self.consumer is not None or self.enrollment['state'] != 'IDLE':
                    raise RuntimeError('Another application operation owns the source or model.')
                selected = deepcopy(self.d1_selected)
                writer.json('START_REQUEST.json', dict(schema='d1-saved-application-start.v1',
                    selected=selected['selection'], scope='saved-input-only', capture=False,
                    source_sha256=spec['pins']['source.wav']['sha256'], maximum_samples=spec['prefix_samples'],
                    session_id=spec['session_id'], native_availability=spec['availability']))
                self.d1_used = self.d1_owned = True
                self._d1_transition('STARTING')
                self.d1_thread = threading.Thread(target=self._d1_run, args=(selected,), name='d1-saved-input', daemon=True)
                try:
                    self.d1_thread.start()
                except BaseException:
                    self.d1_owned = False  # start raised before any source/model owner existed.
                    self._d1_transition('ERROR')
                    raise

        def d1_stop(self):
            self.d1_cancel.set()  # Stop request does not release ownership.
            self._enqueue('d1_stop')

        def _do_d1_stop(self):
            thread = self.d1_thread
            if thread is None:
                return
            with self.d1_lock:
                if not self.d1_owned:
                    return
                self._d1_transition('STOPPING')
            self.d1_cancel.set()
            thread.join(60)
            if thread.is_alive():
                self.d1_error = 'Diarizer worker still owns its source/model.'
                raise TimeoutError(self.d1_error)
            with self.d1_lock:
                closure = deepcopy(self.d1_closure)
                if closure is None or not all(closure[k] for k in
                    ('source_closed', 'model_closed', 'model_pointer_empty', 'stream_pointer_empty', 'bundle_diarizer_empty')):
                    self.d1_error = 'Diarizer cleanup is incomplete; ownership remains held.'
                    raise RuntimeError(self.d1_error)
                closure['worker_joined'] = True
                closer.json('MODEL_CLOSURE.json', closure)
                self.d1_owned = False
                self._d1_transition('ERROR' if self.d1_error else 'STOPPED')

        def _do_close(self):
            self._do_d1_stop()
            if self.d1_owned:
                raise RuntimeError('Cannot release application lease while diarizer is owned.')
            return super()._do_close()

        def _d1_run(self, selected):
            import numpy as np
            import soundfile as sf
            import traceback
            source = model = bundle = None
            samples = frames = before_eof = 0
            chunks = []
            digest = hashlib.sha256()
            checks = []
            original = (modes.check_geometry, modes.check_loaded_paths, modes.verify_assets)
            def geometry(mode, observed):
                value = original[0](mode, observed)
                writer.json('CABI.json', dict(mode=mode, observed=observed));checks.append('actual_c_abi_before_create')
                return value
            def mapped(mode, campaign, paths):
                value = original[1](mode, campaign, paths)
                writer.jsonl('MAPPED.jsonl', dict(mode=mode, paths=sorted(set(p for p in paths if Path(p).name.startswith(('libnemo_speech_', 'libggml'))))))
                checks.append('actual_mapped_libraries');return value
            def assets(mode, campaign):
                value = original[2](mode, campaign)
                writer.json('ASSETS.json', value);checks.append('actual_asset_bytes');return value
            began = time.perf_counter();cpu = time.process_time()
            try:
                modes.check_geometry, modes.check_loaded_paths, modes.verify_assets = geometry, mapped, assets
                endpoint = verify_binding(root.parent, selected['selection']['id'])
                writer.json('ENDPOINT_BINDING.json', endpoint)
                bundle = bind_request(adapter_request(selected), root.parent, spec['installed_n2_source'])
                model = bundle.acquire_diarizer(spec['session_id'])
                assert model.session_id == spec['session_id']
                source = sf.SoundFile(root.parent/spec['retained_run']/'source.wav')
                assert source.samplerate == 16000 and source.channels == 1 and source.frames == 715127
                with self.d1_lock:self._d1_transition('RUNNING')
                def accept(update, kind):
                    nonlocal frames
                    assert update.session_id == spec['session_id'] and update.frame_start == frames
                    assert abs(update.audio_received_sec-samples/16000) < 1e-9
                    assert abs(update.seconds_per_frame-.01) < 1e-6
                    assert update.received_at_monotonic <= update.available_at_monotonic
                    assert update.frame_end*.01 <= samples/16000+.011
                    assert update.is_final is (kind == 'finish')
                    a = update.probabilities
                    assert a.shape == (update.frame_end-frames, 8) and np.isfinite(a).all()
                    assert not a.size or (a.min() >= 0 and a.max() <= 1)
                    writer.jsonl('CALLS.jsonl', dict(kind=kind, source_samples=samples, frame_start=frames,
                        frame_end=update.frame_end, compute_seconds=update.compute_sec))
                    frames = update.frame_end;chunks.append(a.copy())
                    with self.d1_lock:self.d1_samples, self.d1_frames = samples, frames
                while samples < spec['prefix_samples'] and not self.d1_cancel.is_set():
                    block = source.read(min(1600, spec['prefix_samples']-samples), dtype='float32')
                    assert len(block) and np.isfinite(block).all()
                    samples += len(block);digest.update(block.tobytes())
                    accept(model.push(block), 'push')
                    self.d1_cancel.wait(.1)  # Responsive Stop between complete ordered blocks.
                before_eof = frames
                accept(model.finish(), 'finish')
                array = np.concatenate(chunks);raw = io.BytesIO();np.save(raw, array, allow_pickle=False)
                writer.write('PROBABILITIES.npy', raw.getvalue())
                assert array.shape == (expected_frames(samples), 8)
                reference = np.load(root.parent/spec['retained_run']/'saved_full.npy', allow_pickle=False)
                error = float(np.max(np.abs(array[:before_eof]-reference[:before_eof]))) if before_eof else None
                if error is not None:assert error <= spec['tolerance']
                self.d1_outcome = dict(source_samples=samples, output_frames=frames, pre_eof_frames=before_eof,
                    eof_frames=frames-before_eof, endpoint_contract=endpoint, expected_output_frames=expected_frames(samples), pre_eof_max_abs=error, eof_tail_matched_reference=False,
                    source_prefix_float32_sha256=digest.hexdigest(), stop_requested=self.d1_cancel.is_set(),
                    source_position=source.tell(), session_id=model.session_id, native_checks=checks,
                    seconds=time.perf_counter()-began, cpu_seconds=time.process_time()-cpu)
            except BaseException as exc:
                self.d1_cancel.set()
                self.d1_error = type(exc).__name__+': '+str(exc)
                raw = traceback.format_exc().encode('utf-8')
                try:failure.write('WORKER_FAILURE.txt', raw)
                except Exception as retention:
                    self.d1_error += '; raw failure not retained: '+type(retention).__name__
            finally:
                errors = []
                if source is not None:
                    try:source.close()
                    except BaseException as exc:errors.append('source close: '+repr(exc))
                if bundle is not None:
                    try:bundle.close()
                    except BaseException as exc:errors.append('model close: '+repr(exc))
                modes.check_geometry, modes.check_loaded_paths, modes.verify_assets = original
                with self.d1_lock:
                    if errors:self.d1_error = (self.d1_error or '')+'; '.join(errors)
                    self.d1_closure = dict(source_closed=source is not None and source.closed,
                        model_closed=model is not None and model._closed, model_pointer_empty=model is not None and not model._model,
                        stream_pointer_empty=model is not None and not model._stream,
                        bundle_diarizer_empty=bundle is not None and bundle.diarizer is None,
                        samples=samples, frames=frames, session_id=spec['session_id'], worker_joined=False,
                        worker_error=self.d1_error, model_created=model is not None)
                    self._d1_transition('ERROR' if self.d1_error else 'AWAITING_JOIN')
                    # Caller must join and verify closure before clearing owned.

        def d1_snapshot(self):
            with self.d1_lock:
                return dict(selected=deepcopy(self.d1_selected), phase=self.d1_phase, owned=self.d1_owned,
                    used=self.d1_used, samples=self.d1_samples, frames=self.d1_frames, error=self.d1_error,
                    start_available=not self.d1_used and self.d1_phase == 'READY', admitted_mode=spec['mode'],
                    admitted_mode_label=spec['mode_label'], live_start_available=False,
                    saved_application_evidence=deepcopy(spec['saved_application_evidence']), availability=deepcopy(spec['availability']))

    return D1SavedController


def ui_class(Base):
    class D1SavedUI(Base):
        def _page(self, title, *args, **kwargs):
            body = super()._page(title, *args, **kwargs)
            if title == 'Mode':
                holder = self.button(body, 'Diarizer saved test', self.show_d1_saved, key='d1_saved_open')
                holder.pack(fill='x')
            return body

        def show_d1_saved(self):
            import tkinter as tk
            body = self._page('Diarizer saved test')
            self.d1_buttons = {}
            for mode, label in [('delayed', 'Delayed'), ('streaming', 'Streaming'), ('chunk52', 'Chunk52 (experimental)')]:
                b = self.button(body, label, lambda m=mode:self._call('d1_select', m))
                b.pack(fill='x');self.d1_buttons[mode] = b.button
            self.d1_status = tk.Label(body, wraplength=360, justify='left');self.d1_status.pack(fill='x')
            for action, label in [('start', 'Start saved passage'), ('stop', 'Stop and release')]:
                b = self.button(body, label, lambda a=action:self._call('d1_'+a))
                b.pack(fill='x');self.d1_buttons[action] = b.button
            def refresh():
                s = self.controller.d1_snapshot()
                self.d1_status.configure(text=(f"{s['phase']} / {s['samples']} samples / {s['frames']} frames\n"
                    f"All three modes have native passage checks. This admission enables {s['admitted_mode_label']} saved input.\n"
                    'Live capture is unavailable. Choose a fresh process for another run.\n'+(s['error'] or '')))
                self.d1_buttons['start'].configure(state='normal' if s['start_available'] else 'disabled')
                self.d1_buttons['stop'].configure(state='normal' if s['owned'] else 'disabled')
                for mode in ('delayed', 'streaming', 'chunk52'):
                    self.d1_buttons[mode].configure(state='disabled' if s['used'] else 'normal')
            self._page_update = refresh;refresh()
    return D1SavedUI
