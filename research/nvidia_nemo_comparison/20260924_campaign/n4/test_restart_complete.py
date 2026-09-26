"""Restart cross-reader/population composition failures. README_RESTART_COMPLETE_REVIEW.md."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze
from test_restart_run_review import fixture
import review_restart_complete as subject

OUTPUT = None
COORDINATOR = dict(pid=2147483000, create_time=1.)


def leaf_fixture(folder, payload, serial=0):
    owner = dict(pid=2147483100+serial, create_time=2.)
    freeze(folder/'COLLECTED.json', dict(synthetic=True, cell_id=payload['cell_id']))
    freeze(folder/'application/RESULT.json', dict(synthetic=True, cell_id=payload['cell_id']))
    cb = bind(folder/'COLLECTED.json'); rb = bind(folder/'application/RESULT.json')
    sessions = [dict(index=i, epoch=i+1, native_session=str(folder/'application/data/sessions'/('session'+str(i))),
        source_origin_monotonic_sec=10.+i*20, completed_monotonic_sec=20.+i*20) for i in range(2)]
    pair = dict(cell_id=payload['cell_id'], application_owner=owner, full_job_sha256=fingerprint(payload['job']),
                cell_result=rb, sessions=sessions)
    transport = dict(status='PASS_RESTART_TRANSPORT_AND_PAIR_JOINS_ONLY', cell_id=payload['cell_id'],
        application=owner, coordinator=COORDINATOR, collected=cb, pair_review=pair, evidence=[cb, rb],
        actual_restart_qualified=False, N4_accepted=False, integrated_N4_cells=0,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False)
    observation = dict(status='PASS_RESTART_OBSERVATION_ATTRIBUTION_ONLY', pair_review=deepcopy(pair), evidence=[rb],
        viewport_rows_reviewed=True, resource_samples_reviewed=True, native_caption_payloads_joined=False,
        actual_restart_qualified=False, N4_accepted=False, integrated_N4_cells=0,
        source_to_widget_latency_qualified=False, controlled_resources_qualified=False,
        resource_review=dict(status='PASS_RESTART_RESOURCE_WINDOW_ATTRIBUTION_ONLY', reconstruction=dict(owner=owner),
            windows=subject.session_windows(sessions), both_sessions_have_complete_samples=True),
        viewport_reviews=[dict(status='PASS_RESTART_VIEWPORT_SESSION_ATTRIBUTION_ONLY', session='session'+str(i),
            reconstruction=dict(source_origin_monotonic_sec=10.+i*20), native_caption_payloads_joined=False,
            source_to_widget_latency_qualified=False, current_spans=2, retained_spans=2*i) for i in range(2)])
    return transport, observation


class RestartCompleteTests(unittest.TestCase):
    def setUp(self):
        self.folder = OUTPUT/self._testMethodName; self.folder.mkdir()
        self.payload = dict(cell_id='fixture-cell', job=dict(synthetic=True))

    def leaves(self): return leaf_fixture(self.folder/'cell', self.payload)
    def join(self, t, o): return subject.join_reviews(self.folder/'cell', self.payload, t, o)

    def test_common_receipts_and_owner_join_without_acceptance(self):
        t, o = self.leaves(); result = self.join(t, o)
        self.assertEqual(result['observed_sessions'], 2)
        self.assertEqual(result['retained_viewport_spans'], [0, 2])
        self.assertFalse(result['actual_restart_qualified'])
        self.assertFalse(result['native_caption_payloads_joined'])
        freeze(self.folder/'SYNTHETIC_JOIN.json', result)

    def test_conflicting_shared_binding_is_refused(self):
        t, o = self.leaves(); o['evidence'][0] = dict(o['evidence'][0], sha256='0'*64)
        with self.assertRaisesRegex(ValueError, 'Evidence changed'): self.join(t, o)

    def test_pair_changed_between_independent_reads_is_refused(self):
        t, o = self.leaves(); o['pair_review']['sessions'][0]['epoch'] = 99
        with self.assertRaisesRegex(ValueError, 'Pair changed'): self.join(t, o)

    def test_wrong_resource_owner_or_window_is_refused(self):
        t, o = self.leaves()
        for field, changed in (('reconstruction', dict(owner=COORDINATOR)), ('windows', [])):
            with self.subTest(field=field):
                other = deepcopy(o); other['resource_review'][field] = changed
                with self.assertRaisesRegex(ValueError, 'another owner or session'): self.join(t, other)

    def test_swapped_viewport_order_and_clock_are_refused(self):
        t, o = self.leaves(); swapped = deepcopy(o); swapped['viewport_reviews'].reverse()
        with self.assertRaisesRegex(ValueError, 'Viewport review order'): self.join(t, swapped)
        o['viewport_reviews'][1]['reconstruction']['source_origin_monotonic_sec'] = 10.
        with self.assertRaisesRegex(ValueError, 'Viewport review order'): self.join(t, o)

    def test_premature_acceptance_or_missing_observation_coverage_refused(self):
        t, o = self.leaves()
        for changes in (dict(actual_restart_qualified=True), dict(integrated_N4_cells=True),
                        dict(resource_samples_reviewed=False), dict(source_to_widget_latency_qualified=True)):
            other = dict(o, **changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): self.join(t, other)

    def test_cell_wrapper_passes_exact_owner_and_rechecks_evidence(self):
        t, o = self.leaves(); checkpoints = []
        with patch.object(subject, 'review_transport', return_value=t) as transport, \
             patch.object(subject, 'review_observations', return_value=o) as observations:
            result = subject.review_cell(self.folder/'cell', payload=self.payload, checkpoint=lambda: checkpoints.append(True))
        self.assertEqual(result['status'], subject.CELL_STATUS)
        self.assertEqual(observations.call_args.kwargs['application_owner'], t['application'])
        self.assertEqual(transport.call_args.kwargs['payload'], self.payload)
        self.assertEqual(len(checkpoints), 3)

    def population(self):
        f = fixture(1); folder = self.folder/'run'; values = []; collected = []
        for index, row in enumerate(f['plan']['rows']):
            payload = dict(cell_id=row['cell_id'], job=row['job'])
            cell = folder/'cells'/row['cell_id']; t, o = leaf_fixture(cell, payload, index)
            joins = subject.join_reviews(cell, payload, t, o)
            values.append(dict(status=subject.CELL_STATUS, cell_id=payload['cell_id'], collected=t['collected'],
                transport=t, observations=o, joins=joins, viewport_rows_reviewed=True, resource_samples_reviewed=True,
                actual_restart_qualified=False, N4_accepted=False))
            collected.append(t['collected'])
            freeze(folder/'progress'/f'{index+1:04d}.json', dict(completed=index+1, total=2, cell=t['collected'],
                                                             actual_restart_qualified=False, integrated_N4_cells=0))
        f['terminal']['collected'] = collected
        freeze(folder/'PLAN.json', f['plan']); freeze(folder/'RESULT.json', f['terminal'])
        context = dict(folder=folder, plan=f['plan'], terminal=f['terminal'], coordinator=COORDINATOR,
            code=[], parent_code=[], executable={}, coordinator_argv=[], state=self.folder/'inert-supervision',
            plan_binding=bind(folder/'PLAN.json'), bindings=[bind(folder/'RESULT.json')])
        return context, values

    def driver(self, context, values, hook=None):
        calls = []
        def cell(folder, **kwargs):
            index = len(calls); calls.append(kwargs)
            if hook: hook(index)
            return deepcopy(values[index])
        with patch.object(subject, 'execution_payload', side_effect=lambda plan, i:dict(cell_id=plan['rows'][i]['cell_id'], job=plan['rows'][i]['job'])), \
             patch.object(subject, 'review_cell', side_effect=cell):
            result = subject.review_population(context, self.folder/'review', checkpoint=lambda: None)
        return result, calls

    def test_complete_driver_preserves_both_pair_reviews_and_missing_measurement(self):
        context, values = self.population(); values[1]['joins']['both_sessions_have_complete_resource_samples'] = False
        result, calls = self.driver(context, values)
        self.assertEqual(len(result['pair_reviews']), 2); self.assertEqual(result['population']['planned_sessions'], 4)
        self.assertFalse(result['all_pairs_have_complete_resource_samples'])
        self.assertEqual([c['payload']['cell_id'] for c in calls], [r['cell_id'] for r in context['plan']['rows']])
        freeze(self.folder/'SYNTHETIC_POPULATION_REVIEW.json', result)

    def test_missing_pair_refused_before_any_reader_runs(self):
        context, values = self.population()
        # Keep all evidence; simulate a terminal count mismatch without deletion.
        context['terminal'] = dict(context['terminal'], completed=1)
        with patch.object(subject, 'review_cell') as reader:
            with self.assertRaisesRegex(ValueError, 'Terminal run'): subject.review_population(context, self.folder/'review', checkpoint=lambda: None)
            reader.assert_not_called()

    def test_late_input_mutation_refused_after_first_pair_saved(self):
        context, values = self.population(); target = context['folder']/'PLAN.json'
        def change(index):
            if index == 1: target.write_text(json.dumps(dict(context['plan'], tampered=True)), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Binding changed'): self.driver(context, values, change)
        self.assertTrue((self.folder/'review/cells/0001.json').exists())
        self.assertFalse((self.folder/'review/REVIEW.json').exists())

    def test_application_identity_or_session_reuse_between_pairs_refused(self):
        context, values = self.population(); values[1]['transport']['application'] = values[0]['transport']['application']
        with self.assertRaisesRegex(ValueError, 'reused'): self.driver(context, values)

    def test_second_pair_reader_failure_preserves_first_without_terminal_success(self):
        context, values = self.population()
        def fail(index):
            if index == 1: raise ValueError('synthetic second pair failure')
        with self.assertRaisesRegex(ValueError, 'second pair failure'): self.driver(context, values, fail)
        self.assertTrue((self.folder/'review/cells/0001.json').exists())
        self.assertFalse((self.folder/'review/REVIEW.json').exists())
