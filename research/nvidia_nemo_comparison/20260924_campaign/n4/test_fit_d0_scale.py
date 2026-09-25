"""Frozen calibration protocol math and separation tests. README_FIT_D0_SCALE.md."""
from copy import deepcopy
from pathlib import Path
import unittest
import numpy as np
from common import load
from fit_d0_scale import partition,representatives,collect_groups,summarize,transform_profile,gate


class TestScale(unittest.TestCase):
    def setUp(self):self.protocol=load(Path(__file__).with_name('D0_C_SCALE_PROTOCOL_V1.json'))
    def test_partition_stays_with_identity(self):
        import hashlib
        for name in ('person1','person2','person3'):
            self.assertEqual(partition(name),'validation' if int(hashlib.sha256(name.encode()).hexdigest()[:8],16)%3==0 else 'fit')
    def test_representatives_use_geometry_not_scores(self):
        rows=[dict(evidence_kind='short',end_sample=i*4000+8000,start_sample=i*4000,
                   normalized_embedding=[float(i)]+[0.]*191) for i in range(6)]
        result=representatives(rows[::-1])
        self.assertEqual(result['short'][:,0].tolist(),[0.,2.,5.]);self.assertEqual(len(result['mature']),0)
    def test_matched_pairs_and_protected_same_pcm(self):
        v=np.zeros((1,192));v[0,0]=1
        source=dict(source_id='one',pcm='hash1',identity='same',vectors=[dict(short=v,mature=v)]*2)
        other=dict(source,source_id='two',pcm='hash2')
        groups,counts=collect_groups([source,other]);self.assertEqual(len(groups),3)
        self.assertEqual(counts['included_window_pairs_per_encoder'],4)
        other['pcm']='hash1';groups,counts=collect_groups([source,other])
        self.assertEqual(groups,{});self.assertEqual(counts['same_source_or_pcm_excluded'],1)
    def test_cross_partition_pairs_never_fit(self):
        ids=[str(i) for i in range(100)]
        names=[next(i for i in ids if partition(i)==part) for part in ('fit','validation')]
        v=np.zeros((0,192));base=dict(vectors=[dict(short=v,mature=v)]*2)
        groups,counts=collect_groups([dict(base,source_id=str(i),pcm=str(i),identity=n) for i,n in enumerate(names)])
        self.assertEqual(groups,{});self.assertEqual(counts['cross_partition_excluded'],1)
    def test_nested_weighting_and_fit_validation_separation(self):
        def pairs(*scores):return [[np.asarray(s),np.asarray(s)] for s in scores]
        groups={('fit','a','a','short/short'):pairs([.9,.9,.9],[.1]),
                ('fit','a','a','mature/mature'):pairs([.7]),
                ('fit','b','b','short/short'):pairs([.8]),
                ('fit','a','b','short/short'):pairs([.2]),
                ('validation','a','a','short/short'):pairs([-.9])}
        row=summarize(groups,'fit',0)
        self.assertAlmostEqual(row['same'],.7);self.assertAlmostEqual(row['different'],.2)
        error=summarize(groups,'fit',0,.5)
        self.assertAlmostEqual(error['same'],.125);self.assertEqual(error['different'],0.)
    def test_affine_maps_cosines_and_differences_without_mutation(self):
        names=self.protocol['fit'];profile=dict(tracker={k:.4 for k in names['raw_cosine_threshold_fields']})
        profile['tracker'].update({k:.15 for k in names['cosine_difference_fields']});profile['tracker']['joint_margin']=.1
        original=deepcopy(profile)
        result,mapping=transform_profile(profile,dict(different=.2,same=.8),dict(different=.3,same=.9),self.protocol)
        self.assertEqual(profile,original);self.assertAlmostEqual(mapping['slope'],1.)
        self.assertAlmostEqual(result['tracker']['cosine_threshold'],.5)
        self.assertAlmostEqual(result['tracker']['voice_score_scale'],.15)
        self.assertEqual(result['tracker']['joint_margin'],.1)
    def test_invalid_gap_and_parameter_are_not_clipped(self):
        names=self.protocol['fit'];p=dict(tracker={k:.9 for k in names['raw_cosine_threshold_fields']})
        p['tracker'].update({k:.15 for k in names['cosine_difference_fields']})
        with self.assertRaisesRegex(ValueError,'gap'):
            transform_profile(p,dict(different=.2,same=.2),dict(different=.1,same=.9),self.protocol)
        with self.assertRaisesRegex(ValueError,'outside'):
            transform_profile(p,dict(different=.2,same=.5),dict(different=.1,same=.9),self.protocol)
    def test_fixed_gate_both_constraints_required(self):
        nominal=dict(same=.2,different=.1,balanced_mean=.15)
        self.assertTrue(gate(nominal,dict(same=.19,different=.10,balanced_mean=.145)))
        self.assertFalse(gate(nominal,dict(same=.01,different=.12,balanced_mean=.065)))
        self.assertFalse(gate(nominal,dict(same=.3,different=.1,balanced_mean=.2)))
        self.assertFalse(gate(nominal,dict(same=None,different=.1,balanced_mean=None)))


if __name__=='__main__':unittest.main()
