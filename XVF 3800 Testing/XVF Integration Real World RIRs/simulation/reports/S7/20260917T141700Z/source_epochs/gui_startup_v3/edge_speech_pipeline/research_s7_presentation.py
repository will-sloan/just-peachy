"""Opt-in S7 caption ownership; see README_RESEARCH_S7_PRESENTATION_PREFIX.md."""
from collections import Counter, OrderedDict
from copy import deepcopy
from dataclasses import replace
import math
import re
import threading
import time

from .research_s6d import PresentationState

IDENTITY_CLOCK_FIELDS = (
    'observed_policy_decision_ready_at_sec', 'policy_decision_finish_monotonic_sec',
    'source_origin_monotonic_sec', 'source_epoch_monotonic_sec', 'input_available_at_sec', 'modeled_available_at_sec',
    'queue_admission_monotonic_sec', 'policy_worker_receipt_monotonic_sec',
    'publication_monotonic_sec', 'observed_publication_at_sec',
    'live_evidence_id', 'live_evidence_source_end_sec', 'source_evidence_expiry_at_sec',
    'live_evidence_fresh', 'live_evidence_age_sec',
    'live_evidence_fresh_at_policy_ready', 'live_evidence_age_at_policy_ready_sec',
    'live_evidence_fresh_at_publication', 'live_evidence_age_at_publication_sec',
    'historical_eligibility_clock', 'legacy_first_times_clock',
    'observed_first_display_ready_at_sec', 'observed_first_final_ready_at_sec',
    'observed_first_known_name_ready_at_sec', 'historical_only', 'application_scope', 'current_source_permission')


def segment_application_freshness(segment, now):
    '''Actual same-clock apply observation; absent upstream clocks never imply freshness.'''
    result = dict(gui_apply_monotonic_sec=now, live_evidence_fresh_at_gui_apply=None,
        live_evidence_age_at_gui_apply_sec=None, gui_apply_source_relative_sec=None,
        gui_freshness_status='UNAVAILABLE_MISSING_CLOCKS', voice_or_direction_permission=False)
    finite = lambda x: type(x) in (int,float) and math.isfinite(x)
    epoch=segment.get('source_epoch_monotonic_sec')
    alias=segment.get('source_origin_monotonic_sec')
    if epoch is not None and alias is not None and (
            not finite(epoch) or not finite(alias) or abs(epoch-alias)>1e-6):
        result['gui_freshness_status']='UNAVAILABLE_INCONSISTENT_CLOCKS';return result
    origin=epoch if epoch is not None else alias
    ready=segment.get('observed_policy_decision_ready_at_sec')
    finish=segment.get('policy_decision_finish_monotonic_sec')
    if origin is None and finite(ready) and finite(finish):origin=finish-ready
    end=segment.get('live_evidence_source_end_sec'); expiry=segment.get('source_evidence_expiry_at_sec')
    prior=segment.get('live_evidence_fresh_at_publication',segment.get('live_evidence_fresh'))
    if not all(finite(x) for x in (now,origin,ready,finish,end,expiry)) or type(prior) is not bool:
        return result
    relative=now-origin
    if abs((finish-origin)-ready)>1e-6 or relative<ready or expiry<end:
        result['gui_freshness_status']='UNAVAILABLE_INCONSISTENT_CLOCKS';return result
    age=relative-end
    result.update(gui_freshness_status='MEASURED_SAME_MONOTONIC_CLOCK',
        gui_apply_source_relative_sec=relative, live_evidence_age_at_gui_apply_sec=age,
        live_evidence_fresh_at_gui_apply=prior and 0<=age and relative<=expiry+1e-9)
    return result


