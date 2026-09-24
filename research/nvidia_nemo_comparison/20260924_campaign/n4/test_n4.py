"""Adversarial preparation/cache/denominator/metric tests; README_METRICS.md."""
import copy
import unittest
from common import audio_only, cache_key
from prepare import dependency_groups
from metrics import lexical, speaker_words, activity, score_cell, aggregate, canonical
from paired import paired_report
from coverage import coverage
from resources import planning_tier,process_tree
from evidence_archive import verify_archive


class IntegrityTests(unittest.TestCase):
    def job(self):
        return dict(job_id='test_O0',audio_path='unused.wav',audio_sha256='a'*64,
                    frames=16000,sample_rate_hz=16000,gain=1.,reset_between_scenes=True,tap='O0')

    def key(self, **overrides):
        fields=dict(audio=self.job(),model='model-sha-precision',preprocessing='v1',
                    streaming='causal',runtime='pinned',history='scene-reset',scheduler='v1',
                    window=dict(start_sample=0,end_sample=8000,waveform_sha256='b'*64))
        fields.update(overrides)
        return cache_key('embedding',**fields)

    def test_truth_cannot_enter_runtime(self):
        job=self.job();job['transcript']='leak'
        with self.assertRaises(ValueError):audio_only(job)

    def test_prepared_gain_not_applied_twice(self):
        job=self.job();job['gain']=1.4125
        with self.assertRaises(ValueError):audio_only(job)

    def test_cache_invalidates_waveform_model_history_scheduler(self):
        key=self.key()
        for field in ('model','history','scheduler','runtime','streaming','preprocessing'):
            self.assertNotEqual(key,self.key(**{field:'changed'}))
        self.assertNotEqual(key,self.key(window=dict(start_sample=1,end_sample=8000,waveform_sha256='b'*64)))
        self.assertNotEqual(key,self.key(window=dict(start_sample=0,end_sample=8000,waveform_sha256='c'*64)))

    def test_cache_has_no_reference_path_dependency(self):
        job=self.job();job['audio_path']='different_location_same_bytes.wav'
        self.assertEqual(self.key(),self.key(audio=job))

    def test_transitive_multi_actor_clusters(self):
        rows=[dict(case_id='a',actors=['1']),dict(case_id='b',actors=['1','2']),dict(case_id='c',actors=['2'])]
        groups=dependency_groups(rows,['actors'])
        self.assertEqual(len(set(groups.values())),1)


class MetricTests(unittest.TestCase):
    def truth(self, kind='complete_nonoverlap'):
        return dict(job_id='x',reference_class=kind,frames=32000,complete_reference=True,
            turns=[dict(identity='alice',transcript='one two',activity_ranges_samples_estimated=[[0,16000]])])

    def prediction(self, text='', status='COMPLETE'):
        return dict(job_id='x',status=status,raw_text=text,
                    segments=[dict(text=text,track='unknown')] if text else [],activity=[])

    def test_all_missed_words_retained(self):
        row=score_cell(self.truth(),self.prediction())
        self.assertEqual(row['primary_wer']['deletions'],2)
        self.assertEqual(row['primary_wer']['rate'],1.)

    def test_failed_is_not_successful_empty(self):
        row=score_cell(self.truth(),self.prediction(status='FAILED'))
        self.assertIsNone(row['primary_wer'])
        total=aggregate([row])
        self.assertEqual(total['unscored_execution_reference_words'],2)
        self.assertIsNone(total['primary_nonoverlap_WER'])

    def test_empty_insertions(self):
        truth=self.truth('empty_control');truth['turns']=[]
        row=score_cell(truth,self.prediction('one two'))
        self.assertIsNone(row['primary_wer'])
        self.assertEqual(row['inserted_words_per_minute'],60)

    def test_overlap_not_ordinary_wer(self):
        truth=self.truth('complete_overlap')
        truth['turns'].append(dict(identity='bob',transcript='three four',activity_ranges_samples_estimated=[[0,16000]]))
        row=score_cell(truth,self.prediction('one two'))
        self.assertIsNone(row['primary_wer'])
        self.assertEqual(row['cpwer']['words'],4)
        self.assertEqual(row['cpwer']['errors'],2)

    def test_permuted_speakers_cpwer(self):
        refs=[dict(identity='a',transcript='one two'),dict(identity='b',transcript='three four')]
        hyp=[dict(track='b',text='one two'),dict(track='a',text='three four')]
        self.assertEqual(speaker_words(refs,hyp)['cpwer']['errors'],0)

    def test_mimo_utterance_order(self):
        refs=[dict(identity='a',transcript='one two'),dict(identity='a',transcript='three four'),dict(identity='b',transcript='five six')]
        hyp=[dict(track='1',text='one two'),dict(track='2',text='five six three four')]
        self.assertEqual(speaker_words(refs,hyp)['mimo']['value']['errors'],0)

    def test_count_weighted_not_mean_percent(self):
        a=lexical('a','');b=lexical(' '.join(['a']*99),' '.join(['a']*99))
        rows=[dict(primary_wer=w,execution_status='COMPLETE') for w in (a,b)]
        self.assertEqual(aggregate(rows)['primary_nonoverlap_WER'],.01)

    def test_activity_overlap_miss(self):
        ref=[dict(start=0.,end=1.,label='a'),dict(start=0.,end=1.,label='b')]
        hyp=[dict(start=0.,end=1.,label='x')]
        row=activity(ref,hyp,2,complete_reference=True,collar=0)
        self.assertAlmostEqual(row['DER'],.5)
        self.assertAlmostEqual(row['JER'],.5)

    def test_activity_all_unknown_not_perfect_diarization(self):
        ref=[dict(start=0.,end=1.,label='a'),dict(start=1.,end=2.,label='b')]
        one=[dict(start=0.,end=2.,label='unknown')]
        self.assertGreater(activity(ref,one,2,complete_reference=True,collar=0)['DER'],0)

    def test_activity_no_timestamp_clamping(self):
        with self.assertRaises(ValueError):
            activity([], [dict(start=-.01,end=1,label='x')],2,complete_reference=True)

    def test_incomplete_has_no_all_speaker_der(self):
        self.assertIsNone(activity([],[],2,complete_reference=False)['DER'])

    def test_empty_activity_retains_false_alarm_seconds(self):
        row=activity([],[dict(start=0.,end=1.,label='x')],2,complete_reference=True)
        self.assertIsNone(row['DER']);self.assertIsNone(row['JER'])
        self.assertEqual(row['DER_components']['false alarm'],1.)

    def test_speaker_attribution_cannot_drop_caption_tokens(self):
        pred=self.prediction('one two');pred['segments'][0]['text']='one'
        with self.assertRaises(ValueError):score_cell(self.truth(),pred)

    def test_canonical_does_not_drop_missed_words(self):
        self.assertEqual(canonical('DO NOT take two!'),'do not take two')
        self.assertEqual(lexical(canonical('DO NOT take two!'),canonical('take two'))['deletions'],2)


