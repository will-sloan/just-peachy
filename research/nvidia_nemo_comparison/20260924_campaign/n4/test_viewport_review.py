"""Raw viewport reconstruction and tamper checks. README_VIEWPORT_REVIEW.md."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest

from common import bind, load
from viewport_ledger_v2 import ViewportLedger, encoded
from test_viewport_ledger_v2 import fixture
from review_viewport_evidence import review

CONTEXT = {}


class ViewportReviewTests(unittest.TestCase):
    def make(self, observations=None, suffix=''):
        directory = CONTEXT['output']/(self._testMethodName+suffix)
        ledger = ViewportLedger(directory)
        for observed in observations or [fixture(), fixture(11.)]: ledger.add(observed)
        ledger.close(); return directory

    def rewrite(self, directory, *, summary_change=None, record_change=None):
        summary = load(directory/'SUMMARY.json')
        if record_change:
            records = [load_line(line) for line in (directory/'OBSERVATIONS.jsonl').read_bytes().splitlines()]
            record_change(records)
            (directory/'OBSERVATIONS.jsonl').write_bytes(b''.join(encoded(r)+b'\n' for r in records))
            summary['log'] = bind(directory/'OBSERVATIONS.jsonl'); summary['log_bytes'] = summary['log']['bytes']
        if summary_change: summary_change(summary)
        (directory/'SUMMARY.json').write_bytes(encoded(summary)+b'\n')
        return bind(directory/'SUMMARY.json')

    def test_160_saved_actual_histories_reconstruct(self):
        reviewed = [review(case['summary']) for case in CONTEXT['saved']]
        self.assertEqual(len(reviewed), 160)
        self.assertTrue(all(r['observations'] == 2 and r['all_present_panes_have_geometry_counters'] for r in reviewed))
        self.assertTrue(all(r['source_origin_monotonic_sec'] is None and r['integrated_N4_cells'] == 0 for r in reviewed))
        CONTEXT['saved_reviews'] = reviewed

    def test_large_saved_synthetic_history_reconstructs(self):
        result = review(CONTEXT['large']['summary'])
        self.assertEqual((result['spans_reconstructed'],result['observations']), (8192,40))
        self.assertFalse(result['actual_continuity_test']); CONTEXT['large_review'] = result

    def test_clock_finality_heading_resegmentation_and_retirement(self):
        a = fixture(); b = fixture(11.)
        b.update(source_origin_monotonic_sec=10., source_elapsed_sec=1., source_clock='ACTUAL_SOURCE_MONOTONIC', source_relative_times_available=True)
        b['rows'][0]['final'] = True
        c = deepcopy(b); c['observed_monotonic_sec'] = 12.; c['source_elapsed_sec'] = 2.
        c['rows'][0]['panes']['active']['applied_heading_text'] = 'Assumed fixture'
        c['rows'][0]['display_profile_id'] = 'assumed-fixture'
        d = deepcopy(c); d['observed_monotonic_sec'] = 13.; d['source_elapsed_sec'] = 3.; d['rows'][0]['row_id'] = 'r2'
        e = deepcopy(d); e['observed_monotonic_sec'] = 14.; e['source_elapsed_sec'] = 4.; e['rows'] = []
        f = deepcopy(d); f['observed_monotonic_sec'] = 15.; f['source_elapsed_sec'] = 5.
        directory = self.make([a,b,c,d,e,f]); binding = bind(directory/'SUMMARY.json'); before = deepcopy(binding)
        calls=[]; result=review(binding, checkpoint=lambda:calls.append(True))
        self.assertEqual(result['row_retirements'],2); self.assertEqual(result['observations_with_source_clock'],5)
        self.assertEqual(result['source_origin_monotonic_sec'],10.); self.assertFalse(result['actual_source_delivery_verified'])
        self.assertGreaterEqual(len(calls),6); self.assertEqual(bind(directory/'SUMMARY.json'),before)
        self.assertEqual(result['span_summary_sha256'],hashlib.sha256(encoded(load(directory/'SUMMARY.json')['spans'])).hexdigest())

    def test_tampered_summary_counts_references_and_types_refused(self):
        changes=[lambda s:s.update(samples=3), lambda s:s.update(maximum_observation_interval_seconds=7.),
            lambda s:s['spans']['s1']['latest']['row_ref'].update(offset=1),
            lambda s:s['spans']['s1'].update(observed_heading_changes=True),
            lambda s:s['spans']['s1']['latest'].update(observed_monotonic_sec=12.),
            lambda s:s.update(continuous_exposure_measured=True)]
        for i, change in enumerate(changes):
            with self.subTest(i=i):
                directory=self.make(suffix=str(i)); binding=self.rewrite(directory,summary_change=change)
                with self.assertRaises(ValueError):review(binding)

    def test_regressing_changed_and_modeled_source_clock_refused(self):
        changes=[dict(observed_monotonic_sec=9.),dict(source_clock='MODELED'),
            dict(source_origin_monotonic_sec=10.,source_elapsed_sec=5.,source_clock='ACTUAL_SOURCE_MONOTONIC',source_relative_times_available=True)]
        for i, change in enumerate(changes):
            directory=self.make(suffix=str(i))
            binding=self.rewrite(directory,record_change=lambda rows:rows[1]['metadata'].update(change))
            with self.assertRaises(ValueError):review(binding)
        live=fixture(11.);live.update(source_origin_monotonic_sec=10.,source_elapsed_sec=1.,source_clock='ACTUAL_SOURCE_MONOTONIC',source_relative_times_available=True)
        later=deepcopy(live);later['observed_monotonic_sec']=12.;later['source_elapsed_sec']=2.
        directory=self.make([live,later],suffix='origin')
        binding=self.rewrite(directory,record_change=lambda rows:rows[1]['metadata'].update(source_origin_monotonic_sec=11.,source_elapsed_sec=1.))
        with self.assertRaises(ValueError):review(binding)

    def test_retirement_requires_exact_previous_reference(self):
        directory=self.make([fixture(),fixture(11.,[])])
        binding=self.rewrite(directory,record_change=lambda rows:rows[1]['changes'][0]['from_ref'].update(change_index=8))
        with self.assertRaisesRegex(ValueError,'exact prior'):review(binding)

    def test_ambiguous_shared_span_order_is_never_inferred(self):
        observation=fixture();second=deepcopy(observation['rows'][0]);second['row_id']='r2'
        second['panes']['active']['applied_heading_text']='Different fixture';observation['rows'].append(second)
        directory=self.make([observation])
        with self.assertRaisesRegex(ValueError,'Ambiguous'):review(bind(directory/'SUMMARY.json'))

    def test_pane_visibility_and_glyph_census_refused(self):
        changes=[lambda r:r.update(caption_visible=False), lambda r:r.update(strictly_filtered=True),
            lambda r:r['panes']['active'].update(present_in_widget=False),
            lambda r:r['panes']['active'].update(caption_viewport=dict(mapped=True,any_visible=True,
                visible_nonspace_characters=3,checked_characters=2,partially_clipped_characters=0))]
        for i, change in enumerate(changes):
            directory=self.make(suffix=str(i))
            binding=self.rewrite(directory,record_change=lambda rows:change(rows[0]['changes'][0]['row']))
            with self.assertRaises(ValueError):review(binding)

    def test_truncated_foreign_failed_and_duplicate_json_refused(self):
        directory=self.make(suffix='truncated');path=directory/'OBSERVATIONS.jsonl';path.write_bytes(path.read_bytes()[:-1])
        binding=self.rewrite(directory,summary_change=lambda s:s.update(log=bind(path),log_bytes=path.stat().st_size))
        with self.assertRaises(ValueError):review(binding)
        directory=self.make(suffix='foreign');foreign=directory/'OTHER.jsonl';foreign.write_bytes((directory/'OBSERVATIONS.jsonl').read_bytes())
        binding=self.rewrite(directory,summary_change=lambda s:s.update(log=bind(foreign)))
        with self.assertRaisesRegex(ValueError,'Foreign'):review(binding)
        directory=self.make(suffix='failed');binding=self.rewrite(directory,summary_change=lambda s:s.update(status='FAILED_PRESERVED_PREFIX'))
        with self.assertRaises(ValueError):review(binding)
        directory=self.make(suffix='duplicate');path=directory/'OBSERVATIONS.jsonl'
        path.write_bytes(path.read_bytes().replace(b'"index":0',b'"index":0,"index":0',1))
        binding=self.rewrite(directory,summary_change=lambda s:s.update(log=bind(path),log_bytes=path.stat().st_size))
        with self.assertRaisesRegex(ValueError,'Duplicate JSON'):review(binding)

    def test_log_hash_indices_unchanged_changes_and_bounds_refused(self):
        directory=self.make(suffix='hash');binding=bind(directory/'SUMMARY.json')
        with (directory/'OBSERVATIONS.jsonl').open('ab') as stream:stream.write(b'\n')
        with self.assertRaises(ValueError):review(binding)
        for i, change in enumerate([lambda r:r[1].update(index=9),lambda r:r[1].update(changes=deepcopy(r[0]['changes']))]):
            directory=self.make(suffix=str(i));binding=self.rewrite(directory,record_change=change)
            with self.assertRaises(ValueError):review(binding)
        directory=self.make(suffix='bound');binding=self.rewrite(directory,summary_change=lambda s:s.update(samples=100001))
        with self.assertRaises(ValueError):review(binding)


def load_line(line):
    from review_viewport_evidence import decode
    return decode(line)
