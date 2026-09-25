"""Native caption/raw-word partitions. See README_NATIVE_CAPTION_REVIEW.md."""
from copy import deepcopy
from pathlib import Path
import re

from common import fingerprint, verify
from review_native_journal import rows, segments
from review_native_text import review as review_text, text
from review_application_transport import finite
from review_scoring_bank import require

MAX_DISPLAYS = 32768
MAX_SPANS = 8192
MAX_SEGMENTS = 512
MAX_TEXT_BYTES = 8*1024**2
TIMING = 'ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT'
CAUSES = {'s6d_text_ready', 'transcript_partial', 'transcript_final',
          'transcript_label_revision', 's6d_punctuation_revision'}
STABLE = ('id', 'text', 'source_start_sec', 'source_end_sec', 'timing_kind',
          'exact_word_start_sec', 'exact_word_end_sec', 'first_seen_monotonic_sec')
IDENTITY = ('label', 'track_id', 'known_profile_id', 'known_name', 'naming_state',
            'anonymous_label', 'prototype_assignment', 'closed_display_assignment',
            'speaker_revision', 'first_shown_label', 'committed_label')


def same(a, b):
    return fingerprint(a) == fingerprint(b)


def pair(value, maximum):
    require(type(value) is list and len(value) == 2 and all(type(x) is int for x in value)
            and 0 <= value[0] <= value[1] <= maximum, 'Invalid caption partition range')
    return value


