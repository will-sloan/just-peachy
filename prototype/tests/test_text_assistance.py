"""Task07 text safety/provenance tests; see README_TEXT_ASSISTANCE.md."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent),str(ROOT),str(ROOT/'vendor')]
from app.text_assistance import TextAssistance, corrected_partition
from app.sessions import SessionStore,records
from edge_speech_pipeline.contracts import PipelineEvent

PEOPLE=[{'id':'amir-id','name':'Amir'}]


class TextAssistanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.a=TextAssistance(self.root/'vocab.json')
    def enable(self,automatic=False):self.a.change('switch',dict(enabled=True,automatic=automatic),PEOPLE)
    def rule(self,**kw):
        self.a.change('add',dict(preferred='Amir',alias='emir',context='Peachy',kind='name',person_id='amir-id',
                                 approved=True,approved_auto=True,**kw),PEOPLE)
    def test_off_baseline_and_generic_review_without_auto(self):
        self.assertIsNone(self.a.analyze('camptions',PEOPLE)['corrected_text'])
        self.enable(True);r=self.a.analyze('camptions',PEOPLE)
        self.assertEqual(r['suggestions'][0]['after'],'captions');self.assertIsNone(r['corrected_text'])
        self.assertEqual(self.a.analyze('captions',PEOPLE)['suggestions'],[])
    def test_invalid_optional_vocabulary_keeps_baseline_and_file_intact(self):
        self.a.path.write_bytes(b'invalid fixture JSON')
        bad=TextAssistance(self.a.path)
        self.assertTrue(bad.snapshot(PEOPLE)['error']);self.assertIsNone(bad.analyze('captions',PEOPLE)['corrected_text'])
        with self.assertRaises(ValueError):bad.change('switch',{'enabled':True},PEOPLE)
        self.assertEqual(self.a.path.read_bytes(),b'invalid fixture JSON')
    def test_context_authorized_name_preserves_punctuation_and_original(self):
        self.enable(True);self.rule();r=self.a.analyze('EMIR joined Peachy.',PEOPLE)
        self.assertEqual(r['corrected_text'],'Amir joined Peachy.');self.assertEqual(r['input_text'],'EMIR joined Peachy.')
        self.assertIsNone(self.a.analyze('Emir joined yesterday.',PEOPLE)['corrected_text'])
        self.assertIsNone(self.a.analyze('Peachy emirates.',PEOPLE)['corrected_text'])
        self.assertIsNone(self.a.analyze('Peachy emir-like.',PEOPLE)['corrected_text'])
    def test_ambiguous_real_emir_and_title_remain_review(self):
        self.enable(True);self.rule()
        r=self.a.analyze('Emir joined Peachy.',PEOPLE+[{'id':'emir-id','name':'Emir Noor'}])
        self.assertIsNone(r['corrected_text']);self.assertTrue(r['suggestions'])
        self.assertIsNone(self.a.analyze('The emir spoke.',PEOPLE)['corrected_text'])
    def test_protected_negation_numerals_pronouns_safety_never_auto(self):
        self.enable(True);self.rule()
        for text in ('Emir did not join Peachy.','Emir took 2 tablets at Peachy.','He called Emir at Peachy.',
                     'Emir needs insulin at Peachy.','Emir said never at Peachy.',"Emir can't join Peachy."):
            with self.subTest(text=text):self.assertIsNone(self.a.analyze(text,PEOPLE)['corrected_text'])
        for alias,preferred in (("I'm","We're"),("doesn't","does")):
            self.a.change('add',dict(preferred=preferred,alias=alias,context='Peachy',approved=True,approved_auto=True),PEOPLE)
            self.assertIsNone(self.a.analyze(alias+' near Peachy.',PEOPLE)['corrected_text'])
    def test_disable_rename_delete_and_restart(self):
        self.enable(True);self.rule();before=self.a.config.copy()
        for people in ([],[{'id':'amir-id','name':'Ameer'}]):
            self.assertFalse(self.a.snapshot(people)['entries'][0]['active'])
            self.assertIsNone(self.a.analyze('Emir joined Peachy.',people)['corrected_text'])
        self.a.change('switch',{'enabled':False},PEOPLE)
        restarted=TextAssistance(self.a.path);self.assertEqual(len(restarted.config['entries']),1)
        self.assertIsNone(restarted.analyze('Emir joined Peachy.',PEOPLE)['corrected_text'])
    def test_no_approval_no_context_and_conflict_never_silently_choose(self):
        with self.assertRaises(ValueError):self.a.change('add',dict(preferred='Amir'),PEOPLE)
        with self.assertRaises(ValueError):self.a.change('add',dict(preferred='Amir',alias='Emir',context='',approved=True,approved_auto=True),PEOPLE)
        self.enable(True);self.rule()
        self.a.change('add',dict(preferred='Ameer',alias='emir',context='Peachy',approved=True,approved_auto=True),PEOPLE)
        r=self.a.analyze('Emir joined Peachy.',PEOPLE);self.assertIsNone(r['corrected_text'])
        self.assertTrue(all('conflicting' in x['reason'] for x in r['suggestions']))
    def test_bounded_long_input_and_speaker_partition(self):
        self.enable();self.assertEqual(self.a.analyze('word '*129,PEOPLE)['status'],'text_limit; unchanged')
        self.assertEqual(corrected_partition('Emir spoke then Jane','Amir spoke then Jane',(0,2)),'Amir spoke ')
        self.assertIsNone(corrected_partition('Emir spoke','Amir Noor spoke',(0,1)))
        self.assertFalse(self.a.snapshot(PEOPLE)['bias_available'])
    def test_formatted_log_source_links_recovery_manual_undo_and_export(self):
        self.enable(True);self.rule();store=SessionStore(self.root,dict(free_floor_mib=0));identifier=store.new()
        archive=store.begin(identifier,dict(features={},pipeline_input_gain=1.))
        row={'caption_key':'epoch/u1','utterance_id':'u1','text_revision_id':'r1','text':'EMIR JOINED PEACHY',
             'display_text':'Emir joined Peachy.','final':True,'punctuation_for_text_revision':'r1','source_start_sec':0.,'source_end_sec':1.}
        archive.event(PipelineEvent('s6d_display',1.,dict(row)))
        row['text_assistance']=self.a.analyze(row['display_text'],PEOPLE)
        row['text_assistance']['source']={'caption_key':'epoch/u1','start_sample':0,'end_sample':16000}
        archive.formatted(row,[]);store.ended(identifier,archive)
        journal=(archive.path/'events.jsonl').read_bytes();original=store.rows(identifier)
        self.assertEqual(original[0]['text'],'EMIR JOINED PEACHY')
        self.assertEqual(original[0]['text_assistance']['corrected_text'],'Amir joined Peachy.')
        (archive.path/'captions.sqlite').unlink();self.assertEqual(store.rows(identifier),original)
        store.annotate(identifier,'',row_id='epoch/u1',correction='Emir stayed home.')
        edit=store.metadata(identifier)['corrections'][0]
        self.assertEqual(edit['source']['start_sample'],0);self.assertEqual(store.rows(identifier),original)
        store.undo_correction(identifier,edit['id']);self.assertEqual(len(store.metadata(identifier)['corrections']),2)
        self.assertEqual((archive.path/'events.jsonl').read_bytes(),journal)
        with self.assertRaises(ValueError):store.undo_correction(identifier,edit['id'])
        out=self.root/'export.zip';store.export(identifier,out,consent=True)
        with zipfile.ZipFile(out) as z:
            text=json.loads(z.read('transcript.jsonl'));annotations=json.loads(z.read('user_annotations.json'))
        self.assertEqual(text['raw_asr'],'EMIR JOINED PEACHY');self.assertEqual(len(annotations['corrections']),2)


if __name__=='__main__':unittest.main()
