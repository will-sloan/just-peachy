"""Actual Tk transactional controls with a labelled stub backend. See README_ROSTER.md."""
import tkinter as tk
import time
import unittest
from prototype.app.ui import PrototypeUI,prepare_dpi_awareness
from prototype.app.mode_policy import MODE_METADATA,SELECTED_MODES,SEAT_MODES
from prototype.app.roster_ui import score_text
from prototype.tests.test_ui import StubController


class RosterUITests(unittest.TestCase):
    def setUp(self):
        prepare_dpi_awareness();self.root=tk.Tk();self.c=StubController()
        self.c.data['roster_compatibility']=[dict(id='uuid-alex-1',name='Alex',compatible_references=1),dict(id='uuid-alex-2',name='Alex',compatible_references=0)]
        self.c.identity_parameters=lambda values:self.c._record('identity_parameters',values)
        self.ui=PrototypeUI(self.root,self.c);self.root.update()
    def tearDown(self):self.ui.close();self.ui.poll()
    def test_cancel_roster_has_no_controller_mutation_or_capture_stop(self):
        self.ui._choose_mode('selected_closed');self.ui.actions['roster_uuid-alex-1'].invoke()
        self.assertEqual(self.c.calls,[]);self.ui.actions['roster_cancel'].invoke()
        self.assertEqual(self.c.calls,[]);self.assertEqual(self.c.data['mode'],'caption_only')
    def test_empty_is_disabled_and_incompatible_reference_cannot_be_selected(self):
        self.ui._choose_mode('selected_focus')
        self.assertEqual(str(self.ui.actions['roster_apply'].cget('state')),'disabled')
        self.assertEqual(str(self.ui.actions['roster_uuid-alex-2'].cget('state')),'disabled')
        self.ui.actions['roster_uuid-alex-1'].invoke();self.ui.actions['roster_apply'].invoke()
        self.assertEqual(self.c.calls[-1],('switch',(),dict(mode='selected_focus',selected_ids=['uuid-alex-1'],strict=False)))
    def test_numbered_choices_only_advanced_and_selected_modes_open_picker(self):
        self.ui.show_modes();self.assertNotIn('mode_anonymous_conversation',self.ui.actions)
        for mode in SELECTED_MODES:
            self.ui._choose_mode(mode);self.assertEqual(self.ui.page,'seats' if mode in SEAT_MODES else 'roster')
        self.assertEqual(self.c.calls,[])
        self.ui.show_advanced();self.assertIn('mode_anonymous_conversation',self.ui.actions)
    def test_constant_unknown_mode_ignores_old_numbered_toggle(self):
        self.ui.preferences['numbered_unknowns']=True
        row=dict(id='u1',caption_key='c1',label='Speaker_9',raw_asr_text='WORDS')
        self.ui.snapshot['mode']='spatial_assisted';self.ui._identity_labels.turns['c1']=time.perf_counter()-3
        self.assertEqual(self.ui._display_row(row)[0],'Unknown')
        self.ui.snapshot['mode']='open_with_names';self.ui._display_row(row)
        self.ui._identity_labels.candidates['u1']=(('Speaker_9',None,None),time.perf_counter()-1)
        self.assertEqual(self.ui._display_row(row)[0],'Speaker_9')
    def test_scores_are_raw_and_absent_evidence_is_not_fabricated(self):
        self.assertIn('No voice decision yet',score_text(self.c.data))
        self.c.data['metrics']['recent_identity_decisions']=[dict(decision=dict(identity=dict(assignment='forced',
            scores=[dict(name='Alex',profile_id='abcdef123',cosine=.123)],score_threshold=.513,next_candidate_margin=None,
            reason='closed_group_user_assumption',one_selected_person_assumption=True)))]
        text=score_text(self.c.data);self.assertIn('0.123',text);self.assertNotIn('%',text);self.assertIn('FORCED',text)
        self.assertIn('user assumption',text);self.assertIn('cue age —',text)
        self.ui.snapshot=self.c.snapshot();self.ui.show_identity_scores();self.root.update()
    def test_parameter_page_keeps_inactive_controls_disabled(self):
        self.ui.show_identity_parameters();self.assertEqual(str(self.ui.actions['parameter_score_threshold_1'].cget('state')),'disabled')
        self.ui.snapshot.update(mode='spatial_assisted',recipe='balanced');self.ui.show_identity_parameters()
        self.ui.actions['parameter_joint_spatial_weight_1'].invoke()
        self.assertEqual(self.c.calls[-1],('identity_parameters',({'joint_spatial_weight':.7},),{}))

    def test_last_score_keeps_its_effective_recipe_after_a_new_ui_selection(self):
        self.c.data['metrics']['recent_identity_decisions']=[dict(prototype_configuration=dict(mode='selected_closed',recipe='patient',tap='O1'),
            decision=dict(identity=dict(assignment='forced')))]
        text=score_text(self.c.data)
        self.assertIn('Current selection: fast / O0',text);self.assertIn('Recipe: patient / O1',text)
        self.assertIn('Decision mode: Selected · closed group',text);self.assertIn('Fresh at decision',text)

    def test_display_picker_uses_separate_command_and_does_not_change_matching_roster(self):
        self.c.data['selected_ids']=['uuid-alex-2'];self.ui.snapshot=self.c.snapshot()
        self.ui.show_roster();self.ui.actions['roster_uuid-alex-1'].invoke();self.ui.actions['roster_apply'].invoke()
        self.assertEqual(self.c.calls[-1],('display_roster',(['uuid-alex-1'],),{}))
        self.assertEqual(self.c.data['selected_ids'],['uuid-alex-2'])


if __name__=='__main__':unittest.main()