class S7PresentationState(PresentationState):
    """Presentation only: upstream policy retains all evidence horizons and admission gates."""
    s7_enabled = True
    KINDS = {'s6d_text_ready', 'transcript_partial', 'transcript_final',
             'transcript_label_revision', 's6d_punctuation_revision'}

    def __init__(self, settings, options):
        super().__init__(settings)
        self.options = dict(options)  # Root-owned options are preserved without reinterpretation.
        self.session_id = self.options.get('session_id')
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError('S7 requires an explicit session identity')
        self.ownership_mode = self.options.get('ownership_mode', 'conservative_v1')
        if self.ownership_mode not in {'conservative_v1', 'supported_prefix_v2'}:
            raise ValueError('Unknown caption ownership alternative')
        self.mode = self.options.get('mode', 'M1')
        self._validate_mode(self.mode)
        self.display_state = self.options.get('display_state', 'active')
        if self.display_state not in {'active', 'listening', 'dim'}:
            raise ValueError('Invalid software display state')
        self.selected_ids = tuple(settings.selected_profile_ids)
        self.full_view = False
        self.view_revision = self.action_serial = 0
        self.rejected = Counter()
        self._pending = OrderedDict()
        self._columns = {}
        self._retired_through = -1.
        self._lock = threading.RLock()

    def _validate_mode(self, mode):
        if mode not in {f'M{i}' for i in range(8)}:
            raise ValueError('Unknown S7 presentation mode')
        if mode == 'M4' and self.settings.transcript_mode not in {'T1', 'T2'}:
            raise ValueError('M4 requires explicit original T1/T2 settings; no silent substitute')
        selected = getattr(self, 'selected_ids', self.settings.selected_profile_ids)
        if mode == 'M4' and (self.settings.transcript_mode == 'T1' and len(selected) != 1 or
                           self.settings.transcript_mode == 'T2' and not selected and not self.settings.all_enrolled):
            raise ValueError('M4 selection must retain the original T1/T2 cardinality contract')

    def token_ids(self, key, text, revision):
        with self._lock:
            return super().token_ids(self.session_id + '/' + key, text, revision)

    @staticmethod
    def _span(payload, target=False):
        prefix = 'target_' if target and 'target_source_end_sec' in payload else ''
        a, b = (payload.get(prefix + 'source_' + edge + '_sec') for edge in ('start', 'end'))
        if not all(type(value) in (int, float) and math.isfinite(value) for value in (a, b)) or not 0 <= a <= b:
            return None
        return a, b

    @staticmethod
    def _serial(value):
        if type(value) is int:
            return value
        if isinstance(value, str) and value.rsplit(':', 1)[-1].isdigit():
            return int(value.rsplit(':', 1)[-1])
        return -1

    def _version(self, payload, identity=False):
        if identity:
            stamp = payload.get('latest_label_time', payload.get('available_at_sec'))
            if type(stamp) not in (int, float) or not math.isfinite(stamp):
                return None
            return stamp, self._serial(payload.get('identity_version', payload.get('event_id')))
        event = payload.get('text_revision_id', payload.get('input_event_id', payload.get('event_id')))
        serial = self._serial(payload.get('text_version', event))
        span = self._span(payload)
        return (span[1], serial) if span is not None and serial >= 0 else None

    def _reject(self, reason):
        self.rejected[reason] += 1
        return None

    def _identity(self, row, payload):
        support, target = self._span(payload), self._span(payload, target=True)
        version = self._version(payload, identity=True)
        if payload.get('target_text_revision_id') is not None and payload['target_text_revision_id'] != row.get('text_revision_id'):
            return self._reject('identity_wrong_target_revision')
        if support is None or target is None or version is None:
            return self._reject('identity_missing_span_or_version')
        # Target must cover this exact caption's source extent; evidence may cover a subset.
        # The original upstream scheduler, not this view, admits the historical correction.
        if target[0] != row['source_start_sec'] or target[1] < row['source_end_sec']:
            return self._reject('identity_wrong_target_span')
        if max(support[0], row['source_start_sec']) >= min(support[1], row['source_end_sec']):
            return self._reject('identity_disjoint_source')
        signature = tuple(repr(payload.get(k)) for k in ('latest_label', 'latest_known_profile_id',
            'latest_naming_state', 'tracker_id', 'replacement_tracker_id', 'evidence_id', 'evidence_ids'))
        previous = row.get('_identity_version')
        if previous is not None and version <= previous:
            if version == previous and signature != row.get('_identity_signature'):
                return self._reject('conflicting_identity_version')
            return self._reject('duplicate_or_older_identity')
        row.update(_identity_version=version, _identity_signature=signature,
            label=payload.get('latest_label', payload.get('speaker', 'Unknown')),
            known_profile_id=payload.get('latest_known_profile_id'),
            known_name=payload.get('latest_known_name'), naming_state=payload.get('latest_naming_state', 'unresolved'),
            track_id=payload.get('replacement_tracker_id', payload.get('tracker_id')),
            anonymous_label=payload.get('latest_anonymous_label', 'Unknown'),
            identity_source_span=list(support), identity_target_span=list(target),
            identity_version=list(version), identity_event_id=payload.get('event_id'),
            identity_input_event_id=payload.get('input_event_id'),
            evidence_ids=deepcopy(payload.get('evidence_ids', [payload['evidence_id']] if payload.get('evidence_id') else [])))
        row.setdefault('first_supported_identity', self._identity_snapshot(row))
        if self.ownership_mode == 'supported_prefix_v2':
            accepted = self._identity_snapshot(row)
            accepted.update({key:deepcopy(payload.get(key)) for key in IDENTITY_CLOCK_FIELDS})
            accepted.update(identity_event_id=row.get('identity_event_id'), identity_input_event_id=row.get('identity_input_event_id'),
                accepted_text_revision_id=row.get('text_revision_id'), accepted_token_ids=list(row.get('token_ids', [])),
                accepted_raw_text=row['text'], anonymous_label=row.get('anonymous_label', 'Unknown'),
                target_revision_authority='EXACT_TARGET_REVISION' if payload.get('target_text_revision_id') is not None else 'LEGACY_MISSING_COUNTERFACTUAL')
            row['accepted_identity_snapshot'] = deepcopy(accepted)
            row['_token_owners'] = [accepted for _ in row.get('token_ids', [])]
            self._refresh_segments(row)
        return True

    @staticmethod
    def _identity_snapshot(row):
        return {key: deepcopy(row.get(key)) for key in ('label', 'track_id', 'known_profile_id',
            'known_name', 'naming_state', 'identity_source_span', 'identity_target_span', 'identity_version', 'evidence_ids')}

    def _prefix_tokens(self, row, prior_text, payload):
        previous = re.findall(r'\S+', prior_text); current = re.findall(r'\S+', row['text'])
        prefix = 0
        while prefix < min(len(previous), len(current)) and previous[prefix] == current[prefix]:
            prefix += 1
        previous_ids = row.get('token_ids', [])
        owners = row.get('_token_owners', [])
        ids = list(previous_ids[:prefix])
        serial = row.get('_token_serial', 0)
        for _ in current[prefix:]:
            serial += 1; ids.append(f"{row['caption_key']}/token:{serial}")
        row.update(token_ids=ids, _token_serial=serial,
            _token_owners=deepcopy(owners[:prefix]) + [None] * (len(current)-prefix),
            upstream_token_ids=deepcopy(payload.get('token_ids')))
        self._refresh_segments(row)

    def _refresh_segments(self, row):
        spans = [(m.start(), m.end()) for m in re.finditer(r'\S+', row['text'])]
        ids = row.get('token_ids', []); owners = row.get('_token_owners', [])
        if len(spans) != len(ids) or len(owners) != len(ids):
            raise RuntimeError('Caption token/ownership cardinality changed')
        groups = []
        for index, owner in enumerate(owners):
            if groups and groups[-1][2] == owner: groups[-1][1] = index+1
            else: groups.append([index,index+1,owner])
        if not groups: groups = [[0,0,None]]
        old = row.get('segments', []); segments = []
        serial = row.get('_segment_serial', 0)
        for a,b,owner in groups:
            state = 'supported_history' if owner else 'pending'
            segment_ids = ids[a:b]
            previous = next((x for x in old if x['ownership_state']==state and x.get('identity_event_id')==(owner or {}).get('identity_event_id')
                and x['token_ids'] and segment_ids and x['token_ids'][0]==segment_ids[0]), None)
            if previous: segment_id = previous['segment_id']
            else:
                serial += 1; segment_id=f"{row['caption_key']}/segment:{serial}"
            start = spans[a][0] if a else 0
            end = spans[b][0] if b < len(spans) else len(row['text'])
            raw = row['text'][start:end]
            identity = deepcopy(owner) if owner else dict(label='Pending identity', track_id=None,
                known_profile_id=None, known_name=None, naming_state='unresolved', anonymous_label='Unknown',
                identity_source_span=None, identity_target_span=None, identity_version=None,
                evidence_ids=[], identity_event_id=None, identity_input_event_id=None,
                accepted_text_revision_id=None, accepted_token_ids=[])
            segments.append(dict(**identity, session_id=self.session_id, caption_key=row['caption_key'],
                segment_id=segment_id, text_revision_id=row['text_revision_id'], token_ids=list(segment_ids),
                token_range=[a,b], raw_character_range=[start,end], raw_text=raw, display_text=raw,
                ownership_state=state, support_is_historical_only=True, token_time_alignment='UNAVAILABLE',
                caption_application_scope='historical_caption_annotation_only', voice_or_direction_permission=False))
        if len(segments)==1: segments[0]['display_text']=row['display_text']
        if ''.join(x['raw_text'] for x in segments)!=row['text'] or [t for x in segments for t in x['token_ids']]!=ids:
            raise RuntimeError('Segments must partition exact raw text and token IDs')
        row.update(segments=segments, _segment_serial=serial, ownership_mode=self.ownership_mode)
        if len(segments)==1 and segments[0]['ownership_state']=='supported_history':
            for key in ('label','track_id','known_profile_id','known_name','naming_state','anonymous_label'):
                row[key]=deepcopy(segments[0].get(key))
        else:
            row.update(label='Mixed supported / pending' if any(owners) else 'Pending identity',
                track_id=None, known_profile_id=None, known_name=None, naming_state='unresolved', anonymous_label='Unknown')

    def consume(self, kind, payload, now=None):
        with self._lock:
            return self._consume(kind, payload, time.perf_counter() if now is None else now)

    def _consume(self, kind, payload, now):
        if kind not in self.KINDS:
            return None
        if payload.get('session_id') != self.session_id:
            return self._reject('foreign_session')
        key = payload.get('utterance_id')
        if not isinstance(key, str) or not key:
            return self._reject('missing_utterance')
        if kind in {'s6d_text_ready', 'transcript_partial', 'transcript_final'} and (
                not isinstance(payload.get('text'), str) or not isinstance(payload.get('display_text', payload.get('text')), str)):
            return self._reject('nonstring_words')
        row = self.rows.get(key)
        correction = kind in {'transcript_label_revision', 's6d_punctuation_revision'}
        if row is None and correction:
            if len(self._pending) >= self.settings.max_display_rows and key not in self._pending:
                raise RuntimeError('Bounded S7 pending-caption correction capacity exhausted')
            pending = self._pending.setdefault(key, [])
            identifier = payload.get('event_id', payload.get('publication_sequence'))
            if identifier is not None and any(old_kind == kind and old.get('event_id', old.get('publication_sequence')) == identifier
                                              for old_kind, old, _ in pending):
                return self._reject('duplicate_pending_correction')
            if len(pending) >= 32:
                raise RuntimeError('Bounded S7 per-caption correction capacity exhausted')
            pending.append((kind, deepcopy(payload), now))
            self.rejected['deferred_until_caption'] += 1
            return None
        if row is None:
            if self._span(payload) is None or self._version(payload) is None:
                return self._reject('words_missing_span_or_version')
            if self._span(payload)[1] <= self._retired_through:
                return self._reject('retired_caption_cannot_reappear')
            if len(self.rows) >= self.settings.max_display_rows:
                old = next((k for k, item in self.rows.items() if item['final']), None)
                if old is None:
                    raise RuntimeError('Bounded S7 active caption capacity exhausted')
                self._retired_through = max(self._retired_through, self.rows[old]['source_end_sec'])
                del self.rows[old]
                self.evicted_final_rows += 1
            row = dict(session_id=self.session_id, utterance_id=key, caption_key=self.session_id + '/' + key,
                segment_id=self.session_id + '/' + key + '/segment:0', text='', display_text='', label='Pending identity',
                known_profile_id=None, known_name=None, naming_state='unresolved', track_id=None, anonymous_label='Unknown',
                final=False, revision_count=0, display_version=0, first_text_monotonic_sec=now,
                first_visible_monotonic_sec=None, first_display_label='Pending identity', first_final=None)
            self.rows[key] = row
        changed = False
        if kind in {'s6d_text_ready', 'transcript_partial', 'transcript_final'}:
            version = self._version(payload)
            old = row.get('_text_version')
            final = kind == 'transcript_final' or payload.get('final') is True
            if version is not None and (old is None or version > old) and (not row['final'] or final):
                if row.get('source_start_sec', self._span(payload)[0]) != self._span(payload)[0]:
                    return self._reject('words_changed_utterance_origin')
                prior_text = row['text']
                if not isinstance(payload.get('text'), str) or not isinstance(payload.get('display_text', payload['text']), str):
                    return self._reject('nonstring_words')
                if row['text'] != payload.get('text') and row.get('identity_version') is not None:
                    row['previous_supported_identity'] = self._identity_snapshot(row)
                    row.update(label='Pending identity', known_profile_id=None, known_name=None,
                               naming_state='unresolved', track_id=None)
                row.update(text=payload['text'], display_text=payload.get('display_text', payload['text']),
                    source_start_sec=self._span(payload)[0], source_end_sec=self._span(payload)[1], final=final,
                    _text_version=version, text_version=list(version),
                    text_revision_id=payload.get('text_revision_id', payload.get('input_event_id', payload.get('event_id'))))
                if self.ownership_mode == 'supported_prefix_v2':
                    self._prefix_tokens(row, prior_text, payload)
                else:
                    row['token_ids'] = deepcopy(payload.get('token_ids')) or self.token_ids(key, row['text'], version[1])
                row['token_range'] = [0, len(row['token_ids'])]
                if final and row['first_final'] is None:
                    row['first_final'] = dict(text=row['text'], source_span=list(self._span(payload)),
                        text_version=list(version), received_monotonic_sec=now, label=row['label'])
                changed = True
            elif version is None or old is not None and version < old:
                self.rejected['older_or_unversioned_words'] += 1
            elif old == version and payload.get('text') != row['text']:
                self.rejected['conflicting_text_version'] += 1
        if kind in {'transcript_partial', 'transcript_final', 'transcript_label_revision'}:
            changed = bool(self._identity(row, payload)) or changed
        if kind == 's6d_punctuation_revision':
            # Punctuation is attached to exact raw words, never the worker's current caption.
            if payload.get('text') != row['text'] or not row['final']:
                return self._reject('punctuation_wrong_raw_version')
            signature = (payload.get('text'), payload.get('display_text'))
            version = self._serial(payload.get('punctuation_version', payload.get('publication_sequence')))
            if version < 0 or version <= row.get('_punctuation_version', -1):
                return self._reject('older_or_unversioned_punctuation')
            if row.get('_punctuation_signature') == signature:
                return self._reject('duplicate_punctuation')
            row.update(display_text=payload['display_text'], _punctuation_signature=signature,
                       _punctuation_version=version,
                       punctuation_for_text_revision=row['text_revision_id'])
            if self.ownership_mode == 'supported_prefix_v2':
                self._refresh_segments(row)
            changed = True
        if not changed:
            return None
        if kind.endswith('revision'):
            row['revision_count'] += 1
            self.revisions += 1
        row['display_version'] += 1
        row['controller_update_monotonic_sec'] = now
        row['caused_by_event_id'] = payload.get('event_id')
        row['caused_by_publication_sequence'] = payload.get('publication_sequence')
        for field in ('first_display_time', 'first_final_time', 'first_final_label', 'first_known_name', 'first_known_name_time'):
            if field in payload:
                row.setdefault(field, deepcopy(payload[field]))
        pending = self._pending.pop(key, [])
        for pending_kind, pending_payload, pending_time in pending:
            self._consume(pending_kind, pending_payload, max(now, pending_time))
        shown = self.project(row)
        if shown['visible'] and row['first_visible_monotonic_sec'] is None:
            row['first_visible_monotonic_sec'] = now
            shown['first_visible_monotonic_sec'] = now
        return shown

    def project(self, row):
        """Apply current user view to a snapshot without rewriting canonical text/history."""
        with self._lock:
            result = {k: deepcopy(v) for k, v in row.items() if not k.startswith('_')}
            known = row.get('known_profile_id') is not None and row.get('naming_state') == 'confirmed'
            selected = known and (self.settings.all_enrolled or row.get('known_profile_id') in self.selected_ids)
            visible = self.mode != 'M4' or selected or self.full_view
            if self.mode in {'M0', 'M1'}:
                result.update(label='Caption' if self.mode == 'M0' else row.get('anonymous_label', 'Unknown'),
                              known_profile_id=None, known_name=None, naming_state='disabled')
            track = row.get('track_id')
            if track is not None and track not in self._columns and len(self._columns) < 2:
                self._columns[track] = ('left', 'right')[len(self._columns)]
            result.update(s7_enabled=True, mode=self.mode, view_revision=self.view_revision,
                selected_profile_ids=list(self.selected_ids), full_view=self.full_view, visible=visible,
                visibility_state='visible' if visible else 'hidden_unselected' if known else 'pending_identity',
                emphasized=self.mode == 'M3' and selected, display_state=self.display_state,
                column='unresolved' if track is None else self._columns.get(track, 'other'),
                direction_disposition='DIAGNOSTIC_OR_DISABLED_REQUIRES_INDEPENDENT_EVIDENCE',
                optional_model_workload_changed=False)
            if self.ownership_mode == 'supported_prefix_v2':
                segments = []
                for segment in row.get('segments', []):
                    item = deepcopy(segment)
                    person = item.get('known_profile_id') is not None and item.get('naming_state') == 'confirmed'
                    chosen = person and (self.settings.all_enrolled or item.get('known_profile_id') in self.selected_ids)
                    track = item.get('track_id')
                    if track is not None and track not in self._columns and len(self._columns) < 2:
                        self._columns[track] = ('left', 'right')[len(self._columns)]
                    item.update(visible=self.mode != 'M4' or chosen or self.full_view,
                        emphasized=self.mode == 'M3' and chosen,
                        column='unresolved' if track is None else self._columns.get(track, 'other'))
                    if self.mode in {'M0', 'M1'}:
                        item.update(label='Caption' if self.mode == 'M0' else item.get('anonymous_label', 'Unknown'),
                            known_profile_id=None, known_name=None, naming_state='disabled')
                    segments.append(item)
                result.update(ownership_mode=self.ownership_mode, segments=segments,
                    accepted_identity_snapshot=deepcopy(row.get('accepted_identity_snapshot')),
                    visible=any(x['visible'] for x in segments),
                    visibility_state='visible' if any(x['visible'] for x in segments) else 'pending_or_unselected',
                    column=segments[0]['column'] if len(segments)==1 else 'partitioned')
            return result

    def snapshot_rows(self):
        with self._lock:
            return [self.project(row) for row in self.rows.values()]

    def directions(self, observations, speech, identities, now):
        with self._lock:
            if self.mode != 'M6':
                return dict(mode=self.settings.direction_mode, arrows=[], suppressed=[{'reason': 'S7_direction_view_not_enabled'}],
                    evaluated_at_sec=now, association_unavailable_is_not_pass=True, disposition='DISABLED_PRESENTATION_MODE')
            # Change display selection only; preserve all original source/voice/confidence/age gates.
            original = self.settings
            try:
                self.settings = replace(original, selected_profile_ids=self.selected_ids)
                result = super().directions(observations, speech, identities, now)
            finally:
                self.settings = original
            result['disposition'] = ('DIAGNOSTIC_ONLY' if original.direction_mode == 'V0' else
                'OBSERVED_GATED_ARROWS_NOT_QUALIFICATION' if result['arrows'] else 'UNAVAILABLE_OR_ABSTAINING_NOT_EFFICACY_PASS')
            return result

    def user_action(self, action, value, *, now=None):
        """Timestamped view action; caller writes this record without recursive engine emission."""
        with self._lock:
            stamp = time.perf_counter() if now is None else now
            if type(stamp) not in (int, float) or not math.isfinite(stamp):
                raise ValueError('Finite user-action time required')
            if action == 'mode':
                self._validate_mode(value)
                self.mode = value
            elif action == 'selection':
                if not isinstance(value, (list, tuple)) or any(not isinstance(v, str) or not v for v in value) or len(set(value)) != len(value):
                    raise ValueError('Explicit unique selected profile IDs required')
                if self.mode == 'M4' and (self.settings.transcript_mode == 'T1' and len(value) != 1 or
                    self.settings.transcript_mode == 'T2' and not value and not self.settings.all_enrolled):
                    raise ValueError('M4 selection must retain the original T1/T2 cardinality contract')
                self.selected_ids = tuple(value)
            elif action == 'full_view':
                if type(value) is not bool:
                    raise ValueError('Boolean full-view action required')
                self.full_view = value
            elif action == 'display_state':
                if value not in {'active', 'listening', 'dim'}:
                    raise ValueError('Invalid software display state')
                self.display_state = value
            else:
                raise ValueError('Unknown S7 view action')
            self.action_serial += 1
            self.view_revision += 1
            return dict(kind='s7_user_action', session_id=self.session_id, action_id=f'{self.session_id}/action:{self.action_serial}',
                action=action, value=deepcopy(value), receipt_monotonic_sec=stamp, effective_monotonic_sec=stamp,
                view_revision=self.view_revision, mode=self.mode, selected_profile_ids=list(self.selected_ids),
                full_view=self.full_view, display_state=self.display_state, canonical_transcript_rewritten=False,
                presentation_only=True, optional_model_workload_changed=False)

    def lines(self, full_view=False):
        return [f'{row["label"]}: {row["display_text"]}' + (' …' if not row['final'] else '')
                for row in self.snapshot_rows() if full_view or row['visible']]
