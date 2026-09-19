"""Model-free S5 support/gate/reserve fixtures; see README_S5_SUPPORT_METRICS.md."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
import s5_support_metrics as m


def turn(start=3.,stop=5.,speaker='A',active=None,index=0):
    return {'kind':'utterance','source_id':'source'+str(index),'speaker_key':speaker,'participant_id':speaker,
            'dataset':'fixture','rir_id':'rir'+str(index),'source_start_sample':round(start*16000),'source_stop_sample':round(stop*16000),
            'convolution_stop_sample':round(stop*16000)+3200,'source_crop_samples':[0,round((stop-start)*16000)],
            'activity_ranges_samples_estimated':active if active is not None else [[round((start+.05)*16000),round((stop+.05)*16000)]],
            'role':'target_or_conversation'}


def scene(segments=None,case_id='DEV',split='development'):
    return {'case_id':case_id,'split':split,'task_scoring_allowed':split=='development','sample_rate_hz':16000,
            'duration_s':12,'family_id':'F01','segments':[turn()] if segments is None else segments,'all_speaker_reference_complete':True}


def timing(s,offset=-100,lag=200):
    capture={'case_id':s['case_id'],'payload':{'capture_minus_source_offset_samples':offset},'framing':{'startup_frames_excluded':600}}
    audio={'case_id':s['case_id'],'streams':{k:{'relative_delay_median_samples':lag} for k in ['O0','O1']},
           'output_alignment':{k:{'uncertainty_s':.001} for k in ['O0','O1']}}
    return capture,audio


def decision(end,label='Speaker_1',cluster=1):
    return {'event_type':'speaker_decision','source_time_sec':end,'payload':{'anonymous_label':label,'cluster_id':cluster,
            'spatial_evidence':{'source_start_sec':end-.5,'source_end_sec':end,'source_clock':'audio_sample_clock'}}}


def segment(end,speech=True,overlap=False):
    return {'event_type':'segmentation','source_time_sec':end,'payload':{'speech':speech,'overlap':overlap}}


class Tests(unittest.TestCase):
    def fixture(self,s,offset=-100,lag=200):
        g=m.DevelopmentGuard([s],scoring_protocol_sha256='fixture_frozen_protocol')
        c,a=timing(s,offset,lag)
        return g,m.freeze_scene_support(s,c,a,{},g)

    def test_interval_union_and_overlap_not_double_counted(self):
        self.assertEqual(m.union([[0,5],[3,7],[7,9]]),[[0,9]])
        self.assertEqual(m.intersection([[0,8]],[[3,5],[4,10]]),[[3,8]])
        self.assertEqual(m.subtract([[0,10]],[[3,5],[4,7]]),[[0,3],[7,10]])
        self.assertEqual(m.samples([[0,8000],[4000,12000]]),12000)

    def test_absolute_bank_activity_plus800_exactly_once(self):
        # Bank style: start3s, dry active+.5s, retainedRIR+.05s =3.55s.
        s=scene([turn(active=[[56800,60800]])]);g,p=self.fixture(s,100,200)
        self.assertEqual(p['turns'][0]['active_ranges'],[[56800,60800]])
        self.assertEqual(m.mapped_ranges(p['turns'][0]['active_ranges'],300,192000),[[57100,61100]])
        from s4_spatial_analysis import Availability
        cb={'callback_times':[{'first_native_frame':i*480,'frames':480,'host_callback_monotonic_ns':i*10_000_000} for i in range(1300)]}
        av=Availability(cb,600,100)
        expected=600+3*(56800+100)
        first=av.source_range(56800,56801)[0][0]
        self.assertEqual(first,(expected//480)*10_000_000)
        self.assertNotEqual(first,((expected+2400)//480)*10_000_000)

    def test_missing_activity_fallback_has_one_rir_shift_not_active_bin(self):
        t=turn();t.pop('activity_ranges_samples_estimated');s=scene([t]);g,p=self.fixture(s)
        self.assertEqual(p['turns'][0]['support_ranges'],[[48800,80800]])
        self.assertIsNone(p['turns'][0]['active_duration_bin'])

    def test_duration_bins_clip_not_active_duration(self):
        self.assertEqual([m.duration_bin(x) for x in [.999,1,1.999,2]],['<1s','1-<2s','1-<2s','>=2s'])
        s=scene([turn(3,5,active=[[56800,60800]])]);g,p=self.fixture(s)
        self.assertEqual(p['turns'][0]['whole_clip_bin'],'>=2s')
        self.assertEqual(p['turns'][0]['active_duration_bin'],'<1s')

    def test_noise_exact_crop_unknown_speech_and_quiet_not_threshold_silence(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'noise.wav';x=np.zeros(3200,dtype=np.float32);x[960:1600]=.2;sf.write(f,x,16000,subtype='FLOAT')
            sha=hashlib.sha256(f.read_bytes()).hexdigest()
            noise={'kind':'real_noise','source_id':'N','parent_id':'P','rir_id':'R','source_start_sample':32000,
                   'source_stop_sample':33600,'convolution_stop_sample':36800,'source_crop_samples':[640,2240],
                   'speech_content':'unknown','strict_nonspeech_eligible':False,'category':'transient_event_noise'}
            s=scene([noise]);s['all_speaker_reference_complete']=False
            g=m.DevelopmentGuard([s]);c,a=timing(s)
            p=m.freeze_scene_support(s,c,a,{'N':{'noise_id':'N','split':'development','prepared_path':str(f),'prepared_sha256':sha}},g)
            self.assertEqual(p['noise_events'][0]['active_ranges'],[[33120,33760]])
            self.assertEqual(p['noise_events'][0]['interpretation'],'noise_associated_unknown_speech_not_false_speech')
            self.assertEqual(p['regions_source_with_rir_samples']['quiet_outside_all_convolution_envelopes'],[[0,32000],[36800,192000]])
            self.assertTrue(p['regions_source_with_rir_samples']['inactive_or_tail_uncertain_within_envelopes'])

    def test_noise_final_short_frame_remains_unknown(self):
        ranges,detail=m.noise_activity(np.ones(500)*.1)
        self.assertEqual(ranges,[[0,320]]);self.assertEqual(detail['unestimated_tail_samples'],180)

    def test_reserve_refused_before_path_stat_audio_or_task_logs(self):
        s=scene(case_id='RES',split='reserve');g=m.DevelopmentGuard([s],scoring_protocol_sha256='fixture')
        with patch.object(Path,'stat',side_effect=AssertionError('must not inspect path')):
            with self.assertRaises(PermissionError):g.verified_path(s,{'path':'NEVER','sha256':'x'},'task_audio')
            with self.assertRaises(PermissionError):g.read_json(s,{'path':'NEVER','sha256':'x'},'task_logs')
        self.assertEqual(g.receipt()['reserve_performance_scoring_accesses'],0)
        self.assertEqual(len(g.receipt()['refused_before_access']),2)

    def test_metadata_spoof_and_no_protocol_refused(self):
        s=scene();g=m.DevelopmentGuard([s]);spoof=copy.deepcopy(s);spoof['duration_s']=1
        with self.assertRaises(PermissionError):g.require(spoof,'support_freeze')
        with self.assertRaises(PermissionError):g.require(s)

    def test_input_hash_and_support_freeze_tamper(self):
        s=scene();g,p=self.fixture(s)
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'x.json';f.write_text('{}',encoding='utf-8')
            with self.assertRaises(ValueError):g.read_json(s,{'path':str(f),'sha256':'bad'})
        p['turns'][0]['active_ranges'][0][0]+=800
        with self.assertRaises(ValueError):m.validate_support(s,p)

    def test_embedding_export_contract_and_union_duration(self):
        windows=m.embedding_windows([decision(1),decision(1.25)])
        self.assertEqual(m.samples([[w['start'],w['stop']] for w in windows]),12000)
        self.assertEqual(sum(w['stop']-w['start'] for w in windows),16000)
        bad=decision(1);bad['payload']['spatial_evidence']['source_start_sec']=.6
        with self.assertRaises(ValueError):m.embedding_windows([bad])

    def test_returned_label_change_tie_missing_and_within_turn_switch(self):
        s=scene([turn(1,2.5,'A',index=0),turn(4,5.5,'B',index=1),turn(7,9,'A',index=2)])
        g,p=self.fixture(s,0,0)
        w=m.embedding_windows([decision(1.75,'X'),decision(2,'Y'),decision(2.25,'X'),decision(7.75,'Z'),decision(8,'Z')])
        r=m.continuity(p['turns'],w,p['regions_source_with_rir_samples'],'F06')
        self.assertEqual(r['return_group_counts'],{'inconsistent':1})
        self.assertEqual(r['turns'][0]['within_turn_label_switches'],2)
        self.assertEqual(r['turns_without_contained_evidence'],1)
        tied=m.continuity(p['turns'],m.embedding_windows([decision(1.75,'X'),decision(2,'Y'),decision(7.75,'Z')]),p['regions_source_with_rir_samples'],'F06')
        self.assertTrue(tied['turns'][0]['dominant_tied']);self.assertEqual(tied['return_group_counts'],{'unknown':1})

    def test_overlap_crossing_window_cannot_be_identity_evidence(self):
        s=scene([turn(1,3,'A',index=0),turn(2,4,'B',index=1)]);g,p=self.fixture(s,0,0)
        w=m.embedding_windows([decision(2.25),decision(2.75)])
        r=m.continuity(p['turns'],w,p['regions_source_with_rir_samples'],'F04')
        self.assertEqual(r['turns_without_contained_evidence'],2)
        self.assertEqual(r['window_crossings']['whole_clip_boundary'],1)
        self.assertEqual(r['window_crossings']['multiple_speaker_active_boundary_or_overlap'],2)

    def test_segmentation_is_coarse_actual_flag_not_transcript(self):
        rows=m.segmentation_intervals([segment(.75),{'event_type':'transcript_final','source_time_sec':3,'payload':{'text':'hi'}}])
        self.assertEqual(rows[0]['start'],120);self.assertEqual(rows[0]['stop'],12000)
        self.assertEqual(len(rows),1)

    def test_gate_current_state_no_future_and_overlapping_reasons(self):
        pcm=np.full(32000,1000,dtype=np.int16)
        events=[segment(.75,True),decision(.75),decision(1),segment(1.5,True,True)]
        r=m.gate_diagnostics(pcm,events)['counts']
        self.assertEqual(r['eligible_hops_reconstructed'],3)
        self.assertEqual(r['eligible_without_decision'],1)
        self.assertEqual(r['blocked_no_speech'],2);self.assertEqual(r['blocked_short_window'],1)
        self.assertEqual(r['blocked_overlap'],3);self.assertEqual(r['decision_despite_ineligible'],0)

    def test_levels_intervals_union_no_bridging_gap_rails(self):
        x=np.array([8388606,8388606,0,-8388608,-8388608],dtype=np.int32)
        r=m.sample_levels(x,[[0,2],[3,5],[0,1]],bits=24)
        self.assertEqual((r['samples'],r['rail_samples'],r['rail_runs'],r['longest_rail_run_samples']),(4,4,2,2))
        journal=m.sample_levels(np.array([32766,32767,-32768],dtype=np.int16),[[0,3]],bits=16)
        self.assertEqual(journal['rail_samples'],2)

    def test_unknown_ambient_cannot_establish_return_identity(self):
        s=scene([turn(1,3,'A',index=0),turn(6,8,'A',index=1)]);g,p=self.fixture(s,0,0)
        r=m.continuity(p['turns'],m.embedding_windows([decision(2),decision(7)]),p['regions_source_with_rir_samples'],'F01',reference_complete=False)
        self.assertEqual(r['return_group_counts'],{'unknown':1})
        self.assertEqual(r['returning_participant_groups'][0]['unknown_reason'],'unknown_ambient_speech_precludes_source_attribution')

    def test_overlapping_turn_positive_flag_is_not_source_detection(self):
        s=scene([turn(1,3,'A',index=0),turn(2,4,'B',index=1)]);g,p=self.fixture(s,0,0)
        r=m.score_output(s,p,'O1',[segment(2.25)],np.zeros(80000,dtype=np.int16),np.zeros(80000,dtype=np.int32),g)
        self.assertTrue(r['short_turns'][0]['detected_supported_flag'])
        self.assertIsNone(r['short_turns'][0]['source_specific_supported_detection'])

    def test_output_missing_mapping_retains_native_and_whole_audio(self):
        s=scene([]);g,p=self.fixture(s,0,None)
        r=m.score_output(s,p,'O0',[],np.zeros(4000,dtype=np.int16),np.zeros(4000,dtype=np.int32),g)
        self.assertEqual(r['reference_local_status'],'UNAVAILABLE_NO_SAVED_OUTPUT_MAPPING')
        self.assertEqual(r['raw_full_output_levels']['samples'],4000);self.assertIsNone(r['regions'])
        self.assertEqual(r['shared_hardware_direction']['evidence_units'],0)

    def test_partial_segmentation_observation_does_not_prove_whole_turn_miss(self):
        s=scene([turn(0,.7,'A',active=[[800,11200]])]);g,p=self.fixture(s,0,0)
        # This event only covers a late part of the reference support; no positive flag.
        r=m.score_output(s,p,'O1',[segment(1.25,False)],np.zeros(32000,dtype=np.int16),np.zeros(32000,dtype=np.int32),g)
        self.assertIsNone(r['short_turns'][0]['missed_supported_flag'])
        self.assertTrue(r['short_turns'][0]['no_positive_on_observed_support'])
        self.assertFalse(r['short_turns'][0]['fully_observed_support'])

    def test_normalized_float_is_not_silently_treated_as_pcm(self):
        s=scene([]);g,p=self.fixture(s,0,None)
        with self.assertRaises(ValueError):m.score_output(s,p,'O0',[],np.zeros(4000),np.zeros(4000,dtype=np.int32),g)

    def test_noise_direction_helper_no_future_and_one_shared_trace(self):
        # Use injected historical pure helpers to verify source interval is mapped once, no output lag.
        s=scene([]);g,p=self.fixture(s,100,200)
        p.pop('support_sha256');p['noise_events']=[{'segment_index':0,'parent_id':'P','interpretation':'unknown_speech','active_ranges':[[56800,60800]]}]
        p['support_sha256']=m.fingerprint(p);calls=[]
        class Available:
            def __init__(self,metadata,startup,offset):self.offset=offset
            def source_range(self,a,b):calls.append((a,b,self.offset));return [[a*3,b*3]]
        with patch('s4_spatial_analysis.Availability',Available),patch('s4_spatial_analysis.ReceiptTimeline'),patch('s4_spatial_analysis.summarize_window',return_value={'available_seconds':0}):
            c,_=timing(s,100,200);r=m.shared_direction_metrics(s,p,c,{},[],g)
        self.assertEqual(r['physical_trace_evidence_units'],1);self.assertEqual(r['paired_output_evidence_units'],0)
        self.assertTrue(all(x==(56800,60800,100) for x in calls))


class PanelTests(unittest.TestCase):
    def test_panel_exact_pair_guard_rejects_reserve_and_duplicate(self):
        from s5_support_panel import validate_jobs
        s=scene();reserve=scene(case_id='RES',split='reserve');jobs=[]
        for out in ['O0','O1']:
            identity={'case_id':'DEV','stream':out,'scene_reference_sha256':m.fingerprint(s),'raw_audio_sha256':'raw','input_case_result_sha256':'capture'}
            jobs.append({'case_id':'DEV','stream':out,'identity':identity,'job_key':m.fingerprint(identity),
                         'raw_audio':{'sha256':'raw'},'input_provenance':{'accepted_record':{'split':'development'},'case_result':{'sha256':'capture'}}})
        bank={'scenes':[s,reserve]};panel={'development_ids':['DEV'],'jobs':jobs}
        self.assertEqual(len(validate_jobs(bank,panel)),2)
        bad=copy.deepcopy(panel);bad['jobs'][1]['case_id']='RES'
        with self.assertRaises(ValueError):validate_jobs(bank,bad)
        bad=copy.deepcopy(panel);bad['jobs'][1]=bad['jobs'][0]
        with self.assertRaises(ValueError):validate_jobs(bank,bad)

    def test_indexed_binding_requires_exact_unique_hash(self):
        from s5_support_panel import indexed_binding
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'capture_metadata.json'
            b={'path':str(p),'sha256':'a'}
            self.assertEqual(indexed_binding({'files':[b]},p),b)
            with self.assertRaises(ValueError):indexed_binding({'files':[b,{**b,'sha256':'b'}]},p)
            with self.assertRaises(ValueError):indexed_binding({'files':[b]},Path(tmp)/'other.json')

    def test_result_resume_rejects_changed_identity_or_metrics(self):
        from s5_support_panel import saved_record
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'result.json';row={'analysis_identity':'frozen','metrics':{'calls':2},'metrics_sha256':m.fingerprint({'calls':2})}
            p.write_text(json.dumps(row),encoding='utf-8')
            self.assertEqual(saved_record(p,'frozen'),row)
            with self.assertRaises(ValueError):saved_record(p,'changed')
            row['metrics']['calls']=3;p.write_text(json.dumps(row),encoding='utf-8')
            with self.assertRaises(ValueError):saved_record(p,'frozen')


def prior24_regression():
    """Explicit historical development integration; never expand to full panel here."""
    import concurrent.futures
    import time
    from s5_common import bind
    sim=Path(__file__).resolve().parents[1]
    prior=sim/'reports/S4_5/20260909T031300Z'
    manifest_path=sim/'scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json'
    bound=bind(manifest_path,'69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18')
    bank=json.loads(manifest_path.read_text(encoding='utf-8'))
    scenes={s['case_id']:s for s in bank['scenes']}
    guard=m.DevelopmentGuard(bank['scenes'],scoring_protocol_sha256='PRIOR_24_REGRESSION_ONLY_NOT_FULL_PANEL')
    captures=json.loads((prior/'CAPTURE_ANALYSIS.json').read_text(encoding='utf-8'))
    captures={r['case_id']:r for r in captures['cases']}
    noise=json.loads((sim/'staging/s45_noise/NOISE_CATALOG.json').read_text(encoding='utf-8'))
    ids=bank['sentinel_scene_ids']
    if len(ids)!=24:raise ValueError('Prior24 only')
    def one(cid):
        s=scenes[cid];guard.require(s,'prior_24_regression');row=captures[cid]
        c=guard.read_json(s,row['case_result']);a=guard.read_json(s,row['audio_metrics'])
        support=m.freeze_scene_support(s,c,a,noise,guard);outputs=[]
        for output in ['O0','O1']:
            receipt=guard.read_json(s,bind(prior/'h2'/cid/output/'run_receipt.json'))
            result=m.analyze_bound_output(s,support,output,receipt,guard)
            old=guard.read_json(s,receipt['metrics_binding'])
            previous=old['embedding_gate_evidence']['counts'];current=result['embedding_gate']['counts']
            differences={k:[previous.get(k,0),v] for k,v in current.items() if previous.get(k,0)!=v}
            if differences:raise AssertionError((cid,output,differences))
            if old['speaker']['embedding_calls_successful']!=result['successful_embedding_calls']:raise AssertionError('Native call-count mismatch')
            for new_key,old_key in [('rail_samples','rail_samples'),('rail_runs','rail_runs'),('longest_rail_run_samples','maximum_contiguous_rail_run_samples')]:
                if result['raw_full_output_levels'][new_key]!=a['streams'][output][old_key]:raise AssertionError('Historical raw rail mismatch')
            outputs.append({'output':output,'mapping_status':result['reference_local_status']})
        return {'case_id':cid,'noise_events':len(support['noise_events']),'outputs':outputs}
    started=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(one,ids))
    access=guard.receipt()
    return {'status':'PASS','scope':'Prior24 development only; exact inherited gate/native-call-count regression, no new full-panel comparison',
            'scene_manifest':bound,'prior_scenes':len(rows),'prior_outputs':sum(len(r['outputs']) for r in rows),
            'all_native_gate_counts_exact':True,'all_native_successful_call_counts_exact':True,
            'all_raw_rail_counts_runs_maxima_exact':True,
            'elapsed_s':time.monotonic()-started,'maximum_workers':4,
            'noise_cases':sum(r['noise_events']>0 for r in rows),
            'unavailable_mappings':[r['case_id']+'/'+v['output'] for r in rows for v in r['outputs'] if v['mapping_status'].startswith('UNAVAILABLE')],
            'reserve_task_model_accesses':access['reserve_task_model_accesses'],
            'reserve_performance_scoring_accesses':access['reserve_performance_scoring_accesses'],
            'permitted_operation_counts':{operation:sum(r['count'] for r in access['accesses'] if r['operation']==operation) for operation in sorted({r['operation'] for r in access['accesses']})},
            'verified_input_count':len(access['verified_inputs']),
            'verified_input_bindings_sha256':m.fingerprint(sorted(access['verified_inputs'],key=lambda r:r['path'])),
            'support_policy_sha256':m.fingerprint(m.POLICY)}


if __name__=='__main__':
    import sys
    import collections
    if sys.argv[1:]==['--prior24-regression']:
        print(json.dumps(prior24_regression(),indent=2))
    else:unittest.main()
