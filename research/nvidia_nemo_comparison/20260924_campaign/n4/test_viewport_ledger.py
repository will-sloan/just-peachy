"""Saved-observation equivalence and bounded-history failures. README_VIEWPORT_LEDGER.md."""
from copy import deepcopy
import json
from pathlib import Path
import threading
import unittest

from common import bind, load, verify
from viewport_ledger import ViewportLedger, encoded, expand_summary, read_row
from widget_visibility import VisibilityHistory

CONTEXT = {}


def fixture(at=10., rows=None):
    pane = dict(present_in_widget=True, caption_visible=True, heading_visible=True,
        applied_caption_text='Caption fixture.', applied_heading_text='Unknown')
    row = dict(row_id='r1', caption_key='c1', span_ids=['s1'], raw_asr_text='Caption fixture.',
        source_start_sec=0., source_end_sec=1., timing_kind='FIXTURE', speaker_revision=1,
        verified_profile_id=None, display_profile_id=None, naming_state='unknown', identity_assignment=None,
        strictly_filtered=False, final=False, caption_visible=True, heading_visible=True,
        panes=dict(active=deepcopy(pane), history=deepcopy(pane)))
    return dict(schema='n4-tk-viewport-observation-v1', observed_monotonic_sec=at,
        source_origin_monotonic_sec=None, source_elapsed_sec=None, source_clock='UNAVAILABLE',
        physical_scanout_measured=False, source_relative_times_available=False,
        source_to_widget_latency_qualified=False, rows=[row] if rows is None else rows,
        character_checks=0, scope='Synthetic ledger fixture; no source or widget execution')


