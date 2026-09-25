"""Research roster and consumer clock instrumentation. README_PACED_ADAPTERS_V3.md."""
from collections import Counter
from copy import deepcopy
import math
from pathlib import Path
import threading
import time

from edge_speech_pipeline.research_identity_v3 import ResearchGallery
from common import audio_only
from mode_galleries import load_prepared_gallery


class CountedBaselineGallery(ResearchGallery):
    """Delegate every score to the unchanged loaded gallery, including failures.

    No vector copying, normalization, resolver replacement or alternate scoring.
    The count has PersonalGallery's attempted-call semantics. Extra metadata is
    adaptation-off compatibility only; this facade never enables adaptation.
    """
    def __init__(self, gallery):
        from edge_speech_pipeline.research_identity_v3 import ResearchGallery
        if type(gallery) is not ResearchGallery:
            raise ValueError('Only the exact baseline research gallery needs this facade')
        self._gallery = gallery
        self._count_lock = threading.Lock()
        self.query_count = 0
        self.alternate_matrix = None
        self.alternate_enabled = False
        self.last_alternate = None
        self.base_versions = {}
        self.environment_bank = []
        self.adaptation = None

    def __getattr__(self, name):
        return getattr(self._gallery, name)

    def score(self, vector):
        if self.adaptation is not None or self.alternate_enabled:
            raise ValueError('Reference adaptation and alternate scoring are outside the primary comparison')
        with self._count_lock:
            self.query_count += 1
        return self._gallery.score(vector)


class PacedResearchPeople:
    """Fixed verified research roster, independent state per application session.

    Only list, summaries and gallery are implemented. There is no personal
    profile import, enrollment, promotion, mutation or implicit roster fallback.
    """
    def __init__(self, preparation, contract, root, tap):
        if tap not in ('O0', 'O1') or contract['adaptation']:
            raise ValueError('Explicit tap and adaptation-off contract required')
        value, condition = load_prepared_gallery(preparation, contract)
        self.value = CountedBaselineGallery(value) if value is not None and not contract['uses_n2'] else value
        self.condition = condition
        self.contract = deepcopy(contract)
        self.root = Path(root)
        self.tap = tap
        self.preprocessing = getattr(value, 'namespace', {}).get('preprocessing', 'mono-float32-16k-redimnet2-native-l2-v1')
        self.rows = [] if value is None else [dict(id=i, name=n) for i, n in zip(value.ids, value.names)]
        if len(self.rows) != condition['available_size']:
            raise ValueError('Available roster denominator changed')

    def list(self):
        return deepcopy(self.rows)

    def summaries(self, *args, **kwargs):
        return self.list()

    def expected_route(self):
        from app.enhancement import identity_binding
        route = dict(tap=self.tap, sample_rate=16000,
            gain_policy='O0_host_plus3dB_once' if self.tap == 'O0' else 'O1_unity',
            preprocessing=self.preprocessing, waveform_domain='xvf_ua',
            source='verified_live_or_already_gained_file')
        route.update(identity_binding('bypass'))
        return route

    def gallery(self, route, selected_ids=None, *, alternate_advisory=False):
        if self.value is None or route != self.expected_route() or alternate_advisory is not False:
            raise ValueError('Require the exact prepared tap, gain, preprocessing and bypass route')
        selected_mode = self.contract['mode'] in ('selected_focus', 'selected_closed')
        if selected_mode:
            if (not isinstance(selected_ids, (list, tuple)) or not selected_ids
                    or len(selected_ids) != len(self.value.ids) or set(selected_ids) != set(self.value.ids)):
                raise ValueError('Selected IDs must equal the fixed available research roster exactly')
        elif selected_ids is not None:
            raise ValueError('Open research conditions do not accept an implicit selected subset')
        return self.value


