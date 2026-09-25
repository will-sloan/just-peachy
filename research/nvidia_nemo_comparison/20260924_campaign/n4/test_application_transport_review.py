"""Synthetic transport joins and saved native closure; never launch applications."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load, verify
from paced_child_admission import LEASE_SCHEMA
import review_application_transport as review
from test_paced_child_admission import fixture_input, fixture_permit

OUTPUT = None
SAVED = None


class TransportReviewTests(unittest.TestCase):
    def setUp(self):
        if OUTPUT is None: self.skipTest('Use the guarded probe with a fresh private output')
        self.root = OUTPUT/self._testMethodName; self.root.mkdir(parents=True)
        self.case_number = 0

    def fixture(self):
        self.case_number += 1; base = self.root/str(self.case_number); folder = base/'cell'; folder.mkdir(parents=True)
        # These bytes are fixtures only and are never executed or loaded.
        for name in ('fixture.exe','paced_application_runner.py'): (base/name).write_text('INERT TEST DATA',encoding='utf-8')
        exe = bind(base/'fixture.exe'); script = bind(base/'paced_application_runner.py'); payload = fixture_input()
        permit = fixture_permit(); permit['code'] = [script]; permit['output'] = str(folder/'application')
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
        freeze(folder/'transport/LIFETIME.json',lifetime); (folder/'transport/CANCEL').touch()
        freeze(folder/'transport/LEASE.json',dict(schema=LEASE_SCHEMA,status='ADMITTED',nonce=permit['nonce'],permit_sha256=fingerprint(permit),
            coordinator=permit['coordinator'],application=owner,supervised_run=permit['supervised_run'],sequence=3,issued_monotonic=101.))
        cell = dict(status='CELL_CLOSED_REQUIRES_REVIEW',source_start_requested=True,errors=[],callback_errors=[],
            controller_closed=True,controller_worker_exited=True,source_to_widget_latency_qualified=False,complete_N4_acceptance=False,integrated_N4_cells=0)
        freeze(folder/'application/RESULT.json',cell)
        freeze(folder/'application/PREPARED.json',dict(status='PREPARED_NO_SOURCE_OR_MODELS_STARTED',desktop=permit['desktop'],
            contract=payload['contract'],job=payload['job'],runtimes=payload['runtimes'],gallery_preparation=payload['gallery_preparation'],
            logical_client=[480,800],active_height_px=184,no_auto_start=True,integrated_N4_cells=0))
        freeze(folder/'transport/CHILD_RESULT.json',dict(status='COLLECTED_APPLICATION_CELL_REQUIRES_REVIEW',owner=owner,
            input=permit['input'],error=None,cell_result=bind(folder/'application/RESULT.json'),integrated_N4_cells=0,N4_accepted=False))
        rows = [dict(**permit['coordinator'],affinity=[14],parent_pid=permit['supervisor']['pid'],executable=exe['path'],argv_sha256=fingerprint(coord_argv)),
            dict(**permit['supervisor'],affinity=[14],parent_pid=1)]
        slot = dict(coordinator=permit['coordinator'],supervised_run=permit['supervised_run'],census=dict(rows=rows,errors=[]),
            inventory=dict(errors=[],total_logical_bytes=1024),reservation_bytes=review.MAX_CELL_BYTES,cpu_affinity=[4],gpu=False,source_execution_authorized=False)
        freeze(folder/'COLLECTED.json',dict(status='COLLECTED_SOURCE_PACED_CELL_REQUIRES_REVIEW',cell_id=payload['cell_id'],input=permit['input'],
            child_result=bind(folder/'transport/CHILD_RESULT.json'),lifetime=bind(folder/'transport/LIFETIME.json'),
            monitoring=dict(renewals=3,elapsed_seconds=1.8),slot_admission=slot,integrated_N4_cells=0,N4_accepted=False))
        freeze(folder/'PARENT_CLOSURE.json',dict(error=None,cleanup_error=None,lifecycle=lifetime,slot_release=dict(status='APPLICATION_SLOT_RELEASED',
            coordinator=permit['coordinator'],application=owner,child_cleanup_performed_by_guard=False,source_execution_authorized=False),integrated_N4_cells=0,N4_accepted=False))
        args = dict(payload=payload,plan_sha256=permit['plan_sha256'],coordinator=permit['coordinator'],code=[script],
            executable=exe,coordinator_argv=coord_argv,state=Path(permit['state']))
        return folder,args

    def rewrite_fixture(self,path,change):
        value=load(path);change(value);path.write_text(json.dumps(value,allow_nan=False),encoding='utf-8')

    def checked(self,folder,args):
        # Only synthetic PID existence is mocked; saved actual fixtures use fresh OS checks.
        with patch.object(review,'exact_process',return_value=None):return review.review_cell(folder,**args)

    def test_join_preserves_all_acceptance_and_history_limits(self):
        folder,args=self.fixture();result=self.checked(folder,args)
        self.assertEqual(result['status'],'PASS_APPLICATION_TRANSPORT_JOINS_ONLY')
        self.assertEqual(result['process_review']['unobserved_assignment_count'],1)
        for field in ('full_lease_history_available','source_workers_archive_reviewed','viewport_reviewed','resources_reviewed',
            'accuracy_qualified','controlled_resources_qualified','source_to_widget_latency_qualified','N4_accepted'):self.assertIs(result[field],False)
        self.assertEqual(result['integrated_N4_cells'],0)
        freeze(self.root/'SYNTHETIC_REVIEW.json',result)

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
