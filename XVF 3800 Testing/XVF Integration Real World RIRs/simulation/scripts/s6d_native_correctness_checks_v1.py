"""Tiny actual scoring API fixtures; README_S6D_NATIVE_CORRECTNESS_V1.md."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import unittest
import s6d_native_correctness_v1 as S


def reference(incomplete=False):
    pieces=[]
    for i,(person,text) in enumerate([('a','hello world'),('b','good morning')]):
        turn=dict(segment_index=0,source_id='source'+person,metadata_identity=person,transcript=text,
                  normalized_text=text,file_support=[[0,32000]],active_ranges=[[0,32000]],sole=[[0,32000]],activity_available=True)
        pieces.append(dict(index=i,case_id='case'+str(i),start_sample=i*48000,end_sample=i*48000+32000,
                samples=32000,gap_before_samples=16000 if i else 0,all_reference_complete=not(incomplete and i==1),
                transcript_valid=True,task_scoring_allowed=True,support_mapping=dict(source_with_rir_to_output_offset_samples=0),mapped_turns=[turn]))
    return dict(schema='s6d-host-reference-input-plan.v1',pieces=pieces,composition_frames=80000,occurrence_count=2,
                projected_turns=S.E.shift_reference_pieces(pieces,80000))


def final(text='hello world',uid='u',start=0.,end=2.,label='Speaker_1'):
    return dict(utterance_id=uid,text=text,is_final=True,source_start_sec=start,source_end_sec=end,
                latest_anonymous_label=label,latest_label=label,latest_known_profile_id=None,latest_known_name=None)


def gallery():
    return dict(gallery_condition='FIXED_ROTATION_A',available_identities=['a'],intended_identities=['a'],
                profiles=[dict(profile_id='pa',display_name='Alice',metadata_identity='a'),
                          dict(profile_id='px',display_name='Xavier',metadata_identity='x')])


def event(kind,now,p=None,delay=.01):
    payload=dict(p or {},pilot_publication_monotonic_sec=100+now)
    return dict(event_type=kind,payload=payload,actual_consumed_monotonic_sec=100+now+delay)


def display(now,pid='pa',label='Alice',uid='u',start=0.,end=1.,visible=True):
    return event('s6d_display',now,dict(utterance_id=uid,text='hello',display_text='Hello',known_profile_id=pid,
                 label=label,naming_state='confirmed',source_start_sec=start,source_end_sec=end,visible=visible))


class Checks(unittest.TestCase):
    def test_pinned_word_and_cp_counts(self):
        rows=[final('hello earth'),final('good morning','v',3,5,'Speaker_2')]
        score=S.text_metrics(reference(),rows,D)
        self.assertEqual(score['serialized_words']['counts']['substitutions'],1)
        self.assertEqual(score['anonymous_cpwer']['word_counts']['errors'],1)
        self.assertEqual(score['serialized_words']['counts']['reference_words'],4)
    def test_empty_hypothesis_is_deletion_not_success(self):
        out=S.text_metrics(reference(),[],D)
        self.assertEqual(out['serialized_words']['counts']['deletions'],4)
        self.assertEqual(out['anonymous_cpwer']['word_counts']['deletions'],4)
    def test_cross_piece_hypothesis_never_split(self):
        out=S.text_metrics(reference(),[final('hello world good morning',end=5)],D)
        self.assertEqual(out['excluded_hypothesis_rows'][0]['reason'],'CROSS_PIECE_OR_GAP_SPAN')
        self.assertEqual(out['serialized_words']['counts']['deletions'],4)
        self.assertEqual(out['excluded_hypothesis_word_count'],4)
    def test_incomplete_reference_population_retained(self):
        out=S.text_metrics(reference(True),[final(),final('unobserved competitor','v',3,5)],D)
        self.assertEqual(out['all_reference_occurrences'],2)
        self.assertEqual(out['reference_occurrences'],1)
        self.assertEqual(out['full_session_all_speaker_wer_status'],'UNAVAILABLE_INCOMPLETE_OR_UNMAPPED_REFERENCE')
        self.assertEqual(out['excluded_hypothesis_rows'][0]['reason'],'INCOMPLETE_REFERENCE_PIECE')
    def test_global_metadata_person_not_piece_cast(self):
        ref=reference();ref['pieces'][1]['mapped_turns'][0]['metadata_identity']='a'
        ref['projected_turns']=S.E.shift_reference_pieces(ref['pieces'],80000)
        out=S.text_metrics(ref,[final(),final('good morning','v',3,5)],D)
        self.assertEqual(out['anonymous_cpwer']['word_counts']['errors'],0)
    def test_missing_label_not_fabricated(self):
        row=final();row['latest_anonymous_label']=None
        out=S.text_metrics(reference(),[row],D)
        self.assertEqual(out['anonymous_cpwer']['status'],'UNAVAILABLE_ANONYMOUS_LABEL')
    def test_wrong_then_correct_and_stable_retained(self):
        events=[event('source_started',0),display(.5,'px','Xavier'),display(1.,'pa','Alice'),event('session_completed',5.)]
        out=S.name_metrics(reference(),events,gallery(),True,D)
        row=out['opportunities'][0]
        self.assertAlmostEqual(row['metrics']['first_correct_name']['wait_sec'],1.01)
        self.assertAlmostEqual(row['metrics']['first_stable_correct_name']['wait_sec'],1.51)
        self.assertGreater(out['exposure_row_seconds']['wrong_known_name'],0)
        self.assertEqual(out['name_transitions'][0]['after'],'correct_name')
    def test_never_correct_and_withheld_are_distinct(self):
        out=S.name_metrics(reference(),[event('source_started',0),event('session_completed',5)],gallery(),True,D)
        self.assertEqual(out['opportunities'][0]['metrics']['first_correct_name']['status'],'RIGHT_CENSORED')
        self.assertIsNone(out['opportunities'][0]['metrics']['first_correct_name']['wait_sec'])
        self.assertEqual(out['opportunities'][1]['metrics']['first_correct_name']['status'],'WITHHELD_OR_UNSELECTED')
        self.assertEqual(out['census']['first_text_consumption']['right_censored'],2)
    def test_incomplete_never_not_eligible_success(self):
        out=S.name_metrics(reference(True),[event('source_started',0),event('session_completed',5)],gallery(),True,D)
        self.assertEqual(out['opportunities'][1]['metrics']['first_text_publication']['status'],'INCOMPLETE_REFERENCE')
        self.assertEqual(out['wait_summaries']['first_text_publication']['total'],2)
        self.assertIsNone(out['wait_summaries']['first_text_publication']['p99'])
    def test_nonfinite_and_backwards_consumer_clocks(self):
        for value in (float('nan'),99.):
            events=[event('source_started',0),display(.5),event('session_completed',5)]
            events[1]['actual_consumed_monotonic_sec']=value
            out=S.name_metrics(reference(),events,gallery(),True,D)
            self.assertEqual(out['status'],'UNAVAILABLE_ACTUAL_CLOCK')
            self.assertEqual(len(out['opportunities']),2)
    def test_publication_consumption_not_gui(self):
        e=event('s6d_text_ready',.5,dict(utterance_id='u',text='hello',source_start_sec=0.,source_end_sec=1.),delay=.2)
        out=S.name_metrics(reference(),[event('source_started',0),e,event('session_completed',5)],gallery(),True,D)
        self.assertAlmostEqual(out['first_text_rows'][0]['queue_delay_sec'],.2)
        self.assertEqual(out['gui_render_timing'],'UNAVAILABLE_HEADLESS_CONSUMER')
        self.assertEqual(out['scanout_timing'],'UNAVAILABLE')
    def test_missing_profile_label_cannot_be_known_correct(self):
        events=[event('source_started',0),display(.5,'pa','Wrong label'),event('session_completed',5)]
        out=S.name_metrics(reference(),events,gallery(),True,D)
        self.assertEqual(out['opportunities'][0]['metrics']['first_correct_name']['status'],'RIGHT_CENSORED')
        self.assertGreater(out['exposure_row_seconds']['wrong_known_name'],0)
    def test_revision_keeps_arrived_span_not_final_backfill(self):
        partial=dict(utterance_id='u',text='hello',source_start_sec=0.,source_end_sec=1.,latest_label='Speaker_1')
        revision=dict(utterance_id='u',source_start_sec=3.,source_end_sec=5.,latest_known_profile_id='pa',latest_known_name='Alice',latest_label='Alice',latest_naming_state='confirmed')
        events=[event('source_started',0),event('transcript_partial',.5,partial),event('transcript_label_revision',1,revision),event('session_completed',5)]
        out=S.name_metrics(reference(),events,gallery(),False,D)
        self.assertEqual(out['opportunities'][0]['metrics']['first_correct_name']['status'],'OBSERVED')
        self.assertEqual(out['opportunities'][1]['metrics']['first_correct_name']['status'],'WITHHELD_OR_UNSELECTED')
    def test_hidden_row_never_creates_visible_name(self):
        out=S.name_metrics(reference(),[event('source_started',0),display(.5,visible=False),event('session_completed',5)],gallery(),True,D)
        self.assertEqual(out['opportunities'][0]['metrics']['first_correct_name']['status'],'RIGHT_CENSORED')
    def test_missing_consumer_closure_clock_not_imputed(self):
        out=S.name_metrics(reference(),[event('source_started',0),event('session_completed',5)],gallery(),True,D,{})
        self.assertEqual(out['status'],'UNAVAILABLE_ACTUAL_CLOCK')
    def test_duplicate_reference_and_final_row_rejected(self):
        ref=reference();ref['projected_turns'][1]['occurrence_id']=ref['projected_turns'][0]['occurrence_id']
        with self.assertRaises(ValueError):S.text_metrics(ref,[],D)
        with self.assertRaises(ValueError):S.text_metrics(reference(),[final(),final()],D)
    def test_no_approval_no_actual_input_reads(self):
        path=ROOT/'UNAPPROVED.json';path.write_text(json.dumps(dict(schema='s6d-native-scoring-inputs.v1',status='PROPOSED')),encoding='utf-8')
        with self.assertRaises(ValueError):S.run(path,S.E.binding(path)['sha256'])
    def test_paired_missing_row_not_zero_delay(self):
        row=dict(utterance_id='u',source_start_sec=0.,publication_sec=.2,consumption_sec=.3,raw_text='hello')
        a=dict(first=[row],normalized='hello',finals={'u':'hello'})
        b=dict(first=[],normalized='',finals={})
        out=S.compare_pair(a,b)
        self.assertEqual(out['additional_first_text_delay']['publication_right_minus_left_sec']['observed'],0)
        self.assertIsNone(out['additional_first_text_delay']['publication_right_minus_left_sec']['p50'])
        self.assertTrue(out['first_text_pairs'][0]['right_never'])
        self.assertFalse(out['entire_normalized_words_equal'])
    def test_nontext_hypothesis_rejected(self):
        e=event('s6d_text_ready',.5,dict(utterance_id='u',text=None,source_start_sec=0.,source_end_sec=1.))
        with self.assertRaises(ValueError):S.name_metrics(reference(),[event('source_started',0),e,event('session_completed',5)],gallery(),True,D)
    def test_known_render_label_without_profile_not_unknown(self):
        out=S.name_metrics(reference(),[event('source_started',0),display(.5,None,'Alice'),event('session_completed',5)],gallery(),True,D)
        self.assertEqual(out['opportunities'][0]['metrics']['first_correct_name']['status'],'RIGHT_CENSORED')
        self.assertGreater(out['exposure_row_seconds']['wrong_known_name'],0)
    def test_declared_missing_population_preserved_and_omission_rejected(self):
        def put(name,value):
            p=ROOT/name;p.write_text(json.dumps(value),encoding='utf-8');return S.E.binding(p)
        manifest=put('TOY_MANIFEST.json',dict(jobs=[dict(job_id='a'),dict(job_id='b')]))
        base=dict(schema='s6d-native-scoring-inputs.v1',status='APPROVED_CLOSED_NATIVE_INPUTS',
                  owner_exit_verified=True,source_graph_verified=True,scorer=S.E.binding(S.__file__),dependencies=D['sources'],
                  gallery_map=S.E.binding(S.HERE.parent/'reports/S6C/20260910T123540Z/enrollment/SCORER_GALLERY_MAP.json'),
                  execution_manifests=[manifest],jobs=[],unavailable_jobs=[dict(job_id=k,status='ABSENT_NATIVE',reason='Synthetic missing output') for k in ('a','b')],
                  comparison_pairs=[dict(left_job_id='a',right_job_id='b')],output_root=str(ROOT/'missing_population'))
        b=put('TOY_INPUTS.json',base);S.run(b['path'],b['sha256'])
        index=json.loads((ROOT/'missing_population/INDEX.json').read_text())
        self.assertEqual((index['declared_jobs'],index['scored_jobs']),(2,0))
        self.assertEqual(index['comparison_pairs'][0]['status'],'UNAVAILABLE_INCOMPLETE_PAIR')
        self.assertFalse(index['complete_metric_matrix'])
        base['unavailable_jobs'].pop();base['output_root']=str(ROOT/'must_not_exist')
        b=put('TOY_OMITTED.json',base)
        with self.assertRaises(ValueError):S.run(b['path'],b['sha256'])
        self.assertFalse((ROOT/'must_not_exist').exists())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    ROOT=a.output.resolve();ROOT.mkdir(parents=True,exist_ok=False);D=S.dependencies()
    with (ROOT/'TESTS.log').open('x',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    receipt=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                 scorer=S.E.binding(S.__file__),checks=S.E.binding(__file__),dependencies=D['sources'],log=S.E.binding(ROOT/'TESTS.log'),
                 actual_native_outputs_scored=0,models=0,policy_replays=0,devices=0)
    (ROOT/'FIXTURE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=receipt['status'],tests=receipt['tests'],failures=receipt['failures'],errors=receipt['errors'],receipt=S.E.binding(ROOT/'FIXTURE_RECEIPT.json'))))
    raise SystemExit(not result.wasSuccessful())
