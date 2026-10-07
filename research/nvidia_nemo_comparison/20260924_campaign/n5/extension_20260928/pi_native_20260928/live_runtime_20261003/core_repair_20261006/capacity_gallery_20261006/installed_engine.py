"""New session adapter over the pinned installed speech engines. See README.md."""
from __future__ import annotations
from collections import OrderedDict
from copy import deepcopy
from dataclasses import replace
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import threading
import time
import wave

from profiles import RuntimeSelection, SessionPolicy, get_profile
from runtime_support import digest, encoded, publish, strict, verify_files, SegmentedText, DiskBudget, resource_snapshot
from audio_journal import DiskAudioJournal
from telemetry import RollingTelemetry


def load_reference(binding):
    """Verify immutable source bytes before importing any installed graph."""
    base = Path(binding['installed_release'])
    manifest_path = base/'RELEASE_MANIFEST.json'
    if digest(manifest_path) != binding['installed_manifest_sha256']:
        raise ValueError('Installed rollback source manifest changed')
    manifest = strict(manifest_path.read_bytes())
    verify_files(base, manifest['files'])
    reference = Path(binding['reference_code'])
    verify_files(reference, binding['reference_files'])
    sys.path[:0] = [str(reference), str(base), str(base/'vendor'), str(base/'native')]
    spec = importlib.util.spec_from_file_location('v28_readonly_compat', reference/'field_operator_controller_v6.py')
    compat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compat)
    return base, {r['path']: r for r in manifest['files']}, compat


def selected_descriptor(binding, selection):
    if selection.diarizer == 'pyannote':
        key = 'baseline-titanet' if selection.embedding == 'titanet' else 'baseline'
    else:
        mode = 'delayed' if selection.nemotron_profile == 'current_delayed' else 'streaming'
        key = 'd1-'+mode+('-titanet' if selection.embedding == 'titanet' else '')+('-saved' if mode == 'streaming' else '')
    row = binding['profiles'][key]
    path = Path(row['path'])
    if path.stat().st_size > 65536 or digest(path) != row['sha256']:
        raise ValueError('Retained backend descriptor changed')
    descriptor = strict(path.read_bytes())
    document = descriptor['runtime_document']
    if selection.diarizer == 'nemotron':
        document['streaming_profile'] = get_profile(selection.nemotron_profile).native_name
    return descriptor, document


def native_documents(binding, selection, document):
    """Keep embedding/gallery settings separate from the sealed native variant."""
    if selection.nemotron_profile != 'chunk52_threads2':
        return document, document, None
    from native_variant import verify_native_variant
    row = binding.get('native_variants', {}).get('chunk52_threads2')
    if not isinstance(row, dict) or set(row) != {'path', 'sha256'}:
        raise ValueError('Explicit pinned two-thread native binding required')
    variant = verify_native_variant(row['path'], row['sha256'], selection)
    native = variant.document()
    model_document = dict(document)
    for key in ('nemotron_model', 'nemotron_model_sha256', 'nemotron_library',
                'nemotron_library_sha256', 'native_runtime_files',
                'streaming_profile', 'native_device'):
        model_document[key] = native[key]
    return model_document, native, variant


class SavedSource:
    """One exact PCM16 WAV, paced source clock, no resampling/gain or loop reset."""
    def __init__(self, journal, path, callback, policy, stop_event, *,
                 append_batch_samples=1600, clock=time.perf_counter):
        self.journal, self.path, self.callback = journal, Path(path), callback
        from saved_source_metrics import validate_batch_samples
        self.append_batch_samples = validate_batch_samples(append_batch_samples)
        self.clock = clock
        self.policy, self.stop_event = policy, stop_event
        self.thread = None
        self.sent = 0
        self.error = None
        self.done = threading.Event()
        with wave.open(str(self.path), 'rb') as source:
            if (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) != (1, 2, 16000, 'NONE'):
                raise ValueError('Saved replay needs mono PCM16 16 kHz WAV; no silent conversion')
            self.frames = source.getnframes()
        if not 0 < self.frames <= policy.maximum_samples():
            raise ValueError('WAV exceeds this explicit source-duration policy')
        self.sha256 = digest(self.path)

    def start(self):
        self.thread = threading.Thread(target=self._run, name='v29-saved-source', daemon=True)
        self.thread.start()

    def _run(self):
        import numpy as np
        from saved_source_metrics import SavedSourceMetrics
        origin = self.clock()
        metrics = SavedSourceMetrics(origin, self.callback, self.append_batch_samples, clock=self.clock)
        try:
            self.callback('source_started', dict(mode='file', source_epoch_monotonic_sec=origin,
                source_sha256=self.sha256, source_frames=self.frames, physical_microphone=False,
                motion_applied=False, gain=1.0, append_batch_samples=self.append_batch_samples))
            with wave.open(str(self.path), 'rb') as source:
                while not self.stop_event.is_set():
                    raw = source.readframes(self.append_batch_samples)
                    if not raw:
                        break
                    end = self.sent + len(raw)//2
                    if self.stop_event.wait(max(0., origin+end/16000-self.clock())):
                        break
                    audio = np.frombuffer(raw, dtype='<i2').astype(np.float32)/32768.
                    metrics.append(self.journal, audio, end)
                    self.sent = end
                    metrics.progress()
            if digest(self.path) != self.sha256:
                raise RuntimeError('Replay input changed while in use')
        except BaseException as exc:
            self.error = repr(exc)
            self.callback('fatal', dict(reason=self.error))
        finally:
            self.journal.finish(self.error)
            self.callback('source_stopped', dict(sent_samples=self.sent, physical_microphone=False,
                error=self.error, saved_source_metrics=metrics.snapshot()))
            self.done.set()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(5)
            if self.thread.is_alive():
                raise RuntimeError('Saved source remains owned')

    def wait(self, timeout=None):
        return self.done.wait(timeout)


