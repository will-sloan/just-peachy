"""Reference join regressions; run through probe_naming_reference.py."""
from copy import deepcopy
import unittest

from naming_reference import gallery_identities, join_observed, support, validate_population

CONTEXT = {}


def scene(turns, *, complete=True):
    return dict(frames=160000, complete_reference=complete, turns=[dict(identity=name,
        activity_ranges_samples_estimated=[[int(a*16000),int(b*16000)] for a,b in rows])
        for name,rows in turns])


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        CONTEXT['checkpoint']()

    def test_01_complete_existing_population(self):
        p = CONTEXT['context']['population']
        self.assertEqual((p['cells'],p['scenes'],p['turns'],p['identities']), (480,240,1554,43))
        self.assertEqual(sum(p['reference_classes'].values()),480)
        self.assertFalse(p['exact_reference_word_times_available'])

    def test_02_both_actual_E_rosters(self):
        for g in CONTEXT['context']['galleries'].values():
            self.assertEqual((g['available_size'],g['intended_size'],g['unavailable_count']),(24,34,10))
            self.assertEqual(len(g['profile_to_identity']),24)
            self.assertEqual(len(set(g['profile_to_identity'].values())),24)
            self.assertFalse(g['vectors_numerically_used'])
            self.assertFalse(g['calibration_fitted'])

    def test_03_saved_synthetic_observation_join(self):
        result = join_observed(CONTEXT['context'],CONTEXT['observed'],CONTEXT['payload'],
            checkpoint=CONTEXT['checkpoint'])
        self.assertEqual(result['status'],'JOINED_OBSERVED_HEADINGS_TO_EVALUATOR_REFERENCE_ONLY')
        self.assertEqual(result['available_roster_turns']+result['outside_available_roster_turns'],result['reference_turns'])
        self.assertEqual(len(result['native_span_reference_support']),4)
        self.assertFalse(result['naming_accuracy_qualified'])
        self.assertEqual(result['integrated_N4_cells'],0)
        CONTEXT['joined'] = result

    def test_04_changed_or_other_valid_job_refused(self):
        for mutation in ('hash','other_job','cell'):
            p = deepcopy(CONTEXT['payload'])
            if mutation == 'hash': p['job']['audio_sha256'] = '0'*64
            elif mutation == 'cell': p['cell_id'] = 'different_cell'
            else:
                p['job'] = next(j for jid,j in CONTEXT['context']['jobs'].items() if jid != p['job']['job_id'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                join_observed(CONTEXT['context'],CONTEXT['observed'],p)

    def test_05_changed_roster_order_refused(self):
        c = deepcopy(CONTEXT['context']); e = CONTEXT['payload']['contract']['encoder']
        c['galleries'][e]['people'].reverse()
        with self.assertRaises(ValueError): join_observed(c,CONTEXT['observed'],CONTEXT['payload'])

    def test_06_non_E_provenance_refused(self):
        for role in ('Q','C'):
            w = deepcopy(CONTEXT['windows']); selected = CONTEXT['document']['profiles'][0]['provenance']['window_ids'][0]
            next(r for r in w['windows'] if r['window_id'] == selected)['role'] = role
            with self.subTest(role=role), self.assertRaises(ValueError):
                gallery_identities(CONTEXT['document'],w,CONTEXT['windows_binding'])

    def test_07_mixed_E_identities_refused(self):
        w = deepcopy(CONTEXT['windows']); selected = CONTEXT['document']['profiles'][0]['provenance']['window_ids']
        self.assertGreater(len(selected),1)
        next(r for r in w['windows'] if r['window_id'] == selected[0])['identity'] = 'different_synthetic_identity'
        with self.assertRaises(ValueError): gallery_identities(CONTEXT['document'],w,CONTEXT['windows_binding'])

    def test_08_foreign_profile_UUID_refused(self):
        d = deepcopy(CONTEXT['document']); d['profiles'][0]['profile_id'] = '00000000-0000-0000-0000-000000000000'
        with self.assertRaises(ValueError): gallery_identities(d,CONTEXT['windows'],CONTEXT['windows_binding'])

    def test_09_unadmitted_exact_word_times_refused(self):
        t = deepcopy(CONTEXT['truth']); next(c for c in t['cells'] if c['turns'])['turns'][0]['word_times'] = []
        with self.assertRaises(ValueError): validate_population(t,CONTEXT['manifest'])

    def test_10_out_of_file_reference_is_not_clamped(self):
        t = deepcopy(CONTEXT['truth']); c = next(c for c in t['cells'] if c['turns'])
        c['turns'][0]['activity_ranges_samples_estimated'] = [[0,c['frames']+1]]
        with self.assertRaises(ValueError): validate_population(t,CONTEXT['manifest'])

    def test_11_multiple_reference_identities_keep_ambiguity(self):
        r = support(scene([('A',[(0,4)]),('B',[(3,6)])]),1,5)
        self.assertEqual(r['estimated_activity_seconds_by_identity'],{'A':3.,'B':2.})
        self.assertEqual(r['any_estimated_activity_seconds'],4.)
        self.assertEqual(r['status'],'MULTIPLE_INTERSECTING_REFERENCE_IDENTITIES')
        self.assertIsNone(r['single_intersecting_identity'])

    def test_12_incomplete_target_reference_never_complete_identity(self):
        r = support(scene([('A',[(0,4)])],complete=False),1,3)
        self.assertEqual(r['status'],'TARGET_ONLY_INCOMPLETE_REFERENCE')
        self.assertEqual(r['reference_identities'],['A'])
        self.assertIsNone(r['single_intersecting_identity'])

    def test_13_same_identity_overlap_union_not_double_count(self):
        r = support(scene([('A',[(0,4)]),('A',[(3,6)])]),0,7)
        self.assertEqual(r['estimated_activity_seconds_by_identity'],{'A':6.})
        self.assertEqual(r['any_estimated_activity_seconds'],6.)
        self.assertEqual(r['single_intersecting_identity'],'A')

    def test_14_tiny_intersection_is_not_exact_word_identity(self):
        r = support(scene([('A',[(0,0.01)])]),0,9)
        self.assertEqual(r['status'],'SINGLE_INTERSECTING_ESTIMATED_IDENTITY')
        self.assertAlmostEqual(r['any_estimated_activity_seconds'],0.01)
        self.assertFalse(r['exact_word_identity_established'])
        self.assertFalse(r['eligible_as_exact_word_accuracy'])

    def test_15_native_window_validation_and_overhang(self):
        c = scene([('A',[(0,4)])])
        for a,b in ((-1,2),(0,float('nan')),(0,float('inf')),(3,2)):
            with self.subTest(a=a,b=b), self.assertRaises(ValueError): support(c,a,b)
        r = support(c,9,11)
        self.assertEqual(r['status'],'UNAVAILABLE_SOURCE_WINDOW_OUTSIDE_FILE')
        self.assertEqual(r['source_window_seconds'],[9,11])
        self.assertIsNone(r['single_intersecting_identity'])

    def test_16_empty_and_zero_windows_have_no_identity_credit(self):
        r = support(scene([]),0,1)
        self.assertEqual(r['status'],'NO_ESTIMATED_REFERENCE_ACTIVITY')
        self.assertFalse(r['eligible_as_exact_word_accuracy'])
        r = support(scene([('A',[(0,4)])]),2,2)
        self.assertEqual(r['status'],'UNAVAILABLE_ZERO_WIDTH_SOURCE_WINDOW')
        self.assertIsNone(r['single_intersecting_identity'])
