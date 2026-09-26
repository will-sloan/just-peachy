"""Adversarial synthetic transport fixtures; paired leaf review is mocked."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from common import bind, fingerprint, freeze, load
from test_restart_child import payload as restart_payload
import test_application_transport_review as prior
import review_application_transport as original
import review_restart_transport as subject
from restart_application_cell import POLICY
from restart_application_runner import CHILD_SUCCESS, COLLECTED

OUTPUT=None
SAVED=[]


class RestartTransportTests(prior.TransportReviewTests):
    def setUp(self):
        self.root=OUTPUT/self._testMethodName;self.root.mkdir();self.case_number=0;self.expected={}

    def fixture(self):
        folder,args=super().fixture();base=folder.parent;payload=restart_payload()
        for name in ('restart_application_child.py','restart_application_runner.py'):
            (base/name).write_text('INERT RESTART TEST DATA',encoding='utf-8')
        script=bind(base/'restart_application_child.py');code=[script];parent=[script,bind(base/'restart_application_runner.py')]
        self.rewrite_fixture(folder/'transport/INPUT.json',lambda r:(r.clear(),r.update(payload)))
        permit=load(folder/'transport/PERMIT.json');permit.update(code=code,input=bind(folder/'transport/INPUT.json'))
        argv=[args['executable']['path'],'-B',script['path'],'--permit',str(folder/'transport/PERMIT.json'),'--nonce',permit['nonce']]
        permit['application_argv_sha256']=fingerprint(argv)
        self.rewrite_fixture(folder/'transport/PERMIT.json',lambda r:(r.clear(),r.update(permit)))
        life=load(folder/'transport/LIFETIME.json');life.update(script=script,argv_sha256=fingerprint(argv))
        life['events'][0]['argv_sha256']=fingerprint(argv)
        self.rewrite_fixture(folder/'transport/LIFETIME.json',lambda r:(r.clear(),r.update(life)))
        self.rewrite_fixture(folder/'transport/LEASE.json',lambda r:r.update(permit_sha256=fingerprint(permit)))
        app=folder/'application';freeze(app/'PAIR_OBSERVATION.json',dict(synthetic=True))
        for n in ('01','02'):freeze(app/'sessions'/n/'RESULT.json',dict(synthetic=True))
        self.rewrite_fixture(app/'RESULT.json',lambda r:r.update(schema='n4-restart-application-cell-v1',policy=POLICY,
            status='COLLECTED_RESTART_PAIR_CLOSED_REQUIRES_REVIEW',completed_sessions=2,failure_delivery_capture=None,
            actual_restart_qualified=False,pair_observation=bind(app/'PAIR_OBSERVATION.json'),
            sessions=[bind(app/'sessions'/n/'RESULT.json') for n in ('01','02')]))
        self.rewrite_fixture(app/'PREPARED.json',lambda r:r.update(job=payload['job'],contract=payload['contract'],
            runtimes=payload['runtimes'],gallery_preparation=payload['gallery_preparation']))
        self.rewrite_fixture(folder/'transport/CHILD_RESULT.json',lambda r:r.update(status=CHILD_SUCCESS,input=permit['input'],
            cell_result=bind(app/'RESULT.json'),restart_control=subject.control(payload),actual_restart_qualified=False))
        pair=dict(status='PASS_COMPLETE_RESTART_PAIR_EVIDENCE_JOINS_ONLY',cell_id=payload['cell_id'],
            application_owner=permit['application'],cell_result=bind(app/'RESULT.json'),control=subject.control(payload),
            actual_restart_qualified=False,N4_accepted=False,integrated_N4_cells=0,
            evidence=[bind(app/'RESULT.json'),bind(app/'PAIR_OBSERVATION.json')],synthetic=True)
        freeze(folder/'PAIR_EVIDENCE_REVIEW.json',pair);self.expected[str(app)]=deepcopy(pair)
        with patch.object(original,'exact_process',return_value=None):
            process_review=original.validate_lifetime(life,owner=permit['application'],executable=args['executable'],
                script=script,argv_sha256=fingerprint(argv),desktop=permit['desktop'],cpu=4)
        self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(status=COLLECTED,cell_id=payload['cell_id'],input=permit['input'],
            child_result=bind(folder/'transport/CHILD_RESULT.json'),lifetime=bind(folder/'transport/LIFETIME.json'),
            lifetime_review=process_review,restart_control=subject.control(payload),application_policy=subject.APPLICATION_POLICY,
            parent_code_sha256=fingerprint(parent),child_code_sha256=fingerprint(code),actual_restart_qualified=False,
            independent_complete_transport_reviewed=False,pair_evidence_review=bind(folder/'PAIR_EVIDENCE_REVIEW.json')))
        self.rewrite_fixture(folder/'PARENT_CLOSURE.json',lambda r:r.update(lifecycle=life,actual_restart_qualified=False))
        args.update(payload=payload,code=code,parent_code=parent)
        return folder,args

    def leaf(self,app,**kwargs):return deepcopy(self.expected[str(app)])
    def checked(self,folder,args):
        with patch.object(subject,'exact_process',return_value=None),patch.object(original,'exact_process',return_value=None),\
             patch.object(subject,'review_pair',side_effect=self.leaf):return subject.review_cell(folder,**args)

    def test_join_preserves_all_acceptance_and_history_limits(self):
        folder,args=self.fixture();result=self.checked(folder,args)
        self.assertEqual(result['status'],'PASS_RESTART_TRANSPORT_AND_PAIR_JOINS_ONLY')
        self.assertEqual(result['process_review']['unobserved_assignment_count'],1)
        for field in ('full_lease_history_available','complete_process_history_available','viewport_rows_reviewed',
            'resource_samples_reviewed','actual_restart_qualified','source_to_widget_latency_qualified','N4_accepted'):
            self.assertIs(result[field],False)
        self.assertEqual(result['pair_review'],self.expected[str(folder/'application')])
        freeze(self.root/'SYNTHETIC_REVIEW.json',result)
    def test_active_coordinator_or_application_refused(self):
        for active in (20,30):
            folder,args=self.fixture();observe=lambda who:object() if who['pid']==active else None
            with patch.object(subject,'exact_process',side_effect=observe),patch.object(original,'exact_process',side_effect=observe),\
                 patch.object(subject,'review_pair',side_effect=self.leaf),self.assertRaises(ValueError):subject.review_cell(folder,**args)
    def test_saved_actual_native_closure_and_failure_classification(self):
        # Reuse the seven immutable native fixtures with their real fresh OS exit checks.
        with patch.object(prior,'SAVED',SAVED):super().test_saved_actual_native_closure_and_failure_classification()
    def test_parent_manifest_must_contain_the_exact_child_bindings(self):
        folder,args=self.fixture()
        for parent in ([],args['code']+args['code'],[dict(args['code'][0],sha256='0'*64)]):
            changed=dict(args,parent_code=parent)
            with self.assertRaises(ValueError):self.checked(folder,changed)
    def test_old_child_subcommand_and_parent_code_in_permit_rejected(self):
        for mode in ('argv','manifest'):
            folder,args=self.fixture()
            if mode=='argv':self.rewrite_fixture(folder/'transport/PERMIT.json',lambda r:r.update(application_argv_sha256='0'*64))
            else:self.rewrite_fixture(folder/'transport/PERMIT.json',lambda r:r.update(code=args['parent_code']))
            with self.assertRaises(ValueError):self.checked(folder,args)
    def test_pair_reread_must_match_saved_binding_and_content(self):
        for mode in ('binding','content','failure'):
            folder,args=self.fixture()
            if mode=='binding':self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(pair_evidence_review={}))
            elif mode=='content':
                self.rewrite_fixture(folder/'PAIR_EVIDENCE_REVIEW.json',lambda r:r.update(synthetic=False))
                self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(pair_evidence_review=bind(folder/'PAIR_EVIDENCE_REVIEW.json')))
            else:self.expected[str(folder/'application')]['actual_restart_qualified']=True
            with self.assertRaises(ValueError):self.checked(folder,args)
    def test_parent_review_and_restart_control_cannot_be_relabelled(self):
        for change in (dict(parent_code_sha256='0'*64),dict(child_code_sha256='0'*64),dict(lifetime_review={}),
                       dict(restart_control={}),dict(independent_complete_transport_reviewed=True),dict(actual_restart_qualified=True)):
            folder,args=self.fixture();self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r.update(change))
            with self.assertRaises(ValueError):self.checked(folder,args)
    def test_extended_monitoring_limit_and_late_cleanup_failure_rejected(self):
        folder,args=self.fixture();self.rewrite_fixture(folder/'COLLECTED.json',lambda r:r['monitoring'].update(elapsed_seconds=1201))
        with self.assertRaises(ValueError):self.checked(folder,args)
        folder,args=self.fixture();self.rewrite_fixture(folder/'PARENT_CLOSURE.json',lambda r:r.update(cleanup_error='late slot release'))
        with self.assertRaisesRegex(ValueError,'Parent closure'):self.checked(folder,args)
