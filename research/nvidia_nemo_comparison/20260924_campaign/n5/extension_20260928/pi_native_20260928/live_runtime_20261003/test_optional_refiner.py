"""Pure host contracts; no native worker/model launch. See README_OPTIONAL_REFINER.md."""
from collections import deque
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import optional_refiner as subject

from optional_refiner import JournalRPC,OptionalD1Refiner
from optional_refiner_admission import validate_admission,SCHEMA,MIB
from optional_refiner_labels import RefinerLabelBridge,exclusive_union
from optional_refiner_protocol import Channel,BLOCK_SAMPLES
from profiles import RuntimeSelection,SessionPolicy


def row(number,start,end,track=None,*,seen=100.,revision='r1',event=None):
    identifier='session/u'+str(number)
    history=[] if track is None else [dict(event_id=event or 'primary:'+str(number),track_id=track,
        label='Speaker '+track,source_evidence_span=[start,end],identity_version=[100.,number])]
    return dict(session_id='session',utterance_id='u'+str(number),caption_key=identifier,
        text='unchanged words',display_text='Unchanged words.',text_revision_id=revision,
        source_start_sec=start,source_end_sec=end,
        word_spans=[dict(id=identifier+'/token1',source_start_sec=start,source_end_sec=end,
                         first_seen_monotonic_sec=seen,speaker_history=history)],
        segments=[] if track is None else [dict(track_id=track,anonymous_label='Speaker '+track)])


class LabelTests(unittest.TestCase):
    def test_independent_permutation_revision_targets_and_no_duplicates(self):
        bridge=RefinerLabelBridge('session','source',30)
        bridge.append(0,bytes([2]*100+[1]*100+[2]*100),48000)
        rows=[row(1,0,1,'track-A'),row(2,1,2,'track-B'),row(3,2,3)]
        before=deepcopy(rows)
        events=bridge.revisions(rows,watermark=48000,now=110.)
        self.assertEqual(len(events),1)
        self.assertEqual(bridge.last_mapping,{'0':'track-B','1':'track-A'})
        self.assertEqual(events[0]['replacement_tracker_id'],'track-A')
        self.assertEqual(events[0]['target_span_ids'],['session/u3/token1'])
        self.assertEqual(events[0]['target_text_revision_id'],'r1')
        self.assertFalse(events[0]['changes_raw_words'])
        self.assertIsNone(events[0]['latest_known_name'])
        self.assertEqual(rows,before)
        self.assertEqual(bridge.revisions(rows,watermark=48000,now=111.),[])
        rows[2]['text_revision_id']='r2'
        self.assertEqual(len(bridge.revisions(rows,watermark=48000,now=112.)),1)

    def test_overlap_stale_foreign_and_own_feedback_abstain(self):
        bridge=RefinerLabelBridge('session','source',30)
        bridge.append(0,bytes([1]*100+[3]*100+[1]*100),48000)
        rows=[row(1,0,1,'A'),row(2,1,2),row(3,2,3,seen=10.)]
        self.assertEqual(bridge.revisions(rows,watermark=48000,now=110.),[])
        rows[0]['word_spans'][0]['speaker_history'][0]['event_id']='optional-d1:1'
        rows[2]['word_spans'][0]['first_seen_monotonic_sec']=100.
        self.assertEqual(bridge.revisions(rows,watermark=48000,now=111.),[])
        rows[0]['session_id']='foreign'
        with self.assertRaises(ValueError):bridge.revisions(rows,watermark=48000,now=112.)

    def test_conflicting_or_duplicate_anchor_intervals_are_not_double_votes(self):
        self.assertEqual(exclusive_union([(0,100,'A'),(0,100,'A'),(40,60,'B')]),[(0,40,'A'),(60,100,'A')])
        bridge=RefinerLabelBridge('session','source',1)
        bridge.append(0,bytes([1]*100),16000)
        bridge.advance(32000)
        self.assertEqual(list(bridge.runs),[])
        with self.assertRaises(ValueError):bridge.append(0,b'\x01',32160)

    def test_primary_poll_never_waits_for_native_worker(self):
        refiner=OptionalD1Refiner.__new__(OptionalD1Refiner)
        refiner.lock=threading.Lock();refiner.activity=deque();refiner.messages=deque()
        refiner.bridge=RefinerLabelBridge('session','source',30)
        refiner.journal=SimpleNamespace(committed_samples=16000)
        refiner.failure=None
        # There is deliberately no process/thread/native API on this object.
        start=time.perf_counter()
        diagnostics,revisions=refiner.poll([row(1,0,1)],now=100.)
        self.assertEqual(revisions,[])
        self.assertEqual(diagnostics[0]['kind'],'optional_refiner_label_status')
        self.assertLess(time.perf_counter()-start,.5)

    def test_alignment_proof_is_bounded_on_disk_not_repeated_in_each_caption(self):
        with tempfile.TemporaryDirectory(prefix='optional-proof-',dir=os.environ['JP_BENCH_TEST_ROOT']) as directory:
            refiner=OptionalD1Refiner.__new__(OptionalD1Refiner)
            refiner.lock=threading.Lock();refiner.messages=deque()
            refiner.activity=deque([(0,bytes([2]*100+[1]*100+[2]*100),48000)])
            refiner.bridge=RefinerLabelBridge('session','source',30)
            refiner.journal=SimpleNamespace(committed_samples=48000)
            refiner.output=Path(directory);refiner.alignment_bytes=0;refiner.failure=None
            refiner.stop_event=threading.Event()
            rows=[row(1,0,1,'A'),row(2,1,2,'B'),row(3,2,3)]
            _,events=refiner.poll(rows,now=110.)
            self.assertEqual(len(events),1)
            files=list((Path(directory)/'alignment').glob('*.json'))
            self.assertEqual(len(files),1)
            self.assertLessEqual(files[0].stat().st_size,32768)
            self.assertEqual(hashlib.sha256(files[0].read_bytes()).hexdigest(),events[0]['optional_refiner']['alignment_sha256'])
            self.assertNotIn('alignment',events[0]['optional_refiner'])
            self.assertLess(len(json.dumps(events[0])),4096)
            self.assertFalse(refiner.stop_event.is_set())


