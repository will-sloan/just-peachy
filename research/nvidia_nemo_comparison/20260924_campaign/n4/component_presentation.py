"""Explicitly modeled input to the frozen caption state. README_COMPONENT_PRESENTATION.md."""
from copy import deepcopy
import math

CLOCK_KIND = 'MODELED_COMPONENT_REPLAY_NOT_OBSERVED_CONTROLLER_OR_WIDGET'


class ComponentPresentation:
    """Use the actual S7/N1 span implementation; never invent GUI observations.

    The caller owns causal merge and policy execution. This adapter admits raw
    ASR observations, actual policy records and final-only formatting records.
    It is not an integrated application runner or a new speaker association rule.
    """
    def __init__(self, state, *, max_events=100000):
        if state.ownership_mode != 'timestamped_spans_v3' or state.settings.max_display_rows != 512:
            raise ValueError('Require the frozen application span policy and row bound')
        self.state = state
        self.max_events = max_events
        self.now = 0.
        self.serial = 0
        self.text_serial = 0
        self.finals = {}
        self.last_text = {}
        self.events = []
        self.formatted = set()

    def _consume(self, kind, payload, available):
        if (type(available) not in (int, float) or not math.isfinite(available)
                or available < self.now or available < payload.get('source_end_sec', 0)
                or self.serial >= self.max_events):
            raise ValueError('Noncausal or over-budget modeled presentation event')
        if any(k.startswith('observed_') or k in ('publication_monotonic_sec', 'source_epoch_monotonic_sec') for k in payload):
            raise ValueError('Observed application clocks must not enter modeled replay')
        self.now = available
        self.serial += 1
        payload = deepcopy(payload)
        if payload.get('session_id', self.state.session_id) != self.state.session_id:
            raise ValueError('Foreign component session')
        payload['session_id'] = self.state.session_id
        # A source event version is real; this sequence numbers only replay
        # inputs. No production publication or widget receipt is synthesized.
        payload['publication_sequence'] = self.serial
        shown = self.state.consume(kind, payload, now=available)
        self.events.append(dict(kind=kind, input=payload, modeled_available_at_sec=available,
            clock_kind=CLOCK_KIND, presentation=deepcopy(shown), physical_widget_observed=False))
        return shown

    def text(self, observation):
        event = deepcopy(observation)
        if event.get('kind') != 'asr' or event.get('event_id') != f'asr:{self.text_serial+1:08d}':
            raise ValueError('Exact sequential raw ASR observations required')
        uid = event['utterance_id']
        if uid in self.finals:
            raise ValueError('Raw ASR observation after final')
        if event['final'] is not True and event['final'] is not False:
            raise ValueError('Actual final flag required')
        self.text_serial += 1
        payload = dict(event, speaker='Pending identity',
            token_ids=self.state.token_ids(uid, event['text'], self.text_serial),
            text_revision_id=event['event_id'],
            token_timing='untimed hypothesis revision positions; not phonetic alignment',
            identity_pending=True, publication_path='independent_asr_before_policy')
        shown = self._consume('s6d_text_ready', payload, event['available_at_sec'])
        self.last_text[uid] = event
        if event['final']:
            self.finals[uid] = event
        return shown

    def policy(self, record):
        if record.get('event_type') not in ('transcript_partial', 'transcript_final', 'transcript_label_revision'):
            raise ValueError('Only actual caption-policy outputs belong in presentation')
        uid = record.get('utterance_id')
        if uid not in self.last_text:
            raise ValueError('Policy cannot precede independent raw text publication')
        return self._consume(record['event_type'], record, record['available_at_sec'])

    def formatting(self, component):
        uid = component['utterance_id']
        final = self.finals.get(uid)
        if (final is None or uid in self.formatted or component['input_event_id'] != final['event_id']
                or component['raw_text'] != final['text']):
            raise ValueError('Formatting must bind its exact raw final once')
        punctuation = component['punctuation']
        payload = dict(utterance_id=uid, text=component['raw_text'], display_text=punctuation['text'],
            punctuation=punctuation, changes_raw_words=False,
            source_start_sec=final['source_start_sec'], source_end_sec=final['source_end_sec'])
        shown = self._consume('s6d_punctuation_revision', payload, component['modeled_available_at_sec'])
        self.formatted.add(uid)
        return shown

    def snapshot(self):
        rows = self.state.snapshot_rows()
        # These are the actual state object's field names. Every inherited
        # '*monotonic*' value here is explicitly modeled, not measured latency.
        for row in rows:
            expected = self.last_text[row['utterance_id']]
            if row['text'] != expected['text']:
                raise ValueError('Presentation dropped or replaced raw transcript text')
            if row.get('segments') and ''.join(s['raw_text'] for s in row['segments']) != row['text']:
                raise ValueError('Caption fragment reconstruction differs from raw words')
        if {r['utterance_id'] for r in rows} != set(self.last_text):
            raise ValueError('Caption row eviction or missing raw utterance')
        return dict(clock_kind=CLOCK_KIND, rows=rows, event_count=self.serial,
            rejected=dict(self.state.rejected), raw_observations=self.text_serial,
            final_utterances=len(self.finals), formatting_revisions=len(self.formatted),
            physical_widget_observed=False, observed_Controller_parity=False, integrated_N4_cells=0,
            first_visible_latency='UNAVAILABLE_MODELED_REPLAY',
            inherited_monotonic_field_names='MODELED_VALUES_ONLY_NOT_MEASUREMENTS')
