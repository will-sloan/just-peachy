"""Hand-computed fixed-name controls and saved synthetic-reader regressions."""
from copy import deepcopy
import unittest

from common import fingerprint
from review_application_labels import interpret_row
from score_observed_names import project, score_cell

CONTEXT = {}
PEOPLE = [dict(id='profile-A',name='Alice'),dict(id='profile-B',name='Bob')]


def fixture(refs=('A','B','outside'),headings=('Alice','Bob','Unknown')):
    states = {}; spans = {}; timing = {}; supports = {}
    for i,(person,text) in enumerate(zip(refs,headings)):
        sid = str(i)
        pane = dict(present_in_widget=True,applied_heading_text=text,caption_visible=True,heading_visible=bool(text))
        row = dict(panes={p:deepcopy(pane) for p in ('active','history')},verified_profile_id='profile-A',
            display_profile_id='profile-A',naming_state='confirmed',identity_assignment=dict(track_id=0))
        states[sid] = dict(span_ids=[sid],labels=interpret_row(row,PEOPLE))
        spans[sid] = dict(first_visible=sid,first_final_visible=sid,latest=sid,observed_heading_changes=0,observed_visible_heading_changes=0)
        timing[sid] = dict(kind='lexical_word')
        supports[sid] = dict(status='SINGLE_INTERSECTING_ESTIMATED_IDENTITY',reference_identities=[person],
            single_intersecting_identity=person,exact_word_identity_established=False)
    observed = dict(labels=dict(states=states,spans=spans),observed=dict(timing=dict(spans=timing)))
    joined = dict(status='JOINED_OBSERVED_HEADINGS_TO_EVALUATOR_REFERENCE_ONLY',job_id='fixture',
        reference_class='complete_nonoverlap',profile_to_identity={'profile-A':'A','profile-B':'B'},
        native_span_reference_support=supports,roster=dict(available_size=2,intended_size=3,unavailable_count=1))
    return joined,observed


def evaluate(joined,observed):
    # Fixture-only rebinding; score_cell's production path performs independent admission.
    joined['observed_review_sha256'] = fingerprint(observed)
    return project(joined,observed)


def counts(value,scenario='observed',stage='first_visible',pane='active'):
    return value['scenarios'][scenario][stage][pane]


