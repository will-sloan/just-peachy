"""Actual pinned naming/tracker math; no model/device load. See README_IDENTITY_MODES.md."""
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

from identity_modes import IdentityModeAdapter
from d1_spatial_policy import SourceClockSpatialPolicy

DEFAULT_RELEASE = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/field-artifact-install-v2-evidence/target/deployment/releases/b01-offline-20260930-v12'
MANIFEST_SHA256 = '274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0'


def voice(serial, start, end, *, delay=20.):
    return dict(event_id=f'fixture:{serial}',source_start_sec=start,source_end_sec=end,
        available_at_sec=end+delay,speech=True,overlap=False,vector=[1.]+[0.]*191,
        evidence_kind='mature' if end-start >= 1.5 else 'short',clean_intervals=[[start,end]])


class PinnedContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get('JUST_PEACHY_PINNED_RELEASE',DEFAULT_RELEASE)).resolve()
        manifest_raw = (cls.root/'RELEASE_MANIFEST.json').read_bytes()
        if hashlib.sha256(manifest_raw).hexdigest() != MANIFEST_SHA256:
            raise ValueError('Exact pinned build28 original source manifest required')
        pins = {p['path']:p['sha256'] for p in json.loads(manifest_raw)['files']}
        for package, relative in (('edge_speech_pipeline','vendor/edge_speech_pipeline'),('app','app')):
            if package in sys.modules:
                raise RuntimeError('Run test_identity_pinned.py alone in a fresh Python process')
            # A package shell prevents __init__ importing PipelineEngine/models.
            # The actual hash-verified relative math modules remain unchanged.
            shell = ModuleType(package)
            shell.__path__ = [str(cls.root/relative)]
            sys.modules[package] = shell
        cls.tracking = importlib.import_module('edge_speech_pipeline.research_tracking_v3')
        cls.identity = importlib.import_module('app.n2_identity')
        cls.spatial = importlib.import_module('app.live_spatial')
        cls.observation = importlib.import_module('edge_speech_pipeline.research_profiles').DeliveredSpatialObservation
        for module in list(sys.modules.values()):
            source = getattr(module,'__file__',None)
            if source and Path(source).resolve().is_relative_to(cls.root):
                relative = Path(source).resolve().relative_to(cls.root).as_posix()
                if relative not in pins or hashlib.sha256(Path(source).read_bytes()).hexdigest() != pins[relative]:
                    raise ValueError('Loaded pinned math source differs: '+relative)
        for candidate in ('C079','C060'):
            path = cls.root/'config'/('parent_'+candidate+'.json')
            relative = path.relative_to(cls.root).as_posix()
            if hashlib.sha256(path.read_bytes()).hexdigest() != pins[relative]:
                raise ValueError('Pinned spatial profile differs')
        cls.namespace = dict(model_sha256='5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609',
            preprocessing='mono-float32-16k-redimnet2-native-l2-v1',dimension=192,normalization='L2',min_samples=8000)

    def gallery(self):
        import numpy as np
        class Gallery:
            ids,names,gallery_id = ['fixture-person'],['Fixture Person'],'fixture-unvalidated-gallery'
            calibration = dict(status='UNCALIBRATED_PERSONAL_DOMAIN')
            receipt = dict(templates=[dict(references=[{}])])
            query_count = 0
            def score(gallery, vector):
                gallery.query_count += 1
                # Declared synthetic vector, no enrolled/private vector read.
                return [dict(profile_id='fixture-person',name='Fixture Person',cosine=float(np.asarray(vector)[0]))]
        result = Gallery()
        result.namespace = deepcopy(self.namespace)
        return result

    def config(self, candidate):
        row = json.loads((self.root/'config'/('parent_'+candidate+'.json')).read_bytes())
        return self.tracking.S6CTrackingConfig.from_mapping(row['tracker'])

    def provider(self):
        observation = self.observation
        class Provider:
            count = 0
            def evidence_for_window(provider,start,end,available):
                provider.count += 1
                return observation(angle_deg=30.,available_at_sec=end-.01,source_start_sec=start,
                    source_end_sec=end-.01,energy=1.,reliability=1.,valid=True,sequence=provider.count)
        return Provider()

    def test_actual_name_map_queries_but_does_not_accept_uncalibrated_identical_voice(self):
        gallery = self.gallery()
        adapter = IdentityModeAdapter(self.identity.N2NameMap(gallery),self.namespace)
        first = adapter.resolve(dict(tracker_id='t'),voice(1,0.,1.))
        second = adapter.resolve(dict(tracker_id='t'),voice(2,.5,1.5))
        self.assertTrue(first['identity']['query_executed'])
        self.assertEqual(second['identity']['unique_clean_sec'],1.5)
        self.assertEqual(second['identity']['new_unique_sec'],.5)
        self.assertEqual(second['identity']['scores'][0]['cosine'],1.)
        self.assertEqual(second['naming_state'],'unknown')
        self.assertIsNone(second['known_profile_id'])
        self.assertFalse(second['identity']['voice_identity_verified'])

    def test_actual_closed_map_fallback_and_current_voice_remain_assumptions(self):
        adapter = IdentityModeAdapter(self.identity.N2NameMap(self.gallery(),closed=True),self.namespace)
        before = adapter.annotate_caption(dict(source_start_sec=0.,source_end_sec=.1))
        self.assertEqual(before['closed_display_assignment']['profile_id'],'fixture-person')
        result = adapter.resolve(dict(tracker_id='t'),voice(1,0.,.5))
        self.assertEqual(result['naming_state'],'closed_assumption')
        self.assertEqual(result['name_revision']['replacement_naming_state'],'closed_assumption')
        self.assertFalse(result['identity']['voice_identity_verified'])

    def test_actual_C079_C060_reuse_original_cue_math_and_audio_gate(self):
        for candidate in ('C079','C060'):
            with self.subTest(candidate=candidate):
                tracker = self.tracking.S6CTracker(self.config(candidate))
                policy = SourceClockSpatialPolicy(tracker,self.provider())
                admitted = policy.associate(dict(tracker_id='native0'),voice(1,0.,.5))
                self.assertEqual(admitted['cue']['qualified_bearing_deg'],30.)
                self.assertEqual(admitted['spatial_association']['model_delay_from_source_sec'],20.)
                rejected = policy.associate(dict(tracker_id='native0'),dict(voice(2,.5,1.),overlap=True))
                self.assertEqual(rejected['reason'],'audio_gate_reject')
                self.assertIsNone(rejected['tracker_id'])
                with self.assertRaisesRegex(ValueError,'duplicate embedding support'):
                    policy.associate(dict(tracker_id='native0'),voice(3,.5,1.))

    def test_actual_motion_frame_change_clears_spatial_memory_and_preserves_voice_track(self):
        tracker = self.tracking.S6CTracker(self.config('C079'))
        motion = SimpleNamespace(snapshot=lambda:dict(frame_generation=1,unsafe_generation=0))
        guarded = self.spatial.MotionFrameTracker(tracker,motion)
        policy = SourceClockSpatialPolicy(guarded,self.provider())
        first = policy.associate(dict(tracker_id='native0'),voice(1,0.,.5))
        self.assertIsNotNone(tracker.tracks[0].location)
        motion.snapshot=lambda:dict(frame_generation=2,unsafe_generation=0)
        second = policy.associate(dict(tracker_id='native0'),voice(2,.5,1.))
        self.assertEqual(guarded.location_resets,1)
        self.assertIsNone(second['cue']['qualified_bearing_deg'])
        self.assertIsNone(tracker.tracks[0].location)
        self.assertEqual(first['tracker_id'],second['tracker_id'])


if __name__ == '__main__':
    unittest.main()
