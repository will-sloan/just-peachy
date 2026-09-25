"""Full-bank integrity and causal-event regressions. README_REVIEW_D0_BANK.md."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from common import bind, fingerprint
from d0_bank_components import cell_key
from review_d0_bank import check_cell, check_index, exact_path, scan_events, terminal


def fixture(root):
    wave = np.full(8042, .125, dtype=np.float32)
    job = dict(job_id='synthetic_O0', audio_path='not_read.wav', audio_sha256='a'*64,
        frames=len(wave), sample_rate_hz=16000, gain=1, reset_between_scenes=True, tap='O0')
    profile = dict(embedding=dict(cadence='fixed'))
    row = dict(start_sample=0, end_sample=8000, evidence_kind='short', clean_intervals=[[0., .5]],
        waveform_sha256=hashlib.sha256(wave[:8000].astype('<f4').tobytes()).hexdigest(),
        normalized_embedding=[1.]+[0.]*191)
    cell = dict(schema='n4-d0-component-cell-v1', job=job, encoder='E0', status='COMPLETE', error=None,
        admission_sha256='admission', profile_sha256=fingerprint(profile), namespace='E0-test',
        vectors=[row], segmentation_calls=1, cache_key=cell_key('admission',job,'E0',profile),
        observed_compute_is_live_latency=False, tracker_name_or_ASR_outputs_present=False,
        telemetry=dict(identity_audio_samples=len(wave), paired_audio_samples=len(wave),
            speaker_unanalyzed_short_tail_sec=42/16000))
    def admission(end, role, admitted):
        return dict(source_start_sec=max(0., end-(.5 if role=='short' else 1.5)), source_end_sec=end,
            evidence_kind=role, samples=8000 if role=='short' else 24000, clean_intervals=[[0.,.5]],
            cadence_policy='fixed', naming_used_for_schedule=False, cue_event=False,
            tracking_context_used=False, admitted=admitted, reason='admitted' if admitted else 'insufficient_contiguous_audio')
    events=[]
    def add(kind, end, payload):
        events.append(dict(event_type=kind, source_time_sec=end,
                           payload=dict(payload, modeled_available_at_sec=end+.01)))
    for role in ('short','mature'):
        add('research_embedding_admission',.25,admission(.25,role,False))
    add('research_segmentation',.5,dict(source_start_sec=0.,source_end_sec=.5,
        receptive_start_sec=0.,receptive_end_sec=.5,left_padding_sec=9.5,
        frame_step_sec=.016875,frame_duration_sec=.0619375,speech_frames=[0,1,1],overlap_frames=[0,0,0],
        speech_probability_frames=[0.,.9,.9],overlap_probability_frames=[0.,.1,.1]))
    add('research_embedding_admission',.5,admission(.5,'short',True))
    add('research_embedding',.5,dict(source_start_sec=0.,source_end_sec=.5,available_at_sec=.51,
        evidence_event_id='embedding:00000001',normalized_embedding=row['normalized_embedding'],
        evidence_kind='short',clean_intervals=row['clean_intervals'],admission=admission(.5,'short',True)))
    add('research_embedding_admission',.5,admission(.5,'mature',False))
    cell['events'] = dict(path=str(root/'LANE_EVENTS.jsonl.gz'))
    write_events(cell, events)
    index = dict(status='COMPLETE',completed=1,total=1,cpu_affinity=[4],one_native_model_thread=True,
        namespace='E0-test',profiles=dict(O0=profile),cells={job['job_id']:dict(path='not-opened')})
    progress = dict(admission_sha256='admission',completed=1,total=1,failed=0,cells=deepcopy(index['cells']))
    return cell, wave, events, index, progress


def write_events(cell, events):
    path = Path(cell['events']['path'])
    data = ''.join(json.dumps(e, separators=(',',':'))+'\n' for e in events).encode('utf-8')
    with gzip.open(path, 'wb') as stream:
        stream.write(data)
    cell['events'] = bind(path)
    cell['events_expanded'] = dict(uncompressed_sha256=hashlib.sha256(data).hexdigest(),uncompressed_bytes=len(data))


class TestBankReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.cell,self.wave,self.events,self.index,self.progress=fixture(self.root)
    def tearDown(self):
        self.tmp.cleanup()
    def test_valid_causal_dispatch_and_partial_tail(self):
        scan=scan_events(self.cell,self.wave)
        self.assertEqual(scan['events']['research_embedding_admission'],4)
        self.assertEqual(scan['rejection_reasons']['insufficient_contiguous_audio'],3)
        check_cell(self.cell,self.cell['job'],'E0',self.index,'admission')
        check_index(self.index,self.progress,[self.cell['job']],'admission')
    def test_complete_no_embedding_cell_is_retained(self):
        self.cell['vectors']=[]
        events=deepcopy(self.events);events.pop(4)
        events[3]['payload'].update(admitted=False,reason='no_speech_gate')
        write_events(self.cell,events)
        scan=scan_events(self.cell,self.wave)
        self.assertEqual(scan['events'].get('research_embedding',0),0)
        self.assertEqual(sum(scan['rejection_reasons'].values()),4)
    def test_every_closed_byte_and_gzip_crc_checked(self):
        path=Path(self.cell['events']['path']);path.write_bytes(path.read_bytes()[:-3])
        self.cell['events']=bind(path)
        with self.assertRaises(EOFError):scan_events(self.cell,self.wave)
    def test_expanded_binding_mismatch_rejected(self):
        self.cell['events_expanded']['uncompressed_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Expanded'):scan_events(self.cell,self.wave)
    def test_vector_in_log_must_match_result_even_with_valid_gzip(self):
        self.events[4]['payload']['normalized_embedding']=[0.,1.]+[0.]*190
        write_events(self.cell,self.events)
        with self.assertRaisesRegex(ValueError,'Vector'):scan_events(self.cell,self.wave)
    def test_actual_waveform_must_match_logged_slice(self):
        self.wave[10]=.5
        with self.assertRaisesRegex(ValueError,'Vector'):scan_events(self.cell,self.wave)
    def test_rejected_admission_cannot_be_silently_dropped(self):
        write_events(self.cell,self.events[1:])
        with self.assertRaisesRegex(ValueError,'census'):scan_events(self.cell,self.wave)
    def test_admitted_event_cannot_be_missing_or_duplicated(self):
        for events in [self.events[:4]+self.events[5:], self.events[:5]+[self.events[4]]+self.events[5:]]:
            write_events(self.cell,events)
            with self.assertRaises(ValueError):scan_events(self.cell,self.wave)
    def test_future_or_backward_available_times_rejected(self):
        for value in [.1,float('nan')]:
            events=deepcopy(self.events);events[4]['payload']['modeled_available_at_sec']=value
            write_events(self.cell,events)
            with self.assertRaises(ValueError):scan_events(self.cell,self.wave)
    def test_invalid_probabilities_or_frame_geometry_rejected(self):
        for key,value in [('speech_probability_frames',[1.5]),('frame_step_sec',.02),('speech_frames',[.5,.5,.5])]:
            events=deepcopy(self.events);events[2]['payload'][key]=value;write_events(self.cell,events)
            with self.assertRaises(ValueError):scan_events(self.cell,self.wave)
    def test_semantic_hash_ignores_only_timing_not_model_gate(self):
        first=scan_events(self.cell,self.wave)['paired_lane_semantics_sha256']
        events=deepcopy(self.events);events[2]['payload']['compute_ms']=120.
        write_events(self.cell,events)
        self.assertEqual(first,scan_events(self.cell,self.wave)['paired_lane_semantics_sha256'])
        events[2]['payload']['speech_probability_frames'][1]=.8;write_events(self.cell,events)
        self.assertNotEqual(first,scan_events(self.cell,self.wave)['paired_lane_semantics_sha256'])
    def test_cache_namespace_profile_and_tail_cannot_drift(self):
        for field,value in [('cache_key','different'),('namespace','E1-test'),('profile_sha256','different'),
                            ('telemetry',dict(paired_audio_samples=8042,speaker_unanalyzed_short_tail_sec=0.))]:
            cell=deepcopy(self.cell);cell[field]=value
            with self.assertRaises(ValueError):check_cell(cell,cell['job'],'E0',self.index,'admission')
    def test_census_and_checkpoint_must_agree(self):
        for progress in [dict(self.progress,failed=1),dict(self.progress,cells={}),dict(self.progress,completed=0)]:
            with self.assertRaises(ValueError):check_index(self.index,progress,[self.cell['job']],'admission')
        with self.assertRaises(ValueError):check_index(self.index,self.progress,[],'admission')
    def test_live_exact_owner_rejected_pid_reuse_allowed(self):
        final=dict(status='COLLECTED_REQUIRES_REVIEW',completed=960,total=960,admission={'a':1},
            child=None,integrated_N4_cells=0,owner=dict(pid=42,create_time=100.))
        with patch('psutil.Process') as process:
            process.return_value.create_time.return_value=100.
            with self.assertRaisesRegex(ValueError,'alive'):terminal(final,{'a':1})
            process.return_value.create_time.return_value=101.
            terminal(final,{'a':1})
        with self.assertRaisesRegex(ValueError,'Terminal'):terminal(dict(final,status='RUNNING'),{'a':1})
    def test_another_cell_path_cannot_be_substituted(self):
        with self.assertRaisesRegex(ValueError,'path'):
            exact_path(self.cell['events'],self.root/'other'/'LANE_EVENTS.jsonl.gz')


if __name__=='__main__':
    unittest.main()
