"""Pure and live-refusal child gate tests. Use the guarded probe entry point."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import psutil
from common import bind, freeze
from metric_process import identity
from paced_child_admission import (ChildAdmission, EXECUTION_POLICY, INPUT_FIELDS, LEASE_SCHEMA, SCHEMA,
    assert_plain_path, bounded_json, validate_input, validate_lease, validate_permit, write_lease)


def fixture_permit():
    return dict(schema=SCHEMA, status='ADMITTED_SINGLE_APPLICATION_CHILD', nonce='a'*64,
        coordinator=dict(pid=20, create_time=100.), application=dict(pid=30, create_time=101.),
        supervisor=dict(pid=10, create_time=99.), supervised_run='synthetic-test-not-production',
        coordinator_argv_sha256='b'*64, application_argv_sha256='c'*64, desktop='codex-n1-n4-'+'d'*32,
        plan_sha256='e'*64, input={}, output='unused', state='unused', code=[{}])


def fixture_input():
    return dict(schema='n4-paced-cell-input-v1', cell_id='fixture_only',
        job=dict(job_id='fixture', audio_path='not-opened.wav', audio_sha256='0'*64, frames=16000,
            sample_rate_hz=16000, gain=1, reset_between_scenes=True, tap='O0'),
        contract=dict(mode='open_with_names'), execution=deepcopy(EXECUTION_POLICY), source_receipt={}, catalog={},
        runtimes=[dict(path='n2_runtime.json'),dict(path='n3_runtime.json')], gallery_preparation={},
        models_root='NO_MODEL_PAYLOAD', assets=[{}], source_execution_authorized=False, remaining_gate='Fixture only')


def fixture_lease(permit):
    return dict(schema=LEASE_SCHEMA, status='ADMITTED', nonce=permit['nonce'], permit_sha256='f'*64,
        coordinator=permit['coordinator'], application=permit['application'], supervised_run=permit['supervised_run'],
        sequence=3, issued_monotonic=100.)


class ChildAdmissionTests(unittest.TestCase):
    def permit_check(self, value):
        baseline=fixture_permit()
        return validate_permit(value, nonce=baseline['nonce'], application=baseline['application'],
            parent=baseline['coordinator'], desktop=baseline['desktop'])

    def lease_check(self, value, *, now=102., previous=2):
        return validate_lease(value, fixture_permit(), 'f'*64, now_monotonic=now, previous_sequence=previous)

    def test_input_truth_and_policy_firewall(self):
        self.assertEqual(set(fixture_input()), INPUT_FIELDS); validate_input(fixture_input())
        for field in ('truth', 'transcript', 'selection', 'report', 'speaker_positions'):
            value=fixture_input(); value[field]={}
            with self.assertRaises(ValueError): validate_input(value)
        for change in ('execution','source_execution_authorized','gain','mode','assets'):
            value=fixture_input()
            if change=='execution': value['execution']['cells_concurrent']=2
            elif change=='gain': value['job']['gain']=1.4125
            elif change=='mode': value['contract']['mode']='selected_closed'
            elif change=='assets': value['assets']=[]
            else:value[change]=True
            with self.assertRaises(ValueError): validate_input(value)

    def test_permit_exact_identity_and_desktop(self):
        self.permit_check(fixture_permit())
        for change in ('application','coordinator','desktop','nonce','role_alias'):
            value=fixture_permit()
            if change in ('application','coordinator'):value[change]['create_time']+=.001
            elif change=='desktop':value['desktop']='Default'
            elif change=='nonce':value['nonce']='9'*64
            else:value['supervisor']=deepcopy(value['coordinator'])
            with self.assertRaises(ValueError):self.permit_check(value)

    def test_permit_bounds_and_digests(self):
        for change in ('code','digest','extra','nan'):
            value=fixture_permit()
            if change=='code':value['code']=[{}]*129
            elif change=='digest':value['plan_sha256']='bad'
            elif change=='extra':value['truth']=True
            else:value['supervisor']['create_time']=float('nan')
            with self.assertRaises(ValueError):self.permit_check(value)

    def test_lease_monotonic_expiry_and_future(self):
        value=fixture_lease(fixture_permit())
        self.assertEqual(self.lease_check(value,now=105.),3)
        for now in (105.001,99.,float('nan')):
            with self.assertRaises(ValueError):self.lease_check(value,now=now)
        for issued in (float('inf'),float('nan'),True):
            changed=deepcopy(value);changed['issued_monotonic']=issued
            with self.assertRaises(ValueError):self.lease_check(changed)

    def test_lease_owner_nonce_run_and_rollback(self):
        value=fixture_lease(fixture_permit()); self.assertEqual(self.lease_check(value,previous=3),3)
        with self.assertRaises(ValueError):self.lease_check(value,previous=4)
        for field,new in [('nonce','0'*64),('status','REVOKED'),('supervised_run','other'),('permit_sha256','0'*64),
                          ('coordinator',dict(pid=20,create_time=999.)),('application',dict(pid=30,create_time=999.)),('sequence',True)]:
            changed=deepcopy(value);changed[field]=new
            with self.assertRaises(ValueError):self.lease_check(changed)

    def test_record_read_bounds(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'record.json';path.write_text('{"okay":true}',encoding='utf-8')
            self.assertEqual(bounded_json(path,100),{'okay':True})
            with self.assertRaises(ValueError):bounded_json(path,2)

    def test_output_containment(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.assertEqual(assert_plain_path(root/'fresh/application',root),(root/'fresh/application').resolve())
            with self.assertRaises(ValueError):assert_plain_path(root.parent/'outside',root)

    def test_actual_helper_refused_before_source_or_input_reads(self):
        process=psutil.Process();self.assertEqual(process.cpu_affinity(),[14])
        with tempfile.TemporaryDirectory() as temp:
            value=fixture_permit();value['application']=identity(process);value['coordinator']=identity(process.parent())
            value['supervisor']=dict(pid=2147483647,create_time=1.)
            path=Path(temp)/'PERMIT.json';freeze(path,value)
            with self.assertRaisesRegex(ValueError,'already be pinned to CPU4'):
                ChildAdmission(path,nonce=value['nonce'],desktop=value['desktop'],expected_code=[])
            self.assertEqual({p.name for p in Path(temp).iterdir()},{'PERMIT.json'})

    def test_foreign_helper_cannot_renew(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'LEASE.json'
            with self.assertRaisesRegex(ValueError,'Only exact CPU14 coordinator'):
                write_lease(path,fixture_permit(),'f'*64,0)
            self.assertFalse(path.exists())
