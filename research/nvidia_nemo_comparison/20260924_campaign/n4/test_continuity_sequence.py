"""Continuity capacity, reference firewall and lossless PCM tests. README_CONTINUITY_SEQUENCE.md."""
from copy import deepcopy
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import wave
from common import bind, fingerprint
import continuity_sequence as sequence

CONTEXT={}


class SequenceTests(unittest.TestCase):
    def fixture(self,suffix='',channels=1):
        directory=CONTEXT['output']/(self._testMethodName+suffix);directory.mkdir()
        segments=[];offset=0;raw=b''
        for i,values in enumerate(([1,-2,32767],[-32768,0,7,99])):
            path=directory/f'input-{i}.wav';data=struct.pack('<'+'h'*len(values),*values);raw+=data
            with wave.open(str(path),'wb') as stream:
                stream.setnchannels(channels);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(data if channels==1 else data*2)
            job=dict(job_id=f'fixture-{i}',audio_path=str(path),audio_sha256=bind(path)['sha256'],frames=len(values),sample_rate_hz=16000,gain=1.,reset_between_scenes=True,tap='O0')
            segments.append(dict(index=i,job=job,destination_start_frame=offset,destination_end_frame=offset+len(values)));offset+=len(values)
        plan=dict(schema='n4-continuity-sequence-plan-v1',status='PREPARED_INPUT_ONLY',frames=7,sequence_id='fixture-sequence',segments=segments)
        return directory,plan,raw

    def materialize(self,plan,path):
        with patch.object(sequence,'TARGET_FRAMES',6),patch.object(sequence,'MAX_FRAMES',12):
            return sequence.materialize(plan,path)

    def test_full_actual_bank_selection_is_deterministic_and_capacity_safe(self):
        plan,truth=sequence.build(CONTEXT['docs'],CONTEXT['bindings'])
        self.assertEqual(plan['original_sessions'],27);self.assertEqual(plan['frames'],19308429)
        self.assertEqual(plan['distinct_actor_count'],8)
        self.assertEqual(plan['reference_classes'],{'complete_nonoverlap':23,'empty_control':1,'complete_overlap':3})
        self.assertFalse(plan['reset_at_joins']);self.assertFalse(plan['actual_continuity_test'])
        reordered=deepcopy(CONTEXT['docs'])
        for name,key in [('AUDIO_ONLY_480.json','jobs'),('EVALUATOR_TRUTH.json','cells'),('EVALUATOR_STRATA.json','scenes'),('PAIRED_CAPTURE_PROVENANCE.json','pairs')]:
            reordered[name][key].reverse()
        self.assertEqual(sequence.build(reordered,CONTEXT['bindings']),(plan,truth))
        CONTEXT['plan']=plan;CONTEXT['truth']=truth

    def test_reference_offsets_preserve_all_words_and_global_actors(self):
        plan,truth=sequence.build(CONTEXT['docs'],CONTEXT['bindings']);original={t['job_id']:t for t in CONTEXT['docs']['EVALUATOR_TRUTH.json']['cells']}
        joined=[]
        for segment in plan['segments']:
            for old in original[segment['job']['job_id']]['turns']:
                new=truth['turns'][len(joined)];joined.append(new)
                for key in old:
                    if key not in ('turn_id','file_support_samples','activity_ranges_samples_estimated'):self.assertEqual(new[key],old[key])
                self.assertEqual(new['file_support_samples'],[x+segment['destination_start_frame'] for x in old['file_support_samples']])
                self.assertEqual(new['activity_ranges_samples_estimated'],[[x+segment['destination_start_frame'] for x in pair] for pair in old['activity_ranges_samples_estimated']])
        self.assertEqual(len(joined),len(truth['turns']));self.assertEqual(len({t['turn_id'] for t in joined}),len(joined))
        self.assertTrue(truth['NEVER_PASS_TO_RUNTIME']);self.assertEqual(truth['reference_class'],'complete_overlap')

    def test_missing_pair_truth_and_gain_provenance_refused(self):
        edits=[lambda d:d['PAIRED_CAPTURE_PROVENANCE.json']['pairs'][0]['cells'].pop(),
            lambda d:d['EVALUATOR_TRUTH.json']['cells'][0].update(frames=1),
            lambda d:d['PAIRED_CAPTURE_PROVENANCE.json']['pairs'][0]['cells'][0].update(gain_already_applied=1.),
            lambda d:d['EVALUATOR_TRUTH.json']['cells'][0].update(scene_cast=[])]
        for edit in edits:
            docs=deepcopy(CONTEXT['docs']);edit(docs)
            with self.assertRaises(ValueError):sequence.build(docs,CONTEXT['bindings'])

    def test_capacity_and_insufficient_duration_refused(self):
        jobs,scenes,_,_=sequence.validate_bank(CONTEXT['docs'])
        crowded=deepcopy(scenes)
        for scene in crowded:scene['actor_group_ids']=[f'fixture-{i}' for i in range(9)]
        with self.assertRaises(ValueError):sequence.choose(crowded,jobs)
        with self.assertRaises(ValueError):sequence.choose(scenes[:1],jobs)

    def test_partial_or_exact_word_timing_never_silently_clipped(self):
        old=deepcopy(CONTEXT['docs']['EVALUATOR_TRUTH.json']['cells'][0]['turns'][0])
        for change in (dict(file_support_samples=[-1,10]),dict(activity_ranges_samples_estimated=[[0,999999999]]),dict(word_times=[])):
            bad=deepcopy(old);bad.update(change)
            with self.assertRaises(ValueError):sequence.shifted_turn(bad,0,1600000,0)

    def test_actual_pcm_bytes_copied_exactly_and_runtime_input_has_no_truth(self):
        directory,plan,raw=self.fixture();job,receipt=self.materialize(plan,directory/'output.wav')
        with wave.open(str(directory/'output.wav'),'rb') as stream:
            self.assertEqual(stream.getparams()[:4],(1,2,16000,7));self.assertEqual(stream.readframes(7),raw)
        self.assertEqual(set(job),{'job_id','audio_path','audio_sha256','frames','sample_rate_hz','gain','reset_between_scenes','tap'})
        self.assertTrue(job['reset_between_scenes']);self.assertEqual(job['gain'],1.)
        self.assertEqual(sum(s['frames'] for s in receipt['segments']),7);self.assertFalse(receipt['actual_source_execution'])

    def test_changed_waveform_and_gain_refused_with_prefix_preserved(self):
        directory,plan,_=self.fixture();plan['segments'][1]['job']['audio_sha256']='0'*64
        with self.assertRaises(ValueError):self.materialize(plan,directory/'failed.wav')
        self.assertTrue((directory/'failed.wav').exists())
        directory,plan,_=self.fixture('gain');plan['segments'][0]['job']['gain']=1.4125375446227544
        with self.assertRaises(ValueError):self.materialize(plan,directory/'failed.wav')

    def test_join_gap_duplicate_offset_and_mixed_tap_refused(self):
        changes=[lambda p:p['segments'][1].update(destination_start_frame=4),lambda p:p['segments'][1].update(index=0),
            lambda p:p['segments'][1]['job'].update(tap='O1')]
        for i,change in enumerate(changes):
            directory,plan,_=self.fixture(str(i));change(plan)
            with self.assertRaises(ValueError):self.materialize(plan,directory/'failed.wav')

    def test_foreign_pcm_and_frame_census_refused(self):
        directory,plan,_=self.fixture('stereo',channels=2)
        with self.assertRaises(ValueError):self.materialize(plan,directory/'failed.wav')
        directory,plan,_=self.fixture('frames');plan['frames']=8
        with self.assertRaises(ValueError):self.materialize(plan,directory/'failed.wav')

    def test_no_overwrite_or_unbounded_assembly(self):
        directory,plan,_=self.fixture();out=directory/'existing.wav';out.write_bytes(b'preserve')
        with self.assertRaises(ValueError):self.materialize(plan,out)
        self.assertEqual(out.read_bytes(),b'preserve')
        plan['frames']=13
        with self.assertRaises(ValueError):self.materialize(plan,directory/'absent.wav')
        self.assertFalse((directory/'absent.wav').exists())
