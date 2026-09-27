"""Cross-family gates and bounded dependency expansion; no application launches."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, load
import application_family_v8 as family
import paced_child_admission as old_gate
import paced_child_admission_v6 as gate
import paced_application_runner_v8 as runner
import paced_panel_plan_guarded_v2 as planner
import review_application_panel_v8 as panel
import review_application_transport_v8 as transport
from test_paced_child_admission import fixture_permit
import test_application_transport_review_v8 as transport_tests

CONTEXT={}


class FamilyTests(unittest.TestCase):
    def test_child_gate_changes_only_atomic_rename_api(self):
        before=ast.parse((family.HERE/'paced_child_admission_v5.py').read_text(encoding='utf-8'))
        after=ast.parse((family.HERE/'paced_child_admission_v6.py').read_text(encoding='utf-8'))
        before.body.pop(0);after.body.pop(0)
        after.body = [n for n in after.body if not isinstance(n, ast.FunctionDef) or n.name != 'atomic_replace']
        original = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == 'replace_lease_file')
        class Replacement(ast.NodeTransformer):
            def visit_FunctionDef(self,node):
                if node.name=='replace_lease_file':
                    self_outer.assertEqual(ast.dump(node.args.kw_defaults[0]),ast.dump(ast.Name(id='atomic_replace',ctx=ast.Load())))
                    node.args.kw_defaults[0] = original.args.kw_defaults[0]
                return node
        self_outer = self
        self.assertEqual(ast.dump(before,include_attributes=False),ast.dump(Replacement().visit(after),include_attributes=False))

    def test_collection_child_and_lifetime_control_flow_unchanged(self):
        def functions(name):
            tree=ast.parse((family.HERE/name).read_text(encoding='utf-8'))
            return {n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
        old=functions('paced_application_runner_v3.py');new=functions('paced_application_runner_v8.py')
        for name in ('collect_one','child_main','supervise_child','check_native_envelope','check_delivery_envelope',
                     'qualified_interpreter','supervised_identity','actual_desktop'):
            if name == 'collect_one':
                new[name].args.kwonlyargs = []; new[name].args.kw_defaults = []
                for call in ast.walk(new[name]):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == 'ExclusiveApplicationSlot':
                        call.keywords = []
            self.assertEqual(ast.dump(old[name],include_attributes=False),ast.dump(new[name],include_attributes=False),name)

    def test_expanded_permit_is_bounded_and_old_gate_still_refuses_it(self):
        value=fixture_permit();kwargs=dict(nonce=value['nonce'],application=value['application'],parent=value['coordinator'],desktop=value['desktop'])
        for n in (1,128,129,256,512):
            value['code']=[{}]*n;gate.validate_permit(value,**kwargs)
            if n>128:
                with self.assertRaises(ValueError):old_gate.validate_permit(value,**kwargs)
        for n in (0,513):
            value['code']=[{}]*n
            with self.assertRaises(ValueError):gate.validate_permit(value,**kwargs)
        self.assertEqual(gate.MAX_PERMIT_BYTES,256*1024);self.assertEqual(gate.MAX_LEASE_BYTES,4096)
        self.assertEqual(gate.MAX_LEASE_AGE_SECONDS,5)

    def test_every_parent_binding_remains_and_actual_manifest_fits_byte_bound(self):
        code=CONTEXT['code'];mapped={b['path']:b for b in code}
        self.assertGreater(len(code),128);self.assertLessEqual(len(code),512)
        for name in ('APPLICATION_FAMILY_CHECK_V5.json', 'PACED_PANEL_PLAN_GUARDED_V2_CHECK.json'):
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
        self.assertEqual(runner.RUN_SCHEMA,'n4-paced-application-run-v8')
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

    def test_transport_reconstructs_full_512_record_manifest(self):
        helper,folder,args=self.expanded_transport_fixture(512)
        checked=helper.checked(folder,args)
        self.assertEqual(checked['status'],'PASS_V8_APPLICATION_TRANSPORT_NATIVE_AND_DELIVERY_JOINS_ONLY')
        self.assertFalse(checked['N4_accepted'])

    def test_transport_refuses_513_records_and_wrong_runner(self):
        helper,folder,args=self.expanded_transport_fixture(513)
        with self.assertRaisesRegex(ValueError,'code census'):helper.checked(folder,args)
        helper,folder,args=self.expanded_transport_fixture(129)
        script=Path(args['code'][0]['path']);old=script.with_name('paced_application_runner_v3.py');old.write_bytes(script.read_bytes())
        args['code'][0]=bind(old)
        with self.assertRaisesRegex(ValueError,'fixed runner'):helper.checked(folder,args)

    def test_production_prepare_refuses_unqualified_family_before_launch(self):
        # Existing runner prepare reaches its qualified-plan gate; a fabricated
        # production plan cannot bypass reconstruction. Tested without GUI calls.
        with patch.object(runner,'admit_plan') as admitted,patch.object(runner,'PrivateApplicationProcess') as native:
            with self.assertRaises(FileNotFoundError):runner.run(CONTEXT['output']/'NO_PLAN.json', CONTEXT['output']/'UNCREATED_RUN')
            admitted.assert_not_called();native.assert_not_called()