class ConsumerSourceClock:
    """One-session, bounded observer of the actual Controller event seam.

    The event payload clock and the consumer receipt clock remain separate.
    This observer never certifies FileSource delivery, full journal closure,
    inference, visible widgets or latency by itself. Original hook behavior and
    exceptions are preserved; observer errors invalidate its own evidence only.
    """
    def __init__(self, job):
        self.job = deepcopy(audio_only(job))
        self.lock = threading.RLock()
        self.controller = self.engine = None
        self.epoch = None
        self.original = self.wrapper = None
        self.had_instance_hook = False
        self.installed = False
        self.counts = Counter()
        self.events = self.errors = 0
        self.violations = []
        self.started = None
        self.last_received = None
        self.last_publication_sequence = 0
        self.missing_publication_sequences = 0
        self.publication_session = None
        self.observer_cpu_wall_sec = 0.

    def install(self, controller):
        if self.controller is not None or getattr(controller, '_n4_source_clock_observer', None) is not None:
            raise ValueError('Use one fresh clock observer per session')
        if controller.engine is not None or (controller.consumer is not None and controller.consumer.is_alive()):
            raise ValueError('Install only after the previous engine and consumer have closed')
        if (not controller.saved_audio_only or controller.collect_references or controller.use_references
                or controller.settings.get('enhancement_route', 'bypass') != 'bypass'):
            raise ValueError('Saved audio with reference adaptation and enhancement off required')
        self.controller = controller
        self.original = controller._adaptation_event
        self.had_instance_hook = '_adaptation_event' in vars(controller)

        def observed(engine, event):
            receipt = time.perf_counter()
            try:
                self._observe(engine, event, receipt)
            except Exception as exc:
                self._invalid('observer_exception:' + type(exc).__name__)
            finally:
                with self.lock:
                    self.observer_cpu_wall_sec += time.perf_counter() - receipt
            return self.original(engine, event)

        self.wrapper = observed
        controller._adaptation_event = observed
        controller._n4_source_clock_observer = self
        self.installed = True
        return self

    def _invalid(self, reason):
        with self.lock:
            self.errors += 1
            if len(self.violations) < 32:
                self.violations.append(dict(event_index=self.events - 1, reason=reason))

    def _observe(self, engine, event, receipt):
        with self.lock:
            self.events += 1
            kind = event.event_type
            if not isinstance(kind, str) or not 0 < len(kind) <= 128:
                self._invalid('invalid_event_type'); return
            if kind not in self.counts and len(self.counts) >= 128:
                self._invalid('event_type_bound'); return
            self.counts[kind] += 1
            if self.last_received is not None and receipt < self.last_received:
                self._invalid('consumer_clock_regressed')
            self.last_received = receipt
            if self.engine is None:
                self.engine, self.epoch = engine, self.controller.epoch
            if (engine is not self.engine or engine is not self.controller.engine
                    or self.epoch != self.controller.epoch or self.controller.source_kind != 'file'):
                self._invalid('foreign_engine_epoch_or_source'); return
            p = event.payload
            if not isinstance(p, dict):
                self._invalid('invalid_payload'); return
            sequence = p.get('publication_sequence')
            published = p.get('publication_monotonic_sec')
            session = p.get('session_id')
            cursor = p.get('publication_source_cursor_sec')
            consumed = p.get('consumer_monotonic_sec')
            age = p.get('consumer_queue_age_sec')
            if (type(sequence) is not int or sequence <= self.last_publication_sequence
                    or type(published) not in (int, float) or not math.isfinite(published) or not 0 < published <= receipt
                    or type(consumed) not in (int,float) or not math.isfinite(consumed) or not published <= consumed <= receipt
                    or type(age) not in (int,float) or not math.isfinite(age) or not 0 <= age <= receipt-published+.001
                    or not isinstance(session, str) or not 0 < len(session) <= 256
                    or type(cursor) not in (int, float) or not math.isfinite(cursor) or not 0 <= cursor <= self.job['frames']/16000):
                self._invalid('invalid_publication_metadata'); return
            self.missing_publication_sequences += sequence-self.last_publication_sequence-1
            self.last_publication_sequence = sequence
            self.publication_session = self.publication_session or session
            actual_session = getattr(engine, 'session_dir', None)
            if session != self.publication_session or actual_session is not None and session != Path(actual_session).name:
                self._invalid('foreign_publication_session'); return
            if kind != 'source_started':
                return
            if self.counts[kind] != 1:
                self._invalid('duplicate_source_started'); return
            # Match the unchanged FileSource payload, not a replay/host stamp.
            if set(p) != {'source_epoch_monotonic_sec', 'mode', 'path', 'start_sample', 'gain', 'pacing',
                    'publication_sequence', 'publication_monotonic_sec', 'session_id', 'publication_source_cursor_sec',
                    'consumer_monotonic_sec', 'consumer_queue_age_sec'}:
                self._invalid('unexpected_source_payload'); return
            origin = p['source_epoch_monotonic_sec']
            if (type(origin) not in (int, float) or not math.isfinite(origin) or not 0 < origin <= published
                    or p['mode'] != 'file' or p['pacing'] != 'absolute' or type(p['start_sample']) is not int
                    or p['start_sample'] != 0 or type(p['gain']) not in (int, float) or p['gain'] != 1.
                    or Path(p['path']).resolve() != Path(self.job['audio_path']).resolve()):
                self._invalid('unqualified_source_payload'); return
            self.started = dict(event_index=self.events - 1, event_payload=deepcopy(p),
                source_epoch_monotonic_sec=origin, consumer_received_monotonic_sec=receipt,
                consumer_receipt_delay_sec=receipt - origin)

    def snapshot(self):
        with self.lock:
            available = self.started is not None and self.errors == 0 and self.counts['source_started'] == 1
            return dict(schema='n4-consumer-source-clock-v1', event_count=self.events, event_counts=dict(self.counts),
                last_publication_sequence=self.last_publication_sequence, publication_session=self.publication_session,
                missing_publication_sequences=self.missing_publication_sequences,
                epoch=self.epoch, source_started=deepcopy(self.started), errors=self.errors,
                violations=deepcopy(self.violations), violations_truncated=self.errors > len(self.violations),
                source_event_clock_available=available,
                source_epoch_monotonic_sec=self.started['source_epoch_monotonic_sec'] if available else None,
                observer_elapsed_sec=self.observer_cpu_wall_sec, installed=self.installed,
                actual_source_delivery_verified=False, full_event_consumer_closure_verified=False,
                source_to_widget_latency_qualified=False)

    def reconcile_inbox(self):
        """After drain, account for the actual inbox's permitted coalescence.

        This is an event census only. Source delivery, finalization/archives and
        the actual engine publication journal must be reviewed separately.
        """
        from edge_speech_pipeline.research_s6d import EventInbox
        c = self.controller; engine = self.engine
        if (engine is None or c.consumer is not None and c.consumer.is_alive()
                or type(engine.events) is not EventInbox):
            raise ValueError('Require the stopped actual Controller EventInbox')
        inbox = engine.events.snapshot()
        published = engine._s6d_event_serial
        if (self.errors or inbox['depth'] != 0 or inbox['consumed'] != self.events
                or published != self.last_publication_sequence
                or inbox['coalesced_obsolete_ui_partials'] != self.missing_publication_sequences
                or self.events + self.missing_publication_sequences != published):
            self._invalid('unreconciled_event_inbox')
            raise ValueError('Publication/consumer/coalescence counts disagree')
        return dict(status='PASS_ACTUAL_EVENT_INBOX_CENSUS', published=published,
            consumed=self.events, coalesced_obsolete_ui_partials=self.missing_publication_sequences,
            inbox=inbox, source_delivery_verified=False, full_pipeline_acceptance=False)

    def detach(self):
        if not self.installed:
            raise ValueError('Observer is not installed')
        c = self.controller
        if c.consumer is not None and c.consumer.is_alive():
            raise ValueError('Do not detach from an active consumer')
        if c._adaptation_event is not self.wrapper or c._n4_source_clock_observer is not self:
            raise ValueError('Observer ownership changed; do not overwrite another hook')
        if self.had_instance_hook:
            c._adaptation_event = self.original
        else:
            del c._adaptation_event
        del c._n4_source_clock_observer
        self.installed = False
