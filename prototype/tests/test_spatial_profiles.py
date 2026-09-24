"""Bounded model-free checks of the actual retained spatial trackers.

Inputs are explicit synthetic 192-D vectors, not recorded people or inference.
See README_SPATIAL_PROFILES.md for commands, scope and expected output.
"""
from dataclasses import asdict
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.paths import read_json
from app.pipeline import (MODES, RECIPES, SPATIAL_PARENTS, PrototypeEngine,
                          effective_profile)
from edge_speech_pipeline.research_profiles import DeliveredSpatialObservation
from edge_speech_pipeline.research_tracking_v3 import S6CTracker
from edge_speech_pipeline.runtime import PipelineEngine


def vector(*values):
    return np.pad(np.asarray(values,dtype=np.float32),(0,192-len(values)))


def observe(tracker,voice,start,end,angle=None,*,stamp=None,reliability=1.):
    stamp=end if stamp is None else stamp
    cue=(None if angle is None else DeliveredSpatialObservation(angle_deg=angle,
         available_at_sec=stamp,reliability=reliability,energy=1.,valid=True,
         sequence=int(stamp*1000),source_start_sec=stamp,source_end_sec=stamp))
    return tracker.update(voice,start,end,end,spatial=cue,evidence_kind='mature',
                          clean_intervals=[[start,end]])


def seeded(mode):
    tracker=S6CTracker(effective_profile('balanced',mode,'O0').tracker)
    observe(tracker,vector(1,0,0),0.,.5,20.)
    observe(tracker,vector(0,1,0),.5,1.,140.)
    return tracker


