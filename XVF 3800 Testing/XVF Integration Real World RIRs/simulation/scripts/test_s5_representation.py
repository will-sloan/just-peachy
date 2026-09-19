"""Synthetic model-free fixtures for the optional representation diagnostic."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import s5_representation as r

class Fixtures(unittest.TestCase):
    def window(self,n,person='P',case=None,quality='clean'):
        return {'case_id':case or f'D{n}','segment_index':0,'speaker_key':person,'participant_id':'A',
                'source_id':f's{n}','source_pcm_sha256':f'h{n}','prompt_group':f't{n}',
                'dataset':'corpus','quality_partition':quality,'family_id':'F1','room_table':'room',
                'rir_id':'rir','relative_source_db':0,'noise_ids':[],'window_id':f'W{n}'}
    def test_activity_shift_once_and_margin(self):
        seg={'source_start_sample':1000,'source_stop_sample':21000,'activity_ranges_samples_estimated':[[1800,21800]]}
        self.assertEqual(r.candidate_interval(seg,[],320),[7800,15800])
    def test_other_convolution_tail_blocks(self):
        seg={'source_start_sample':0,'source_stop_sample':12000,'activity_ranges_samples_estimated':[[800,12800]]}
        other={'kind':'utterance','source_start_sample':0,'convolution_stop_sample':9000}
        self.assertIsNone(r.candidate_interval(seg,[other],320))
    def test_short_or_missing_activity_not_replaced(self):
        self.assertIsNone(r.candidate_interval({'source_start_sample':0,'source_stop_sample':16000},[],0))
        self.assertIsNone(r.candidate_interval({'source_start_sample':0,'source_stop_sample':8000,'activity_ranges_samples_estimated':[[800,8800]]},[],320))
    def test_bad_double_shift_activity_rejected(self):
        with self.assertRaises(ValueError):r.candidate_interval({'source_start_sample':0,'source_stop_sample':9000,'activity_ranges_samples_estimated':[[1600,10600]]},[],0)
    def test_subtract_disjoint_boundaries(self):
        self.assertEqual(r.subtract([[0,20]],[[3,7],[10,13]]),[[0,3],[7,10],[13,20]])
    def test_reserve_guard_before_stat(self):
        guard=r.Guard([{'case_id':'R','split':'reserve','task_scoring_allowed':False}])
        with patch.object(Path,'stat',side_effect=AssertionError('Must not stat reserve')):
            with self.assertRaises(PermissionError):guard.path('R',{'path':'forbidden','sha256':'x'},'output_audio')
        self.assertEqual(len(guard.denied),1)
    def test_bound_file_change_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.json';p.write_text('{}');b=r.binding(p);p.write_text('{"a":1}')
            g=r.Guard([{'case_id':'D','split':'development','task_scoring_allowed':True}])
            with self.assertRaises(ValueError):g.json('D',b)
    def test_unique_pcm_and_participant_cap(self):
        rows=[self.window(i,case='D') for i in range(8)];rows.append(dict(rows[0],source_id='alias'))
        out=r.choose_windows(rows)
        self.assertEqual(len(out),4);self.assertEqual(len({w['source_pcm_sha256'] for w in out}),4)
    def test_window_max_and_identity_round_robin(self):
        rows=[self.window(i,person=str(i%3)) for i in range(20)]
        out=r.choose_windows(rows,maximum=3)
        self.assertEqual(len(out),3);self.assertEqual(len({w['speaker_key'] for w in out}),3)
    def test_genuine_disjoint_and_balanced_impostors(self):
        rows=[self.window(i,person=str(i//4)) for i in range(12)]
        trials,info=r.comparisons(rows);lookup={x['window_id']:x for x in rows}
        self.assertEqual(info['genuine_count'],6);self.assertEqual(info['impostor_count'],6)
        used=[]
        for t in trials:
            a,b=lookup[t['left']],lookup[t['right']]
            self.assertEqual(a['speaker_key']==b['speaker_key'],t['kind']=='genuine')
            if t['kind']=='genuine':used.extend([t['left'],t['right']])
        self.assertEqual(len(used),len(set(used)))
    def test_same_prompt_no_genuine(self):
        rows=[self.window(1),self.window(2)];rows[1]['prompt_group']=rows[0]['prompt_group']
        trials,info=r.comparisons(rows);self.assertEqual(info['genuine_count'],0)
    def test_missing_matching_quality_impostor_explicit(self):
        rows=[self.window(1,quality='other'),self.window(2,quality='other'),self.window(3,person='Q')]
        trials,info=r.comparisons(rows);self.assertEqual(info['genuine_count'],1);self.assertEqual(info['impostor_count'],0)
        self.assertEqual(len(info['unmatched_impostor_gaps']),1)
    def test_native_journal_adapter_once(self):
        class FakeJournal:
            def append(self,x):
                self._writer.write(np.round(np.clip(x,-1,.999969)*32768).astype('<i2').tobytes())
        raw=np.tile(np.asarray([-.8,-.1,0,.1,.7],np.float32),1600)
        values,h=r.native_pcm16_window(raw,1.1,FakeJournal)
        expected=(raw.astype(np.float64)*1.1).astype(np.float32)
        expected=np.round(np.clip(expected,-1,.999969)*32768).astype('<i2').astype(np.float32)/32768
        np.testing.assert_array_equal(values,expected)
        self.assertEqual(len(h),64)
        with self.assertRaises(ValueError):r.native_pcm16_window(raw,2,FakeJournal)
    def test_cosine_recipe_pairing_and_missing_denominator(self):
        rows=[self.window(1),self.window(2),self.window(3,person='Q'),self.window(4,person='Q')]
        trials,pairing=r.comparisons(rows);plan={'windows':rows,'comparisons':trials,'selected_distributions':{},'pairing':pairing,'limitations':[]}
        vectors={(w['window_id'],o):np.asarray([1.,0.]) for w in rows for o in ('O0','O1')}
        with patch.object(r,'binding',return_value={'sha256':'fixture'}):
            result=r.summarize(plan,vectors,[])
            self.assertEqual(result['complete_paired_comparisons'],4)
            self.assertTrue(all(x['O1_minus_O0']==0 for x in result['scores']))
            del vectors[('W1','O1')]
            result=r.summarize(plan,vectors,[])
            self.assertLess(result['complete_paired_comparisons'],result['planned_comparisons'])
            self.assertEqual(result['status'],'PARTIAL_WITH_WINDOW_FAILURES')

if __name__=='__main__':unittest.main()