class JournalAndProtocolTests(unittest.TestCase):
    def test_continuous_small_reads_and_exact_eof(self):
        raw=b'\0'*((BLOCK_SAMPLES+7)*4)
        class Journal:
            max_read_samples=BLOCK_SAMPLES
            def __init__(self):self.spool=self
            def snapshot(self):return dict(committed_samples=len(raw)//4,finished=True,fatal_error=None)
            def read_processed(self,start,count):return raw[start*4:(start+count)*4]
        rpc=JournalRPC(Journal(),len(raw)//4)
        first=rpc.read(dict(kind='read',start_sample=0,maximum_samples=BLOCK_SAMPLES))
        self.assertEqual(len(base64.b64decode(first['audio'])),BLOCK_SAMPLES*4)
        second=rpc.read(dict(kind='read',start_sample=BLOCK_SAMPLES,maximum_samples=BLOCK_SAMPLES))
        self.assertEqual(len(base64.b64decode(second['audio'])),28)
        self.assertEqual(rpc.digest.hexdigest(),hashlib.sha256(raw).hexdigest())
        self.assertTrue(second['finished'])
        with self.assertRaises(ValueError):rpc.read(dict(kind='read',start_sample=0,maximum_samples=BLOCK_SAMPLES))

    def test_partial_frame_timeout_and_invalid_capacity(self):
        left,right=socket.socketpair();channel=Channel(left)
        try:
            raw=json.dumps({'kind':'read','start_sample':0}).encode()
            right.sendall(struct.pack('!I',len(raw))+raw[:2])
            self.assertIsNone(channel.receive())
            right.sendall(raw[2:]);self.assertEqual(channel.receive()['start_sample'],0)
            right.sendall(struct.pack('!I',65537))
            with self.assertRaises(ValueError):channel.receive()
        finally:channel.close();right.close()


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        # This fixture is explicitly synthetic and never launches a worker.
        self.selection=RuntimeSelection('pyannote','redimnet','saved',allow_experimental=True,optional_d1_refiner=True)
        selected=self.selection.validate()
        self.policy=SessionPolicy()
        self.pins={k:'1'*64 for k in ('candidate_content_sha256','installed_manifest_sha256','operational_binding_sha256','selected_asset_inventory_sha256')}
        owner=dict(pid=1,start_ticks=2,boot_id='00000000-0000-0000-0000-000000000000')
        self.value=dict(schema=SCHEMA,status='MEASURED_COMBINED_CM5_2GB_EXPERIMENTAL',synthetic=False,
            experimental_only=True,sustained_realtime_qualified=False,timing_reviewed=True,fallback_reviewed=True,
            selection=selected,policy=self.policy.validate(),pins=self.pins,refinement_profile='current_delayed',
            refinement_embedding='anonymous',cpus=[2,3],cpu_quota_percent=200,maximum_tasks=64,
            measurement_scope='whole_owned_unit',quality_qualified=False,
            measurement_receipt_sha256='2'*64,closure_receipt_sha256='3'*64,measurement_source_sha256='4'*64,
            qualified_binding_sha256='5'*64,qualified_package_manifest_sha256='6'*64,
            closure=dict(primary_models_closed=True,refiner_model_closed=True,all_owners_dead=True,cgroup_empty=True,leases_released=True,
                         full_mirror_verified=True,owners=[owner,dict(owner,pid=3)]),
            limits=dict(child_as_bytes=768*MIB,child_physical_reserve_bytes=320*MIB,whole_unit_rss_soft_stop_bytes=1024*MIB,
                        available_ram_floor_bytes=192*MIB,maximum_lag_seconds=30),
            measured=dict(total_ram_bytes=1920*MIB,audio_seconds=300,peak_combined_rss_bytes=500*MIB,peak_combined_pss_bytes=480*MIB,
                peak_child_virtual_bytes=400*MIB,peak_child_rss_bytes=200*MIB,minimum_available_ram_bytes=800*MIB,
                primary_source_phase_seconds=320,primary_matched_baseline_seconds=310,whole_unit_cpu_seconds=420,whole_unit_elapsed_seconds=350,
                maximum_primary_backlog_seconds=10,maximum_label_lag_seconds=25,
                refiner_uncovered_samples=0,refiner_disabled=False,refiner_complete_eof=True,refiner_restart_count=0,refiner_pause_count=0,
                cpu_measurement_scope="whole_owned_cgroup",timing_definition="paced source-origin to EOF; includes waits; CPU seconds separate",
                dropped_samples=0,complete_eof=True,continuous_source_clock=True,
                source_samples=4800000,primary_source_samples=4800000,refiner_source_samples=4800000,
                refiner_output_frames=30001))
    def verify(self,available=1000*MIB):
        raw=json.dumps(self.value).encode()
        return validate_admission(raw,hashlib.sha256(raw).hexdigest(),self.selection,self.policy,self.pins,available,
                                  physical_ram_bytes=1920*MIB)
    def test_exact_scope_policy_resource_and_complete_closure(self):
        self.assertEqual(self.verify()['schema'],SCHEMA)
        with self.assertRaises(ValueError):self.verify(700*MIB)
        self.value['measurement_scope']='component_only'
        with self.assertRaises(ValueError):self.verify()

    def test_reviewed_cpu_lag_fallback_does_not_require_invented_combined_rtf(self):
        measured=self.value['measured']
        measured.update(refiner_disabled=True,refiner_complete_eof=False,refiner_source_samples=1600000,
            refiner_output_frames=10000,refiner_uncovered_samples=3200000,refiner_fallback_reason='lag limit; primary retained',
            maximum_label_lag_seconds=31)
        self.value['closure']['refiner_model_closed']=False
        self.assertFalse(self.verify()['sustained_realtime_qualified'])
        measured['maximum_combined_rolling_rtf']=.5
        with self.assertRaises(ValueError):self.verify()

    def test_short_actual_evidence_can_only_be_reviewed_as_experimental(self):
        self.value['measured'].update(audio_seconds=44.6954375,source_samples=715127,primary_source_samples=715127,
            refiner_source_samples=715127,refiner_output_frames=4470)
        self.assertTrue(self.verify()['experimental_only'])
        self.value['sustained_realtime_qualified']=True
        with self.assertRaises(ValueError):self.verify()

    def test_distinct_optional_selection_is_default_off_and_fail_closed(self):
        self.assertFalse(RuntimeSelection().optional_d1_refiner)
        for kwargs in (dict(allow_experimental=False),dict(diarizer='nemotron',nemotron_profile='current_delayed'),
                       dict(refinement_profile='chunk52'),dict(provisional_correction=True)):
            values=dict(diarizer='pyannote',allow_experimental=True,optional_d1_refiner=True)
            values.update(kwargs)
            with self.assertRaises(ValueError):RuntimeSelection(**values).validate()

    def test_installed_engine_rejects_missing_admission_before_model_imports(self):
        from installed_engine import InstalledSession
        engine=InstalledSession.__new__(InstalledSession)
        engine.selection=self.selection
        engine.optional_refiner_options=None
        with self.assertRaisesRegex(RuntimeError,'measured combined native admission'):
            engine._validate_optional_refiner()

    def test_missing_or_synthetic_or_short_or_unclosed_receipt_fails(self):
        for field,value in (('synthetic',True),('closure',{}),('pins',{})):
            original=self.value[field];self.value[field]=value
            with self.assertRaises(ValueError):self.verify()
            self.value[field]=original
        self.value['measured']['audio_seconds']=44.7
        with self.assertRaises(ValueError):self.verify()

    def test_one_boot_and_actual_physical_memory_bounds_required(self):
        self.value['closure']['owners'][1]['boot_id']='11111111-1111-1111-1111-111111111111'
        with self.assertRaises(ValueError):self.verify()
        self.value['closure']['owners'][1]['boot_id']=self.value['closure']['owners'][0]['boot_id']
        self.value['measured']['peak_combined_rss_bytes']=3000*MIB
        with self.assertRaises(ValueError):self.verify()
        self.value['measured']['peak_combined_rss_bytes']=500*MIB
        self.value['measured']['total_ram_bytes']=2048*MIB
        with self.assertRaises(ValueError):self.verify()


class ChildLifecycleTests(unittest.TestCase):
    def test_exact_child_eof_and_close_without_loading_native(self):
        raw=b'\0'*(BLOCK_SAMPLES*4)
        owner=dict(pid=123,parent_pid=os.getpid(),start_ticks=456,boot_id='synthetic',affinity=[2,3])
        messages=deque([dict(kind='owner',owner=owner),dict(kind='ready',initialization_seconds=.01),
            dict(kind='read',start_sample=0,maximum_samples=BLOCK_SAMPLES),
            dict(kind='activity',frame_start=0,frame_end=0,received_samples=BLOCK_SAMPLES,masks='',final=False),
            dict(kind='activity',frame_start=0,frame_end=21,received_samples=BLOCK_SAMPLES,
                 masks=base64.b64encode(bytes([1]*21)).decode(),final=True),
            dict(kind='closed',owner=owner,delivered_samples=BLOCK_SAMPLES,output_frames=21,
                delivered_f32_sha256=hashlib.sha256(raw).hexdigest(),complete_eof=True,model_closed=True,failure=None)])
        class FakeChannel:
            def __init__(self,sock):self.sock=sock
            def send(self,value):pass
            def receive(self):return messages.popleft()
            def close(self):self.sock.close()
        class FakeProcess:
            pid=123;returncode=None
            def poll(self):return self.returncode
            def wait(self,timeout):self.returncode=0;return 0
        class Journal:
            max_read_samples=BLOCK_SAMPLES;committed_samples=BLOCK_SAMPLES
            def __init__(self):self.spool=self
            def snapshot(self):return dict(committed_samples=BLOCK_SAMPLES,finished=True,fatal_error=None)
            def read_processed(self,start,count):return raw[start*4:(start+count)*4]
        with tempfile.TemporaryDirectory(prefix='optional-life-',dir=os.environ['JP_BENCH_TEST_ROOT']) as directory:
            worker=OptionalD1Refiner.__new__(OptionalD1Refiner)
            worker.output=Path(directory);worker.admission=dict(limits=dict(child_as_bytes=768*MIB,maximum_lag_seconds=30,available_ram_floor_bytes=192*MIB))
            worker.policy=SessionPolicy();worker.unit='synthetic.service';worker.config={}
            worker.resource_guard=SimpleNamespace(exceeded=lambda:False,last=None)
            worker.journal=Journal();worker.rpc=JournalRPC(worker.journal,4800000)
            worker.started=time.monotonic();worker.stop_event=threading.Event();worker.lock=threading.Lock()
            worker.ready=worker.done=False;worker.failure=worker.child_owner=worker.child_result=None
            worker.frames=worker.received=worker.diagnostic_drops=0
            worker.activity=deque(maxlen=8);worker.messages=deque(maxlen=32)
            with patch.object(subject,'Channel',FakeChannel),patch.object(subject,'available_ram',return_value=1500*MIB),patch.object(subject.subprocess,'Popen',return_value=FakeProcess()) as spawned:
                worker._run()
            self.assertIsNone(worker.failure)
            self.assertTrue(worker.closed_receipt['complete_eof'])
            self.assertTrue(worker.closed_receipt['child_dead'])
            self.assertEqual(worker.rpc.cursor,BLOCK_SAMPLES)
            self.assertEqual(worker.frames,21)
            self.assertFalse(spawned.call_args.kwargs['start_new_session'])
            self.assertEqual(len(spawned.call_args.kwargs['pass_fds']),1)
            self.assertTrue((Path(directory)/'CLOSURE.json').is_file())

    def test_stuck_exact_child_is_terminated_then_killed_and_reaped(self):
        class FakeProcess:
            returncode=None
            terminated=killed=False
            def poll(self):return self.returncode
            def wait(self,timeout):
                if self.killed:self.returncode=-9;return -9
                raise subprocess.TimeoutExpired('synthetic',timeout)
            def terminate(self):self.terminated=True
            def kill(self):self.killed=True
        worker=OptionalD1Refiner.__new__(OptionalD1Refiner)
        worker.process=FakeProcess();worker.done=False;worker.failure=None
        worker._reap()
        self.assertTrue(worker.process.terminated and worker.process.killed)
        self.assertEqual(worker.process.returncode,-9)
        self.assertIn('exited -9',worker.failure)
if __name__=='__main__':unittest.main()
