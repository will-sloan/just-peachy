"""Live/archive equivalence and refusal fixtures; README_EVIDENCE.md."""
import copy
import tempfile
import unittest
from pathlib import Path
from common import bind, fingerprint, freeze, load
from evidence_archive import pack
from evidence_reader import ControllerEvidence
from score_controller import convert
from metrics import score_cell


class EvidenceReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'cell'/'attempt'
        self.snapshot = self.root/'FINAL_SNAPSHOT.json'
        self.events = self.root/'RUNTIME_EVENTS.jsonl'
        freeze(self.snapshot, dict(rows=[dict(utterance_id='u',raw_asr_text='one two',
            token_range=[0,2],track_id='track-1')]))
        # JSON is also a one-record JSONL stream when compactly serialized.
        import json
        self.events.write_text(json.dumps(dict(event_type='n2_diarization_frames',
            payload=dict(frame_step_sec=.5,frame_start=0,audio_received_sec=1.,
            probabilities=[[.9],[.8],[.9]],track_ids=['track-1'])))+'\n',encoding='utf-8')
        self.result = dict(status='COMPLETE',checks=dict(saved=True),attempt=str(self.root),
            job_id='fixture_O0',audio=dict(frames=16000),
            evidence=[bind(self.snapshot),bind(self.events)])
        self.result_path = self.root/'RESULT.json'
        freeze(self.result_path,self.result)
        freeze(self.root.parent/'CHECKPOINT.json',dict(status='COMPLETE',result=bind(self.result_path)))
        self.zip_path = Path(self.tmp.name)/'evidence.zip'
        self.receipt = pack(self.result_path,self.zip_path)

    def test_archive_alone_preserves_prediction_and_metrics(self):
        live = convert(self.result)
        truth = dict(job_id='fixture_O0',reference_class='complete_nonoverlap',frames=16000,
            complete_reference=True,turns=[dict(identity='alice',transcript='one two',
            activity_ranges_samples_estimated=[[0,16000]])])
        live_score = score_cell(truth,live)
        # Remove only this test's temporary fixture; campaign sources are never removed.
        self.snapshot.unlink();self.events.unlink()
        archived = convert(self.result,self.receipt['archive'])
        self.assertEqual(live,archived)
        self.assertEqual(live_score,score_cell(truth,archived))
        self.assertEqual(archived['activity_support']['overhang_seconds'],.5)
        self.assertFalse(self.snapshot.exists())
        self.assertFalse(self.events.exists())

    def test_changed_live_evidence_is_rejected(self):
        self.snapshot.write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed'):convert(self.result)

    def test_changed_archive_binding_is_rejected(self):
        with self.zip_path.open('ab') as stream:stream.write(b'changed')
        with self.assertRaisesRegex(ValueError,'binding changed'):
            convert(self.result,self.receipt['archive'])

    def test_other_result_contents_are_rejected(self):
        result=copy.deepcopy(self.result);result['job_id']='another_O0'
        with self.assertRaisesRegex(ValueError,'different result contents'):
            convert(result,self.receipt['archive'])

    def test_outside_and_unbound_paths_are_rejected_in_both_modes(self):
        for binding in (None,self.receipt['archive']):
            with ControllerEvidence(self.result,binding) as reader:
                with self.assertRaisesRegex(ValueError,'escapes'):
                    reader.read_bytes(self.root.parent/'outside.json')
                with self.assertRaisesRegex(ValueError,'not bound'):
                    reader.read_bytes(self.root/'unbound.json')

    def test_duplicate_bindings_are_rejected(self):
        result=copy.deepcopy(self.result);result['evidence'].append(result['evidence'][0])
        with self.assertRaisesRegex(ValueError,'Duplicate'):ControllerEvidence(result)


class ScorerArchiveIndexTests(unittest.TestCase):
    setUp = EvidenceReaderTests.setUp
    def prepare_index(self, *, wrong_result=False):
        from types import SimpleNamespace
        base=Path(self.tmp.name)/'scoring'
        audio=dict(job_id='fixture_O0',audio_path='unused.wav',audio_sha256='a'*64,
            frames=16000,sample_rate_hz=16000,gain=1.,reset_between_scenes=True,tap='O0')
        manifest=base/'AUDIO_ONLY.json';freeze(manifest,dict(jobs=[audio]))
        contract=dict(manifest=bind(manifest));contract_sha=fingerprint(contract)
        result=dict(self.result,audio=audio,cache_key=fingerprint(dict(contract=contract_sha,job=audio)))
        # Only replace owned setup fixtures, before binding or archiving them.
        self.result_path.unlink();freeze(self.result_path,result)
        checkpoint=self.root.parent/'CHECKPOINT.json';checkpoint.unlink()
        freeze(checkpoint,dict(status='COMPLETE',result=bind(self.result_path),cache_key=result['cache_key']))
        receipt=pack(self.result_path,Path(self.tmp.name)/'scorer-evidence.zip')
        freeze(base/'ADMISSION.json',dict(contract=contract,contract_sha256=contract_sha))
        index=base/'RESULT_INDEX.json'
        freeze(index,dict(contract_sha256=contract_sha,completed={'fixture_O0':str(self.result_path)},failed={}))
        truth=base/'TRUTH.json'
        freeze(truth,dict(cells=[dict(job_id='fixture_O0',reference_class='complete_nonoverlap',
            frames=16000,complete_reference=True,turns=[dict(identity='alice',transcript='one two',
            activity_ranges_samples_estimated=[[0,16000]])])]))
        source=dict(receipt['source'])
        if wrong_result:source['bytes']+=1
        archive_index=base/'ARCHIVES.json'
        freeze(archive_index,dict(schema='n4-archive-index-v1',archives={receipt['source']['sha256']:
            dict(execution_result=source,archive=receipt['archive'])}))
        self.snapshot.unlink();self.events.unlink()
        return SimpleNamespace(index=index,manifest=manifest,truth=truth,scope='fixture only',
            archive_index=archive_index,output=base/'scores')

    def test_scoring_main_reads_archive_index_without_extraction(self):
        from score_controller import main
        import contextlib,io
        args=self.prepare_index()
        with contextlib.redirect_stdout(io.StringIO()):main(args)
        result=load(args.output/'SCORES.json')
        self.assertEqual(result['metrics']['primary_nonoverlap_WER'],0.)
        self.assertEqual(len(result['archive_sources']),1)
        self.assertEqual(result['archive_index'],bind(args.archive_index))
        self.assertFalse(self.events.exists())

    def test_wrong_archive_index_execution_is_rejected(self):
        from score_controller import main
        with self.assertRaisesRegex(ValueError,'different execution'):
            main(self.prepare_index(wrong_result=True))


if __name__=='__main__':unittest.main(verbosity=2)