class NameScoringTests(unittest.TestCase):
    def setUp(self): CONTEXT['checkpoint']()

    def test_01_saved_actual_reader_synthetic_join(self):
        value = score_cell(CONTEXT['context'],CONTEXT['observed'],CONTEXT['payload'],checkpoint=CONTEXT['checkpoint'])
        self.assertEqual(value['native_lexical_spans'],4)
        self.assertEqual(counts(value,stage='first_final_visible')['missing_stage'],1)
        self.assertFalse(value['naming_accuracy_qualified'])
        self.assertEqual(value['integrated_N4_cells'],0)
        CONTEXT['saved_score'] = value

    def test_02_correct_names_and_unknown_outside(self):
        value = evaluate(*fixture()); c = counts(value)
        self.assertEqual(c['single_available_reference_spans'],2)
        self.assertEqual(c['single_outside_available_reference_spans'],1)
        self.assertEqual(c['outcome_counts'],{'ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME':2,'VISIBLE_UNKNOWN':1})
        self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],1.)
        self.assertEqual(c['rates']['visible_Unknown_per_native_lexical_span'],1/3)

    def test_03_all_unknown_control_cannot_earn_known_name_credit(self):
        c = counts(evaluate(*fixture()),'all_unknown')
        self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],0.)
        self.assertEqual(c['rates']['visible_Unknown_per_joint_visible_span'],1.)
        self.assertEqual(c['single_available_reference_spans'],2)

    def test_04_constant_name_control_exposes_wrong_and_false_known(self):
        value = evaluate(*fixture()); c = counts(value,'constant_name')
        self.assertEqual(value['constant_control_profile_id'],'profile-A')
        self.assertEqual(c['outcome_counts'],{'ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME':1,
            'ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME':1,'KNOWN_NAME_ON_OUTSIDE_AVAILABLE_REFERENCE':1})
        self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],.5)
        self.assertEqual(c['rates']['known_name_per_single_outside_available_reference_span'],1.)

    def test_05_swapped_fixed_names_are_not_permuted_into_success(self):
        c = counts(evaluate(*fixture(('A','B'),('Bob','Alice'))))
        self.assertEqual(c['outcome_counts'],{'ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME':2})
        self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],0.)

    def test_06_forced_choice_is_not_recognition(self):
        c = counts(evaluate(*fixture(('A',),('Alice · assumed',))))
        self.assertEqual(c['outcome_counts'],{'VISIBLE_FORCED_ROSTER_ASSUMPTION':1})
        self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],0.)

    def test_07_core_known_proposal_never_overwrites_unknown(self):
        j,o = fixture(('A',),('Unknown',)); self.assertEqual(o['labels']['states']['0']['labels']['native_verified_profile_id'],'profile-A')
        self.assertEqual(counts(evaluate(j,o))['outcome_counts'],{'VISIBLE_UNKNOWN':1})

    def test_08_missing_stage_stays_in_reference_denominator(self):
        j,o = fixture(('A','B'),('Alice','Bob'));o['labels']['spans']['1']['first_final_visible'] = None
        value = evaluate(j,o);c = counts(value,stage='first_final_visible')
        self.assertEqual((c['native_lexical_spans'],c['single_available_reference_spans'],c['missing_stage']),(2,2,1))
        self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],.5)
        self.assertEqual(counts(value,'constant_name','first_final_visible')['missing_stage'],1)

    def test_09_pane_conflict_has_no_chosen_winner(self):
        j,o = fixture(('A',),('Alice',));p=o['labels']['states']['0']['labels']['panes']['history']
        p.update(roster_profile_id='profile-B',applied_text='Bob')
        value = evaluate(j,o)
        self.assertEqual(value['pane_conflicts']['first_visible']['conflicting_visible_roster_names'],1)
        self.assertEqual(counts(value)['outcome_counts'],{'ESTIMATED_SUPPORT_CORRECT_AVAILABLE_NAME':1})
        self.assertEqual(counts(value,pane='history')['outcome_counts'],{'ESTIMATED_SUPPORT_WRONG_AVAILABLE_NAME':1})

    def test_10_offscreen_or_cross_pane_visibility_gets_no_credit(self):
        j,o = fixture(('A',),('Alice',))
        for p in o['labels']['states']['0']['labels']['panes'].values():p['heading_and_caption_glyphs_visible_in_same_pane'] = False
        value = evaluate(j,o)
        for scenario in value['scenarios']:
            c = counts(value,scenario);self.assertEqual(c['not_jointly_visible'],1)
            self.assertEqual(c['rates']['estimated_correct_name_per_single_available_reference_span'],0.)
            self.assertIsNone(c['rates']['visible_Unknown_per_joint_visible_span'])

    def test_11_suppression_is_not_inherited_or_unknown(self):
        value = evaluate(*fixture(('A',),('',)))
        for scenario in value['scenarios']:
            c = counts(value,scenario);self.assertEqual(c['heading_kind_counts'],{'SUPPRESSED':1})
            self.assertEqual(c['outcome_counts'],{'NO_SAME_PANE_VISIBLE_HEADING_AND_CAPTION':1})

    def test_12_incomplete_overlap_and_no_activity_are_not_scored_as_known(self):
        for status in ('TARGET_ONLY_INCOMPLETE_REFERENCE','MULTIPLE_INTERSECTING_REFERENCE_IDENTITIES',
                       'NO_ESTIMATED_REFERENCE_ACTIVITY','UNAVAILABLE_SOURCE_WINDOW_OUTSIDE_FILE'):
            j,o=fixture(('A',),('Alice',));j['native_span_reference_support']['0'].update(status=status,single_intersecting_identity=None)
            with self.subTest(status=status):
                c=counts(evaluate(j,o));self.assertEqual(c['unresolved_reference_spans'],1)
                self.assertEqual(c['outcome_counts'],{'VISIBLE_NAME_UNRESOLVED_REFERENCE':1})
                self.assertIsNone(c['rates']['estimated_correct_name_per_single_available_reference_span'])

    def test_13_empty_caption_not_a_reference_word(self):
        j,o=fixture();o['observed']['timing']['spans']['empty']=dict(kind='empty_caption')
        o['labels']['spans']['empty']=dict(first_visible=None,first_final_visible=None,latest=None)
        j['native_span_reference_support']['empty']=dict(status='NOT_A_LEXICAL_WORD')
        value=evaluate(j,o);self.assertEqual((value['native_spans'],value['native_lexical_spans'],value['empty_caption_spans_excluded']),(4,3,1))
        self.assertEqual(counts(value)['native_lexical_spans'],3)

    def test_14_outside_available_is_not_certified_genuine_outsider(self):
        value=evaluate(*fixture(('missing_E_person',),('Alice',)))
        self.assertEqual(counts(value)['outcome_counts'],{'KNOWN_NAME_ON_OUTSIDE_AVAILABLE_REFERENCE':1})
        self.assertFalse(value['outside_available_is_genuine_outsider'])
        self.assertFalse(value['exact_word_identity_established'])

    def test_15_zero_population_rates_are_null(self):
        value=evaluate(*fixture((),()));c=counts(value)
        self.assertEqual(c['native_lexical_spans'],0)
        self.assertTrue(all(v is None for v in c['rates'].values()))

    def test_16_missing_revision_counts_are_not_zero(self):
        j,o=fixture();o['labels']['spans']['0'].update(observed_heading_changes=None,observed_visible_heading_changes=None)
        o['labels']['spans']['1'].update(observed_heading_changes=3,observed_visible_heading_changes=1)
        value=evaluate(j,o);r=value['revision_counts']['observed_heading_changes']
        self.assertEqual(r,dict(sum_over_native_spans=3,spans_with_recorded_count=2,spans_without_recorded_count=1))

    def test_17_changed_binding_foreign_profile_and_span_are_rejected(self):
        j,o=fixture();j['observed_review_sha256']='0'*64
        with self.assertRaises(ValueError):project(j,o)
        j,o=fixture();o['labels']['states']['0']['labels']['panes']['active']['roster_profile_id']='foreign'
        with self.assertRaises(ValueError):evaluate(j,o)
        j,o=fixture();o['labels']['states']['0']['span_ids']=[]
        with self.assertRaises(ValueError):evaluate(j,o)

    def test_18_unavailable_constant_control_without_available_profiles(self):
        j,o=fixture(('outside',),('Unknown',));j['profile_to_identity']={}
        value=evaluate(j,o)
        self.assertNotIn('constant_name',value['scenarios'])
        self.assertEqual(value['constant_control_status'],'UNAVAILABLE_NO_AVAILABLE_PROFILE')
