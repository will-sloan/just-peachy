"""Synthetic contract checks only. See README_SCRIPT_EVIDENCE.md."""
from copy import deepcopy
import hashlib,json
from pathlib import Path
import sys,tempfile,unittest,threading,queue
from unittest.mock import Mock,patch
from types import SimpleNamespace
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'vendor')]
from app.script_evidence import build_evidence,estimated_words,validate,preview,words,stored_size
from app.people import PersonalStore
from app.enrollment_quality import EnrollmentQuality
from app.paths import read_json,sha256,ApplicationLock,atomic_json
from app.controller import Controller
from app.enrollment_progress import ReadProgress,reference_text
from test_people import ROUTE,BACKEND


class Models:
    def segment(self,x,**kw):return dict(speech=np.ones(100),overlap=np.zeros(100))
    def embed(self,x):
        v=np.zeros(192,np.float32);v[0]=1;return v


def fixture(script='please sit by the window please sit by the window'):
    audio=np.full(8*16000,.1,np.float32);models=Models()
    q=EnrollmentQuality(models,SimpleNamespace(minimum_rms=.002),None);q.process(audio)
    quality,base=q.result(source_kind='synthetic_contract')
    row=dict(utterance_id='e0',start_sample=0,end_sample=len(audio),raw_asr_text='please sit by the window please sit by the window',
        token_timing=dict(tokens=['▁'+w for w in words('please sit by the window please sit by the window')],
                          timestamps_sec=[.1,.7,1.3,2.,2.7,4.1,4.7,5.3,6.,6.7],segment_start_sec=0))
    doc=build_evidence(audio,quality,{'utterances':[row]},script,ROUTE,models,{'redimnet2_b2_fp32':BACKEND})
    return quality,base,doc,row


