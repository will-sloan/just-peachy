"""One changed native factory passage; README_D1_CHUNK52_BINDING_V1.md."""
import hashlib
import io
import json
from pathlib import Path
import time


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def run(root, admission):
    import numpy as np
    import soundfile as sf
    import d1_modes_v1 as modes
    from field_sidecar_budget_v1 import GroupWriter
    root = Path(root)
    spec = json.loads((root/'code/D1_CHUNK52_BINDING_INPUT_V1.json').read_bytes())
    assert spec['mode'] == 'chunk52' and spec['prefix_samples'] == 70327 and spec['push_samples'] == 1600
    old = root.parent/spec['retained_run']
    for name, pin in spec['pins'].items():
        if name == 'REVIEW.json':  # Independently verified host receipt, not copied into old Pi evidence.
            continue
        assert (old/name).stat().st_size == pin['bytes'] and sha(old/name) == pin['sha256']
    assert admission['declared_passage_directories'] == ['passage', 'passage_closure']
    assert admission['passage_directory_reserve_bytes'] == 2*65536
    for name in admission['declared_passage_directories']:
        (root/name).mkdir()
    assert sum(max(p.stat().st_size, p.stat().st_blocks*512) for p in [root/'passage', root/'passage_closure']) <= 2*65536
    writer = GroupWriter(root/'passage', admission['passage_limits'])
    closer = GroupWriter(root/'passage_closure', admission['passage_closure_limits'])
    with sf.SoundFile(old/'source.wav') as source:
        assert source.samplerate == 16000 and source.channels == 1 and source.frames == 715127
        audio = source.read(spec['prefix_samples'], dtype='float32')
    assert audio.shape == (70327,) and np.isfinite(audio).all()
    reference = np.load(old/'saved_full.npy', allow_pickle=False)
    assert reference.shape == (4470, 8)
    native_checks = []
    original_geometry, original_paths, original_assets = modes.check_geometry, modes.check_loaded_paths, modes.verify_assets

    def checked_geometry(mode, observed):
        value = original_geometry(mode, observed)
        writer.json('CABI.json', dict(mode=mode, observed=observed))
        native_checks.append('actual_c_abi_before_create')
        return value

    def checked_paths(mode, campaign, paths):
        value = original_paths(mode, campaign, paths)
        writer.jsonl('MAPPED.jsonl', dict(mode=mode, paths=sorted(set(p for p in paths if Path(p).name.startswith(('libnemo_speech_', 'libggml'))))))
        native_checks.append('actual_mapped_libraries')
        return value

    def checked_assets(mode, campaign):
        value = original_assets(mode, campaign)
        writer.json('ASSETS.json', value)
        native_checks.append('actual_asset_bytes')
        return value

    modes.check_geometry, modes.check_loaded_paths, modes.verify_assets = checked_geometry, checked_paths, checked_assets
    from d1_model_binding_v1 import bind_request
    assert sha(spec['installed_n2_source']) == spec['installed_n2_sha256']
    bundle = bind_request(spec['application_request'], root.parent, spec['installed_n2_source'])
    model = None
    cursor = samples = pre_eof_frames = 0
    values, calls = [], []
    started = time.perf_counter()
    completed = False
    try:
        model = bundle.acquire_diarizer('d1-chunk52-binding-v1')
        assert model is bundle.diarizer and model.session_id == 'd1-chunk52-binding-v1'
        load_seconds = time.perf_counter()-started
        session = model.session_id  # Explicit independent session bound before the first sample.
        manifest = model.manifest()
        began = time.perf_counter(); cpu = time.process_time()

        def accept(update, kind):
            nonlocal cursor
            assert update.session_id == session and update.frame_start == cursor
            assert abs(update.audio_received_sec-samples/16000) < 1e-9
            assert abs(update.seconds_per_frame-.01) < 1e-6
            assert update.received_at_monotonic <= update.available_at_monotonic
            assert update.frame_end*.01 <= samples/16000+.011
            assert update.is_final is (kind == 'finish')
            assert update.probabilities.shape == (update.frame_end-cursor, 8)
            assert np.isfinite(update.probabilities).all()
            assert not update.probabilities.size or (update.probabilities.min() >= 0 and update.probabilities.max() <= 1)
            cursor = update.frame_end
            values.append(update.probabilities)
            row = dict(kind=kind, source_samples=samples, frame_start=update.frame_start, frame_end=cursor,
                       compute_seconds=update.compute_sec, available_elapsed_seconds=update.available_at_monotonic-began)
            writer.jsonl('CALLS.jsonl', row)
            calls.append(row)

        for offset in range(0, len(audio), spec['push_samples']):
            block = audio[offset:offset+spec['push_samples']]
            samples += len(block)
            accept(model.push(block), 'push')
        pre_eof_frames = cursor
        accept(model.finish(), 'finish')
        elapsed, cpu_seconds = time.perf_counter()-began, time.process_time()-cpu
        array = np.concatenate(values)
        raw = io.BytesIO(); np.save(raw, array, allow_pickle=False)
        writer.write('PROBABILITIES.npy', raw.getvalue())
        assert samples == 70327 and array.shape == (440, 8) and 0 < pre_eof_frames < len(array)
        matched_error = float(np.max(np.abs(array[:pre_eof_frames]-reference[:pre_eof_frames])))
        assert matched_error <= spec['tolerance']
        assert native_checks.count('actual_c_abi_before_create') == 1 and native_checks.count('actual_mapped_libraries') == 2
        assert native_checks.count('actual_asset_bytes') == 1
        emitting = [c for c in calls if c['frame_end'] > c['frame_start']]
        completed = True
    finally:
        if model is not None:
            bundle.close()
            assert bundle.diarizer is None
        closure = dict(factory_returned=model is not None, model_closed=bool(model is not None and model._closed),
                       model_pointer_empty=bool(model is not None and not model._model),
                       stream_pointer_empty=bool(model is not None and not model._stream),
                       samples=samples, frames=cursor, passage_checks_complete=completed, bundle_diarizer_empty=bundle.diarizer is None, session_id=bundle._session)
        closer.json('MODEL_CLOSURE.json', closure)
        modes.check_geometry, modes.check_loaded_paths, modes.verify_assets = original_geometry, original_paths, original_assets
    assert all(closure[k] for k in ['model_closed','model_pointer_empty','stream_pointer_empty','passage_checks_complete'])
    return dict(selected_model_boundary=True, original_bundle_constructor=False, session_id=session, status='PASS_CHUNK52_SELECTED_MODEL_BINDING_ONLY', mode='chunk52', source_samples=samples,
                source_prefix_float32_sha256=hashlib.sha256(audio.tobytes()).hexdigest(), output_frames=cursor,
                pre_eof_frames=pre_eof_frames, eof_frames=cursor-pre_eof_frames, pre_eof_max_abs=matched_error,
                tolerance=spec['tolerance'], eof_tail_matched_reference=False, model_closed=True,
                load_and_asset_check_seconds=load_seconds, passage_seconds=elapsed, passage_cpu_seconds=cpu_seconds,
                passage_rtf=elapsed/(samples/16000), first_emission_source_seconds=emitting[0]['source_samples']/16000,
                first_emission_unpaced_wall_seconds=emitting[0]['available_elapsed_seconds'],
                finish_compute_seconds=calls[-1]['compute_seconds'], calls=len(calls), native_checks=native_checks,
                manifest=manifest, capture=False, audio_saved=False, ASR=False, GUI=False,
                application_integrated=False, new_speedup_claim=False, accuracy_claim=False,
                original_rc5_concurrent=True, paced=False)
