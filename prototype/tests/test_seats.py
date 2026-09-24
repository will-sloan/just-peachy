"""Synthetic mechanics only; no acoustic accuracy claims. See README_SEATS.md."""
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.seats import SeatSession,SeatSpatialProvider,validate_layout,collisions
from app.live_spatial import ANGLE,ENERGY,SELECTED
from app.seat_identity import SeatIdentityResolver
from app.people import PersonalStore
from app.pipeline import effective_profile
from app.controller import Controller
from app.paths import default_models_root,read_json
from test_people import quality,ROUTE,BACKEND
from test_roster_policy import vector,event


class SeatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.store=PersonalStore(self.root/'people',BACKEND)
        self.a=self.store.save('Alex',vector(0),quality('A'),ROUTE)['id']
        self.b=self.store.save('Alex',vector(1),quality('B'),ROUTE)['id']
        self.rows=[dict(person_id=self.a,angle_deg=30.,tolerance_deg=25.),dict(person_id=self.b,angle_deg=150.,tolerance_deg=25.)]
        self.decision=dict(tracker_id=1,anonymous_label='Speaker_1',state='committed',reason='fixture clean voice')
        self.make()

    def make(self,direction=True,rows=None,strength='soft',ack=False):
        self.seats=SeatSession(self.rows if rows is None else rows,strength=strength,acknowledged=ack,clock=lambda:100.)
        mode='assigned_direction' if direction else 'assigned_hybrid'
        self.profile=effective_profile('balanced',mode,'O0',seat_strength=strength)
        self.provider=SeatSpatialProvider('O0',self.profile.tracker,seats=self.seats,enabled=True,clock=lambda:101.2)
        self.provider.bind_origin(100.)
        self.provider.attach(SimpleNamespace(beam_diagnostics=SimpleNamespace(snapshot=lambda:dict(state='RUNNING'))))
        self.resolver=SeatIdentityResolver(self.profile.identity,None if direction else self.store.gallery(ROUTE,[self.a,self.b]),
            seats=self.seats,names={p['id']:p['name'] for p in self.store.list()},provider=self.provider,
            tracker_config=self.profile.tracker,direction_only=direction)

    def cue(self,end=1.2,angle=30.,energies=None,angles=None,delay=.02):
        energies=energies if energies is not None else [.5,0.,0.,.5]
        angles=angles if angles is not None else [angle]*4
        for i,(key,values) in enumerate(((ANGLE,[math.radians(a) if a is not None else None for a in angles]),(ENERGY,energies),(SELECTED,[math.radians(angle),math.radians(angle)]))):
            completed=100.+end-delay-(2-i)*.002
            self.provider.receive(key,values,completed-.001,completed)
        self.provider.advance_audio(SimpleNamespace(callback_perf_counter_ns=round((100.+end)*1e9),
            model_start_sample=round(end*16000)-320,audio=np.zeros(320,np.float32)))

    def result(self,v=None,start=0.,**changes):
        e=event(v,start=start);e.update(changes);return self.resolver.resolve(self.decision,e)

    def test_stable_direction_and_speaker_change_are_assumptions_without_gallery(self):
        self.cue();one=self.result(vector(1))
        self.assertEqual(one['known_profile_id'],self.a);self.assertEqual(one['identity']['assignment'],'seat_assumed')
        self.assertEqual(one['identity']['scores'],[]);self.assertEqual(self.resolver.query_calls,0)
        self.cue(2.4,150.);two=self.result(vector(0),1.2)
        self.assertEqual(two['known_profile_id'],self.b)
        self.assertEqual(two['identity']['seat']['basis'],'forced seating assumption')

    def test_overlap_same_bearing_and_front_back_equivalent_remain_ambiguous(self):
        for bearing in (30.,40.):
            rows=[self.rows[0],{**self.rows[1],'angle_deg':bearing}]
            with self.assertRaises(ValueError):SeatSession(rows)
            self.make(rows=rows,ack=True);self.cue()
            r=self.result();self.assertIsNone(r['known_profile_id']);self.assertEqual(r['identity']['assignment'],'ambiguous')
        self.assertTrue(self.seats.snapshot()['front_back_ambiguous'])

    def test_missing_stale_music_overlap_and_no_beam_energy_do_not_name(self):
        for mode in ('missing','stale','music','overlap','no_energy','multiple','unmatched','negative_energy'):
            with self.subTest(mode=mode):
                self.make();changes={}
                if mode!='missing':
                    self.cue(energies=[0.,0.,0.,.5] if mode=='no_energy' else [-1.,0.,0.,.5] if mode=='negative_energy' else [.5,.5,0.,.5] if mode=='multiple' else None,
                             angles=[30.,150.,30.,30.] if mode=='multiple' else [100.]*4 if mode=='unmatched' else None)
                if mode=='stale':changes['available_at_sec']=1.8
                if mode=='music':changes['speech']=False
                if mode=='overlap':changes['overlap']=True
                r=self.result(**changes);self.assertIsNone(r['known_profile_id']);self.assertNotEqual(r['identity']['assignment'],'seat_assumed')
        self.make();self.cue(angle=90.);self.assertIsNone(self.result()['known_profile_id'])

    def test_raw_radians_native_degrees_mapping_and_causal_limits_retained(self):
        self.cue();d=self.result()['identity']['seat']
        self.assertAlmostEqual(d['native_fields'][SELECTED]['values'][0],math.pi/6)
        self.assertAlmostEqual(d['native_degrees'][SELECTED][0],30.)
        self.assertIn('DSP time unknown',d['mapping']);self.assertLessEqual(d['mapped_audio_end_sec'],1.2)
        self.make();self.cue(delay=.3);self.assertIsNone(self.result()['known_profile_id'])

    def test_voice_outsider_stays_unknown_even_at_assigned_seat(self):
        self.make(direction=False)
        for start in (0.,1.2):self.cue(start+1.2);r=self.result(vector(2),start)
        self.assertIsNone(r['known_profile_id']);self.assertFalse(r['identity']['forced'])

    def test_input_cue_age_and_scheduler_publication_age_remain_distinct(self):
        self.cue();self.resolver.clock=lambda:1.48
        accepted=self.result();self.assertEqual(accepted['known_profile_id'],self.a)
        detail=accepted['identity']['seat']
        self.assertAlmostEqual(detail['cue_age_sec'],.05);self.assertAlmostEqual(detail['decision_cue_age_sec'],.28)
        self.resolver.clock=lambda:2.01
        rejected=self.result();self.assertIsNone(rejected['known_profile_id'])
        self.assertEqual(rejected['identity']['seat']['reason'],'direction_expired_at_decision')

    def test_hybrid_voice_acceptance_and_missing_direction_are_explicit(self):
        self.make(direction=False)
        for start in (0.,1.2):r=self.result(vector(0),start)
        self.assertEqual(r['known_profile_id'],self.a)
        self.assertTrue(r['identity']['seat']['voice_only_fallback'])
        self.assertEqual(r['identity']['seat']['reason'],'no_fresh_direction')

    def test_native_joint_prior_resolves_qualified_voice_margin_soft_and_strong(self):
        v=np.zeros(192,np.float32);v[:3]=[.60,.61,math.sqrt(1-.6**2-.61**2)]
        terms=[]
        for strength in ('soft','strong'):
            self.make(direction=False,strength=strength)
            for start in (0.,1.2):self.cue(start+1.2);r=self.result(v,start)
            self.assertEqual(r['known_profile_id'],self.a);self.assertEqual(r['identity']['assignment'],'spatial_supported')
            terms.append(r['identity']['seat']['joint_terms'][self.a]['cue_score'])
            self.assertLess(r['identity']['margin'],self.profile.identity.margin_threshold)
        self.assertAlmostEqual(terms[1]/terms[0],1.5)

    def test_clear_voice_conflict_releases_seat_prior_without_altering_profiles(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.store.root.rglob('*') if p.is_file()}
        self.make(direction=False)
        for start in (0.,1.2):self.cue(start+1.2);r=self.result(vector(1),start)
        self.assertEqual(r['known_profile_id'],self.b);self.assertEqual(r['identity']['seat']['basis'],'voice')
        self.assertEqual(set(self.seats.snapshot()['released']),{self.a,self.b})
        self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.store.root.rglob('*') if p.is_file()})
        self.assertEqual(self.seats.snapshot()['rows'],self.rows)

    def test_motion_invalidates_seating_and_caption_link_not_voice_memory(self):
        self.cue();r=self.result();row=dict(known_profile_id=self.a,naming_state='confirmed',evidence_ids=['e0.0'],text='all words preserved')
        self.assertEqual(self.resolver.annotate_caption(row)['prototype_assignment'],'seat_assumed')
        self.seats.motion.moved();self.provider.invalidate_positions()
        shown=self.resolver.annotate_caption(row);self.assertIsNone(shown['known_profile_id']);self.assertEqual(shown['text'],row['text'])
        self.cue(2.4);self.assertIsNone(self.result(start=1.2)['known_profile_id'])
        self.make(direction=False)
        for start in (0.,1.2):self.cue(start+1.2);self.result(start=start)
        states=self.resolver.states;vectors=states[1]['vectors'][:]
        self.seats.motion.moved('stub_motion_event')
        self.assertIs(self.resolver.states,states);self.assertEqual(len(states[1]['vectors']),len(vectors))

    def test_layout_validation_tolerance_uuid_and_parent_bindings(self):
        for change in ({'angle_deg':181},{'angle_deg':True},{'angle_deg':float('nan')},{'tolerance_deg':0}):
            with self.assertRaises(ValueError):validate_layout([{**self.rows[0],**change}])
        with self.assertRaises(ValueError):validate_layout([self.rows[0],self.rows[0]])
        with self.assertRaises(ValueError):validate_layout(self.rows,{self.a})
        self.assertFalse(collisions(self.rows))
        for strength,parent in (('soft','C079'),('strong','C060')):
            profile=effective_profile('balanced','assigned_hybrid','O0',seat_strength=strength)
            self.assertEqual(asdict(profile.tracker),read_json(ROOT/('config/parent_'+parent+'.json'))['tracker'])

    def test_controller_templates_cancel_motion_and_missing_anchor(self):
        c=Controller(self.root/'controller',default_models_root());self.addCleanup(lambda:(c.close(),c.commands.join(),c.worker.join(10)))
        c.store=self.store;c.route=lambda:dict(ROUTE)
        c.seats_save_template(self.rows,'strong');c.commands.join();self.assertIsNone(c.error)
        self.assertFalse(c.seats.snapshot()['valid']);self.assertEqual(c.mode,'caption_only')
        c.switch(mode='assigned_direction');c.commands.join();self.assertIn('re-anchor',c.error)
        c.seats_apply(self.rows,'assigned_direction');c.commands.join();self.assertIsNone(c.error)
        self.assertEqual(c.mode,'assigned_direction');self.assertTrue(c.seats.snapshot()['valid']);self.assertEqual(c.models.streams,0)
        c.reset_spatial();c.commands.join();self.assertFalse(c.seats.snapshot()['valid']);self.assertEqual(c.models.streams,0)
        self.assertFalse(read_json(c.data_root/'seat_template.json')['valid'])

    def test_uuid_rename_delete_and_display_recovery_after_motion(self):
        c=Controller(self.root/'controller',default_models_root());self.addCleanup(lambda:(c.close(),c.commands.join(),c.worker.join(10)))
        c.store=self.store;c.route=lambda:dict(ROUTE)
        c.seats_apply(self.rows,'assigned_hybrid');c.commands.join();self.assertIsNone(c.error)
        c.display_roster([self.a]);c.commands.join();c.reset_spatial();c.commands.join()
        c.switch(strict=False);c.commands.join();self.assertIsNone(c.error)
        c.rename_person(self.a,'Renamed Alex');c.commands.join();self.assertIsNone(c.error)
        self.assertEqual(c.seats.snapshot()['rows'][0]['person_id'],self.a);self.assertFalse(c.seats.snapshot()['valid'])
        c.seats_apply(self.rows,'assigned_hybrid');c.commands.join();self.assertIsNone(c.error)
        c.delete_person(self.b);c.commands.join();self.assertFalse(c.seats.snapshot()['valid'])
        c.seats_apply(self.rows,'assigned_hybrid');c.commands.join();self.assertIn('UUID',c.error)

    def test_restart_never_activates_template_and_direction_ignores_voice_knobs(self):
        c=Controller(self.root/'restart',default_models_root());c.store=self.store
        try:c.seats_save_template(self.rows,'strong');c.commands.join();self.assertIsNone(c.error)
        finally:c.close();c.commands.join();c.worker.join(10)
        c=Controller(self.root/'restart',default_models_root())
        try:
            self.assertFalse(c.seats.snapshot()['valid']);self.assertEqual(c.seat_template['strength'],'strong')
            p=effective_profile('balanced','assigned_direction','O0',{'joint_spatial_weight':1.2,'score_threshold':.35},seat_strength='strong')
            self.assertEqual(p.tracker.joint_spatial_weight,.6);self.assertEqual(p.identity.mode,'none')
        finally:c.close();c.commands.join();c.worker.join(10)


if __name__=='__main__':unittest.main()