class InstalledSession:
    """One fresh process/session; existing models and identity decisions retained."""
    def __init__(self, binding, selection, policy, spool, *, saved_path=None,
                 saved_session_id=None, saved_store_root=None, notify=None,
                 optional_refiner_options=None, repeat_input_seconds=None, repeat_input_sha256=None,
                 application=None, user_data_root=None):
        self.binding, self.selection, self.policy, self.spool = binding, selection, policy, spool
        selection.validate(); policy.validate()
        from application_contract import validate, default, SPATIAL
        intent = application or default(selection.embedding)
        if (selection.input_source == 'saved' and intent.get('mode') in SPATIAL and
                (saved_session_id is None or saved_store_root is None)):
            raise ValueError('Spatial replay requires a complete kept session with recorded beam/BMI evidence; plain WAV has no spatial evidence')
        self.application = validate(intent, selection)
        self.user_data_root = Path(user_data_root) if user_data_root is not None else spool.store.root.parent
        self.saved_path, self.notify = saved_path, notify or (lambda row: None)
        self.saved_session_id, self.saved_store_root = saved_session_id, saved_store_root
        from developer_replay import validate_repeat
        self.repeat_input_seconds=validate_repeat(selection,policy,saved_path,saved_session_id,repeat_input_seconds)
        self.repeat_input_sha256=repeat_input_sha256
        self.stop_event = threading.Event()
        self.engine = self.source = self.motion = self.models = None
        self.failure = None
        self.rows = OrderedDict()
        self.caption_payloads = OrderedDict()
        self.projection_versions = OrderedDict()
        self.started = time.monotonic()
        self.costs = {}
        self.cost_lock = threading.Lock()
        self.recent_health = []
        self.first_caption = self.first_speaker = None
        self.late_labels = None
        self.optional_refiner = None
        self.optional_refiner_options = optional_refiner_options
        self.optional_refiner_health = dict(state='off')
        self.last_optional_poll = -1.
        self.attribution_writer = None
        self.spatial_archive = None
        self.saved_spatial = None
        self.saved_spatial_receipt = None
        self.caption_projection = None
        self.text_preferences = None
        self.gallery_people = []
        self.capture_origin = None
        self.rolling = RollingTelemetry(backlog_limit_seconds=policy.max_backlog_seconds)
        self.last_diarizer_cost = (0, 0.)
        self.work = spool.directory/'work'
        self.work.mkdir()
        from model_load_trace import ModelLoadTrace
        self.model_memory = ModelLoadTrace(self.work/'model_load_memory.jsonl')

    def fail(self, reason):
        if self.failure is None:
            self.failure = str(reason)
        self.stop_event.set()
        if self.source is not None:
            # Source adapter owns restoration; this never joins on a model callback.
            event = getattr(self.source, 'stop_event', None)
            if event is not None:
                event.set()

    def guard(self):
        if time.monotonic()-self.started > self.policy.total_deadline_seconds:
            self.fail('Finite session process deadline')
            raise TimeoutError(self.failure)
        snapshot = resource_snapshot()
        if snapshot['available_ram'] < 192*1024**2:
            self.fail('Available RAM crossed 192 MiB stop floor')
            raise MemoryError(self.failure)
        return snapshot

    def stop(self):
        self.stop_event.set()
        if self.source:
            self.source.stop()

    def _close_motion(self):
        if self.motion is None:
            return
        # The pinned mounted BMI270 worker exposes close(), which joins its
        # owner thread and returns its closure result after native/lease cleanup.
        closed = self.motion.close()
        thread = getattr(self.motion, 'thread', None)
        if closed is not True or thread is not None and thread.is_alive():
            raise RuntimeError('Mounted IMU closure incomplete; worker ownership retained')
        self.motion = None

    def _caption(self, row, *, _skip_late_labels=False):
        producer_revision = row.get('display_version')
        assistance = None
        if self.text_preferences is not None:
            assistance = self.text_preferences.snapshot(self.gallery_people)
            if row.get('final') is True:
                row = dict(row, text_assistance=self.text_preferences.analyze(
                    row.get('raw_asr_text') or row.get('text') or row.get('display_text') or '', self.gallery_people))
        if self.late_labels is not None and not _skip_late_labels:
            row = self.late_labels.project(row, now=time.perf_counter())
            if row is None:
                return
            if type(producer_revision) is int and producer_revision > 0:
                row = dict(row, display_version=producer_revision)
        if self.engine is not None:
            segment_row = getattr(self.engine, 'asr_segment_row', None)
            if segment_row is not None:
                row = segment_row(row)
        key = row.get('caption_key') or str(row.get('session_id'))+'/'+str(row.get('utterance_id'))
        # Bounded canonical presentation payloads allow expiry to replace the
        # exact parent partition instead of resurrecting a summary parent row.
        canonical_payload = deepcopy(row)
        if self.engine is not None:
            resolver = self.engine.prototype_identity
            if resolver is not None:
                # Caption-before-voice closed assumptions and source-linked
                # seat assumptions share this final policy handoff. Acoustic
                # identity and assumed display assignment remain separate.
                from identity_modes import annotate_caption_policy
                row = annotate_caption_policy(resolver, row, self.application['mode'])
        start = max(0, round(float(row.get('source_start_sec', 0))*16000))
        end = max(start, round(float(row.get('source_end_sec', start/16000))*16000))
        end = min(end, self.spool.processed_samples)
        start = min(start, end)
        text = row.get('display_text') or row.get('text') or ''
        label = row.get('known_name') or row.get('label') or row.get('speaker') or 'Unknown'
        supported_segments = [s.get('ownership_state') == 'supported_history' for s in row.get('segments', [])]
        supported = row.get('speaker_supported', any(supported_segments))
        provisional = row.get('provisional', not bool(supported_segments and all(supported_segments)))
        provenance = dict(engine=getattr(self.engine, 'loaded_parent_engine',
                              type(self.engine).__mro__[1].__name__) if self.engine is not None else 'UNAVAILABLE',
                          installed_manifest_sha256=self.binding['installed_manifest_sha256'],
                          timing_kind=row.get('timing_kind', 'UNAVAILABLE'),
                          ownership_mode=row.get('ownership_mode', 'UNAVAILABLE'),
                          text_revision=row.get('text_revision_id'), input_source=self.selection.input_source,
                          speaker_attribution=self.selection.speaker_attribution,
                          attribution_status=row.get('attribution_status'), speaker_supported=supported,
                          asr_final=row.get('final') is True)
        if 'attribution_spans' in row:
            # Full per-span provenance is bounded by the helper and retained in
            # the segmented engine event log; the index stores its exact digest.
            spans = json.dumps(row['attribution_spans'], sort_keys=True, allow_nan=False).encode()
            provenance.update(attribution_spans_sha256=hashlib.sha256(spans).hexdigest(),
                              attribution_span_count=len(row['attribution_spans']))
            self.attribution_writer.write(json.dumps(dict(kind='caption_attribution', caption_key=key,
                attribution_spans=row['attribution_spans'], attribution_status=row['attribution_status'],
                attribution_spans_sha256=provenance['attribution_spans_sha256']),
                sort_keys=True, allow_nan=False)+'\n')
            self.spool.store.write_event(self.spool.session_id, 'caption_attribution',
                dict(caption_key=key, spans_sha256=provenance['attribution_spans_sha256'],
                     status=provenance['attribution_status']))
        # Existing timestamped-span engine can revise the same key; persistent
        # UPSERT changes its label/text rather than duplicating a caption.
        if not self.caption_projection:
            self.spool.store.write_caption(self.spool.session_id, key, start, end, text, str(label),
                provisional, provenance)
        else:
            projected_rows = []
            for part_index, part in enumerate(self.caption_projection(row, self.application, self.gallery_people, assistance)):
                part = dict(part)
                for field in ('recognition_segment_final', 'utterance_final', 'utterance_group_id',
                              'endpoint_kind', 'utterance_boundary_kind', 'spoken_punctuation_ready'):
                    if field in row:
                        part[field] = deepcopy(row[field])
                if 'leading_text_joiner' in row:
                    # Supplied by an admitted recognizer segment contract;
                    # never infer continuation from caption words or timing.
                    part['leading_text_joiner'] = row['leading_text_joiner'] if part_index == 0 else ' '
                part_start_sec = part.get('source_start_sec')
                part_end_sec = part.get('source_end_sec')
                part_start = min(self.spool.processed_samples, max(0, round(float(start/16000 if part_start_sec is None else part_start_sec)*16000)))
                part_end = min(self.spool.processed_samples, max(part_start, round(float(end/16000 if part_end_sec is None else part_end_sec)*16000)))
                part_provenance = dict(provenance, profile_id=part.get('profile_id'),
                    display_profile_id=part.get('display_profile_id'), ui_projection=part,
                    timing_kind=part.get('timing_kind', 'UNAVAILABLE'),
                    speaker_supported=part.get('identity_status') == 'supported',
                    application_mode=self.application['mode'], supersedes_parent=key)
                part_key = str(part['id'])
                projected_rows.append(dict(caption_id=part_key, start_sample=part_start, end_sample=part_end,
                    text=part.get('final_punctuated_display_text') or part.get('provisional_display_text') or part['raw_asr_text'],
                    speaker=str(part['label']), provisional=part.get('identity_status') != 'supported',
                    provenance=part_provenance))
            # Producer and policy expiry revisions are different clocks.
            # Keep source ordering, while allocating a fresh durable version
            # when expiry changes a partition without changing ASR words.
            revision, stale = self._projection_revision(key, projected_rows, row.get('display_version'))
            if stale:
                return
            self.spool.store.replace_caption_projection(self.spool.session_id, key, projected_rows,
                projection_revision=revision, projection_source_start_sample=start)
        self.caption_payloads[key] = canonical_payload
        while len(self.caption_payloads) > 128:
            self.caption_payloads.popitem(last=False)
        self.rows[key] = dict(id=key, text=text, speaker=label, provisional=provisional,
                             start_sample=start, end_sample=end, provenance=provenance)
        while len(self.rows) > 128:
            self.rows.popitem(last=False)
        now = time.perf_counter()
        if text and self.first_caption is None:
            self.first_caption = now
        if supported and self.first_speaker is None:
            self.first_speaker = now
        self.notify(dict(kind='caption', row=self.rows[key]))

    def _projection_revision(self, key, rows, producer_revision):
        source = producer_revision if type(producer_revision) is int and producer_revision > 0 else None
        signature = hashlib.sha256(json.dumps(rows, sort_keys=True, allow_nan=False).encode()).hexdigest()
        previous = self.projection_versions.get(key)
        if previous is not None and source is not None and previous['source'] is not None and source < previous['source']:
            return previous['revision'], True
        source = max(source or 0, previous['source'] or 0) if previous is not None else source
        changed = previous is None or previous['signature'] != signature
        revision = (max(1, source or 0) if previous is None else
            previous['revision']+1 if changed else previous['revision'])
        self.projection_versions[key] = dict(source=source, signature=signature, revision=revision)
        self.projection_versions.move_to_end(key)
        # Same bound as the actual pinned S7 presentation's active row set.
        while len(self.projection_versions) > 512:
            self.projection_versions.popitem(last=False)
        return revision, False

    def _expire_late_captions(self, now):
        if self.late_labels is None:
            return
        for patch in self.late_labels.expire(now=now):
            prior = self.caption_payloads.get(patch['caption_key'])
            if prior is not None:
                self._caption(dict(deepcopy(prior), **patch), _skip_late_labels=True)

    def _cost(self, key, elapsed, samples):
        with self.cost_lock:
            value = self.costs.setdefault(key, dict(calls=0, seconds=0., samples=0))
            value['calls'] += 1; value['seconds'] += elapsed; value['samples'] += samples

    def _validate_optional_refiner(self):
        if not self.selection.optional_d1_refiner:
            if self.optional_refiner_options is not None:
                raise ValueError('Optional refiner configuration supplied without explicit selection')
            return
        options = self.optional_refiner_options
        required = {'binding_path', 'binding_sha256', 'admission_raw', 'admission_sha256',
                    'expected_pins', 'unit', 'reserved_output_bytes'}
        if type(options) is not dict or set(options) != required:
            raise RuntimeError('Optional Pyannote + delayed D1 requires measured combined native admission; currently unavailable')
        if type(options['reserved_output_bytes']) is not int or options['reserved_output_bytes'] < 4*1024**2:
            raise ValueError('Optional child output and independent mirror must be reserved before model startup')
        from optional_refiner_admission import validate_requested_admission as validate_admission, operational_binding_sha256
        from optional_refiner import available_ram, physical_ram
        validate_admission(options['admission_raw'], options['admission_sha256'], self.selection,
            self.policy, options['expected_pins'], available_ram(), physical_ram_bytes=physical_ram())
        if (digest(options['binding_path']) != options['binding_sha256'] or
                options['expected_pins']['operational_binding_sha256'] != operational_binding_sha256(strict(Path(options['binding_path']).read_bytes()))):
            raise ValueError('Optional worker binding changed before primary model startup')

    def _optional_diagnostic(self, row):
        self.spool.store.write_event(self.spool.session_id, 'optional_refiner', row)
        self.notify(dict(kind='diagnostic', value=row))

    def _poll_optional(self, now):
        if self.optional_refiner is not None and now-self.last_optional_poll >= .25:
            self.last_optional_poll = now
            self.optional_refiner_health = self.optional_refiner.poll()

    def _close_optional(self):
        if getattr(self, 'optional_refiner', None) is not None:
            supervisor=self.optional_refiner.supervisor
            deadline=min(time.monotonic()+self.policy.max_drain_seconds,
                         self.started+self.policy.total_deadline_seconds-self.policy.cleanup_seconds)
            # Natural EOF may collect child completion after primary text has
            # finished. Explicit Stop skips this drain; no late closed-trace patch.
            while (self.failure is None and not self.stop_event.is_set() and
                   getattr(self.engine,'state',None)=='COMPLETED' and
                   not supervisor.done and supervisor.failure is None and time.monotonic()<deadline):
                self.optional_refiner.poll(publish_labels=False)
                self.guard();self.stop_event.wait(.05)
            result = self.optional_refiner.close()
            self.optional_refiner_closure=result
            self.optional_refiner_health = dict(state='closed', closure=result)
            if not result.get('child_dead') or not result.get('supervisor_thread_closed'):
                raise RuntimeError('Optional refiner ownership retained after Stop')
            self.optional_refiner = None

    def run(self):
        # Reject an unadmitted optional feature before any model import/load.
        self._validate_optional_refiner()
        if self.selection.provisional_correction:
            raise RuntimeError('Dual-diarizer native admission is pending; choose a single diarizer')
        if self.selection.nemotron_profile == 'chunk52_threads2':
            from native_variant import require_fresh_variant_loader
            require_fresh_variant_loader()
        self.model_memory.record('runtime_import','before')
        import numpy as np
        base, manifest, compat = load_reference(self.binding)
        descriptor, document = selected_descriptor(self.binding, self.selection)
        document, native_document, native_variant = native_documents(
            self.binding, self.selection, document)
        from app import paths, pipeline, people, n2_people
        from app.n2_models import N2ResidentModels
        from app.n2_pipeline import N2Engine
        from edge_speech_pipeline import research_s7
        self.model_memory.record('runtime_import','after')
        if Path(pipeline.__file__).resolve() != base/'app/pipeline.py':
            raise ValueError('Loaded installed module origin')
        contract = strict((base/'config/field_contract.json').read_bytes())
        config = replace(paths.pipeline_config(self.work, Path(contract['models_root'])),
                         asr_threads=1, speaker_threads=1, punctuation_threads=1)
        for row in document.get('native_runtime_files', []):
            if digest(row['path']) != row['sha256']:
                raise ValueError('Offline native asset changed')
        embedding = 'E1' if self.selection.embedding == 'titanet' else 'E0'
        from app.n2_models import redim_namespace
        namespace = document.get('embedding_namespace') if embedding == 'E1' else redim_namespace(config)
        gallery_roots = descriptor['runtime_profile']['galleries']
        if embedding == 'E1':
            from edge_speech_pipeline import titanet_embedding
            if digest(document['titanet_manifest']) != document['titanet_manifest_sha256']:
                raise ValueError('Existing TitaNet manifest changed')
            compat.bind_titanet_memory(titanet_embedding, Path(titanet_embedding.__file__))
        from personal_gallery import open_store
        store = open_store(self.binding, self.selection, self.user_data_root,
                           config, people, n2_people, compat, self.guard,
                           budget=DiskBudget(1, reserve_bytes=self.spool.store.policy.reserve_bytes,
                               reserve_fraction=self.spool.store.policy.reserve_fraction))
        from application_contract import validate
        from app.mode_policy import NAMED_MODES, SELECTED_MODES, SPATIAL_PARENTS, SEAT_MODES
        self.application = validate(self.application, self.selection, people=[p['id'] for p in store.list()])
        mode = self.application['mode']
        from retained_caption_projection import load
        self.caption_projection = load(self.binding)
        self.gallery_people = store.summaries()
        from app.text_assistance import TextAssistance
        self.text_preferences = TextAssistance(self.user_data_root/'vocabulary.json')
        route = dict(tap='O0', sample_rate=16000, gain_policy='O0_host_plus3dB_once',
                     preprocessing=store.preprocessing, waveform_domain='xvf_ua',
                     source='verified_live_or_already_gained_file')
        from app.enhancement import identity_binding
        route.update(identity_binding('bypass'))
        gallery = store.gallery(route, self.application['selected_ids'] if mode in SELECTED_MODES else None) if mode in NAMED_MODES and mode != 'assigned_direction' else None
        from identity_modes import gallery_status
        self.identity_readiness = gallery_status(gallery, namespace,
            policy='retained_c088' if self.selection.diarizer == 'pyannote' and embedding == 'E0' else 'n2')
        self.spool.store.write_event(self.spool.session_id, 'identity_readiness', self.identity_readiness)
        if gallery is not None and not self.identity_readiness['calibrated'] and self.identity_readiness['policy'] == 'n2':
            self.notify(dict(kind='diagnostic', value=dict(kind='identity_readiness',
                reason=self.identity_readiness['reason'], state=self.identity_readiness['status'])))
        seat = None
        if mode in SEAT_MODES:
            from app.seats import SeatSession
            intent = self.application['seating']
            seat = SeatSession(intent['rows'], strength=intent['strength'], acknowledged=intent['ambiguous_acknowledged'])
        profile = pipeline.effective_profile(self.application['recipe'], mode, 'O0',
            self.application['identity_overrides'], seat.strength if seat is not None else 'soft')
        profile = replace(profile, runtime=replace(profile.runtime,
                           lane_drain_timeout_sec=self.policy.max_drain_seconds))
        if self.selection.diarizer == 'nemotron':
            from edge_speech_pipeline import nemotron_diarization
            from nemotron_binding import bind
            factory = bind(nemotron_diarization, self.selection, self.policy, native_document,
                           verified_variant=native_variant)
            nemotron_diarization.NemotronDiarizer = factory
            if native_variant is not None:
                self.spool.store.write_event(self.spool.session_id, 'native_variant',
                                            native_variant.receipt())
        self.models = (pipeline.ResidentModels() if self.selection.diarizer == 'pyannote' and embedding == 'E0'
                       else N2ResidentModels('D1' if self.selection.diarizer == 'nemotron' else 'D0', embedding, document))
        spatial = None
        if self.selection.input_source == 'live':
            Worker, motion_config = compat._bind_mounted_runtime(base, manifest)
            from app.motion import MotionSafety
            motion_safety = MotionSafety()
            def motion_event(event):
                decision = motion_safety.accept(event)
                if decision['invalidate']:
                    if seat is not None:
                        seat.invalidate(decision['reason'])
                    if spatial is not None:
                        spatial.invalidate_positions()
            self.motion = Worker(motion_config, motion_event).start()
            from app.live_spatial import LiveSpatialProvider
            from runtime_ui_channel import SpatialViews
            provider_type = LiveSpatialProvider
            provider_arguments = {}
            if seat is not None:
                from app.seats import SeatSpatialProvider
                provider_type = SeatSpatialProvider
                provider_arguments['seats'] = seat
            spatial = SpatialViews(
                provider_type('O0', profile.tracker, enabled=mode in SPATIAL_PARENTS, display=True, motion=self.motion, **provider_arguments),
                LiveSpatialProvider('O0', profile.tracker, enabled=False, display=True, motion=None))
        elif mode in SPATIAL_PARENTS:
            if self.saved_session_id is None or self.saved_store_root is None:
                raise ValueError('Recorded spatial Modes need a kept session; plain WAV cannot supply beam/BMI evidence')
            from saved_spatial import SavedSpatialViews
            spatial = self.saved_spatial = SavedSpatialViews(self.saved_store_root,
                self.saved_session_id, profile.tracker, enabled=True, seats=seat, compensation=True)
            self.spool.store.write_event(self.spool.session_id, 'saved_spatial_binding', spatial.receipt())
        session = self
        # Keep the initial byte estimate for accounting. Cumulative metadata
        # is governed by actual free space, not the recording-duration estimate.
        from storage import metadata_limits
        metadata_budget = DiskBudget(metadata_limits(self.spool.spec,
            self.spool.store.policy.metadata_allowance_bytes)['text_bytes'],
            reserve_bytes=self.spool.store.policy.reserve_bytes,
            reserve_fraction=self.spool.store.policy.reserve_fraction)
        if mode in NAMED_MODES:
            from personal_gallery import snapshot_used_gallery
            self.used_gallery = snapshot_used_gallery(store.root, self.work/'gallery',
                metadata_budget, self.guard)
        if spatial is not None and self.selection.input_source == 'live':
            from spatial_archive import ArchivedSpatialViews
            spatial = self.spatial_archive = ArchivedSpatialViews(
                spatial.primary, spatial.device, self.motion, self.work,
                metadata_budget, self.fail)
        if self.selection.speaker_attribution == 'single_d1_late_labels':
            # The UI consumer can outlive the installed engine's trace closure.
            # Its own writer shares physical-capacity accounting and
            # closes only after the last queued caption has been consumed.
            self.attribution_writer = SegmentedText(self.work/'caption-attribution.jsonl',
                maximum_bytes=metadata_budget.maximum, budget=metadata_budget, fail=self.fail)

        class Trace:
            def __init__(self, path, session_id, capacity=16384):
                self.session_id = session_id
                self.sink = SegmentedText(path, maximum_bytes=metadata_budget.maximum,
                                          budget=metadata_budget, fail=session.fail)
                self.thread = self.sink.thread
                self.closed = False
            def record(self, kind, **fields):
                self.sink.write(encoded(dict(schema='edge-s7-clock.v1', kind=kind,
                    session_id=self.session_id, monotonic_sec=time.perf_counter(), **fields)).decode()+'\n')
            def close(self, timeout=30):
                self.sink.close(); self.closed = True
            def snapshot(self):
                return self.sink.metrics()
        research_s7.TraceWriter = Trace
        Parent = pipeline.PrototypeEngine if isinstance(self.models, pipeline.ResidentModels) and not isinstance(self.models, N2ResidentModels) else N2Engine
        seat_hook_receipt = None
        if seat is not None and Parent is N2Engine:
            from seat_backend import install_factory_hook
            seat_hook_receipt = install_factory_hook(pipeline, manifest['app/pipeline.py']['sha256'])

        from asr_segment_runtime import SegmentedAsrMixin
        n2_caption_reviser = None
        if Parent is N2Engine:
            from d1_caption_snapshot import bind_revision
            n2_caption_reviser = bind_revision(Parent, base/'app/n2_pipeline.py',
                manifest['app/n2_pipeline.py']['sha256'])

        from gallery_capacity_admission import bind_capacity_admission
        capacity_admission = bind_capacity_admission(Parent, base, manifest, session.guard)

        class Engine(SegmentedAsrMixin, Parent):
            def _admit_research_gallery(engine, gallery, maximum_profiles):
                return capacity_admission(engine, gallery, maximum_profiles)
            def __init__(engine, *args, **kwargs):
                super().__init__(*args, **kwargs)
                engine.loaded_parent_engine = Parent.__module__+'.'+Parent.__name__
                engine._segment_storage_policy = session.spool.store.policy
                if seat is not None and Parent is N2Engine:
                    from app.seat_identity import SeatIdentityResolver
                    from seat_backend import make_resolver
                    engine.n2_name_map = make_resolver(session.selection, mode,
                        legacy_factory=SeatIdentityResolver,
                        settings=engine._research_profile.identity, gallery=engine._research_gallery,
                        seats=seat, names=engine.seat_names, provider=engine.live_spatial,
                        tracker_config=engine._research_profile.tracker,
                        clock=lambda:engine._s7_observed_clock.relative(), voice_map=engine.n2_name_map)
                    # The hash-bound method hook consults this instance before
                    # either D0 or D1 starts. Its default C088 factory is intact.
                    engine._seat_identity_factory = lambda *args, **kwargs:engine.n2_name_map
                elif Parent is N2Engine:
                    from identity_modes import IdentityModeAdapter
                    from d1_spatial_policy import SPATIAL_MODES, make_policy
                    spatial_policy = make_policy(engine._research_profile.tracker, engine.live_spatial) if (
                        session.selection.diarizer == 'nemotron' and mode in SPATIAL_MODES) else None
                    engine.n2_name_map = IdentityModeAdapter(engine.n2_name_map, namespace,
                        spatial_policy=spatial_policy)
            def begin(engine):
                super().begin()
                if Parent is N2Engine and seat is None:
                    from identity_modes import install_revision_bridge
                    engine.identity_revision_bridge = install_revision_bridge(engine)
                elif Parent is not N2Engine and mode == 'selected_closed':
                    from identity_modes import RetainedClosedModeAdapter, install_revision_bridge
                    from edge_speech_pipeline.research_s7_policy import _MeasuredDelegate
                    engine.prototype_identity = RetainedClosedModeAdapter(engine.prototype_identity)
                    engine._scheduler.scheduler.identity_resolver = _MeasuredDelegate(
                        engine.prototype_identity, engine._s7_observed_clock, 'identity')
                    engine.identity_revision_bridge = install_revision_bridge(engine, retained_closed=True)
            def _revise_supported_spans(engine, utterance_id=None, blocking=True):
                if Parent is not N2Engine:
                    return
                started = time.perf_counter()
                try:
                    if getattr(engine.n2_name_map, 'spatial_policy', None) is not None:
                        from d1_spatial_policy import revise_spatial_caption_spans
                        return revise_spatial_caption_spans(engine, utterance_id, blocking)
                    return n2_caption_reviser(engine, utterance_id, blocking)
                finally:
                    session._cost('d1_caption_revision', time.perf_counter()-started, 0)
            def _watch_session(engine):
                from final_snapshot import ClosedSchedulerSnapshot
                dispatcher=engine._scheduler
                if dispatcher is None:
                    return super()._watch_session()
                engine._external_snapshot=ClosedSchedulerSnapshot(dispatcher,engine._session_dir,metadata_budget)
                original=dispatcher.snapshot
                dispatcher.snapshot=engine._external_snapshot.snapshot
                try:
                    return super()._watch_session()
                finally:
                    dispatcher.snapshot=original
            def _write_revised_transcript(engine):
                from final_snapshot import write_revised_transcript
                if engine._session_dir is not None and engine._scheduler is not None:
                    return write_revised_transcript(engine,engine._external_snapshot,metadata_budget)
            def _write_summary(engine):
                from final_snapshot import write_summary
                return write_summary(engine,metadata_budget)
            def _source_status(engine, kind, payload):
                if kind == 'source_started':
                    session.capture_origin = payload['source_epoch_monotonic_sec']
                return super()._source_status(kind, payload)
            def _make_audio_journal(engine, path):
                def observe(start, audio):
                    end = start + len(audio)
                    if end >= getattr(engine, '_quality_next', 0):
                        engine.coordinator.observe('waveform', start/16000, end/16000,
                            dict(rms=float(np.sqrt(np.mean(audio.astype(np.float64)**2))),
                                 clipped_fraction=float(np.mean(np.abs(audio)>=.999))),
                            'actual post-XVF samples; unchanged gain, no SNR inference')
                        engine._quality_next = end+8000
                return DiskAudioJournal(session.spool, policy=session.spool.spec,
                    observer=observe, request_stop=lambda reason: session.fail('Audio journal failed: '+str(reason)),
                    fault_receipt=lambda row: session.spool.store.write_event(session.spool.session_id, 'journal_fault', row))
            def _open_journal_text(engine, path):
                from event_compaction import CompactEventText
                Writer=CompactEventText if Path(path).name=='events.jsonl' else SegmentedText
                writer = Writer(path, maximum_bytes=metadata_budget.maximum,
                                       budget=metadata_budget, fail=session.fail)
                engine.text_writers.append(writer)
                return writer
            def _cost_call(engine, key, function, *args, samples=0, **kwargs):
                started = time.perf_counter()
                try:
                    if key == 'model_setup':
                        return session.model_memory.call('asr_punctuation_embedding',
                            super()._cost_call,key,function,*args,samples=samples,**kwargs)
                    return super()._cost_call(key, function, *args, samples=samples, **kwargs)
                finally:
                    session._cost(key, time.perf_counter()-started, int(samples))
        kwargs = dict(spatial_provider=spatial,
                      ram_horizon_sec=self.application['settings'].get('ram_horizon_sec', 120),
                      seats=seat, seat_names={p['id']:p['name'] for p in store.list()})
        if Parent is N2Engine:
            kwargs['diarization'] = 'D1' if self.selection.diarizer == 'nemotron' else 'D0'
        self.engine = Engine(config, self.models, profile, gallery, mode, **kwargs)
        gallery_capacity = getattr(self.engine, '_gallery_capacity_admission', None)
        if gallery_capacity is not None:
            self.spool.store.write_event(self.spool.session_id, 'gallery_capacity_admission', gallery_capacity)
        self.engine.mode_configuration = dict(selection=self.selection.validate(), source_policy=self.policy.validate(),
            application=self.application, gallery=gallery.receipt if gallery else None,
            effective_profile=__import__('dataclasses').asdict(profile),
            raw_capability=self.spool.spec.get('raw_capability', 'UNAVAILABLE_PENDING_QUALIFICATION'),
            seat_backend_hook=seat_hook_receipt,
            saved_spatial=self.saved_spatial.receipt() if self.saved_spatial is not None else None,
            identity_readiness=self.identity_readiness,
            gallery_capacity_admission=gallery_capacity,
            native_qualified=False)
        self.engine.begin()
        if self.selection.optional_d1_refiner:
            from optional_refiner import attach_optional_refiner
            try:
                self.optional_refiner = attach_optional_refiner(self.engine, self.selection, self.policy,
                    diagnostic=self._optional_diagnostic,
                    session_id=self.engine._s6d_presentation.session_id, source_id=self.spool.session_id,
                    output_directory=self.work/'optional-refiner', **self.optional_refiner_options)
                self.optional_refiner_health = dict(state='starting')
            except Exception as exc:
                self.optional_refiner_health = dict(state='disabled', reason=str(exc)[:1024])
                self._optional_diagnostic(dict(kind='optional_refiner_start_failed',
                    reason=str(exc)[:1024], primary_continues=True))
        if self.selection.speaker_attribution == 'single_d1_late_labels':
            from late_labels import SingleD1LateLabels
            self.late_labels = SingleD1LateLabels(self.selection,
                self.engine._s6d_presentation.session_id, self.spool.session_id)
        from sparse_embedding import attach_sparse_schedule
        self.embedding_schedule = attach_sparse_schedule(self.engine,
            lambda row: self.spool.store.write_event(self.spool.session_id, 'embedding_schedule', row))
        if self.selection.input_source == 'saved':
            if self.saved_session_id is not None:
                from saved_replay import SavedSessionSource
                self.source = SavedSessionSource(self.engine._input_journal, self.saved_store_root,
                    self.saved_session_id, self.engine._source_status, self.policy, self.stop_event,
                    spatial=self.saved_spatial)
            else:
                if self.repeat_input_seconds is None:
                    self.source = SavedSource(self.engine._input_journal, self.saved_path,
                                              self.engine._source_status, self.policy, self.stop_event)
                else:
                    from developer_replay import RepeatedSavedSource
                    self.source=RepeatedSavedSource(self.engine._input_journal,self.saved_path,
                        self.engine._source_status,self.policy,self.stop_event,
                        repeat_input_seconds=self.repeat_input_seconds,expected_sha256=self.repeat_input_sha256)
        else:
            from installed_source import create_source
            source_binding = dict(self.binding, consent=True)
            self.source = create_source(self.engine._input_journal, source_binding,
                self.engine._source_status, spatial, self.policy, self.spool)
            if spatial is not None:
                spatial.attach(self.source.live)
        # Prewarm D1 before capture. This is measured model loading, not RTF.
        if self.selection.diarizer == 'nemotron':
            self.model_memory.call('nemotron_prewarm',self.models.acquire_diarizer,self.engine._session_dir.name)
            # Existing N2 speaker loop calls acquire exactly once; return the
            # already acquired stream without reset/recreating model state.
            current = self.models.diarizer
            called = []
            def once(session_id):
                if called or session_id != current.session_id:
                    raise RuntimeError('One prewarmed D1 stream per worker')
                called.append(True)
                return current
            self.models.acquire_diarizer = once
        if time.monotonic()-self.started > self.policy.model_load_seconds:
            raise TimeoutError('Model startup budget exceeded before capture')
        actual_start = self.source.start
        def admitted_start():
            self.guard()
            if time.monotonic()-self.started > self.policy.model_load_seconds:
                raise TimeoutError('All-model startup deadline before microphone Start')
            return actual_start()
        self.source.start = admitted_start
        self.engine._launch(self.source)
        last_health = 0.
        drain_start = None
        while True:
            now = time.monotonic()
            if self.stop_event.is_set() and not self.engine._journal.finished:
                self.source.stop()
            if self.engine._journal.finished and drain_start is None:
                drain_start = now
            if drain_start and now-drain_start > self.policy.max_drain_seconds:
                self.fail('Processing drain deadline exceeded; recording is incomplete')
                raise TimeoutError(self.failure)
            try:
                event = self.engine.events.get(block=False)
            except queue.Empty:
                event = None
            if event is not None:
                if event.event_type == 's6d_display':
                    self._caption(event.payload)
                elif event.event_type in ('fatal', 'failure'):
                    self.fail(event.payload.get('reason', event.payload))
                elif event.event_type == 'speaker_decision' and mode in NAMED_MODES and now-getattr(self, 'last_identity_notice', -1) >= 1:
                    self.last_identity_notice = now
                    from identity_modes import decision_diagnostic_line
                    decision = event.payload.get('decision', event.payload)
                    self.notify(dict(kind='diagnostic', value=dict(kind='identity_decision',
                        reason=decision_diagnostic_line(decision, self.selection.embedding),
                        state=(decision.get('identity') or {}).get('naming_state'))))
                if spatial is not None:
                    if event.event_type == 'speaker_decision': spatial.observe_decision(event.payload)
                    elif event.event_type == 'research_segmentation': spatial.observe_segmentation(event.payload)
            self._poll_optional(now)
            if (spatial is not None and getattr(self,'gui_spatial_enabled',lambda:False)()
                    and now-getattr(self,'last_gui_spatial',-1)>=.2):
                self.last_gui_spatial=now
                # Existing provider/motion snapshots only; no hardware query,
                # SQLite row or disk snapshot is created for a GUI refresh.
                self.notify(dict(kind='spatial',value=spatial.display_snapshot()))
            if now-last_health >= 1:
                last_health = now
                self._expire_late_captions(time.perf_counter())
                state = self.guard()
                values = self.engine.telemetry()
                backlog = max(float(values.get('speaker_lag_sec', 0)), float(values.get('asr_lag_sec', 0)))
                with self.cost_lock:
                    costs = json.loads(json.dumps(self.costs))
                diar = costs.get('diarizer_push', dict(samples=0, seconds=0.))
                prior_samples, prior_seconds = self.last_diarizer_cost
                samples = diar['samples']-prior_samples
                if samples:
                    self.rolling.observe(now=now, audio_seconds=samples/16000,
                        compute_seconds=max(0., diar['seconds']-prior_seconds), backlog_seconds=backlog)
                    self.last_diarizer_cost = (diar['samples'], diar['seconds'])
                else:
                    self.rolling.observe(now=now, audio_seconds=0., compute_seconds=0.,
                                         backlog_seconds=backlog)
                origin = self.capture_origin
                state.update(elapsed=None if origin is None else time.perf_counter()-origin,
                    backlog_seconds=backlog, costs=costs, diarizer_rolling=self.rolling.snapshot(now),
                    speaker_lag_seconds=float(values.get('speaker_lag_sec', 0)),
                    asr_lag_seconds=float(values.get('asr_lag_sec', 0)),
                    speaker_cursor_seconds=values.get('speaker_cursor_sec'),
                    speaker_analyzed_through_seconds=values.get('speaker_analyzed_through_sec'),
                    asr_cursor_seconds=values.get('asr_cursor_sec'),
                    rolling_scope='diarizer_push_only; finish cost retained separately',
                    source_samples=self.spool.processed_samples,
                    first_caption_latency=None if self.first_caption is None or origin is None else self.first_caption-origin,
                    first_speaker_latency=None if self.first_speaker is None or origin is None else self.first_speaker-origin,
                    state=self.engine.state, dropped_audio=values.get('audio_frames_dropped'),
                    refinement=self.optional_refiner_health if self.selection.optional_d1_refiner else
                        'NOT_ADMITTED_NO_NATIVE_RESOURCE_PROOF' if self.selection.provisional_correction else 'off')
                resolver = self.engine.prototype_identity
                if resolver is not None:
                    state['identity'] = resolver.snapshot()
                self.spool.store.write_event(self.spool.session_id, 'health', state)
                self.recent_health = (self.recent_health+[state])[-120:]
                self.notify(dict(kind='health', value=state))
                if backlog >= self.policy.max_backlog_seconds:
                    self.fail('Configured backlog limit exceeded; source stopped without skipping speech')
            finalizer = self.engine._finalization_thread
            if finalizer is not None and not finalizer.is_alive() and self.engine.events.empty():
                break
            if event is None:
                time.sleep(.02)
        self._close_optional()
        self.engine.record_s6d_consumer_closure('v29 persistent indexed captions; events fully drained')
        self.source.stop()
        if hasattr(self.models, 'close'):
            self.models.close()
        self._close_motion()
        self.engine.wait_for_completion(1)
        self._close_saved_spatial()
        if self.attribution_writer is not None:
            self.attribution_writer.close()
        if self.failure or self.engine.state == 'FAILED':
            raise RuntimeError(self.failure or 'Installed engine failed')
        return dict(status='FUNCTIONAL_SESSION_COMPLETED', selection=self.selection.validate(),
                    source_policy=self.policy.validate(), source_samples=self.spool.processed_samples,
                    costs=self.costs, native_cm5=True, sustained_realtime_qualified=False,
                    quality_evaluated=False,
                    saved_spatial=self.saved_spatial_receipt,
                    optional_refiner_closure=getattr(self,'optional_refiner_closure',None),
                    combined_paced_eof_wall_seconds=None if self.capture_origin is None else time.perf_counter()-self.capture_origin,
                    combined_timing_scope='paced first source origin through required consumers; includes waits, not compute RTF', 
                    native_variant=None if native_variant is None else native_variant.receipt(),
                    raw_qualified=self.spool.spec.get('raw', {}).get('qualification', {}).get('qualified') is True,
                    raw_capability=self.spool.spec.get('raw_capability', 'UNAVAILABLE_PENDING_QUALIFICATION'))

    def _close_saved_spatial(self):
        if self.saved_spatial is None:
            return
        provider = self.saved_spatial
        receipt = provider.receipt()
        if provider.close() is not True:
            raise RuntimeError('Recorded spatial replay lease/source verification is incomplete')
        self.saved_spatial_receipt = dict(receipt, source_verified_after_drain=True,
            source_shared_lease_closed=True, current_motion_used=False)
        self.saved_spatial = None
        self.spool.store.write_terminal_event(self.spool.session_id, 'saved_spatial_closed', self.saved_spatial_receipt)

    def close(self):
        errors = []
        self.stop_event.set()
        completed = []
        model_lanes_owned = self.engine is not None
        self.cleanup_receipt = dict(attempted=True, completed=completed,
            model_lanes_owned=model_lanes_owned, failure_preserved=self.failure)
        # Never destroy a model while its lane still executes native code.
        if self.source is not None:
            try:
                self.source.stop()
                completed.append('source_stop_join')
            except BaseException as exc:
                errors.append(repr(exc))
        try:
            self._close_optional()
            completed.append('optional_refiner')
        except BaseException as exc:
            errors.append(repr(exc))
        if self.spatial_archive is not None:
            try:
                self.spatial_archive.close_archive()
                completed.append('spatial_archive')
            except BaseException as exc:
                errors.append(repr(exc))
        # Stop the sensor even when a speech lane cannot yet be reaped. Native
        # speech models below still remain owned until all their lanes exit.
        try:
            self._close_motion()
            completed.append('motion')
        except BaseException as exc:
            errors.append(repr(exc))
        if self.engine:
            if (self.engine._finalization_thread is None
                    and getattr(self.engine, '_session_dir', None) is not None
                    and self.failure is None):
                self.fail('Session closed before source launch completed')
            if self.failure and self.engine.state not in ('FAILED', 'COMPLETED'):
                try:
                    self.engine._fail(self.failure)
                except BaseException as exc:
                    errors.append(repr(exc))
            finalizer = self.engine._finalization_thread
            if finalizer is None and getattr(self.engine, '_session_dir', None) is not None:
                # begin() allocates scheduler/journal/trace writers before source
                # validation and D1 prewarm. Reuse the installed cleanup path
                # when those steps fail before _launch() creates its watcher.
                journal = getattr(self.engine, '_journal', None)
                if journal is not None:
                    try:
                        journal.finish(self.failure)
                    except BaseException as exc:
                        # Failure diagnostics may exhaust their allocation.
                        # Still run the installed lane/writer cleanup below.
                        errors.append(repr(exc))
                def finalize_unlaunched():
                    try:
                        self.engine._watch_session()
                    except BaseException as exc:
                        self.engine._finalization_error = exc
                finalizer = threading.Thread(target=finalize_unlaunched,
                    name='v29-prelaunch-cleanup', daemon=True)
                self.engine._finalization_thread = finalizer
                self.engine._threads.append(finalizer)
                finalizer.start()
            if finalizer and finalizer.is_alive():
                finalizer.join(self.policy.cleanup_seconds)
            alive = [t.name for t in self.engine._threads if t.is_alive()]
            writers = list(getattr(self.engine, 'text_writers', []))
            trace = getattr(self.engine, '_s7_trace', None)
            if trace is not None:
                writers.append(trace)
            alive.extend(writer.thread.name for writer in writers
                         if getattr(writer, 'thread', None) is not None and writer.thread.is_alive())
            if alive:
                errors.append('Model ownership retained; still-running workers: '+','.join(alive))
            else:
                model_lanes_owned = False
                completed.append('engine_lanes_writers_joined')
            if finalizer is not None and not alive:
                try:
                    self.engine.wait_for_completion(0)
                except BaseException as exc:
                    errors.append(repr(exc))
        for target, method in ((self.models, 'close'), (self.attribution_writer, 'close')):
            if target is not None and hasattr(target, method):
                if target is self.models and model_lanes_owned:
                    continue
                try:
                    getattr(target, method)()
                    completed.append('models' if target is self.models else 'attribution_writer')
                except BaseException as exc:
                    errors.append(repr(exc))
        try:
            self._close_saved_spatial()
            completed.append('saved_spatial_lease')
        except BaseException as exc:
            errors.append(repr(exc))
        trace = getattr(self, 'model_memory', None)
        if trace is not None and not trace.closed:
            try:
                try:
                    trace.record('session_cleanup','failed' if self.failure or errors else 'after',
                        error=self.failure,logical_success=self.failure is None and not errors,
                        physical_process_closed=False)
                finally:
                    trace.close()
                    completed.append('model_memory_writer')
            except BaseException as exc:
                errors.append(repr(exc))
        self.cleanup_receipt.update(model_lanes_owned=model_lanes_owned,
            errors=errors[:], logical_cleanup_complete=not errors,
            physical_process_closed=False)
        terminal = dict(attempted=True, completed=completed[:],
            model_lanes_owned=model_lanes_owned, error_count=len(errors),
            errors_sha256=hashlib.sha256(encoded(errors)).hexdigest(),
            failed_recording=self.failure is not None,
            logical_cleanup_complete=not errors, physical_process_closed=False)
        try:
            self.spool.store.write_terminal_event(self.spool.session_id,
                'session_cleanup', terminal)
            self.cleanup_receipt['terminal_receipt_published'] = True
        except BaseException as exc:
            errors.append(repr(exc))
            self.cleanup_receipt.update(errors=errors[:], logical_cleanup_complete=False,
                terminal_receipt_published=False)
        if errors:
            raise RuntimeError('; '.join(errors))
