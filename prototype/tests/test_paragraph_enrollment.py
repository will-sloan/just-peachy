"""Task 06 deterministic contracts; no microphone. See README_ENROLLMENT.md."""
import hashlib
from pathlib import Path
import queue
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from app.controller import Controller
from app.enrollment_quality import EnrollmentQuality
from app.enrollment_progress import ReadProgress, VerifiedAnimation, agreement, reference_text
from app.people import PersonalStore
from tests.test_people import ROUTE, BACKEND
from tests.test_enrollment_cleanup import FakeLive


class Models:
    def __init__(self, speech=1., overlap=0.):
        self.speech=speech;self.overlap=overlap;self.calls=0
    def segment(self,x,**kwargs):
        return {'speech':np.full(100,self.speech), 'overlap':np.full(100,self.overlap)}
    def embed(self,x):
        self.calls+=1
        v=np.arange(192,dtype=np.float32)+1
        return v/np.linalg.norm(v)


class ParagraphTests(unittest.TestCase):
    def quality(self,audio=None,target=None,models=None):
        q=EnrollmentQuality(models or Models(),SimpleNamespace(minimum_rms=.002),target)
        q.process(np.full(16000,.1,np.float32) if audio is None else audio)
        return q

    def test_done_short_valid_and_timed_share_exact_math(self):
        done=self.quality();timed=self.quality(target=15)
        a,v=done.result();b,w=timed.result()
        self.assertTrue(a['can_save']);self.assertFalse(b['can_save'])
        self.assertEqual(a['evidence_status'],'limited_short_reference')
        self.assertEqual(a['accepted_intervals'],b['accepted_intervals'])
        np.testing.assert_array_equal(v,w)

    def test_quality_rejects_short_silent_clipped_overlap_or_corrupt(self):
        for audio,m in [(np.full(7999,.1,np.float32),Models()),(np.zeros(16000,np.float32),Models()),
                        (np.ones(16000,np.float32),Models()),(np.full(16000,.1,np.float32),Models(overlap=1.))]:
            self.assertFalse(self.quality(audio,models=m).result()[0]['can_save'])
        with self.assertRaises(ValueError):self.quality(np.full(8000,np.nan,np.float32))
        self.assertFalse(self.quality().result(gaps=1)[0]['can_save'])

    def test_duplicate_source_support_never_counts_or_infers_again(self):
        q=self.quality();audio=np.full(16000,.1,np.float32)
        before=q.result()[0]
        self.assertFalse(q.process(audio,source_start=0))
        self.assertEqual(q.result()[0],before)
        with self.assertRaises(ValueError):q.process(audio,source_start=8000)
        with self.assertRaises(ValueError):q.process(audio*2,source_start=0)
        with self.assertRaises(ValueError):q.process(audio,source_start=32000)

    def test_incremental_progress_is_real_and_animation_cannot_extrapolate(self):
        q=EnrollmentQuality(Models(),SimpleNamespace(minimum_rms=.002),None);rows=[]
        q.process(np.full(16000,.1,np.float32),publish=rows.append)
        self.assertEqual([r['usable_s'] for r in rows],[.5,1.,1.])
        animation=VerifiedAnimation();animation.update(0,0)
        values=[animation.update(1.,t/10) for t in range(1,11)]
        self.assertTrue(0<values[0]<1);self.assertEqual(values,sorted(values))
        self.assertEqual(animation.update(1.,100),1.)
        self.assertEqual(animation.update(0.,101),0.)
        self.assertEqual(q.model_embedding_calls,2)

    def test_skips_empty_reference_and_paraphrases_are_estimates_only(self):
        score=agreement('Please sit with me by the window','please sit by the window')
        self.assertGreater(score['estimated_coverage'],0)
        self.assertLess(score['estimated_coverage'],1)
        self.assertFalse(score['affects_voice_quality'])
        self.assertIsNone(agreement('','free speech')['estimated_coverage'])
        self.assertEqual(reference_text('Alex')['sha256'],hashlib.sha256(b'Alex').hexdigest())

    def test_asr_endpoint_ids_and_final_drain_do_not_duplicate_text(self):
        stream=SimpleNamespace(accept=Mock(return_value=('hello',True)),reset_endpoint=Mock(return_value='hello'),finish=Mock(return_value='world'))
        reader=ReadProgress(stream,'hello skipped world');reader.accept(np.zeros(1600,np.float32))
        row=reader.finish();self.assertEqual(reader.finish(),row)
        self.assertEqual([x['raw_asr_text'] for x in row['utterances']],['hello','world'])
        self.assertEqual(row['estimated_coverage'],2/3);stream.finish.assert_called_once()
        with self.assertRaises(ValueError):reader.accept(np.zeros(1))

    def test_paragraph_persistence_export_import_tap_mismatch_and_duplicate(self):
        q,v=self.quality().result();q['offered_reference']=reference_text('Please skip words if needed')
        q['script_estimate']=agreement(q['offered_reference']['offered_text'],'different speech')
        with tempfile.TemporaryDirectory() as temp:
            store=PersonalStore(Path(temp)/'people',BACKEND);person=store.save('Fixture',v,q,ROUTE)
            again=PersonalStore(store.root,BACKEND);row=again.list()[0]
            self.assertEqual(row['id'],person['id']);self.assertIsNone(row['references'][0]['target_sec'])
            self.assertEqual(row['references'][0]['source_provenance']['offered_reference'],q['offered_reference'])
            with self.assertRaises(ValueError):again.gallery(dict(ROUTE,tap='O1'))
            with self.assertRaises(ValueError):again.save('Fixture',v,q,ROUTE,person_id=person['id'])
            archive=Path(temp)/'export.zip';again.export(archive,True)
            imported=PersonalStore(Path(temp)/'imported',BACKEND);imported.import_archive(archive,True)
            self.assertEqual(imported.gallery(ROUTE).ids,[person['id']])

    def test_stop_reports_drain_analysis_and_keeps_save_disabled_until_ready(self):
        c=Controller.__new__(Controller);c._quality=self.quality();c._enroll_stop=threading.Event()
        c.enrollment={'state':'RECORDING','gaps':0,'can_save':False};c._enroll_live=None
        c._enroll_route={'source_session_id':'fixture'};c._enroll_integrity={'ok':True};c._observe_output=Mock()
        def capture_join(_):self.assertEqual(c.enrollment['state'],'DRAINING');self.assertFalse(c.enrollment['can_save'])
        def quality_join(_):self.assertEqual(c.enrollment['state'],'ANALYZING');self.assertFalse(c.enrollment['can_save'])
        c._enroll_thread=SimpleNamespace(join=capture_join,is_alive=lambda:False)
        c._quality_thread=SimpleNamespace(join=quality_join,is_alive=lambda:False)
        c._do_enrollment_stop();self.assertEqual(c.enrollment['state'],'READY');self.assertTrue(c.enrollment['can_save'])

    def test_quality_worker_asr_failure_does_not_change_voice_quality(self):
        c=Controller.__new__(Controller);c.enrollment={};c._quality=EnrollmentQuality(Models(),SimpleNamespace(minimum_rms=.002),None)
        c._enroll_read=SimpleNamespace(accept=Mock(side_effect=RuntimeError('ASR fixture error')))
        c._quality_queue=queue.Queue();c._quality_queue.put((0,np.full(16000,.1,np.float32)));c._quality_queue.put(None)
        c._quality_loop()
        self.assertTrue(c._quality.result()[0]['can_save']);self.assertEqual(c.enrollment['script_estimate']['state'],'unavailable')
        self.assertNotIn('gaps',c.enrollment);self.assertEqual(c._quality_queue.unfinished_tasks,0)

    def test_capture_and_worker_preserve_unique_offsets_and_release_source(self):
        for repeated in (False,True):
            c=Controller.__new__(Controller);c._enroll_stop=threading.Event();c.enrollment={'gaps':0}
            c.config=SimpleNamespace(minimum_rms=.002);c._enroll_live=FakeLive();c._enroll_read=None
            c._quality_queue=queue.Queue(20);c._quality=EnrollmentQuality(Models(),c.config,None)
            c._enqueue=Mock();c.error=None
            rows=iter([SimpleNamespace(audio=np.full(16000,.1,np.float32),model_start_sample=x) for x in (0,0 if repeated else 16000)])
            def read(_):
                try:return next(rows)
                except StopIteration:c._enroll_stop.set();return None
            c._enroll_live.read=read
            c._record_enrollment();c._quality_loop()
            self.assertTrue(c._enroll_live.finished)
            self.assertEqual(c.enrollment['usable_s'],1. if repeated else 2.)
            self.assertEqual(c.enrollment['gaps'],1 if repeated else 0)
            self.assertEqual(c._quality_queue.unfinished_tasks,0)

    def test_timed_storage_omits_offered_script_and_legacy_metadata_loads(self):
        from tests.test_people import quality
        q=quality();q['offered_reference']=reference_text('Timed guide is not saved')
        with tempfile.TemporaryDirectory() as temp:
            store=PersonalStore(Path(temp)/'people',BACKEND)
            row=store.save('Timed fixture',np.ones(192,np.float32),q,ROUTE)
            self.assertNotIn('offered_reference',row['references'][0]['source_provenance'])
            self.assertEqual(PersonalStore(store.root,BACKEND).list()[0]['id'],row['id'])


if __name__=='__main__':unittest.main()