class SpatialProfileTests(unittest.TestCase):
    def test_unchanged_frontend_and_exact_complete_parent_tracker(self):
        for recipe in ('balanced','patient'):
            base=effective_profile(recipe,'open_with_names','O0')
            for mode,parent in SPATIAL_PARENTS.items():
                historical=read_json(ROOT/('config/parent_'+parent+'.json'))
                for tap in ('O0','O1'):
                    with self.subTest(recipe=recipe,mode=mode,tap=tap):
                        actual=effective_profile(recipe,mode,tap)
                        self.assertEqual(asdict(actual.tracker),historical['tracker'])
                        self.assertEqual(asdict(actual.xvf),historical['xvf'])
                        for name in ('asr','embedding','segmentation','identity'):
                            if name=='identity' and mode=='assigned_direction':
                                self.assertEqual(actual.identity.mode,'none');continue
                            self.assertEqual(asdict(getattr(actual,name)),asdict(getattr(base,name)))
                        self.assertEqual(actual.input.asr_tap,tap)
                        self.assertEqual(actual.input.identity_tap,tap)
                        self.assertEqual(actual.identity.mode,'none' if mode=='assigned_direction' else 'post_association')
                        self.assertEqual(actual.xvf.mode,'tracking_only')

    def test_existing_modes_and_recipe_restrictions_preserved(self):
        existing=('caption_only','enrolled_names','anonymous_conversation','open_with_names','selected_focus')
        self.assertTrue(set(existing).issubset(MODES))
        self.assertEqual({r['id'] for r in RECIPES},{'fast','classic','balanced','patient'})
        for recipe in RECIPES:
            self.assertTrue(recipe['available'])
            for mode in recipe['compatible_modes']:
                actual=effective_profile(recipe['id'],mode,'O0')
                if mode not in SPATIAL_PARENTS:
                    self.assertEqual(actual.xvf.mode,'none')
                    self.assertFalse(actual.tracker.cues_enabled)
        for recipe in ('fast','classic'):
            for mode in SPATIAL_PARENTS:
                with self.assertRaises(ValueError):effective_profile(recipe,mode,'O0')

    def test_stronger_existing_parent_can_prefer_seat_when_voice_is_ambiguous(self):
        query=vector(.35,.57,math.sqrt(1-.35**2-.57**2))
        standard=observe(seeded('spatial_assisted'),query,1.,1.5,20.)
        strong=observe(seeded('strongly_spatial_assisted'),query,1.,1.5,20.)
        self.assertEqual(standard['tracker_id'],2)
        self.assertEqual(strong['tracker_id'],1)
        standard_cue=standard['cue']['candidate_contributions']['1']['cue_score']
        strong_cue=strong['cue']['candidate_contributions']['1']['cue_score']
        self.assertAlmostEqual(strong_cue/standard_cue,1.5)

    def test_clear_voice_overrules_seat_and_relocates_after_person_or_tablet_motion(self):
        for mode in SPATIAL_PARENTS:
            tracker=seeded(mode)
            decision=observe(tracker,vector(1,0,0),1.,1.5,140.)
            self.assertEqual(decision['tracker_id'],1)
            self.assertNotIn('2',decision['cue']['candidate_contributions'])
            self.assertEqual(tracker.operations['strong_voice_relocation'],1)
            self.assertGreater(tracker.tracks[0].location,20.)
            self.assertLessEqual(abs(decision['cue']['candidate_contributions']['1']['cue_score']),
                                 tracker.config.joint_spatial_weight*.1)

    def test_stale_low_quality_and_missing_angles_fall_back_to_voice(self):
        query=vector(.35,.57,math.sqrt(1-.35**2-.57**2))
        cases=[dict(angle=None),dict(angle=20.,stamp=1.),dict(angle=20.,reliability=.1)]
        for mode in SPATIAL_PARENTS:
            for kwargs in cases:
                with self.subTest(mode=mode,kwargs=kwargs):
                    decision=observe(seeded(mode),query,1.,1.5,**kwargs)
                    self.assertEqual(decision['tracker_id'],2)
                    self.assertIsNone(decision['cue']['qualified_bearing_deg'])
                    self.assertTrue(all(r['cue_score']==0 for r in decision['cue']['candidate_contributions'].values()))

    def test_last_known_location_loses_credit_with_silence(self):
        query=vector(.35,.57,math.sqrt(1-.35**2-.57**2))
        for mode in SPATIAL_PARENTS:
            fresh=observe(seeded(mode),query,1.,1.5,20.)
            later=observe(seeded(mode),query,7.,7.5,20.)
            fresh_credit=fresh['cue']['candidate_contributions']['1']['cue_score']
            later_credit=later['cue']['candidate_contributions']['1']['cue_score']
            self.assertAlmostEqual(later_credit/fresh_credit,math.exp(-.5))

    def test_angle_never_bypasses_severe_voice_disagreement(self):
        for mode in SPATIAL_PARENTS:
            decision=observe(seeded(mode),vector(0,0,1),1.,1.5,20.)
            self.assertEqual(decision['tracker_id'],3)
            self.assertEqual(decision['cue']['candidate_contributions'],{})

    def test_engine_passes_causal_provider_to_existing_scheduler(self):
        profile=effective_profile('balanced','spatial_assisted','O0')
        provider=object()
        with patch.object(PipelineEngine,'__init__',return_value=None) as initialize:
            PrototypeEngine(None,None,profile,None,'spatial_assisted',spatial_provider=provider)
        self.assertIs(initialize.call_args.kwargs['spatial_provider'],provider)

    def test_source_clock_bound_before_runtime_publishes_start(self):
        calls=[]
        engine=PrototypeEngine.__new__(PrototypeEngine)
        engine._spatial_provider=SimpleNamespace(bind_origin=lambda origin:calls.append(('bind',origin)))
        with patch.object(PipelineEngine,'_source_status',side_effect=lambda *args:calls.append(('publish',args))):
            engine._source_status('source_started',{'source_epoch_monotonic_sec':123.})
        self.assertEqual(calls[0],('bind',123.))
        self.assertEqual(calls[1][0],'publish')

    def test_live_provider_attached_before_live_launch(self):
        calls=[]
        engine=PrototypeEngine.__new__(PrototypeEngine)
        engine._journal=object();engine._input_journal=object()
        engine.begin=lambda:calls.append('begin')
        engine._spatial_provider=SimpleNamespace(attach=lambda live:calls.append(('attach',live)))
        engine._launch=lambda source:calls.append(('launch',source))
        source=SimpleNamespace(live=object())
        with patch('app.pipeline.LivePipelineSource',return_value=source) as constructor:
            engine.start_xvf('explicit test configuration')
        self.assertEqual(calls,['begin',('attach',source.live),('launch',source)])
        self.assertIs(constructor.call_args.args[3],engine._spatial_provider)
        self.assertIs(constructor.call_args.args[0],engine._input_journal)


if __name__=='__main__':unittest.main(verbosity=2)