def project(events, *, raw):
    """Pure interpretation of already reviewed native facts, not UI replay."""
    require(raw['status'] == 'PASS_NATIVE_RAW_TEXT_PUBLICATION_LINEAGE_ONLY', 'Reviewed raw lineage required')
    revisions = {r['event_id']: r for r in raw['raw_revisions']}
    require(len(revisions) == len(raw['raw_revisions']), 'Duplicate reviewed raw revision')
    causes = {}; captions = {}; span_facts = {}; seen_revisions = set(); displays = []; total = 0
    formatting = {}
    for f in raw['formatting_revisions']:
        formatting.setdefault(f['raw_revision_id'], []).append(f)
    previous_serial = 0
    for event in events:
        p = event['payload']; kind = event['event_type']; serial = p['publication_sequence']
        require(type(serial) is int and serial > previous_serial and p['session_id'] == raw['session_id'],
                'Native caption event order/session differs')
        previous_serial = serial
        if kind in CAUSES:
            causes[serial] = dict(kind=kind, utterance_id=p.get('utterance_id'),
                publication=p['publication_monotonic_sec'])
        if kind != 's6d_display': continue
        require(len(displays) < MAX_DISPLAYS, 'Native display budget exceeded')
        rid = p['text_revision_id']; require(rid in revisions, 'Caption has no raw ASR revision')
        r = revisions[rid]; key = raw['session_id']+'/'+r['utterance_id']
        require(p['utterance_id'] == r['utterance_id'] and p['caption_key'] == key
                and p['ownership_mode'] == 'timestamped_spans_v3', 'Caption identity or ownership contract differs')
        require(all(same(p[k], r[k]) for k in ('text', 'final', 'source_start_sec', 'source_end_sec')),
                'Caption changed raw words, finality or source support')
        require(r['text_ready']['publication_sequence'] < serial, 'Caption precedes raw text publication')
        cause = causes.get(p['caused_by_publication_sequence'])
        require(cause is not None and cause['utterance_id'] == p['utterance_id'], 'Caption cause is missing or foreign')
        applied, published = p['controller_update_monotonic_sec'], p['publication_monotonic_sec']
        require(finite(applied) and finite(published) and cause['publication'] <= applied <= published,
                'Caption cause/state/publication clock differs')
        version = p['display_version']
        require(type(version) is int and version > 0, 'Invalid native display version')
        prior = captions.get(key)
        require(prior is None or version > prior['version'], 'Native display version reused or moved backwards')
        display_text = text(p['display_text'])
        allowed = [r['display_text']]+[f['display_text'] for f in formatting.get(rid, [])
            if f['publication']['publication_sequence'] < serial]
        require(display_text in allowed, 'Caption formatting has no preceding raw/formatting publication')
        tokens, words, parts = p['token_ids'], p['word_spans'], p['segments']
        lexical = list(re.finditer(r'\S+', p['text']))
        require(type(tokens) is list and type(words) is list and len(tokens) == len(words) == len(lexical)
                and len(tokens) <= MAX_SPANS and all(type(t) is str and 0 < len(t) <= 512 for t in tokens)
                and len(set(tokens)) == len(tokens), 'Caption token/span census differs')
        require(type(parts) is list and 0 < len(parts) <= MAX_SEGMENTS
                and len({part['segment_id'] for part in parts}) == len(parts), 'Caption segment census differs')
        prior_ids = prior['tokens'] if prior else set()
        for token, word, match in zip(tokens, words, lexical):
            require(word['id'] == token and word['text'] == match.group()
                    and token.startswith(key+'/token:'), 'Caption word/span identity differs')
            a, b, first = word['source_start_sec'], word['source_end_sec'], word['first_seen_monotonic_sec']
            require(all(finite(v) for v in (a, b, first)) and r['source_start_sec'] <= a <= b <= r['source_end_sec']
                    and word['timing_kind'] == TIMING and word['exact_word_start_sec'] is None
                    and word['exact_word_end_sec'] is None and 0 < first <= applied,
                    'Caption word support or timing authority differs')
            stable = {k: word[k] for k in STABLE}
            if token in span_facts:
                require(token in prior_ids and same(span_facts[token], stable),
                        'Retired native span reappeared or stable word facts changed')
            else:
                require(len(span_facts) < MAX_SPANS and first >= r['text_ready']['publication_monotonic_sec'],
                        'New span precedes text publication or exceeds budget')
                span_facts[token] = deepcopy(stable)
        cursor = character = 0; compact = []
        for part in parts:
            a, b = pair(part['token_range'], len(tokens)); c, d = pair(part['raw_character_range'], len(p['text']))
            require((a < b or not tokens and len(parts) == 1) and type(part['segment_id']) is str
                    and part['segment_id'].startswith(key+'/segment:') and len(part['segment_id']) <= 512,
                    'Empty or foreign caption segment')
            require(a == cursor and c == character, 'Caption fragments have a gap, overlap or changed order')
            start = lexical[a].start() if a else 0
            end = lexical[b].start() if b < len(lexical) else len(p['text'])
            require([c, d] == [start, end] and part['raw_text'] == p['text'][c:d]
                    and part['token_ids'] == part['span_ids'] == tokens[a:b]
                    and same(part['word_spans'], words[a:b]), 'Caption fragment changed raw words or span membership')
            require(part['session_id'] == raw['session_id'] and part['caption_key'] == key
                    and part['text_revision_id'] == rid and part['timing_kind'] == TIMING,
                    'Caption fragment lineage differs')
            require(part['source_start_sec'] == min((w['source_start_sec'] for w in words[a:b]), default=r['source_start_sec'])
                    and part['source_end_sec'] == max((w['source_end_sec'] for w in words[a:b]), default=r['source_end_sec']),
                    'Caption fragment source bounds differ')
            require(part['display_text'] == (display_text if len(parts) == 1 else part['raw_text']),
                    'Caption segment formatting differs from native span policy')
            compact.append(dict(segment_id=part['segment_id'], token_range=[a, b], raw_character_range=[c, d],
                raw_text=part['raw_text'], span_ids=list(tokens[a:b]), source_start_sec=part['source_start_sec'],
                source_end_sec=part['source_end_sec'], identity={k: deepcopy(part.get(k)) for k in IDENTITY}))
            cursor, character = b, d
        require(cursor == len(tokens) and character == len(p['text']), 'Caption fragments omitted raw text')
        total += len(p['text'].encode('utf-8'))+len(display_text.encode('utf-8'))
        require(total <= MAX_TEXT_BYTES, 'Caption text accumulation exceeds budget')
        seen_revisions.add(rid)
        captions[key] = dict(version=version, tokens=set(tokens))
        displays.append(dict(publication_sequence=serial, publication_monotonic_sec=published,
            caption_key=key, raw_revision_id=rid, display_version=version,
            caused_by_publication_sequence=p['caused_by_publication_sequence'],
            controller_update_monotonic_sec=applied, final=p['final'], display_text=display_text,
            segments=compact, payload_sha256=fingerprint(p)))
    missing = sorted(set(revisions)-seen_revisions)
    return dict(status='PASS_NATIVE_CAPTION_RAW_PARTITIONS_ONLY', session_id=raw['session_id'],
        displays=displays, stable_word_spans=list(span_facts.values()), raw_revision_count=len(revisions),
        represented_raw_revisions=len(seen_revisions), missing_raw_revision_ids=missing,
        raw_revision_caption_coverage_complete=not missing, native_display_count=len(displays),
        raw_final_text=raw['raw_final_text'], partial_only_utterance_ids=raw['partial_only_utterance_ids'],
        scope='Native raw/caption/word-fragment lineage only; labels preserved as predictions, no truth or actual pane interpretation',
        raw_caption_partitions_reviewed=True, naming_accuracy_qualified=False, raw_hypothesis_completeness_qualified=False,
        actual_widget_content_joined=False, source_to_widget_latency_qualified=False, physical_scanout_measured=False,
        application_owner_reviewed=False, production_panel_reviewed=False, integrated_N4_cells=0, N4_accepted=False)


def review(session, *, job, expected_envelope, checkpoint=None):
    """Reconstruct raw lineage, then native caption partitions, with final binds."""
    raw = review_text(session, job=job, expected_envelope=expected_envelope, checkpoint=checkpoint)
    result = project(rows(expected_envelope['journal'], checkpoint), raw=raw)
    require(segments(session) == expected_envelope['journal'], 'Native segment set changed during caption review')
    for binding in raw['evidence']: verify(binding)
    result.update(native_raw_review_sha256=fingerprint(raw), native_envelope_sha256=raw['native_envelope_sha256'],
                  job_sha256=raw['job_sha256'], evidence=raw['evidence'])
    return result
