"""Saved synthetic restart attribution failures. README_RESTART_OBSERVATIONS.md."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from application_resources import ResourceLedger, PHASES
from common import bind, freeze, load
from viewport_ledger_v2 import ViewportLedger
import review_restart_observations as subject

OUTPUT = None
OWNER = dict(pid=2147483000, create_time=1.)
SESSIONS = [dict(index=0, epoch=1, native_session='native/first', source_origin_monotonic_sec=10.5, completed_monotonic_sec=20.),
            dict(index=1, epoch=2, native_session='native/second', source_origin_monotonic_sec=30., completed_monotonic_sec=50.)]


def row(session='first', suffix='one', *, visible=True, final=True):
    key = session+'/'+suffix
    geometry = dict(mapped=True, visible_nonspace_characters=int(visible), checked_characters=1,
                    partially_clipped_characters=0, any_visible=visible)
    pane = dict(present_in_widget=True, caption_visible=visible, heading_visible=visible,
                applied_caption_text='Synthetic caption.', applied_heading_text='Unknown',
                caption_viewport=geometry, heading_viewport=deepcopy(geometry))
    return dict(row_id=key+'/row', caption_key=key, span_ids=[key+'/token'], final=final,
        raw_asr_text='Synthetic caption.', source_start_sec=0., source_end_sec=1., timing_kind='FIXTURE',
        speaker_revision=1, verified_profile_id=None, display_profile_id=None, naming_state='unknown', identity_assignment=None,
        strictly_filtered=False, caption_visible=visible, heading_visible=visible, panes=dict(active=pane, history=deepcopy(pane)))


def observation(at, rows, origin):
    return dict(schema='n4-tk-viewport-observation-v1', observed_monotonic_sec=at, rows=rows,
        source_origin_monotonic_sec=origin, source_elapsed_sec=None if origin is None else at-origin,
        source_clock='UNAVAILABLE' if origin is None else 'ACTUAL_SOURCE_MONOTONIC',
        source_relative_times_available=origin is not None, physical_scanout_measured=False,
        source_to_widget_latency_qualified=False, character_checks=0)


def viewport(folder, observations):
    ledger = ViewportLedger(folder)
    for item in observations: ledger.add(item)
    summary = ledger.close()
    freeze(folder/'RESULT.json', dict(status='RECORDED_RENDER_AND_TIMER_OBSERVATIONS', failure=None,
        timer_cancelled=True, ledger=bind(folder/'SUMMARY.json'), samples=summary['samples'],
        render_calls=2, periodic_calls=1, deferred_context=0, actual_source_delivery_verified=False,
        source_to_widget_latency_qualified=False, physical_scanout_measured=False, integrated_N4_cells=0))
    return bind(folder/'SUMMARY.json')


def resource(folder, *, missing_second=False, duplicate=False):
    folder.mkdir(parents=True); rows = []; ledger = ResourceLedger(OWNER); marks = []; count = 0
    for phase, at in zip(PHASES, (1., 2., 3., 10., 11., 40., 51.)):
        mark = dict(kind='phase', phase=phase, monotonic_sec=at); rows.append(mark); marks.append(mark)
        times = [(at+.1, at+.11)]
        if phase == 'running': times += [(15., 15.1), (19.9, 20.1), (25., 25.1), (29.9, 30.1), (35., 35.1)]
        for start, end in times:
            count += 1; memory = count*100
            proc = dict(OWNER, ppid=1, memory_info_bytes=dict(rss=memory, private=memory//2),
                unique_set_size_bytes=memory//4, proportional_set_size_bytes=None, threads=2,
                cpu_seconds=dict(user=float(count), system=0.))
            complete = not (missing_second and 30 <= start <= 50)
            tree = dict(status='ALIVE', processes=[proc], complete=complete, retired=[],
                incomplete_processes=[] if complete else [dict(pid=99, status='UNAVAILABLE_ACCESS_DENIED')],
                rss_sum_bytes_not_unique_physical=memory, private_commit_sum_bytes=memory//2,
                unique_set_size_sum_bytes=memory//4, pss_sum_bytes=None, thread_count_sum=2)
            value = dict(kind='sample', phase_at_start=phase, phase_at_end=phase,
                         began_monotonic_sec=start, ended_monotonic_sec=end, tree=tree)
            rows.append(value); ledger.accept(value)
    data = b''.join((json.dumps(r)+'\n').encode() for r in rows)
    if duplicate: data = data.replace(b'"rss": 100', b'"rss": 0, "rss": 100', 1)
    (folder/'SAMPLES.jsonl').write_bytes(data)
    result = dict(ledger.summary(), status='OBSERVED_HOST_RESOURCES', owner=OWNER, error=None, observer_thread_exited=True,
        phase_marks=marks, all_lifecycle_marks_present=True, interval_sec=.5, elapsed_sec=60.,
        gpu_visibility_environment='-1', controlled_whole_stack_qualified=False, target_qualified=False, integrated_N4_cells=0,
        evidence=bind(folder/'SAMPLES.jsonl'), observer_bytes=len(data))
    freeze(folder/'RESULT.json', result); return bind(folder/'RESULT.json')


class RestartObservationTests(unittest.TestCase):
    def folder(self, suffix=''):
        return OUTPUT/(self._testMethodName+suffix)

    def vp(self, observations, index=1, sessions=None, registry=None, suffix=''):
        b = viewport(self.folder(suffix), observations)
        return subject.partition_viewport(b, sessions=sessions or deepcopy(SESSIONS), index=index, registry=registry)

    def test_retained_caption_uses_original_clock_before_and_after_restart(self):
        value = self.vp([observation(21., [row()], None), observation(31., [row(), row('second')], 30.),
                         observation(49., [row(), row('second')], 30.)])
        self.assertEqual((value['current_spans'], value['retained_spans']), (1, 1))
        old = value['spans']['first/one/token']['first_visible_in_this_ledger']
        self.assertEqual(old['original_source_elapsed_sec'], 10.5)
        self.assertIsNone(old['current_ledger_source_elapsed_sec'])
        self.assertFalse(value['source_to_widget_latency_qualified'])

    def test_offscreen_old_caption_first_visibility_keeps_old_origin(self):
        value = self.vp([observation(21., [row(visible=False)], None), observation(31., [row()], 30.)])
        first = value['spans']['first/one/token']['first_visible_in_this_ledger']
        self.assertEqual((first['original_source_elapsed_sec'], first['current_ledger_source_elapsed_sec']), (20.5, 1.))

    def test_retired_and_resegmented_spans_remain_in_denominator(self):
        a = row('second'); b = deepcopy(a); b['row_id'] += 'new'
        value = self.vp([observation(31., [a], 30.), observation(32., [], 30.), observation(33., [b], 30.),
                         observation(34., [], 30.)])
        self.assertEqual(value['current_spans'], 1); self.assertEqual(value['distinct_rows'], 2)

    def test_foreign_caption_refused(self):
        with self.assertRaisesRegex(ValueError, 'Foreign or future'):
            self.vp([observation(31., [row('foreign')], 30.)])

    def test_future_session_caption_refused_in_first_ledger(self):
        with self.assertRaisesRegex(ValueError, 'Foreign or future'):
            self.vp([observation(12., [row('second')], 10.5)], index=0)

    def test_missing_caption_key_refused(self):
        a = row(); a['caption_key'] = None
        with self.assertRaisesRegex(ValueError, 'no session'): self.vp([observation(31., [a], 30.)])

    def test_current_caption_before_clock_refused(self):
        with self.assertRaisesRegex(ValueError, 'predates'):
            self.vp([observation(29., [row('second')], None), observation(31., [], 30.)])

    def test_changed_origin_refused(self):
        with self.assertRaises(ValueError): self.vp([observation(31., [row()], 29.)])

    def test_viewport_after_release_refused(self):
        with self.assertRaisesRegex(ValueError, 'escaped'): self.vp([observation(51., [row()], 30.)])

    def test_second_viewport_before_first_release_refused(self):
        with self.assertRaisesRegex(ValueError, 'escaped'):
            self.vp([observation(19., [row()], None), observation(31., [], 30.)])

    def test_cross_session_span_collision_refused(self):
        registry = dict(rows={}, spans={})
        self.vp([observation(12., [row()], 10.5)], index=0, registry=registry, suffix='first')
        b = row('second'); b['span_ids'] = row()['span_ids']
        with self.assertRaisesRegex(ValueError, 'reassigned'): self.vp([observation(31., [b], 30.)], registry=registry)

    def test_cross_session_row_collision_refused(self):
        registry = dict(rows={}, spans={})
        self.vp([observation(12., [row()], 10.5)], index=0, registry=registry, suffix='first')
        b = row('second'); b['row_id'] = row()['row_id']
        with self.assertRaisesRegex(ValueError, 'reassigned'): self.vp([observation(31., [b], 30.)], registry=registry)

    def test_overlapping_windows_refused(self):
        s = deepcopy(SESSIONS); s[1]['source_origin_monotonic_sec'] = 19.
        with self.assertRaisesRegex(ValueError, 'overlap'): subject.session_windows(s)

    def test_same_session_name_refused(self):
        s = deepcopy(SESSIONS); s[1]['native_session'] = s[0]['native_session']
        with self.assertRaisesRegex(ValueError, 'reuse'): subject.session_windows(s)

    def test_resource_crossing_samples_not_counted_twice(self):
        value = subject.partition_resources(resource(self.folder()), sessions=SESSIONS, expected_owner=OWNER)
        self.assertEqual(value['boundary_crossing_samples'], 2)
        self.assertEqual([g['samples'] for g in value['session_samples'].values()], [2, 2])
        self.assertTrue(value['both_sessions_have_complete_samples'])
        self.assertNotIn('pss_sum_bytes', value['session_samples']['0']['peaks'])
        self.assertFalse(value['controlled_whole_stack_qualified'])

    def test_missing_complete_second_samples_stays_unavailable(self):
        value = subject.partition_resources(resource(self.folder(), missing_second=True), sessions=SESSIONS, expected_owner=OWNER)
        self.assertFalse(value['both_sessions_have_complete_samples'])
        self.assertIsNone(value['session_samples']['1']['first'])
        self.assertEqual(value['session_samples']['1']['peaks'], {})

    def test_resource_wrong_owner_refused(self):
        with self.assertRaisesRegex(ValueError, 'different application'):
            subject.partition_resources(resource(self.folder()), sessions=SESSIONS, expected_owner=dict(pid=99, create_time=1.))

    def test_resource_duplicate_json_keys_refused(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON'):
            subject.partition_resources(resource(self.folder(), duplicate=True), sessions=SESSIONS, expected_owner=OWNER)

    def test_resource_window_outside_lifecycle_refused(self):
        s = deepcopy(SESSIONS); s[1]['completed_monotonic_sec'] = 52.
        with self.assertRaisesRegex(ValueError, 'lifecycle'):
            subject.partition_resources(resource(self.folder()), sessions=s, expected_owner=OWNER)

    def test_resource_changed_during_reread_refused(self):
        b = resource(self.folder()); called = [False]
        def mutate():
            if not called[0]:
                called[0] = True
                with (self.folder()/'SAMPLES.jsonl').open('ab') as stream: stream.write(b'\n')
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            subject.partition_resources(b, sessions=SESSIONS, expected_owner=OWNER, checkpoint=mutate)

    def composition(self):
        app = self.folder()/'application'; resource(app/'resources')
        prepared = dict(backend_id='fixture-backend'); freeze(app/'PREPARED.json', prepared)
        evidences = [bind(app/'PREPARED.json'), bind(app/'resources/RESULT.json')]
        for index, name in enumerate(('01', '02')):
            folder = app/'sessions'/name; current = [row()] if index == 0 else [row(), row('second')]
            at, origin = (12., 10.5) if index == 0 else (31., 30.)
            vp = app/'viewport' if index == 0 else folder/'viewport'
            viewport(vp, [observation(at, current, origin), observation(at+1, current, origin),
                          observation(SESSIONS[index]['completed_monotonic_sec']-.1, current, origin)])
            freeze(folder/'RESULT.json', dict(viewport=bind(vp/'RESULT.json')))
            freeze(folder/'ENGINE_CLOSURE.json', dict(observed_monotonic_sec=SESSIONS[index]['completed_monotonic_sec']-.2))
            controller_rows = []
            for item in current:
                r = deepcopy(item); r['id'] = r.pop('row_id'); r['profile_id'] = r.pop('verified_profile_id'); controller_rows.append(r)
            freeze(folder/'CONTROLLER_SNAPSHOT.json', dict(rows=controller_rows, state='STOPPED', error=None,
                saved_audio_only=True, epoch=index+1, backend_id='fixture-backend', mode='fixture', tap='O0',
                recipe='balanced', selected_ids=[], strict=False, pending_actions=0, reference_comparison=None, settings={}))
            evidences += [bind(p) for p in folder.glob('*.json')]+[bind(vp/'RESULT.json'), bind(vp/'SUMMARY.json')]
        pair = dict(sessions=deepcopy(SESSIONS), evidence=evidences)
        return app, pair

    def test_composition_reconstructs_both_raw_ledgers_and_resource_log(self):
        app, pair = self.composition()
        with patch.object(subject, 'review_pair', return_value=pair), patch.object(subject, 'prepared_context', return_value={}):
            value = subject.review_observations(app, payload=dict(contract=dict(mode='fixture'), job=dict(tap='O0')), application_owner=OWNER)
        self.assertTrue(value['viewport_rows_reviewed']); self.assertTrue(value['resource_samples_reviewed'])
        self.assertEqual(value['viewport_reviews'][1]['retained_spans'], 1)
        self.assertFalse(value['actual_restart_qualified']); self.assertFalse(value['native_caption_payloads_joined'])

    def test_composition_rejects_pair_binding_changed_before_observation_read(self):
        app, pair = self.composition(); path = app/'sessions/02/CONTROLLER_SNAPSHOT.json'
        value = load(path); value['strict'] = True; path.write_text(json.dumps(value), encoding='utf-8')
        with patch.object(subject, 'review_pair', return_value=pair), patch.object(subject, 'prepared_context', return_value={}):
            with self.assertRaisesRegex(ValueError, 'changed after pair'):
                subject.review_observations(app, payload=dict(contract=dict(mode='fixture'), job=dict(tap='O0')), application_owner=OWNER)
