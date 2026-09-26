"""Cross-family gates and bounded dependency expansion; no application launches."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, load
import application_family_v4 as family
import paced_child_admission as old_gate
import paced_child_admission_v2 as gate
import paced_application_runner_v4 as runner
import paced_panel_plan_v4 as planner
import review_application_panel_v4 as panel
import review_application_transport_v4 as transport
from test_paced_child_admission import fixture_permit
import test_application_transport_review_v4 as transport_tests

CONTEXT={}


class FamilyTests(unittest.TestCase):
    def test_child_gate_changes_only_dependency_count(self):
        before=ast.parse((family.HERE/'paced_child_admission.py').read_text(encoding='utf-8'))
        after=ast.parse((family.HERE/'paced_child_admission_v2.py').read_text(encoding='utf-8'))
        before.body.pop(0);after.body.pop(0)
        class Cap(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                if node.name=='validate_permit':
                    for child in ast.walk(node):
                        if isinstance(child,ast.Constant) and child.value==256:child.value=128
                return node
        self.assertEqual(ast.dump(before,include_attributes=False),ast.dump(Cap().visit(after),include_attributes=False))

    def test_collection_child_and_lifetime_control_flow_unchanged(self):
        def functions(name):
            tree=ast.parse((family.HERE/name).read_text(encoding='utf-8'))
            return {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        old=functions('paced_application_runner_v3.py');new=functions('paced_application_runner_v4.py')
        for name in ('collect_one','child_main','supervise_child','check_native_envelope','check_delivery_envelope',
                     'qualified_interpreter','supervised_identity','actual_desktop'):
            self.assertEqual(ast.dump(old[name],include_attributes=False),ast.dump(new[name],include_attributes=False),name)

    def test_expanded_permit_is_bounded_and_old_gate_still_refuses_it(self):
        value=fixture_permit();kwargs=dict(nonce=value['nonce'],application=value['application'],parent=value['coordinator'],desktop=value['desktop'])
        for n in (1,128,129,256):
            value['code']=[{}]*n;gate.validate_permit(value,**kwargs)
            if n>128:
                with self.assertRaises(ValueError):old_gate.validate_permit(value,**kwargs)
        for n in (0,257):
            value['code']=[{}]*n
            with self.assertRaises(ValueError):gate.validate_permit(value,**kwargs)
        self.assertEqual(gate.MAX_PERMIT_BYTES,256*1024);self.assertEqual(gate.MAX_LEASE_BYTES,4096)
        self.assertEqual(gate.MAX_LEASE_AGE_SECONDS,5)

    def test_every_parent_binding_remains_and_actual_manifest_fits_byte_bound(self):
        code=CONTEXT['code'];mapped={b['path']:b for b in code}
        self.assertGreater(len(code),128);self.assertLessEqual(len(code),256)
        for name in family.PARENTS:
            q=load(family.HERE/name)
            for b in [bind(family.HERE/name),*q['code']]:self.assertEqual(mapped[b['path']],b)
        permit=fixture_permit();permit['code']=code
        self.assertLess(len(json.dumps(permit,indent=2,ensure_ascii=False).encode('utf-8')),gate.MAX_PERMIT_BYTES)
        self.assertEqual(runner.code_bindings(),panel.code_bindings())

    def test_matching_planner_and_child_gate_are_wired_without_policy_change(self):
        self.assertIs(runner.admit_plan,planner.admit_plan);self.assertIs(panel.admit_plan,planner.admit_plan)
        self.assertIs(runner.execution_payload,planner.execution_payload);self.assertIs(panel.execution_payload,planner.execution_payload)
        self.assertIs(runner.ChildAdmission,gate.ChildAdmission)
        self.assertEqual(runner.APPLICATION_POLICY,planner.APPLICATION_POLICY)
        self.assertEqual(runner.RUN_SCHEMA,'n4-paced-application-run-v4')
        self.assertIs(transport.validate_permit,gate.validate_permit)

    def expanded_transport_fixture(self,count):
        helper=transport_tests.TransportReviewTests();helper.root=CONTEXT['output']/('expanded-'+str(count));helper.root.mkdir()
        helper.case_number=0;folder,args=helper.fixture()
        # Bind inert metadata files only; no executable or audio is opened.
        for i in range(count-len(args['code'])):
            path=helper.root/f'dep-{i:03d}.txt';path.write_text('INERT DEPENDENCY FIXTURE',encoding='utf-8');args['code'].append(bind(path))
        permit_path=folder/'transport/PERMIT.json';permit=load(permit_path);permit['code']=args['code']
        permit_path.write_text(json.dumps(permit),encoding='utf-8')
        lease_path=folder/'transport/LEASE.json';lease=load(lease_path);lease['permit_sha256']=fingerprint(permit)
        lease_path.write_text(json.dumps(lease),encoding='utf-8')
        return helper,folder,args

    def test_transport_reconstructs_full_256_record_manifest(self):
        helper,folder,args=self.expanded_transport_fixture(256)
        checked=helper.checked(folder,args)
        self.assertEqual(checked['status'],'PASS_V4_APPLICATION_TRANSPORT_NATIVE_AND_DELIVERY_JOINS_ONLY')
        self.assertFalse(checked['N4_accepted'])

    def test_transport_refuses_257_records_and_wrong_runner(self):
        helper,folder,args=self.expanded_transport_fixture(257)
        with self.assertRaisesRegex(ValueError,'code census'):helper.checked(folder,args)
        helper,folder,args=self.expanded_transport_fixture(129)
        script=Path(args['code'][0]['path']);old=script.with_name('paced_application_runner_v3.py');old.write_bytes(script.read_bytes())
        args['code'][0]=bind(old)
        with self.assertRaisesRegex(ValueError,'fixed runner'):helper.checked(folder,args)

    def test_production_prepare_refuses_unqualified_family_before_launch(self):
        # Existing runner prepare reaches its qualified-plan gate; a fabricated
        # production plan cannot bypass reconstruction. Tested without GUI calls.
        with patch.object(runner,'admit_plan') as admitted,patch.object(runner,'PrivateApplicationProcess') as native:
            with self.assertRaises(FileNotFoundError):runner.run(CONTEXT['output']/'NO_ADMISSION.json')
            admitted.assert_not_called();native.assert_not_called()
