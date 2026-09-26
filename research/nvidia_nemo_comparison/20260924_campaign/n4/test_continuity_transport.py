"""Synthetic transport joins and saved native closure; never launch applications."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load, verify
from paced_child_admission import LEASE_SCHEMA
import review_continuity_transport as review
from test_paced_child_admission import fixture_input, fixture_permit
from test_native_journal_review import NativeJournalTests
import review_native_journal as journal
from delivery_review_fixtures import add_delivery
from paced_panel_plan_v3 import APPLICATION_POLICY

OUTPUT = None
SAVED = None
SOURCE = None


class TransportReviewTests(unittest.TestCase):
    def setUp(self):
        if OUTPUT is None: self.skipTest('Use the guarded probe with a fresh private output')
        self.root = OUTPUT/self._testMethodName; self.root.mkdir(parents=True)
        self.case_number = 0

    def fixture(self, *, frames=None):
        self.case_number += 1; base = self.root/str(self.case_number); folder = base/'cell'; folder.mkdir(parents=True)
        # These bytes are fixtures only and are never executed or loaded.
        for name in ('fixture.exe','continuity_application_runner.py'): (base/name).write_text('INERT TEST DATA',encoding='utf-8')
        exe = bind(base/'fixture.exe'); script = bind(base/'continuity_application_runner.py'); payload = fixture_input()
        payload['job']['audio_path']=str(base/'NEVER_OPENED.wav');payload['contract']['engine']='PrototypeEngine'
        payload['source_receipt']=SOURCE
        if frames is not None:payload['job']['frames']=frames
        # Real production code includes the preserved V1 dependency too. Only
        # the exact continuity filename may be selected as the executable script.
        (base/'paced_application_runner.py').write_text('PRESERVED INERT V1',encoding='utf-8')
        code=[script,bind(base/'paced_application_runner.py')]
        permit = fixture_permit(); permit['code'] = [script]; permit['output'] = str(folder/'application')
        permit['code']=code
        permit['state'] = str(base/'state'); coord_argv = ['inert','fixture']; permit['coordinator_argv_sha256'] = fingerprint(coord_argv)
        argv = [exe['path'],'-B',script['path'],'child','--permit',str(folder/'transport/PERMIT.json'),'--nonce',permit['nonce']]
        permit['application_argv_sha256'] = fingerprint(argv)
        freeze(folder/'transport/INPUT.json',payload); permit['input'] = bind(folder/'transport/INPUT.json')
        freeze(folder/'transport/PERMIT.json',permit)
        owner = permit['application']
        lifetime = dict(status='OWNED_PROCESS_LIFETIME_CLOSED',owner=owner,executable=exe,script=script,
            argv_sha256=fingerprint(argv),desktop=permit['desktop'],input_desktop_before='Default',input_desktop_after='Default',
            source_execution_authorized=False,resumed=True,forced=False,job_empty_verified=True,observed_members_exited=True,
            final_job=dict(active=0,total=2,terminated=0),root_exit_code=0,error=None,cleanup_errors=[],events=[
                dict(kind='spawned_suspended_and_assigned',monotonic=100.,owner=owner,affinity=[4],argv_sha256=fingerprint(argv),job=dict(active=1,total=1,terminated=0)),
                dict(kind='resumed_after_registration',monotonic=100.2),
                dict(kind='job_members_observed',monotonic=102.,members=[]),
                dict(kind='cancel_requested',monotonic=102.),
                dict(kind='all_observed_member_identities_exited',monotonic=102.,owners=[owner])])
        if frames is not None:
            for event in lifetime['events'][2:]:event['monotonic']=100.+frames/16000+3.
        freeze(folder/'transport/LIFETIME.json',lifetime); (folder/'transport/CANCEL').touch()
        freeze(folder/'transport/LEASE.json',dict(schema=LEASE_SCHEMA,status='ADMITTED',nonce=permit['nonce'],permit_sha256=fingerprint(permit),
            coordinator=permit['coordinator'],application=owner,supervised_run=permit['supervised_run'],sequence=3,issued_monotonic=101.))
        cell = dict(status='CELL_WITH_SOURCE_DELIVERY_CLOSED_REQUIRES_REVIEW',source_start_requested=True,errors=[],callback_errors=[],
            controller_closed=True,controller_worker_exited=True,source_to_widget_latency_qualified=False,complete_N4_acceptance=False,integrated_N4_cells=0)
        freeze(folder/'application/RESULT.json',cell)
        freeze(folder/'application/PREPARED.json',dict(status='PREPARED_NO_SOURCE_OR_MODELS_STARTED',desktop=permit['desktop'],
            contract=payload['contract'],job=payload['job'],runtimes=payload['runtimes'],gallery_preparation=payload['gallery_preparation'],
            logical_client=[480,800],active_height_px=184,no_auto_start=True,integrated_N4_cells=0,
            application_variant=APPLICATION_POLICY['variant'],delivery_policy=APPLICATION_POLICY['delivery']))
        freeze(folder/'transport/CHILD_RESULT.json',dict(status='COLLECTED_DELIVERY_APPLICATION_CELL_REQUIRES_REVIEW',owner=owner,
            input=permit['input'],error=None,cell_result=bind(folder/'application/RESULT.json'),integrated_N4_cells=0,N4_accepted=False))
        rows = [dict(**permit['coordinator'],affinity=[14],parent_pid=permit['supervisor']['pid'],executable=exe['path'],argv_sha256=fingerprint(coord_argv)),
            dict(**permit['supervisor'],affinity=[14],parent_pid=1)]
        slot = dict(coordinator=permit['coordinator'],supervised_run=permit['supervised_run'],census=dict(rows=rows,errors=[]),
            inventory=dict(errors=[],total_logical_bytes=1024),reservation_bytes=review.MAX_CELL_BYTES,cpu_affinity=[4],gpu=False,source_execution_authorized=False)
        fixture=NativeJournalTests();fixture.folder=folder/'application/data/sessions';fixture.folder.mkdir(parents=True)
        fixture.job=payload['job'];session,events=fixture.fixture();fixture.write(session,events)
        if frames is not None:
            # The shared native fixture is deliberately one second long. Only
            # this new synthetic long case replaces its terminal sample counts;
            # the immutable original fixture and production checks stay exact.
            path=session/'session_finalization_v3.json';final=load(path)
            final.update(source_samples=frames,identity_samples=frames)
            path.write_text(json.dumps(final,allow_nan=False),encoding='utf-8')
            duration=frames/16000
            for index,event in enumerate(events):
                cursor=max(0,index-1)*duration/4
                at=100.+cursor+.25*min(index,1)
                event['source_time_sec']=cursor
                event['payload'].update(publication_source_cursor_sec=cursor,publication_monotonic_sec=at)
                event['journal_write_monotonic_sec']=at+.02
            events[1]['payload']['source_epoch_monotonic_sec']=100.
            fixture.write(session,events)
            path=session/'s6d_consumer_closure.json';consumer=load(path)
            consumer['monotonic_sec']=100.+duration+2.
            path.write_text(json.dumps(consumer,allow_nan=False),encoding='utf-8')
        freeze(folder/'application/ENGINE_CLOSURE.json',dict(job=payload['job'],engine_class='PrototypeEngine',session=str(session)))
        add_delivery(folder,payload)
        freeze(folder/'NATIVE_JOURNAL_ENVELOPE.json',dict(schema='n4-cell-native-envelope-v1',cell_id=payload['cell_id'],
            job_sha256=fingerprint(payload['job']),engine_closure=bind(folder/'application/ENGINE_CLOSURE.json'),
            session=str(session.resolve()),review=journal.inspect(session,job=payload['job']),integrated_N4_cells=0,N4_accepted=False))
        freeze(folder/'COLLECTED.json',dict(status='COLLECTED_SOURCE_DELIVERY_PACED_CELL_REQUIRES_REVIEW',cell_id=payload['cell_id'],input=permit['input'],
            child_result=bind(folder/'transport/CHILD_RESULT.json'),lifetime=bind(folder/'transport/LIFETIME.json'),
            native_journal_envelope=bind(folder/'NATIVE_JOURNAL_ENVELOPE.json'),
            source_delivery_envelope=bind(folder/'SOURCE_DELIVERY_ENVELOPE.json'),application_policy=APPLICATION_POLICY,
            monitoring=dict(renewals=3,elapsed_seconds=1.8 if frames is None else frames/16000+2.8),slot_admission=slot,integrated_N4_cells=0,N4_accepted=False))
        freeze(folder/'PARENT_CLOSURE.json',dict(error=None,cleanup_error=None,lifecycle=lifetime,slot_release=dict(status='APPLICATION_SLOT_RELEASED',
            coordinator=permit['coordinator'],application=owner,child_cleanup_performed_by_guard=False,source_execution_authorized=False),integrated_N4_cells=0,N4_accepted=False))
        args = dict(payload=payload,plan_sha256=permit['plan_sha256'],coordinator=permit['coordinator'],code=code,
            executable=exe,coordinator_argv=coord_argv,state=Path(permit['state']))
        return folder,args

    def rewrite_fixture(self,path,change):
        value=load(path);change(value);path.write_text(json.dumps(value,allow_nan=False),encoding='utf-8')

    def checked(self,folder,args):
        # Only synthetic PID existence is mocked; saved actual fixtures use fresh OS checks.
        with patch.object(review,'exact_process',return_value=None):return review.review_cell(folder,**args)

    def test_join_preserves_all_acceptance_and_history_limits(self):
        folder,args=self.fixture();result=self.checked(folder,args)
        self.assertEqual(result['status'],'PASS_CONTINUITY_TRANSPORT_NATIVE_AND_DELIVERY_JOINS_ONLY')
        self.assertEqual(result['process_review']['unobserved_assignment_count'],1)
        self.assertTrue(result['native_envelope_review']['complete_envelope'])
        self.assertEqual(result['native_envelope_review']['retained_events'],6)
        self.assertFalse(result['native_payload_semantics_reviewed'])
        self.assertTrue(result['delivery_trace_independently_parsed']);self.assertFalse(result['source_delivery_deadlines_accepted'])
        self.assertEqual(result['source_delivery_review']['summary']['records'],50)
        for field in ('full_lease_history_available','source_workers_archive_reviewed','viewport_reviewed','resources_reviewed',
            'accuracy_qualified','controlled_resources_qualified','source_to_widget_latency_qualified','N4_accepted'):self.assertIs(result[field],False)
        self.assertEqual(result['integrated_N4_cells'],0)
        freeze(self.root/'SYNTHETIC_REVIEW.json',result)

    def test_full_twenty_minute_trace_including_last_partial_chunk(self):
        frames=19308429;folder,args=self.fixture(frames=frames);result=self.checked(folder,args)
        summary=result['source_delivery_review']['summary']
        self.assertEqual(summary['successful_samples'],frames)
        self.assertEqual(summary['records'],(frames+319)//320)
        self.assertEqual(summary['planned_duration_seconds'],1206.7768125)
        self.assertTrue(summary['complete_source']);self.assertFalse(result['source_delivery_deadlines_accepted'])
        self.assertFalse(result['source_delivery_review']['deadline_or_continuity_accepted'])
        freeze(self.root/'SYNTHETIC_LONG_TRACE_REVIEW.json',result)

    def test_reconstructed_input_and_permit_do_not_alias(self):
        for relative,change in [
            ('transport/INPUT.json',lambda r:r['job'].update(tap='O1')),
            ('transport/PERMIT.json',lambda r:r.update(plan_sha256='f'*64)),
            ('transport/PERMIT.json',lambda r:r['application'].update(create_time=102.)),
            ('transport/PERMIT.json',lambda r:r.update(output=str(self.root/'foreign'))),
            ('transport/PERMIT.json',lambda r:r.update(nonce='f'*64)),
            ('transport/PERMIT.json',lambda r:r.update(coordinator_argv_sha256='f'*64))]:
            with self.subTest(relative=relative,change=change):
                folder,args=self.fixture();self.rewrite_fixture(folder/relative,change)
                with self.assertRaises(ValueError):self.checked(folder,args)

    def test_changed_bound_runner_refused(self):
        folder,args=self.fixture();Path(args['code'][0]['path']).write_text('CHANGED',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Binding changed'):self.checked(folder,args)

    def test_only_v1_runner_cannot_substitute(self):
        folder,args=self.fixture();args['code']=args['code'][1:]
        with self.assertRaisesRegex(ValueError,'fixed runner'):self.checked(folder,args)

    def test_changed_or_foreign_envelope_receipt_rejected_even_if_rebound(self):
        changes=[lambda r:r.update(cell_id='different'),lambda r:r.update(job_sha256='0'*64),
            lambda r:r['review'].update(retained_events=7),lambda r:r.update(session=str(self.root)),
            lambda r:r.update(N4_accepted=True)]
        for change in changes:
            with self.subTest(change=change):
                folder,args=self.fixture();self.rewrite_fixture(folder/'NATIVE_JOURNAL_ENVELOPE.json',change)
                self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(native_journal_envelope=bind(folder/'NATIVE_JOURNAL_ENVELOPE.json')))
                with self.assertRaisesRegex(ValueError,'independent reconstruction'):self.checked(folder,args)
        folder,args=self.fixture()
        self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r['native_journal_envelope'].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'envelope binding'):self.checked(folder,args)

    def test_native_truncation_cannot_pass_with_fresh_rebound_receipt(self):
        folder,args=self.fixture();path=folder/'application/data/sessions/session/events.jsonl'
        path.write_bytes(b''.join(path.read_bytes().splitlines(keepends=True)[3:]))
        self.rewrite_fixture(folder/'NATIVE_JOURNAL_ENVELOPE.json',lambda r:r.update(review=journal.inspect(path.parent,job=args['payload']['job'])))
        self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(native_journal_envelope=bind(folder/'NATIVE_JOURNAL_ENVELOPE.json')))
        with self.assertRaisesRegex(ValueError,'retained tail'):self.checked(folder,args)

    def test_active_coordinator_or_application_refused(self):
        for active_pid in (20,30):
            folder,args=self.fixture()
            with patch.object(review,'exact_process',side_effect=lambda who:object() if who['pid']==active_pid else None):
                with self.assertRaisesRegex(ValueError,'stopped panel|still active'):review.review_cell(folder,**args)

    def test_lifetime_failures_rejected_even_with_rebound_parent(self):
        changes=[lambda r:r.update(forced=True),lambda r:r.update(root_exit_code=1),lambda r:r.update(resumed=False),
            lambda r:r.update(input_desktop_after='Another'),lambda r:r['final_job'].update(active=1),
            lambda r:r['events'][0].update(affinity=[14]),lambda r:r['events'][1].update(monotonic=99.),
            lambda r:r['events'][-1].update(owners=[]),lambda r:r.update(cleanup_errors=['job'])]
        for change in changes:
            with self.subTest(change=change):
                folder,args=self.fixture();self.rewrite_fixture(folder/'transport/LIFETIME.json',change)
                self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(lifetime=bind(folder/'transport/LIFETIME.json')))
                self.rewrite_fixture(folder/'PARENT_CLOSURE.json',lambda r:r.update(lifecycle=load(folder/'transport/LIFETIME.json')))
                with self.assertRaises(ValueError):self.checked(folder,args)

    def test_final_lease_must_join_permit_monitoring_and_lifetime(self):
        for change in (lambda r:r.update(sequence=2),lambda r:r.update(issued_monotonic=99.),
            lambda r:r.update(permit_sha256='0'*64),lambda r:r.update(nonce='0'*64),lambda r:r.update(status='REVOKED')):
            folder,args=self.fixture();self.rewrite_fixture(folder/'transport/LEASE.json',change)
            with self.assertRaises(ValueError):self.checked(folder,args)

    def test_uncertain_competing_or_incomplete_slot_census_refused(self):
        for change in (lambda r:r['slot_admission']['census']['errors'].append({'kind':'AccessDenied'}),
            lambda r:r['slot_admission']['census']['rows'].pop(),
            lambda r:r['slot_admission']['census']['rows'][0].update(affinity=[4]),
            lambda r:r['slot_admission']['census']['rows'].append({'pid':40,'create_time':200.}),
            lambda r:r['slot_admission']['inventory'].update(total_logical_bytes=50*1024**3)):
            folder,args=self.fixture();self.rewrite_fixture(folder/'COLLECTED.json',change)
            with self.assertRaises(ValueError):self.checked(folder,args)

    def test_parent_release_must_match_application_and_normal_closure(self):
        for change in (lambda r:r.update(error='late failure'),lambda r:r.update(cleanup_error='job'),
            lambda r:r.update(slot_release=None),lambda r:r['slot_release']['application'].update(create_time=102.)):
            folder,args=self.fixture();self.rewrite_fixture(folder/'PARENT_CLOSURE.json',change)
            with self.assertRaises(ValueError):self.checked(folder,args)

    def test_child_and_prepared_application_must_match(self):
        for relative,change in [('transport/CHILD_RESULT.json',lambda r:r.update(error='failure')),
            ('application/PREPARED.json',lambda r:r['job'].update(tap='O1')),
            ('application/PREPARED.json',lambda r:r.update(logical_client=[800,480])),
            ('application/RESULT.json',lambda r:r.update(callback_errors=['late Tk error']))]:
            folder,args=self.fixture();self.rewrite_fixture(folder/relative,change)
            with self.assertRaises(ValueError):self.checked(folder,args)

    def test_missing_cancel_or_changed_collected_binding_refused(self):
        folder,args=self.fixture();(folder/'transport/CANCEL').write_bytes(b'not the zero-byte marker')
        with self.assertRaisesRegex(ValueError,'cancellation marker'):self.checked(folder,args)
        folder,args=self.fixture();self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r['child_result'].update(sha256='0'*64))
        with self.assertRaisesRegex(ValueError,'Collected receipt'):self.checked(folder,args)

    def test_bounded_records_reject_ambiguous_json(self):
        for text in ('{"x":1,"x":2}','{"x":NaN}','[]',' '* (review.MAX_JSON+1)):
            path=self.root/'invalid.json';path.write_text(text,encoding='utf-8')
            with self.assertRaises(ValueError):review.record(path,self.root)

    def test_saved_actual_native_closure_and_failure_classification(self):
        self.assertIsNotNone(SAVED);classified=[]
        for binding in SAVED:
            verify(binding);value=load(binding['path'])
            expected = value['root_exit_code']==0 and value['resumed'] and not value['forced']
            args=dict(owner=value['owner'],executable=value['executable'],script=value['script'],argv_sha256=value['argv_sha256'],desktop=value['desktop'],cpu=14)
            if expected:
                result=review.validate_lifetime(value,**args);self.assertEqual(result['status'],'PASS_RECORDED_NORMAL_PRIVATE_PROCESS_CLOSURE')
            else:
                with self.assertRaises(ValueError):review.validate_lifetime(value,**args)
            classified.append(dict(input=binding,normal_resumed_exit=bool(expected)))
        self.assertEqual(len(classified),7);self.assertEqual(sum(r['normal_resumed_exit'] for r in classified),2)
        freeze(self.root/'SAVED_CLASSIFICATIONS.json',dict(rows=classified,no_new_process_started=True))

    def test_rebound_delivery_envelope_cannot_replace_trace_reconstruction(self):
        for change in (lambda r:r.update(cell_id='foreign'),lambda r:r['review'].update(source_samples=1),
                lambda r:r['review']['summary'].update(records=1),lambda r:r.update(N4_accepted=True),
                lambda r:r['application_policy'].update(variant='old')):
            folder,args=self.fixture();self.rewrite_fixture(folder/'SOURCE_DELIVERY_ENVELOPE.json',change)
            self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(source_delivery_envelope=bind(folder/'SOURCE_DELIVERY_ENVELOPE.json')))
            with self.assertRaisesRegex(ValueError,'delivery envelope.*independent reconstruction'):self.checked(folder,args)

    def test_missing_changed_trace_or_foreign_capture_is_rejected(self):
        for change in ('truncated','foreign','fixture','origin'):
            folder,args=self.fixture();capture=folder/'application/delivery/CAPTURE.json'
            if change=='truncated':
                path=folder/'application/delivery/TRACE.bin';path.write_bytes(path.read_bytes()[:-1])
                self.rewrite_fixture(capture,lambda r:r.update(trace=bind(path)))
            if change=='foreign':self.rewrite_fixture(capture,lambda r:r.update(trace=r['observation']))
            if change in ('fixture','origin'):
                path=folder/'application/delivery/OBSERVATION.json'
                self.rewrite_fixture(path,lambda r:r.update(**({'test_seams_used':True} if change=='fixture' else {'source_origin_perf_counter':101.})))
                self.rewrite_fixture(capture,lambda r:r.update(observation=bind(path)))
            with self.subTest(change=change),self.assertRaises(ValueError):self.checked(folder,args)

    def test_old_status_policy_and_delivery_collection_binding_are_rejected(self):
        for relative,change in (
                ('transport/CHILD_RESULT.json',lambda r:r.update(status='COLLECTED_APPLICATION_CELL_REQUIRES_REVIEW')),
                ('application/RESULT.json',lambda r:r.update(status='CELL_CLOSED_REQUIRES_REVIEW')),
                ('application/PREPARED.json',lambda r:r.update(application_variant='old')),
                ('COLLECTED.json',lambda r:r.update(application_policy={})),
                ('COLLECTED.json',lambda r:r['source_delivery_envelope'].update(sha256='0'*64))):
            folder,args=self.fixture();self.rewrite_fixture(folder/relative,change)
            with self.subTest(relative=relative),self.assertRaises(ValueError):self.checked(folder,args)
