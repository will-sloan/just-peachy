"""Reference denominator/control fixtures; README_S6A_CUES.md."""
import copy
import unittest
from s6a_cue_score import state_intersections,tracking_metrics


def support():
    turns=[]
    for i,key in enumerate(('A','B','A')):
        turns.append(dict(segment_index=i,speaker_key=key,participant_id=key,source_id='clip'+str(i),
                          whole_clip_bin='1-<2s',active_duration_bin='1-<2s',whole_clip_duration_s=1.,
                          activity_available=True,active_ranges=[[i*16000,(i+1)*16000]],
                          file_support=[[i*16000,(i+1)*16000]]))
    return dict(output_mappings={'O0':{'source_with_rir_to_output_offset_samples':0}},turns=turns,
                all_speaker_reference_complete=True)


class ScoreTests(unittest.TestCase):
    def test_all_unknown_and_one_person_do_not_win(self):
        one=tracking_metrics(support(),'O0',[],48000,control='one_person')
        unknown=tracking_metrics(support(),'O0',[],48000,control='all_unknown')
        self.assertEqual(one['sole_active_samples'],48000);self.assertEqual(one['false_merge_samples'],16000)
        self.assertEqual(unknown['unknown_samples'],48000);self.assertEqual(unknown['false_merge_samples'],0)
        self.assertGreater(one['unassigned_or_conflated_fraction'],0)
        self.assertEqual(unknown['unassigned_or_conflated_fraction'],1)

    def test_future_decision_not_credited(self):
        decisions=[dict(available_at_sec=1.,source_end_sec=.9,anonymous_label='Speaker_1')]
        result=state_intersections(decisions,0,8000)
        self.assertEqual(result,[(0,8000,'Unknown')])

    def test_expiry_and_interval_duration(self):
        decisions=[dict(available_at_sec=.5,source_end_sec=.5,anonymous_label='Speaker_1')]
        result=state_intersections(decisions,0,32000)
        self.assertEqual(sum(b-a for a,b,_ in result),32000)
        self.assertEqual(sum(b-a for a,b,label in result if label=='Speaker_1'),12000)

    def test_missing_alignment_retains_source_turn_denominator(self):
        value=support();value['output_mappings']['O0']['source_with_rir_to_output_offset_samples']=None
        result=tracking_metrics(value,'O0',[],48000)
        self.assertEqual(result['source_turns'],3);self.assertEqual(len(result['turns']),3)
        self.assertTrue(all(not t['mapping_available'] for t in result['turns']))
        self.assertIsNone(result['unknown_samples'])

    def test_overlap_not_double_counted_in_sole_support(self):
        value=support();value['turns'][1]['active_ranges']=[[8000,24000]]
        result=tracking_metrics(value,'O0',[],48000,control='one_person')
        self.assertEqual(result['sole_active_samples'],32000)

    def test_missing_predecessor_return_remains_unknown(self):
        result=tracking_metrics(support(),'O0',[],48000,control='all_unknown')
        self.assertEqual(result['return_unknown'],1)
        self.assertEqual(result['return_consistent'],0)

    def test_reference_rename_changes_only_analysis_identifiers(self):
        original=support();renamed=copy.deepcopy(original)
        for t in renamed['turns']:t['speaker_key']='renamed'+t['speaker_key']
        a=tracking_metrics(original,'O0',[],48000,control='one_person')
        b=tracking_metrics(renamed,'O0',[],48000,control='one_person')
        self.assertEqual(a['false_merge_samples'],b['false_merge_samples'])
        self.assertEqual(a['return_consistent'],b['return_consistent'])


if __name__=='__main__':unittest.main()