class LedgerTests(unittest.TestCase):
    def directory(self, suffix=''):
        return CONTEXT['output']/(self._testMethodName+suffix)

    def test_saved_160_actual_viewport_histories_match_exactly(self):
        checks = []
        for i, binding in enumerate(CONTEXT['saved_cases']):
            verify(binding); saved = load(binding['path'])
            ledger = ViewportLedger(self.directory(f'-{i:03d}'))
            ledger.add(saved['first']); ledger.add(saved['last']); summary = ledger.close()
            self.assertEqual(expand_summary(ledger.path, summary), saved['history'])
            checks.append(dict(input=binding, summary=bind(ledger.directory/'SUMMARY.json'),
                exact_prior_history_equal=True, samples=summary['samples'], log_bytes=summary['log_bytes']))
        CONTEXT['saved_checks'] = checks

    def test_final_label_changes_resegmentation_and_retirement_match(self):
        observations = [fixture()]
        second = deepcopy(observations[-1]); second['observed_monotonic_sec'] += 1
        second['rows'][0]['final'] = True; observations.append(second)
        third = deepcopy(second); third['observed_monotonic_sec'] += 1
        third['rows'][0]['panes']['active']['applied_heading_text'] = 'Research fixture · assumed'
        third['rows'][0]['display_profile_id'] = 'fixture-assumed'; observations.append(third)
        fourth = deepcopy(third); fourth['observed_monotonic_sec'] += 1
        fourth['rows'][0]['row_id'] = 'r2'; observations.append(fourth)
        observations.append(fixture(14., []))
        observations.append(fixture(15.))
        legacy = VisibilityHistory(); ledger = ViewportLedger(self.directory())
        for observation in observations:
            before = deepcopy(observation); legacy.add(observation); ledger.add(observation)
            self.assertEqual(before, observation)
        self.assertEqual(expand_summary(ledger.path, ledger.close()), legacy.summary())

    def test_large_span_history_keeps_no_caption_copies_in_metadata(self):
        ledger = ViewportLedger(self.directory()); observation = fixture()
        row = observation['rows'][0]; row['span_ids'] = [f's{i}' for i in range(8192)]
        long_text = 'fixture caption '*3500
        row['raw_asr_text'] = long_text
        for pane in row['panes'].values(): pane['applied_caption_text'] = long_text
        ledger.add(observation)
        for i in range(1, 40):
            observation['observed_monotonic_sec'] = 10.+i*30
            observation['rows'][0]['final'] = True
            ledger.add(observation)
        self.assertEqual(len(ledger.spans), 8192)
        self.assertEqual(set(ledger.rows['r1']), {'sha256','span_ids','heading_hash','row_ref'})
        self.assertLess(ledger.bytes_written, 1024**2)
        summary = ledger.close(); summary_bytes = len(encoded(summary))
        self.assertLess(summary_bytes, 8*1024**2)
        self.assertNotIn(long_text[:100], encoded(summary).decode('utf-8'))
        CONTEXT['large_history'] = dict(summary=bind(ledger.directory/'SUMMARY.json'),
            spans=8192, synthetic_observations=40, log_bytes=ledger.bytes_written,
            compact_serialized_bytes=summary_bytes, actual_elapsed_continuity_test=False,
            process_memory_or_target_fit_qualified=False)

    def test_log_bound_preserves_prefix_and_no_silent_observation_loss(self):
        ledger = ViewportLedger(self.directory(), maximum_log_bytes=4096)
        ledger.add(fixture()); prefix = ledger.path.read_bytes()
        over = fixture(11.); over['rows'][0]['raw_asr_text'] = 'oversize '*2000
        with self.assertRaisesRegex(ValueError, 'allocation'): ledger.add(over)
        self.assertEqual(ledger.path.read_bytes(), prefix); self.assertEqual(ledger.samples, 1)
        with self.assertRaisesRegex(ValueError, 'failed'): ledger.add(fixture(12.))
        result = ledger.close(); self.assertEqual(result['status'], 'FAILED_PRESERVED_PREFIX')

    def test_corruption_and_foreign_file_are_rejected(self):
        ledger = ViewportLedger(self.directory()); ledger.add(fixture()); summary = ledger.close()
        ref = summary['spans']['s1']['latest']['row_ref']
        self.assertEqual(read_row(ledger.path, ref)['row_id'], 'r1')
        with self.assertRaises(ValueError): expand_summary(ledger.directory/'foreign', summary)
        # Deliberate corruption belongs only to this negative-test fixture.
        with ledger.path.open('r+b') as stream: stream.write(b'!')
        with self.assertRaisesRegex(ValueError, 'changed'): read_row(ledger.path, ref)

    def test_source_clock_and_observation_order_rejections(self):
        invalid = [dict(observed_monotonic_sec=9.), dict(observed_monotonic_sec=float('nan')),
            dict(source_origin_monotonic_sec=1., source_elapsed_sec=9., source_relative_times_available=True, source_clock='MODELED'),
            dict(source_origin_monotonic_sec=11., source_elapsed_sec=-1., source_relative_times_available=True, source_clock='ACTUAL_SOURCE_MONOTONIC')]
        for i, change in enumerate(invalid):
            ledger = ViewportLedger(self.directory(str(i))); ledger.add(fixture())
            bad = fixture(); bad.update(change)
            with self.assertRaises(ValueError): ledger.add(bad)
            self.assertEqual(ledger.samples, 1); ledger.close()
        ledger = ViewportLedger(self.directory('source-transition')); ledger.add(fixture())
        live = fixture(11.); live.update(source_origin_monotonic_sec=10., source_elapsed_sec=1.,
            source_relative_times_available=True, source_clock='ACTUAL_SOURCE_MONOTONIC')
        ledger.add(live)
        with self.assertRaises(ValueError): ledger.add(fixture(12.))
        ledger.close()

    def test_original_thread_ownership_is_enforced(self):
        ledger = ViewportLedger(self.directory()); errors = []
        def foreign():
            try: ledger.add(fixture())
            except ValueError as exc: errors.append(str(exc))
        thread = threading.Thread(target=foreign); thread.start(); thread.join(5.)
        self.assertFalse(thread.is_alive()); self.assertEqual(len(errors), 1)
        self.assertEqual(ledger.samples, 0); ledger.add(fixture()); ledger.close()

    def test_span_and_row_bounds_do_not_evict_evidence(self):
        ledger = ViewportLedger(self.directory()); ledger.add(fixture()); prefix = ledger.path.read_bytes()
        bad = fixture(11.); bad['rows'][0]['span_ids'] = [f'x{i}' for i in range(8193)]
        with self.assertRaisesRegex(ValueError, 'bound'): ledger.add(bad)
        self.assertEqual(ledger.path.read_bytes(), prefix); self.assertEqual(len(ledger.spans), 1); ledger.close()
        ledger = ViewportLedger(self.directory('rows')); bad = fixture()
        bad['rows'] = [dict(bad['rows'][0], row_id=f'r{i}') for i in range(513)]
        with self.assertRaisesRegex(ValueError, 'bounded'): ledger.add(bad)
        self.assertEqual(ledger.bytes_written, 0); ledger.close()
