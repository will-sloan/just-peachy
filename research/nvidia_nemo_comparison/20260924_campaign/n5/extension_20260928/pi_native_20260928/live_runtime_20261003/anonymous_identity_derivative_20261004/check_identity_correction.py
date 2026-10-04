"""Bounded host replay, no native imports. See README_IDENTITY_CORRECTION.md."""
import psutil
psutil.Process().cpu_affinity([14])
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-package', required=True)
    parser.add_argument('--closed-monitor', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    output = Path(args.output_root)/('identity-correction-check-'+uuid.uuid4().hex)
    output.mkdir()
    with (output/'REGISTERED_OWNER.json').open('x') as stream:
        json.dump(dict(pid=os.getpid(), create_time=psutil.Process().create_time(), affinity=[14]), stream)
        stream.flush(); os.fsync(stream.fileno())
    base, local = Path(args.base_package), Path(__file__).parent
    assert hashlib.sha256((base/'PACKAGE_MANIFEST.json').read_bytes()).hexdigest() == \
        'a8808f4807321bfaae814a0297c7602cb071ba1f54c849381d3a4d63473fb476'
    monitor = Path(args.closed_monitor)
    assert (monitor/'MIRROR_COMPLETE.json').is_file()
    paths = list((monitor/'closed-output').rglob('events.jsonl.index.json'))
    assert len(paths) == 1
    sys.path[:0] = [str(local), str(base)]
    sys.dont_write_bytecode = True
    from event_compaction import iter_events
    from profiles import RuntimeSelection
    from late_labels import SingleD1LateLabels
    from admitted_identity import admitted_anonymous_identity
    spec = importlib.util.spec_from_file_location('unchanged13_late_labels', base/'late_labels.py')
    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    selection = RuntimeSelection('nemotron', 'redimnet', 'saved', 'current_delayed',
        allow_experimental=True, speaker_attribution='single_d1_late_labels',
        embedding_schedule='sparse_clean_turn')
    counts = Counter(); sample = None; revised = previous = None; now = 0.
    for event in iter_events(paths[0].with_name('events.jsonl'), maximum_bytes=16*1024**2, maximum_records=20000):
        if event.get('event_type') != 's6d_display':
            continue
        row = event['payload']; counts['actual_display_rows'] += 1
        if revised is None:
            revised = SingleD1LateLabels(selection, row['session_id'], 'actual-source-clock')
            previous = old.SingleD1LateLabels(selection, row['session_id'], 'actual-source-clock')
        now = max(now, row['controller_update_monotonic_sec'])
        before, after = previous.project(row, now=now), revised.project(row, now=now)
        if before: counts['old_supported_publications'] += before['speaker_supported']
        if after:
            counts['new_supported_publications'] += after['speaker_supported']
            assert after['text'] == row['text'] and after['display_text'] == row['display_text']
            assert after['caption_key'] == row['caption_key']
            assert after['source_start_sec'] == row['source_start_sec']
            assert after['source_end_sec'] == row['source_end_sec']
            for span in after['attribution_spans']:
                if span['evidence'] and span['evidence']['evidence_kind'] == 'admitted_native_anonymous_track':
                    assert span['evidence']['known_profile_id'] is None
                    counts['anonymous_evidence_publications'] += 1
        for word in row.get('word_spans', []):
            history = word.get('speaker_history', [])
            if history and admitted_anonymous_identity(row, word, history[-1]) is not None:
                counts['actual_matched_anonymous_observations'] += 1
                if sample is None:
                    sample = deepcopy(row), word['id'], now
    assert sample is not None and counts['old_supported_publications'] == 0
    assert counts['new_supported_publications'] > 0
    row, identifier, stamp = sample

    def resolve(changed):
        word = next(w for w in changed['word_spans'] if w['id'] == identifier)
        return admitted_anonymous_identity(changed, word, word['speaker_history'][-1])

    assert resolve(row) is not None
    for case in ('foreign_event', 'null_track', 'missing_source_evidence', 'wrong_revision',
                 'unsupported_owner', 'foreign_segment', 'missing_voice_track', 'name_not_anonymous'):
        changed = deepcopy(row)
        word = next(w for w in changed['word_spans'] if w['id'] == identifier)
        history = word['speaker_history'][-1]
        segment = next(s for s in changed['segments'] if identifier in s['token_ids'])
        if case == 'foreign_event': history['event_id'] = 'foreign:1'
        elif case == 'null_track': history['track_id'] = None
        elif case == 'missing_source_evidence': segment['identity_source_span'] = None
        elif case == 'wrong_revision': segment['text_revision_id'] = 'foreign:1'
        elif case == 'unsupported_owner': segment['ownership_state'] = 'pending'
        elif case == 'foreign_segment': segment['session_id'] = 'foreign-session'
        elif case == 'missing_voice_track': segment['track_id'] = None
        else: segment['known_profile_id'] = 'unverified-person'
        assert resolve(changed) is None, case
        counts['negative_contract_cases'] += 1

    expired = SingleD1LateLabels(selection, row['session_id'], 'actual-source-clock')
    late_stamp = max(w['first_seen_monotonic_sec'] for w in row['word_spans']) + 31.
    result = expired.project(row, now=late_stamp)
    assert not result['speaker_supported']
    counts['expired_evidence_rejected'] += 1
    fresh = SingleD1LateLabels(selection, row['session_id'], 'actual-source-clock')
    first = fresh.project(row, now=stamp)
    assert fresh.project(row, now=stamp) is None
    retracted = deepcopy(row)
    for word in retracted['word_spans']:
        if word.get('speaker_history'):
            history = word['speaker_history'][-1]
            history.update(label='Unknown', track_id=None, profile_id=None,
                           identity_version=[history['identity_version'][0]+1, history['identity_version'][1]+1])
    result = fresh.project(retracted, now=stamp+.01)
    assert result and not result['speaker_supported'] and result['caption_key'] == first['caption_key']
    counts['unknown_retraction_and_no_duplicate_verified'] += 1
    report = dict(schema='just-peachy.anonymous-identity-correction-check.v1', counts=dict(counts),
        native_executed=False, scope='Actual captured S7 row replay with negative boundary mutations; no model or quality test',
        source={name:hashlib.sha256((local/name).read_bytes()).hexdigest()
                for name in ('admitted_identity.py','late_labels.py','check_identity_correction.py')},
        mirrored_completion_sha256=hashlib.sha256((monitor/'MIRROR_COMPLETE.json').read_bytes()).hexdigest())
    (output/'RESULT.json').write_text(json.dumps(report, sort_keys=True), encoding='utf-8')
    print(json.dumps(dict(output=str(output), counts=dict(counts), native_executed=False)))


if __name__ == '__main__':
    main()
