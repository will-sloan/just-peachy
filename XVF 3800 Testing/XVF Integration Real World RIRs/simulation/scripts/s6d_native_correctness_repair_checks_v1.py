"""Narrow scorer repair fixtures; README_S6D_NATIVE_CORRECTNESS_REPAIR_CHECKS_V1.md."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
import wave
import s6d_native_correctness_v1 as S
import s6d_native_correctness_checks_v1 as F
import s6d_native_evidence_checks_v1 as G


def put(path, value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
    return S.E.binding(path)


def admitted():
    job=dict(expected_frames=16000,audio_duration_sec=1.,audio_pcm_sha256='a'*64,
             expected_identity_frames=16000,audio=dict(path='SYNTHETIC.wav',bytes=32044,sha256='b'*64))
    audit=dict(source=S.E.binding(S.E.__file__),journals=dict(
        source=dict(source=job['audio'],frames=16000,bytes=32000,sha256='a'*64),
        asr=dict(bytes=32000,sha256='a'*64),identity=dict(bytes=32000,sha256='a'*64)))
    return deepcopy((job,audit))


def pair():
    first=dict(utterance_id='u',source_start_sec=0.,source_end_sec=1.,publication_sec=.2,consumption_sec=.3,raw_text='hello')
    left=dict(first=[first],normalized='hello world',finals={'u':'hello world'},final_spans={'u':[0.,2.]})
    right=deepcopy(left);right['first'][0]['publication_sec']=.4
    return left,right


class Checks(unittest.TestCase):
    def test_required_predeclarations_reject_missing_bool_nonfinite_and_nonhex(self):
        for field,value in [('expected_frames',None),('expected_frames',True),('expected_frames',float('nan')),
                            ('audio_pcm_sha256',None),('audio_pcm_sha256','z'*64),('expected_identity_frames',True)]:
            job,audit=admitted();job[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):S.admit_full_source(job,audit)

    def test_audited_pcm_or_source_binding_mismatch_rejected(self):
        for lane,field,value in [('source','frames',15999),('source','bytes',31998),('source','sha256','c'*64),
                                 ('source','source',{}),('asr','sha256','c'*64),('identity','bytes',31998)]:
            job,audit=admitted();audit['journals'][lane][field]=value
            with self.subTest(lane=lane,field=field),self.assertRaises(ValueError):S.admit_full_source(job,audit)

    def test_wrong_audit_source_rejected_valid_source_accepted(self):
        job,audit=admitted();S.admit_full_source(job,audit)
        audit['source']['sha256']='b'*64
        with self.assertRaises(ValueError):S.admit_full_source(job,audit)

    def test_final_endpoint_change_is_retained_but_not_timing_benefit(self):
        left,right=pair();right['final_spans']['u'][1]=2.5
        out=S.compare_pair(left,right);q=out['additional_first_text_delay']['publication_right_minus_left_sec']
        self.assertEqual((q['observed'],q['all_row_opportunities'],q['unmatched_or_incompatible']),(0,1,1))
        self.assertIsNone(q['p95']);self.assertFalse(out['final_source_spans_equal'])

    def test_equal_normalized_but_different_exact_raw_final_excluded(self):
        left,right=pair();right['finals']['u']='Hello world.'
        out=S.compare_pair(left,right)
        self.assertTrue(out['entire_normalized_words_equal']);self.assertEqual(len(out['utterance_raw_differences']),1)
        self.assertIsNone(out['first_text_pairs'][0]['consumer_right_minus_left_sec'])

    def test_first_hypothesis_change_and_missing_endpoint_excluded(self):
        for field,value in [('raw_text','hello world'),('source_end_sec',None)]:
            left,right=pair();right['first'][0][field]=value;out=S.compare_pair(left,right)
            self.assertFalse(out['first_text_pairs'][0]['timing_comparable'])
            self.assertIsNone(out['additional_first_text_delay']['publication_right_minus_left_sec']['p99'])
            self.assertEqual(out['first_text_pairs'][0]['right_first_row'][field],value)

    def test_equivalent_pair_positive_control(self):
        left,right=pair();out=S.compare_pair(left,right)
        self.assertTrue(out['raw_output_timing_gate']);self.assertTrue(out['first_text_pairs'][0]['timing_comparable'])
        self.assertAlmostEqual(out['additional_first_text_delay']['publication_right_minus_left_sec']['p95'],.2)

    def test_impossible_clock_keeps_every_opportunity_and_null_summary(self):
        events=[F.event('source_started',0),F.event('s6d_text_ready',-10,dict(utterance_id='u',text='hello',source_start_sec=0.,source_end_sec=1.),delay=10.2),F.event('session_completed',5)]
        out=S.name_metrics(F.reference(),events,F.gallery(),True,D)
        self.assertEqual(out['status'],'UNAVAILABLE_ACTUAL_CLOCK');self.assertEqual(len(out['opportunities']),2)
        for metric,summary in out['wait_summaries'].items():
            self.assertEqual((summary['total'],summary['observed'],summary['unavailable']),(2,0,2))
            self.assertIsNone(summary['p95'])
        clock,_=S.clocks([F.event('session_created',-1),F.event('source_started',0),F.event('session_completed',5)])
        self.assertTrue(clock['valid'])

    def test_valid_declared_tiny_source_reaches_closed_synthetic_index(self):
        d=OUT/'valid_synthetic_only';d.mkdir();o=d/'job';session=o/'sessions'/'synthetic';session.mkdir(parents=True)
        audio=d/'zero.wav';pcm=bytes(32000)
        with wave.open(str(audio),'wb') as f:f.setparams((1,2,16000,0,'NONE',''));f.writeframes(pcm)
        result,job,final,proofs,closure=G.good()
        job.update(job_id='SYNTHETIC_ONLY',audio=S.E.binding(audio),audio_pcm_sha256=hashlib.sha256(pcm).hexdigest(),
                   expected_identity_frames=16000,output=str(o),settings=None,gallery=None)
        mb=put(d/'MANIFEST.json',dict(fixture_only=True,jobs=[job],helper=S.E.binding(__file__)))
        result.update(job=job,manifest=mb,helper=S.E.binding(__file__),session_dir=str(session),fixture_only=True)
        rb=put(o/'RESULT.json',result);put(session/'session_finalization_v3.json',final)
        (session/'audio_spool.pcm16').write_bytes(pcm);(session/'identity_audio_spool.pcm16').write_bytes(pcm)
        rows=G.dispatch();rows.insert(3,dict(event_type='transcript_final',payload=F.final('hello',end=1)))
        for i,row in enumerate(rows):
            row['payload']['pilot_publication_monotonic_sec']=100+i/2;row['actual_consumed_monotonic_sec']=100+i/2+.01
        ep=o/'consumer_events.jsonl';ep.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
        latest=session/'latest_labelled_transcript.jsonl';latest.write_text(json.dumps(F.final('hello',end=1))+'\n',encoding='utf-8')
        audit=S.E.audit(mb['path'],mb['sha256'],job['job_id']);self.assertEqual(audit['status'],'PASS_OFFLINE_EVIDENCE');ab=put(d/'AUDIT.json',audit)
        ref=F.reference();ref['pieces']=ref['pieces'][:1];p=ref['pieces'][0];p.update(samples=16000,end_sample=16000)
        p['mapped_turns'][0].update(transcript='hello',normalized_text='hello',file_support=[[0,16000]],active_ranges=[[0,16000]],sole=[[0,16000]])
        ref.update(composition_frames=16000,occurrence_count=1,input_audio=job['audio'],projected_turns=S.E.shift_reference_pieces(ref['pieces'],16000))
        refb=put(d/'REFERENCE.json',ref);gallery=put(d/'NONE_GALLERY.json',dict(gallery_condition='NONE',manifest=None,profiles=[],available_identities=[],intended_identities=[]))
        spec=dict(schema='s6d-native-scoring-inputs.v1',status='APPROVED_CLOSED_NATIVE_INPUTS',fixture_only=True,
                  owner_exit_verified=True,source_graph_verified=True,scorer=S.E.binding(S.__file__),dependencies=D['sources'],
                  gallery_map=S.E.binding(S.HERE.parent/'reports/S6C/20260910T123540Z/enrollment/SCORER_GALLERY_MAP.json'),
                  execution_manifests=[mb],unavailable_jobs=[],output_root=str(d/'SYNTHETIC_SCORES'),jobs=[dict(job_id=job['job_id'],manifest=mb,result=rb,
                  completion_audit=ab,reference=refb,consumer_events=S.E.binding(ep),latest=S.E.binding(latest),gallery_row=gallery)])
        sb=put(d/'SYNTHETIC_ACCEPTANCE.json',spec);S.run(sb['path'],sb['sha256'])
        index=json.loads((d/'SYNTHETIC_SCORES'/'INDEX.json').read_text());self.assertEqual((index['declared_jobs'],index['scored_jobs']),(1,1))
        self.assertEqual(json.loads(Path(index['rows'][0]['score']['path']).read_text())['text']['serialized_words']['counts']['errors'],0)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    OUT=a.output.resolve()
    if OUT.drive.upper()!='G:':raise ValueError('All fresh outputs must stay on G')
    OUT.mkdir(parents=True,exist_ok=False);D=S.dependencies()
    with (OUT/'TESTS.log').open('x',encoding='utf-8') as log:r=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    receipt=dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),
                 scorer=S.E.binding(S.__file__),fixture=S.E.binding(__file__),dependencies=D['sources'],log=S.E.binding(OUT/'TESTS.log'),
                 actual_native_outputs_scored=0,synthetic_sources=1,models=0,policy_replays=0,devices=0,ui_calls=0)
    put(OUT/'RECEIPT.json',receipt);print(json.dumps(receipt));raise SystemExit(not r.wasSuccessful())