class ScriptTests(unittest.TestCase):
    def test_correct_wrong_skipped_repeated_never_changes_original_quality(self):
        q,v,d,row=fixture();self.assertTrue(d['bank']);self.assertLessEqual(d['retained_unique_sec'],q['usable_s'])
        self.assertTrue(d['base_reference_unchanged']);self.assertEqual(d['coverage']['estimated_fraction'],1)
        self.assertEqual(len(d['bank']),1) # repeated identical context does not count twice
        wrong=fixture('seven unusual purple turtles fly')[2]
        self.assertFalse(wrong['bank']);self.assertEqual(wrong['selection_state'],'unavailable_use_base')
        skipped=fixture('please sit with me by the sunny window')[2]
        self.assertTrue(any(r['operation']!='equal' for r in skipped['agreement_operations']))
        self.assertEqual(q['usable_s'],skipped['base_reference_retained_sec'])

    def test_invalid_timing_is_unknown_not_clamped_or_phone_aligned(self):
        _,_,d,row=fixture()
        for change in ({'segment_start_sec':100},{'timestamps_sec':[float('nan')]*10},{'tokens':['<unk>']*10}):
            r=deepcopy(row);r['token_timing'].update(change);self.assertEqual(estimated_words(r,128000),[])
        self.assertIsNone(d['phone_boundaries']);self.assertIsNone(d['matched_content_score'])
        self.assertTrue(all(w['confidence'] is None and w['phone_boundaries'] is None for w in d['word_spans']))

    def test_finish_padding_keeps_prefix_and_preserves_global_word_indices(self):
        q,v,d,row=fixture();row=deepcopy(row)
        row['token_timing']['timestamps_sec'][-1]=8.2
        mapped=estimated_words(row,128000)
        self.assertEqual([x['recognized_index'] for x in mapped],list(range(8)))
        self.assertTrue(all(x['estimated_end_sample']<=128000 for x in mapped))
        # Next endpoint starts at its real decoder offset; no word-index collapse.
        next_row=dict(utterance_id='e1',raw_asr_text='another phrase',end_sample=128000,
            token_timing=dict(tokens=[' another',' phrase'],timestamps_sec=[.1,.6],segment_start_sec=6.5))
        doc=build_evidence(np.full(128000,.1,np.float32),q,{'utterances':[row,next_row]},
            d['script']['text']+' another phrase',ROUTE,Models(),{'redimnet2_b2_fp32':BACKEND})
        tail=doc['word_spans'][-2:]
        self.assertEqual([x['word_index'] for x in tail],[10,11])
        self.assertTrue(all(x['script_agreement'] for x in tail))
        self.assertEqual(tail[0]['estimated_start_sample'],round(6.6*16000))

    def test_token_snapshot_precedes_endpoint_reset_and_is_optional(self):
        result=SimpleNamespace(tokens=[' hello'],timestamps=[.2],start_time=1.)
        rec=SimpleNamespace(get_result_all=Mock(return_value=result))
        stream=SimpleNamespace(recognizer=rec,stream=object(),accept=Mock(return_value=('hello',True)),
            reset_endpoint=Mock(side_effect=lambda: (setattr(result,'start_time',2.) or 'hello')),finish=Mock(return_value=''))
        read=ReadProgress(stream,'hello',token_timing=True);read.accept(np.zeros(1600,np.float32))
        self.assertEqual(read.finish()['utterances'][0]['token_timing']['segment_start_sec'],1.)
        rec.get_result_all.reset_mock();ReadProgress(stream,'hello').accept(np.zeros(1600,np.float32))
        rec.get_result_all.assert_not_called()

    def test_sidecar_roundtrip_rename_delete_original_and_advisory_parity(self):
        q,v,d,_=fixture();q['script_evidence']=d
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);store=PersonalStore(root/'a'/'people',BACKEND)
            row=store.save('Casey',v,q,ROUTE);ref=row['references'][0]
            anchor=store.root/row['id']/ref['vector'];before=sha256(anchor)
            plain=store.gallery(ROUTE);alt=store.gallery(ROUTE,alternate_advisory=True)
            self.assertEqual(plain.score(v),alt.score(v));self.assertTrue(alt.last_alternate['advisory_only'])
            self.assertEqual(alt.last_alternate['candidates'][0]['alternate'],1.)
            alt.alternate_enabled=False;self.assertEqual(plain.score(v),alt.score(v))
            store.rename(row['id'],'New name');self.assertEqual(before,sha256(anchor))
            export=root/'people.zip';store.export(export,True)
            imported=PersonalStore(root/'b'/'people',BACKEND);imported.import_archive(export,True)
            self.assertEqual(imported.list()[0]['id'],row['id']);self.assertEqual(imported.list()[0]['name'],'New name')
            self.assertEqual(read_json(root/'b'/'DATA_SCHEMA.json')['required_features'],['script-evidence-v1'])
            self.assertEqual(before,sha256(imported.root/row['id']/ref['vector']))
            imported.delete(row['id']);self.assertEqual(imported.list(),[])
            with self.assertRaises(ValueError):store.gallery(dict(ROUTE,tap='O1'),[row['id']],alternate_advisory=True)

    def test_sidecar_tamper_overlap_and_wrong_binding_refused(self):
        q,v,d,_=fixture()
        ref=dict(id='fixture',sha256='a'*64,source_sha256=q['source_sha256'],route=ROUTE)
        d.update(reference_id='fixture',anchor_file_sha256=ref['sha256'])
        validate(d,ref,BACKEND)
        for change in ({'reference_id':'another'},{'phone_boundaries':[]},{'advisory_only':False},{'bank':d['bank']*2}):
            doc=deepcopy(d);doc.update(change)
            with self.assertRaises(ValueError):validate(doc,ref,BACKEND)
        p=preview(d);self.assertNotIn('alternate_vector',p);self.assertNotIn('vector',p['bank'][0])
        bad=deepcopy(d);bad['alternate_vector']=[0.,1.]+[0.]*190
        with self.assertRaisesRegex(ValueError,'aggregate'):validate(bad,ref,BACKEND)

    def test_feature_guard_and_actual_storage_bound(self):
        q,v,d,_=fixture()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);data=root/'data';data.mkdir();fake_app=root/'old_app';(fake_app/'config').mkdir(parents=True)
            atomic_json(fake_app/'config/release_capabilities.json',dict(data_features_supported=['paragraph-enrollment-v1']))
            atomic_json(data/'DATA_SCHEMA.json',dict(schema_version=1,required_features=['script-evidence-v1']))
            with patch('app.paths.ROOT',fake_app),self.assertRaisesRegex(ValueError,'features'):ApplicationLock(data)
            self.assertFalse((data/'runtime.lock').exists())
            owner=ApplicationLock(data);owner.close()
            path=data/'sample.json';atomic_json(path,d);self.assertEqual(path.stat().st_size,stored_size(d))
        with patch('app.script_evidence.MAX_BYTES',100):
            with self.assertRaisesRegex(ValueError,'bounded storage'):fixture()

    def test_o1_bank_works_only_with_its_own_compatible_route(self):
        q,v,d,_=fixture();o1=dict(ROUTE,tap='O1');d['source']['route']=o1;q['script_evidence']=d
        with tempfile.TemporaryDirectory() as td:
            store=PersonalStore(Path(td)/'people',BACKEND);person=store.save('O1 fixture',v,q,o1)
            gallery=store.gallery(o1,alternate_advisory=True);gallery.score(v)
            self.assertEqual(gallery.ids,[person['id']]);self.assertEqual(gallery.last_alternate['candidates'][0]['alternate'],1.)
            with self.assertRaises(ValueError):store.gallery(ROUTE,alternate_advisory=True)

    def test_low_level_overlap_short_and_no_common_text_use_original(self):
        q,v,d,row=fixture()
        audio=np.full(128000,.1,np.float32)
        for quality in (dict(q,can_save=False),dict(q,accepted_intervals=[[0,.5]],usable_s=.5)):
            doc=build_evidence(audio,quality,{'utterances':[row]},d['script']['text'],ROUTE,Models(),{'redimnet2_b2_fp32':BACKEND})
            self.assertIsNone(doc['alternate_vector'])
        q['gaps']=1;q['can_save']=False
        self.assertFalse(build_evidence(audio,q,{'utterances':[row]},d['script']['text'],ROUTE,Models(),{'redimnet2_b2_fp32':BACKEND})['bank'])

    def test_controller_stop_review_note_save_and_optional_failure_fallback(self):
        for fail in (False,True):
            with self.subTest(helper_failure=fail),tempfile.TemporaryDirectory() as td:
                q,v,d,row=fixture();c=Controller.__new__(Controller)
                c.config=SimpleNamespace(minimum_rms=.002,assets=[SimpleNamespace(component_id='redimnet2_b2_fp32',sha256=BACKEND)])
                c.models=SimpleNamespace(speakers=Models());c._enroll_stop=threading.Event()
                c._quality=EnrollmentQuality(c.models.speakers,c.config,None)
                c._enroll_thread=c._quality_thread=c._enroll_live=None;c._enroll_integrity={'ok':True}
                c._enroll_route=dict(ROUTE,source_session_id='contract-fixture');c._enroll_script_enabled=True
                c._enroll_audio=[];c._enroll_read=None;c._script_bank=None;c._observe_output=Mock();c._enroll_enhancer=None
                c._quality_queue=queue.Queue();c._quality_queue.put((0,np.full(128000,.1,np.float32)));c._quality_queue.put(None)
                c.enrollment=dict(state='RECORDING',name='Test',gaps=0,offered_reference=reference_text(d['script']['text']),script_estimate={'utterances':[row]})
                c.store=PersonalStore(Path(td)/'people',BACKEND);c.metrics={}
                c._quality_loop();self.assertEqual(len(c._enroll_audio),1)
                if fail:
                    with patch('app.script_evidence.build_evidence',side_effect=RuntimeError('injected optional failure')):c._do_enrollment_stop()
                    self.assertEqual(c.enrollment['script_evidence']['selection_state'],'unavailable_use_base')
                else:
                    c._do_enrollment_stop();self.assertTrue(c._script_bank['bank'])
                    raw=c._script_bank['transcript']['raw_asr_text'];c._do_enrollment_script_note('Actually said sunny window')
                    self.assertEqual(c._script_bank['transcript']['raw_asr_text'],raw)
                self.assertEqual(c._enroll_audio,[]);self.assertTrue(c.enrollment['can_save'])
                np.testing.assert_array_equal(c._enroll_vector,v)
                c._do_enrollment_save();self.assertIsNone(c._script_bank);self.assertEqual(c.enrollment['state'],'SAVED')
                ref=c.store.list()[0]['references'][0];self.assertEqual('script_evidence' in ref,not fail)
                c._do_script_review(c.enrollment['person_id'])
                if not fail:self.assertEqual(c.metrics['stored_script_review']['document']['user_corrections'][0]['revision'],1)
                with self.assertRaises(ValueError):c._do_script_review('deleted-uuid')
                self.assertNotIn('stored_script_review',c.metrics)


if __name__=='__main__':unittest.main()
