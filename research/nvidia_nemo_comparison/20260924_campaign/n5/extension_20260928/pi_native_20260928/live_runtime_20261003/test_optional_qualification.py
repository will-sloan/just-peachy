"""Synthetic finite permit and drain contracts only; README.md."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import optional_refiner_qualification as admission
from profiles import RuntimeSelection,SessionPolicy


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.selection=RuntimeSelection('pyannote','redimnet','saved',allow_experimental=True,optional_d1_refiner=True)
        self.policy=SessionPolicy(60)
        self.pins=dict(candidate_content_sha256='0'*64,installed_manifest_sha256='1'*64,
            operational_binding_sha256='2'*64,selected_asset_inventory_sha256='3'*64)
        self.row=dict(schema=admission.SCHEMA,stage='initial',prior_production_pass_claimed=False,purpose='FIRST_COMBINED_MEASUREMENT_ONLY',production_eligible=False,
            prior_combined_pass_claimed=False,base_target='/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-08',base_content_sha256='0'*64,
            selection=self.selection.validate(),policy=self.policy.validate(),pins=self.pins,
            issued_unix=100,expires_unix=900,nonce='a'*32,boot_id='b'*36,unit='test.service',physical_ram_bytes=2048*admission.MIB,
            limits=dict(primary_as_bytes=768*admission.MIB,child_as_bytes=768*admission.MIB,
                whole_unit_rss_soft_stop_bytes=1024*admission.MIB,available_ram_floor_bytes=192*admission.MIB,
                initial_available_ram_bytes=1216*admission.MIB,child_physical_planning_reserve_bytes=256*admission.MIB,
                reserved_optional_output_bytes=4*admission.MIB,maximum_lag_seconds=30))
        self.context=dict(target=self.row['base_target'],now_unix=200,boot_id='b'*36,unit='test.service',unit_remaining_seconds=500,
            physical_ram_bytes=2048*admission.MIB,available_ram_bytes=1300*admission.MIB,whole_unit_rss_bytes=100*admission.MIB)
    def admit(self,phase='pre_primary',row=None,context=None):
        raw=admission.encoded(row or self.row)
        return admission.validate_permit(raw,hashlib.sha256(raw).hexdigest(),self.selection,self.policy,self.pins,context or self.context,phase)
    def test_first_measurement_requires_no_invented_prior_pass(self):
        result=self.admit();self.assertFalse(result['prior_combined_pass_claimed']);self.assertFalse(result['production_eligible'])
        for key in ('production_eligible','prior_combined_pass_claimed'):
            row=deepcopy(self.row);row[key]=True
            with self.assertRaises(ValueError):self.admit(row=row)
        row=deepcopy(self.row);row['schema']='just-peachy.pyannote-delayed-d1-admission.v1'
        with self.assertRaises(ValueError):self.admit(row=row)
    def test_as_limits_are_separate_from_actual_physical_budget(self):
        # 1300MiB available is below two AS ceilings plus floor, yet explicitly admitted.
        self.admit()
        child=dict(self.context,available_ram_bytes=500*admission.MIB,whole_unit_rss_bytes=600*admission.MIB)
        self.admit('pre_child',context=child)
        with self.assertRaises(MemoryError):self.admit('pre_child',context=dict(child,whole_unit_rss_bytes=800*admission.MIB))
        with self.assertRaises(MemoryError):self.admit(context=dict(self.context,available_ram_bytes=1200*admission.MIB))
        with self.assertRaises(MemoryError):self.admit('pre_child',context=dict(child,available_ram_bytes=440*admission.MIB))
    def test_changed_boot_unit_expiry_scope_and_physical_total_are_refused(self):
        for change in (dict(boot_id='wrong'),dict(unit='other.service'),dict(now_unix=900),dict(unit_remaining_seconds=5),dict(physical_ram_bytes=4096*admission.MIB)):
            with self.assertRaises(ValueError):self.admit(context=dict(self.context,**change))
        row=deepcopy(self.row);row['selection']['embedding']='titanet'
        with self.assertRaises(ValueError):self.admit(row=row)
        row=deepcopy(self.row);row['limits']['child_as_bytes']=512*admission.MIB
        with self.assertRaises(ValueError):self.admit(row=row)
    def test_current_production_style_validator_does_not_accept_qualification_permit(self):
        from optional_refiner_admission import validate_admission
        raw=admission.encoded(self.row)
        with self.assertRaises(ValueError):validate_admission(raw,hashlib.sha256(raw).hexdigest(),self.selection,self.policy,
            self.pins,1500*admission.MIB,physical_ram_bytes=2048*admission.MIB)
    def test_physical_soft_stop_uses_whole_unit_rss_and_one_hz_cache(self):
        import optional_refiner_resources as resources
        with tempfile.TemporaryDirectory(dir=os.environ['JP_BENCH_TEST_ROOT']) as output:
            snapshot=dict(at_monotonic=time.monotonic(),whole_unit_rss_bytes=1024*admission.MIB,
                          whole_unit_pss_bytes=800*admission.MIB,available_ram_bytes=300*admission.MIB)
            guard=resources.CombinedResourceGuard('test.service',Path(output)/'sample.jsonl',self.row['limits'])
            with mock.patch.object(resources,'snapshot',return_value=snapshot) as sampler:
                self.assertTrue(guard.exceeded());self.assertTrue(guard.exceeded());self.assertEqual(sampler.call_count,1)
                self.assertEqual((Path(output)/'sample.jsonl').read_bytes().count(b'\n'),1)

    def test_followup_full_policy_requires_actual_reviewed_same_runtime_feasibility(self):
        self.policy=SessionPolicy(300);self.row['policy']=self.policy.validate();self.context['unit_remaining_seconds']=700
        self.row.update(stage='followup_policy',purpose='FOLLOWUP_POLICY_MEASUREMENT_ONLY',prior_combined_pass_claimed=True)
        with self.assertRaises(ValueError):self.admit()
        evidence=dict(schema='just-peachy.optional-feasibility-review.v1',reviewed=True,production_eligible=False,
            selection=self.selection.validate(),candidate_content_sha256=self.pins['candidate_content_sha256'],
            operational_binding_sha256=self.pins['operational_binding_sha256'],followup_pins=self.pins,
            complete_primary_eof=True,complete_refiner_eof=True,all_models_closed=True,all_owners_dead=True,
            cgroup_empty=True,full_mirror_verified=True,allow_followup_policy_measurement=True,source_samples=715127,dropped_samples=0,
            execution=dict(path='/x/execution',sha256='1'*64),measurement=dict(path='/x/measurement',sha256='2'*64),closure=dict(path='/x/closure',sha256='3'*64))
        self.row['reviewed_feasibility']=evidence;self.admit()
        evidence['all_owners_dead']=False
        with self.assertRaises(ValueError):self.admit()

    def test_auth_only_promotion_hash_preserves_all_operational_settings(self):
        from optional_refiner_admission import operational_binding_sha256 as digest
        binding=dict(target='/frozen08',native_launch_enabled=True,authorization_kind='qualification',admission_sha256='1'*64,
            profiles={'selected':'pin'},live_config={'source':'mic'},gallery={'namespace':'E1'},storage_policy={'cap':123})
        promoted=dict(binding,authorization_kind='production',production_acceptance_sha256='2'*64)
        promoted.pop('admission_sha256')
        self.assertEqual(digest(binding),digest(promoted))
        for key in ('target','profiles','live_config','gallery','storage_policy'):
            changed=dict(promoted);changed[key]='changed'
            self.assertNotEqual(digest(binding),digest(changed))

    def test_permit_cannot_initialize_normal_ui_or_unowned_dispatch(self):
        from optional_refiner_admission import validate_requested_admission
        raw=admission.encoded(self.row)
        with mock.patch.dict(admission.STATE,{},clear=True),self.assertRaises(ValueError):
            validate_requested_admission(raw,hashlib.sha256(raw).hexdigest(),self.selection,self.policy,self.pins,
                1300*admission.MIB,physical_ram_bytes=2048*admission.MIB)
        from optional_refiner_dispatch import ui_eligibility,worker_options
        self.assertFalse(ui_eligibility({},self.selection,self.policy)[0])
        with self.assertRaises(ValueError):worker_options({},dict(optional_refiner_qualification={'x':1}),RuntimeSelection(),SessionPolicy(),None,None,{})

    def test_normal_reference_requires_exact_selection_policy_and_selected_inventory(self):
        import optional_refiner_dispatch as dispatch
        import release_authorization as release
        from optional_refiner_admission import operational_binding_sha256
        from test_optional_refiner import AdmissionTests
        fixture=AdmissionTests();fixture.setUp()
        binding=dict(target='/frozen08',candidate_content_sha256='1'*64,installed_manifest_sha256='1'*64)
        fixture.pins['operational_binding_sha256']=operational_binding_sha256(binding)
        raw=admission.encoded(fixture.value)
        ref=dict(selection=fixture.selection.validate(),policy=fixture.policy.validate(),
            path='/home/peachyprototype/JustPeachy/reviewed_optional.json',sha256=hashlib.sha256(raw).hexdigest(),asset_inventory_sha256='1'*64)
        receipt=dict(optional_refiner_admissions=[ref],assets=[])
        with mock.patch.object(release,'authorization',return_value=('production',receipt)),mock.patch.object(dispatch,'_raw',return_value=raw),             mock.patch.object(release,'selected_inventory_sha256',return_value='1'*64):
            self.assertTrue(dispatch.ui_eligibility(binding,fixture.selection,fixture.policy)[0])
            self.assertFalse(dispatch.ui_eligibility(binding,fixture.selection,SessionPolicy(60))[0])
            different=RuntimeSelection('pyannote','titanet','saved',allow_experimental=True,optional_d1_refiner=True)
            self.assertFalse(dispatch.ui_eligibility(binding,different,fixture.policy)[0])
        with mock.patch.object(release,'authorization',return_value=('production',receipt)),mock.patch.object(release,'selected_inventory_sha256',return_value='2'*64):
            self.assertFalse(dispatch.ui_eligibility(binding,fixture.selection,fixture.policy)[0])

    def test_selected_inventory_hash_ignores_unselected_extras_but_pins_all_required(self):
        import release_authorization as release
        selected=dict(path='/primary',resolved='/primary',bytes=10,sha256='1'*64)
        child=dict(path='/child',resolved='/child',bytes=20,sha256='2'*64)
        extra=dict(path='/other',resolved='/other',bytes=1,sha256='3'*64)
        with mock.patch.object(release,'required_assets',return_value=({'/primary':'1'*64,'/child':'2'*64},set())):
            first=release.selected_inventory_sha256({},self.selection,[selected,child])
            self.assertEqual(first,release.selected_inventory_sha256({},self.selection,[extra,child,selected]))
            with self.assertRaises(ValueError):release.selected_inventory_sha256({},self.selection,[selected])
            with self.assertRaises(ValueError):release.selected_inventory_sha256({},self.selection,[selected,dict(child,sha256='3'*64)])

    def test_gui_plan_exposes_only_explicit_reviewed_optional_selection(self):
        from native_gui_driver import validate_plan
        from launcher import selection_control_states
        chosen=validate_plan(self.selection.validate(),'inspect',5)
        self.assertTrue(chosen['optional_d1_refiner'])
        self.assertEqual(selection_control_states('pyannote','retained',True)['revision'],'normal')
        self.assertEqual(selection_control_states('pyannote','retained')['revision'],'disabled')

    def test_natural_eof_drain_preserves_prompt_stop_and_never_publishes_late_labels(self):
        from installed_engine import InstalledSession
        for stop in (False,True):
            session=InstalledSession.__new__(InstalledSession);session.failure=None;session.started=time.monotonic()
            session.policy=self.policy;session.engine=SimpleNamespace(state='COMPLETED');session.guard=lambda:None
            session.stop_event=mock.Mock();session.stop_event.is_set.return_value=stop
            supervisor=SimpleNamespace(done=False,failure=None)
            attachment=mock.Mock();attachment.supervisor=supervisor
            attachment.poll.side_effect=lambda **kwargs:setattr(supervisor,'done',True)
            attachment.close.return_value=dict(child_dead=True,supervisor_thread_closed=True,complete_eof=not stop)
            session.optional_refiner=attachment;session._close_optional()
            self.assertIsNone(session.optional_refiner);attachment.close.assert_called_once()
            if stop:attachment.poll.assert_not_called()
            else:attachment.poll.assert_called_once_with(publish_labels=False)


if __name__=='__main__':unittest.main()
