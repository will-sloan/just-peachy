"""Private raw-ASR/publication lineage. See README_NATIVE_TEXT_REVIEW.md."""
from copy import deepcopy
from pathlib import Path
import re

from common import fingerprint, verify
from review_application_transport import finite
from review_native_journal import inspect, require_complete, rows, segments
from review_scoring_bank import require

MAX_REVISIONS = 32768
MAX_UTTERANCES = 4096
MAX_TEXT_BYTES = 65536
MAX_TOTAL_TEXT_BYTES = 8*1024**2
RAW_FIELDS = ('kind', 'event_id', 'utterance_id', 'source_start_sec', 'source_end_sec',
              'text', 'final', 'display_text', 'punctuation', 'asr_decode_ms')


def text(value):
    require(type(value) is str and len(value.encode('utf-8')) <= MAX_TEXT_BYTES,
            'Native text must be a bounded string')
    return value


def publication(payload):
    return {key: payload[key] for key in ('publication_sequence', 'publication_monotonic_sec',
                                         'publication_source_cursor_sec')}


def project(events, *, session_id, source_origin, duration):
    """Interpret already envelope-checked records; use review() on real evidence.

    No references, models, names, UI text or inferred word alignment enter the
    raw hypothesis. Partial-only utterances stay explicit and are not finalized.
    """
    revisions = {}; utterances = {}; punctuation = []; counts = {}; total = 0
    previous_sequence = 0
    for event in events:
        kind = event['event_type']; p = event['payload']
        require(p['session_id'] == session_id and type(p['publication_sequence']) is int
                and p['publication_sequence'] > previous_sequence, 'Native text event order/session differs')
        previous_sequence = p['publication_sequence']
        if kind not in ('research_asr_observation', 's6d_text_ready', 's6d_punctuation_revision'):
            continue
        counts[kind] = counts.get(kind, 0)+1
        uid = p['utterance_id']
        require(type(uid) is str and re.fullmatch(r'utterance:[0-9]{6,12}', uid) is not None,
                'Invalid native utterance identity')
        raw = text(p['text']); display = text(p['display_text'])
        total += len(raw.encode('utf-8'))+len(display.encode('utf-8'))
        require(total <= MAX_TOTAL_TEXT_BYTES, 'Native text byte budget exceeded')
        if kind == 'research_asr_observation':
            rid = p['event_id']; serial = len(revisions)+1
            require(serial <= MAX_REVISIONS and rid == f'asr:{serial:08d}', 'ASR revision serial differs')
            require(p['kind'] == 'asr' and type(p['final']) is bool, 'ASR kind/final flag differs')
            a, b = p['source_start_sec'], p['source_end_sec']
            require(finite(a) and finite(b) and 0 <= a <= b and event['source_time_sec'] == b,
                    'ASR source support differs')
            require(finite(p['available_at_sec']) and p['available_at_sec'] >= 0
                    and finite(p['asr_decode_ms']) and p['asr_decode_ms'] >= 0, 'ASR diagnostic clock differs')
            require(p['punctuation'] is None or type(p['punctuation']) is dict, 'Invalid ASR punctuation object')
            if p['punctuation'] is not None:
                require(p['final'] and text(p['punctuation']['text']) == display,
                        'Synchronous punctuation differs from formatted display')
            if uid not in utterances:
                require(len(utterances) < MAX_UTTERANCES, 'Native utterance budget exceeded')
                utterances[uid] = dict(utterance_id=uid, first_revision_id=rid, latest_revision_id=rid,
                                      final_revision_id=None, revision_ids=[])
            utterance = utterances[uid]
            require(utterance['final_revision_id'] is None, 'ASR revised an already finalized utterance')
            if utterance['revision_ids']:
                old = revisions[utterance['latest_revision_id']]
                require(old['source_start_sec'] == a and old['source_end_sec'] <= b,
                        'ASR utterance source support moved backwards')
            item = {key: deepcopy(p[key]) for key in RAW_FIELDS}
            item.update(modeled_available_at_sec=p['available_at_sec'], observation=publication(p),
                        text_ready=None, source_end_outside_audio=b > duration)
            revisions[rid] = item
            utterance['revision_ids'].append(rid); utterance['latest_revision_id'] = rid
            if p['final']: utterance['final_revision_id'] = rid
        elif kind == 's6d_text_ready':
            rid = p['event_id']
            require(rid in revisions and p['text_revision_id'] == rid, 'Text publication has no preceding raw revision')
            item = revisions[rid]
            require(item['text_ready'] is None
                    and fingerprint({key: p[key] for key in RAW_FIELDS})
                    == fingerprint({key: item[key] for key in RAW_FIELDS}),
                    'Text publication duplicated or changed raw-ASR fields')
            require(event['source_time_sec'] == item['source_end_sec'] and p['identity_pending'] is True
                    and p['publication_path'] == 'independent_asr_before_policy'
                    and p['speaker'] == 'Pending identity', 'Text publication path differs')
            ids = p['token_ids']
            require(type(ids) is list and len(ids) == len(raw.split())
                    and all(type(x) is str and 0 < len(x) <= 256 for x in ids)
                    and len(set(ids)) == len(ids), 'Raw publication token census differs')
            require(p['token_timing'] == 'untimed hypothesis revision positions; not phonetic alignment',
                    'Unexpected token timing authority')
            ready = p['observed_text_ready_at_sec']
            require(p['availability_clock'] == 'observed_text_publication_before_policy_admission'
                    and p['modeled_available_at_sec'] == item['modeled_available_at_sec']
                    and finite(ready) and ready == p['available_at_sec']
                    and ready >= item['source_end_sec']
                    and source_origin+ready >= item['observation']['publication_monotonic_sec']
                    and source_origin+ready <= p['publication_monotonic_sec']+1e-6,
                    'Raw text observed/modelled clock lineage differs')
            item['text_ready'] = dict(**publication(p), observed_text_ready_at_sec=ready,
                                     upstream_token_ids=list(ids))
        else:
            require(uid in utterances and utterances[uid]['final_revision_id'] is not None,
                    'Punctuation has no preceding final raw utterance')
            rid = utterances[uid]['final_revision_id']; item = revisions[rid]
            require(raw == item['text'] and p['changes_raw_words'] is False,
                    'Punctuation raw target differs from final ASR words')
            require(type(p['punctuation']) is dict and text(p['punctuation']['text']) == display
                    and event['source_time_sec'] == item['source_end_sec'], 'Punctuation target/display differs')
            start, finish = p['compute_started_monotonic_sec'], p['compute_finished_monotonic_sec']
            require(finite(start) and finite(finish)
                    and item['observation']['publication_monotonic_sec'] <= start <= finish
                    <= p['publication_monotonic_sec'], 'Punctuation compute/publication order differs')
            punctuation.append(dict(utterance_id=uid, raw_revision_id=rid, display_text=display,
                publication=publication(p), compute_started_monotonic_sec=start,
                compute_finished_monotonic_sec=finish, formatting_only_not_raw_hypothesis=True))
    require(all(item['text_ready'] is not None for item in revisions.values()),
            'Raw revisions lack independent text publication')
    final_ids = [u['final_revision_id'] for u in utterances.values() if u['final_revision_id'] is not None]
    unfinished = [u['utterance_id'] for u in utterances.values() if u['final_revision_id'] is None]
    final_text = ' '.join(revisions[rid]['text'] for rid in final_ids)
    return dict(status='PASS_NATIVE_RAW_TEXT_PUBLICATION_LINEAGE_ONLY', session_id=session_id,
        event_counts=counts, raw_revisions=list(revisions.values()), utterances=list(utterances.values()),
        final_revision_ids=final_ids, partial_only_utterance_ids=unfinished, raw_final_text=final_text,
        raw_final_word_count=len(final_text.split()), formatting_revisions=punctuation,
        source_end_overhang_revisions=sum(r['source_end_outside_audio'] for r in revisions.values()),
        source_timestamp_policy='Preserved ASR revision support; diagnostic overhang retained, never clamped',
        raw_text_publication_lineage_reviewed=True, raw_hypothesis_completeness_qualified=False,
        partial_only_policy='Retain unfinished utterances separately; do not fabricate final words or silently accept a final-only metric',
        caption_strings_independently_scored=False, names_independently_scored=False,
        accuracy_qualified=False, source_to_widget_latency_qualified=False,
        token_time_alignment='UNAVAILABLE', full_native_payload_semantics_reviewed=False,
        application_owner_reviewed=False, production_panel_reviewed=False, integrated_N4_cells=0, N4_accepted=False)


def review(session, *, job, expected_envelope, checkpoint=None):
    """Recheck complete native history and its exact binding to a prior review.

    Caller must separately reconstruct V2 transport/ownership and plan coverage.
    The returned private text is never a public qualification or Git artifact.
    """
    envelope = require_complete(inspect(session, job=job, checkpoint=checkpoint))
    require(fingerprint(envelope) == fingerprint(expected_envelope), 'Native envelope changed before text interpretation')
    result = project(rows(envelope['journal'], checkpoint), session_id=Path(session).name,
        source_origin=envelope['source_start']['source_epoch_monotonic_sec'], duration=job['frames']/16000)
    require(segments(session) == envelope['journal'], 'Native segment set changed during text interpretation')
    for binding in envelope['journal']+envelope['terminal']: verify(binding)
    result.update(job_sha256=fingerprint(job), native_envelope_sha256=fingerprint(envelope),
                  evidence=envelope['journal']+envelope['terminal'])
    return result
