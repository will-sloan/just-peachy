"""Deterministic roster/closed-voice contracts; no hardware or models. See README_ROSTER.md."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.people import PersonalStore
from app.pipeline import effective_profile
from app.identity_policy import PrototypeIdentityResolver,DiagnosticTracker
from app.controller import Controller
from app.paths import default_models_root
from app.mode_policy import MODE_METADATA,SELECTED_MODES,SPATIAL_PARENTS,validate_overrides
from test_people import quality,ROUTE,BACKEND


def vector(index):
    v=np.zeros(192,np.float32);v[index]=1.;return v


def event(v=None,start=0.,**extra):
    return dict(event_id=f'e{start}',vector=vector(0) if v is None else v,source_start_sec=start,source_end_sec=start+1.2,
        available_at_sec=start+1.25,evidence_kind='mature',speech=True,overlap=False,clean_intervals=[[start,start+1.2]],**extra)


class RosterPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.store=PersonalStore(self.root/'people',BACKEND)
        self.a=self.store.save('Same name',vector(0),quality('A'),ROUTE)['id']
        self.b=self.store.save('Same name',vector(1),quality('B'),ROUTE)['id']
        self.decision=dict(tracker_id=1,anonymous_label='Speaker_1',state='committed',reason='fixture clean voice')
    def resolver(self,closed=False,ids=None):
        return PrototypeIdentityResolver(effective_profile('balanced','selected_closed' if closed else 'selected_focus','O0').identity,
            self.store.gallery(ROUTE,[self.a] if ids is None else ids),closed=closed)
    def test_gallery_really_excludes_unselected_uuid_even_if_it_is_best(self):
        selected=self.store.gallery(ROUTE,[self.a]);all_people=self.store.gallery(ROUTE)
        self.assertEqual(selected.ids,[self.a]);self.assertEqual(selected.score(vector(1))[0]['cosine'],0.)
        self.assertEqual(all_people.score(vector(1))[0]['profile_id'],self.b)
        self.assertNotEqual(selected.gallery_id,all_people.gallery_id)
    def test_open_unknown_for_outsider_closed_forces_without_inventing_similarity(self):
        opened=self.resolver();closed=self.resolver(True)
        for i in range(2):
            a=opened.resolve(self.decision,event(vector(1),start=i*1.2))
            b=closed.resolve(self.decision,event(vector(1),start=i*1.2))
        self.assertIsNone(a['known_profile_id']);self.assertEqual(a['identity']['assignment'],'rejected')
        self.assertEqual(b['known_profile_id'],self.a);self.assertEqual(b['identity']['assignment'],'forced')
        self.assertEqual(b['identity']['top1_score'],0.);self.assertIsNone(b['identity']['next_candidate_margin'])
        self.assertTrue(b['identity']['one_selected_person_assumption'])
    def test_native_acceptance_gates_still_apply_in_open_mode(self):
        r=self.resolver();first=r.resolve(self.decision,event())
        self.assertNotEqual(first['naming_state'],'confirmed')
        second=r.resolve(self.decision,event(start=1.2));self.assertEqual(second['known_profile_id'],self.a)
        self.assertEqual(second['identity']['assignment'],'accepted')
    def test_closed_known_evidence_distinguishes_initial_forcing_from_acceptance(self):
        r=self.resolver(True);first=r.resolve(self.decision,event())
        self.assertEqual(first['identity']['assignment'],'forced')
        second=r.resolve(self.decision,event(start=1.2));self.assertEqual(second['identity']['assignment'],'accepted')
    def test_invalid_stale_silent_and_overlapping_speech_never_force_or_score(self):
        fixtures=[dict(speech=False),dict(overlap=True),dict(clean_intervals=[]),dict(vector=[]),
            dict(vector=np.zeros(192,np.float32)),dict(available_at_sec=5.),dict(vector=np.full(192,np.nan,np.float32))]
        for change in fixtures:
            with self.subTest(change=list(change)):
                r=self.resolver(True);e=event();e.update(change);before=r.gallery.query_count
                result=r.resolve(self.decision,e)
                self.assertIsNone(result['known_profile_id']);self.assertFalse(result['identity']['forced'])
                self.assertEqual(r.gallery.query_count,before);self.assertEqual(result['identity']['scores'],[])
    def test_current_voice_can_change_forced_identity_without_learning_a_person(self):
        r=self.resolver(True,[self.a,self.b]);before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.store.root.rglob('*') if p.is_file()}
        one=r.resolve(self.decision,event(vector(0)));two=r.resolve(self.decision,event(vector(1),start=1.2))
        self.assertEqual(one['known_profile_id'],self.a);self.assertEqual(two['known_profile_id'],self.b)
        self.assertFalse(two['identity']['personal_reference_update'])
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.store.root.rglob('*') if p.is_file()})
    def test_caption_provenance_is_linked_and_unknown_link_is_marked_assumed(self):
        r=self.resolver(True);r.resolve(self.decision,event(vector(1)))
        row=dict(known_profile_id=self.a,evidence_ids=['e0.0'],text='UNCHANGED')
        shown=r.annotate_caption(row);self.assertEqual(shown['prototype_assignment'],'forced')
        self.assertEqual(row['text'],shown['text']);self.assertNotIn('prototype_assignment',row)
        self.assertEqual(r.annotate_caption({**row,'evidence_ids':['missing']})['prototype_assignment'],'assumed_unlinked')
    def test_empty_deleted_and_incompatible_rosters_fail_before_identification(self):
        with self.assertRaises(ValueError):self.store.gallery(ROUTE,[])
        self.store.delete(self.b)
        with self.assertRaises(ValueError):self.store.gallery(ROUTE,[self.b])
        other={**ROUTE,'tap':'O1'}
        self.assertEqual(self.store.summaries(other)[0]['compatible_references'],0)
        with self.assertRaises(ValueError):self.store.gallery(other,[self.a])
    def test_closed_missing_voice_gets_separate_assumption_without_faking_identity(self):
        r=self.resolver(True,[self.a,self.b]);r.resolve(self.decision,{**event(),'overlap':True})
        row=dict(caption_key='epoch/u1',text='FIRST WORDS',source_start_sec=0.,source_end_sec=1.2,
            segments=[dict(segment_id='s1',raw_text='FIRST WORDS',known_profile_id=None,naming_state='unresolved',
                voice_available=False,evidence_ids=[],ownership_state='pending')])
        before=deepcopy(row);queries=r.gallery.query_count;shown=r.annotate_caption(row)
        part=shown['segments'][0];choice=part['closed_display_assignment']
        self.assertEqual(choice['profile_id'],r.gallery.ids[0]);self.assertEqual(choice['basis'],'roster_default_no_voice_match')
        self.assertIsNone(choice['acoustic_confidence']);self.assertFalse(choice['voice_identity_verified'])
        self.assertIsNone(part['known_profile_id']);self.assertEqual(part['naming_state'],'unresolved')
        self.assertFalse(part['voice_available']);self.assertEqual(part['evidence_ids'],[])
        self.assertEqual(row,before);self.assertEqual(queries,r.gallery.query_count)
    def test_closed_assumption_uses_current_then_recent_voice_but_not_future_or_stale_voice(self):
        r=self.resolver(True,[self.a,self.b]);r.resolve(self.decision,event(vector(1)))
        def shown(a,b):
            return r.annotate_caption(dict(text='WORDS',source_start_sec=a,source_end_sec=b,
                known_profile_id=None,naming_state='unresolved'))['closed_display_assignment']
        current=shown(0.,1.2);self.assertEqual(current['profile_id'],self.b)
        self.assertEqual(current['basis'],'same_utterance_voice_winner')
        recent=shown(1.5,2.);self.assertEqual(recent['profile_id'],self.b);self.assertEqual(recent['basis'],'recent_voice_winner')
        self.assertEqual(shown(0.,.6)['basis'],'roster_default_no_voice_match')
        self.assertEqual(shown(4.,5.)['basis'],'roster_default_no_voice_match')
        r.resolve(self.decision,event(vector(0),start=1.2))
        self.assertEqual(shown(1.2,2.4)['profile_id'],self.a)
    def test_open_modes_never_get_closed_display_assumptions_and_new_epoch_has_no_memory(self):
        row=dict(text='WORDS',source_start_sec=0.,source_end_sec=1.2,known_profile_id=None,naming_state='unresolved')
        opened=self.resolver();opened.resolve(self.decision,event(vector(1)))
        self.assertNotIn('closed_display_assignment',opened.annotate_caption(row))
        closed=self.resolver(True);closed.resolve(self.decision,event())
        self.assertEqual(self.resolver(True).annotate_caption(row)['closed_display_assignment']['basis'],'roster_default_no_voice_match')
    def test_identity_helper_failure_keeps_raw_unavailable_and_closed_display_assumed(self):
        from types import SimpleNamespace
        from app.pipeline import PrototypeEngine,PipelineEngine
        from app.noise_coordination import NoiseCoordinator
        engine=PrototypeEngine.__new__(PrototypeEngine);engine.mode='selected_closed'
        engine.coordinator=NoiseCoordinator();engine.live_spatial=None
        engine.prototype_identity=self.resolver(True);engine.enhancement_router=SimpleNamespace(identity_limit=16000)
        row=dict(text='UNCHANGED WORDS',source_start_sec=0.,source_end_sec=2.,segments=[dict(raw_text='UNCHANGED WORDS',
            known_name='old name',known_profile_id=self.a,naming_state='confirmed',voice_available=True)])
        with patch.object(PipelineEngine,'_emit') as emit:engine._emit('s6d_display',2.,row)
        part=emit.call_args.args[2]['segments'][0]
        self.assertIsNone(part['known_profile_id']);self.assertFalse(part['voice_available'])
        self.assertEqual(part['naming_state'],'unavailable');self.assertEqual(part['raw_text'],'UNCHANGED WORDS')
        self.assertEqual(part['closed_display_assignment']['profile_id'],self.a)
    def test_duplicate_names_and_rename_keep_uuid_selection(self):
        self.store.rename(self.a,'Renamed')
        g=self.store.gallery(ROUTE,[self.a]);self.assertEqual(g.ids,[self.a]);self.assertEqual(g.names,['Renamed'])
        self.assertEqual(self.store.gallery(ROUTE,[self.b]).names,['Same name'])
    def test_real_supported_parameters_are_bounded_and_reset_to_frozen_values(self):
        base=effective_profile('balanced','spatial_assisted','O0')
        changed=effective_profile('balanced','spatial_assisted','O0',dict(score_threshold=.6,margin_threshold=.05,joint_spatial_weight=.8))
        self.assertEqual(changed.identity.score_threshold,.6);self.assertEqual(changed.tracker.joint_spatial_weight,.8)
        self.assertEqual(asdict(base),asdict(effective_profile('balanced','spatial_assisted','O0',{})))
        for bad in ({'score_threshold':.1},{'joint_spatial_weight':2.},{'margin_threshold':float('nan')},{'score_threshold':True},{'fake':1}):
            with self.assertRaises(ValueError):validate_overrides(bad)
    def test_spatial_selected_reuses_identical_existing_all_roster_algorithm(self):
        for a,b in (('spatial_assisted','spatial_selected'),('strongly_spatial_assisted','strongly_spatial_selected')):
            for recipe in ('balanced','patient'):
                one,two=(effective_profile(recipe,mode,'O0') for mode in (a,b))
                for field in ('tracker','xvf','identity','embedding','segmentation','asr'):
                    self.assertEqual(asdict(getattr(one,field)),asdict(getattr(two,field)))


class RosterControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        with patch.object(Controller,'_observe_output'):self.c=Controller(Path(self.temp.name),default_models_root())
        self.addCleanup(self.finish);self.c.route=lambda:dict(ROUTE)
        self.a=self.c.store.save('Fixture',vector(0),quality('controller'),ROUTE)['id']
    def finish(self):
        self.c.close();self.c.commands.join();self.c.worker.join(10)
    def test_selected_mode_validation_is_transactional_and_persists_uuid(self):
        c=self.c
        with self.assertRaises(ValueError):c._do_switch('selected_focus',None,None,[],False)
        self.assertEqual(c.mode,'caption_only');self.assertEqual(c.epoch,0)
        c._do_switch('selected_focus',None,None,[self.a],False)
        self.assertEqual(c.mode,'selected_focus');self.assertEqual(c.selected_ids,[self.a]);self.assertFalse(c.strict)
        self.assertEqual(c.models.asr_loads,0)
        from app.paths import read_json
        self.assertEqual(read_json(c.data_root/'settings.json')['roster_ids'],[self.a])
    def test_parameter_change_stops_before_new_epoch_and_is_exported(self):
        c=self.c;c._do_switch('selected_focus',None,None,[self.a],False);c.state='RUNNING';c.source_kind='live'
        order=[]
        with patch.object(c,'_stop_session',side_effect=lambda:order.append('stop')),patch.object(c,'_start_session',side_effect=lambda:order.append('start')):
            c._do_identity_parameters({'score_threshold':.6})
        c.state='IDLE';c.source_kind=None
        self.assertEqual(order,['stop','start']);self.assertEqual(c.mode_configuration()['effective_profile']['identity']['score_threshold'],.6)
        c._do_identity_parameters(None);self.assertEqual(c.identity_overrides,{})
    def test_deleting_last_selected_person_blocks_fresh_identification(self):
        c=self.c;c._do_switch('selected_focus',None,None,[self.a],False);c._do_person_mutation('delete',self.a)
        self.assertEqual(c.selected_ids,[])
        with self.assertRaises(ValueError):c._do_switch('selected_closed',None,None,[],False)
        self.assertEqual(c.models.streams,0)

    def test_display_roster_and_hiding_do_not_change_gallery_or_restart_source(self):
        c=self.c;b=c.store.save('Other fixture',vector(1),quality('display'),ROUTE)['id']
        c._do_switch('selected_focus',None,None,[self.a],False);c.state='RUNNING';c.source_kind='live'
        with patch.object(c,'_stop_session') as stop,patch.object(c,'_start_session') as start:
            c._do_display_roster([b]);c._do_switch(None,None,None,None,True)
            self.assertEqual(c.selected_ids,[self.a]);self.assertEqual(c.display_ids,[b]);self.assertTrue(c.strict)
            c._do_switch(None,None,None,None,False)
            self.assertFalse(c.strict);self.assertEqual(c.mode,'selected_focus')
            stop.assert_not_called();start.assert_not_called()
        c.state='IDLE';c.source_kind=None


if __name__=='__main__':unittest.main()