class PairTests(unittest.TestCase):
    def rows(self,n):
        return [dict(case_id=str(i),tap=t,baseline_errors=1,baseline_words=10,
            candidate_errors=0,candidate_words=10,dependency_cluster=str(i),
            room=str(i%2),actor_cluster=str(i),family_id='f') for i in range(n) for t in ('O0','O1')]

    def test_taps_not_independent(self):
        row=paired_report(self.rows(7),replicates=100)
        self.assertEqual(row['pairs'],14)
        self.assertEqual(row['clusters'],7)
        self.assertIsNone(row['interval95'])

    def test_paired_interval_deterministic(self):
        report=paired_report(self.rows(8),replicates=100)
        self.assertEqual(report,paired_report(self.rows(8),replicates=100))
        self.assertEqual(report['interval95'],[-.1,-.1])

    def test_duplicate_and_mismatched_denominators_rejected(self):
        rows=self.rows(8)
        with self.assertRaises(ValueError):paired_report(rows+[rows[0]],replicates=100)
        rows[0]['candidate_words']=9
        with self.assertRaises(ValueError):paired_report(rows,replicates=100)


class AccountingTests(unittest.TestCase):
    def test_full_matrix_does_not_lose_unreported_rows(self):
        total=coverage([str(i) for i in range(16)],[str(i) for i in range(480)],[])
        self.assertEqual(total['required'],7680)
        self.assertEqual(total['not_tested'],7680)
        self.assertFalse(total['fully_complete'])

    def test_status_denominators(self):
        rows=[dict(profile='p',job_id='a',status='FAILED',reason='actual failure'),
              dict(profile='p',job_id='b',status='INCOMPATIBLE',reason='tested missing operation')]
        total=coverage(['p'],['a','b','c'],rows)
        self.assertEqual((total['failed'],total['incompatible'],total['not_tested']),(1,1,1))
        with self.assertRaises(ValueError):coverage(['p'],['a'],[dict(profile='p',job_id='a',status='COMPLETE')])

    def test_2gb_total_requires_os_headroom(self):
        row=planning_tier(int(1.8*1024**3),controlled_whole_stack=True,cpu_paced_pass=True)
        self.assertEqual(row['tier'],'4GB_PLANNING_CANDIDATE')
        self.assertFalse(row['target_qualified'])
        self.assertFalse(row['deployable'])
        self.assertEqual(planning_tier(1,controlled_whole_stack=False,cpu_paced_pass=True)['tier'],'UNKNOWN')

    def test_pid_reuse_rejected_and_actual_self_sample(self):
        import psutil
        p=psutil.Process()
        self.assertEqual(process_tree(p.pid,p.create_time()-1)['status'],'PID_REUSED')
        row=process_tree(p.pid,p.create_time())
        self.assertEqual(row['status'],'ALIVE')
        self.assertTrue(any(r['pid']==p.pid for r in row['processes']))

    def test_archive_rejects_changed_payload_and_unsafe_paths(self):
        import tempfile,zipfile,json,hashlib
        from pathlib import Path
        digest=hashlib.sha256(b'original').hexdigest()
        for rel,payload in [('valid.json',b'changed'),('../escape.json',b'original')]:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'fixture.zip'
                row=dict(relative_path=rel,sha256=digest,bytes=8,object='objects/'+digest)
                with zipfile.ZipFile(path,'x') as archive:
                    archive.writestr('MANIFEST.json',json.dumps(dict(files=[row])))
                    archive.writestr(row['object'],payload)
                with self.assertRaises(ValueError):verify_archive(path)


if __name__=='__main__':unittest.main(verbosity=2)
