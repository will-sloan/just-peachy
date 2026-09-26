"""Exact selected-population and stopped-run admission fixtures; no execution."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from common import bind, freeze, load
import review_restart_run as subject

OUTPUT=None


def fixture(count=2):
    candidates=([subject.BASELINE]+sorted(subject.COMPOSITIONS-{subject.BASELINE}))[:count] if count else []
    rows=[]
    for candidate in candidates:
        for tap,jid in zip(('O0','O1'),subject.JOBS):
            job=dict(job_id=jid,audio_path='INERT/'+jid+'.wav',audio_sha256='0'*64,frames=64000,
                sample_rate_hz=16000,gain=1.,reset_between_scenes=True,tap=tap)
            rows.append(dict(cell_id='restart_0_'+jid+'_'+candidate,composition=candidate,job=job,
                kind='restart_pair',repeat=0,collection_credit=0,stop_after_samples=32000))
    required=len(rows);bindings=[dict(path='INERT/'+r['cell_id']+'/COLLECTED.json',sha256=f'{i:064x}',bytes=100) for i,r in enumerate(rows)]
    plan=dict(schema=subject.PLAN_SCHEMA,status=subject.PLAN_STATUS,restart=deepcopy(subject.POLICY),
        required=required,required_sessions=2*required,candidates=candidates,rows=rows,actual_restart_qualified=False,
        source_execution_authorized=False,N4_accepted=False,integrated_N4_cells=0)
    terminal=dict(schema=subject.RUN_SCHEMA,status='COLLECTED_SELECTED_RESTART_PAIRS_REQUIRES_REVIEW',completed=required,
        required=required,required_sessions=2*required,error=None,collected=deepcopy(bindings),actual_restart_qualified=False,
        independent_complete_transport_reviewed=False,integrated_N4_cells=0,N4_accepted=False)
    progress=[dict(completed=i+1,total=required,cell=b,actual_restart_qualified=False,integrated_N4_cells=0) for i,b in enumerate(bindings)]
    return dict(plan=plan,terminal=terminal,collected=bindings,progress=progress,cell_names=[r['cell_id'] for r in rows],
        progress_names=[f'{i+1:04d}.json' for i in range(required)])


class RestartPopulationTests(unittest.TestCase):
    def setUp(self):self.folder=OUTPUT/self._testMethodName;self.folder.mkdir()
    def test_complete_minimum_and_maximum_selected_populations(self):
        for count in (1,6):
            f=fixture(count);before=deepcopy(f);r=subject.validate_population(**f)
            self.assertEqual(f,before);self.assertEqual(r['planned_pairs'],2*count);self.assertEqual(r['planned_sessions'],4*count)
            self.assertEqual(r['additional_or_missing_pairs'],0)
    def test_missing_extra_or_duplicate_cells_and_progress_rejected(self):
        for key in ('cell_names','progress_names'):
            for mode in ('missing','extra','duplicate'):
                f=fixture()
                if mode=='missing':f[key].pop()
                elif mode=='extra':f[key].append('foreign')
                else:f[key][-1]=f[key][0]
                with self.assertRaises(ValueError):subject.validate_population(**f)
    def test_partial_failed_or_promoted_run_rejected(self):
        for change in (dict(completed=3),dict(completed=True),dict(required_sessions=4),dict(error='pair failed'),
            dict(status='READY_FOR_REVIEW'),dict(actual_restart_qualified=True),dict(independent_complete_transport_reviewed=True),
            dict(N4_accepted=True),dict(integrated_N4_cells=4)):
            f=fixture();f['terminal'].update(change)
            with self.assertRaisesRegex(ValueError,'Terminal run'):subject.validate_population(**f)
    def test_terminal_collection_sequence_is_exact(self):
        for mode in ('missing','reverse','duplicate'):
            f=fixture();v=f['terminal']['collected']
            if mode=='missing':v.pop()
            elif mode=='reverse':v.reverse()
            else:v[-1]=v[0]
            with self.assertRaisesRegex(ValueError,'collected sequence'):subject.validate_population(**f)
    def test_progress_identity_and_flags_must_match(self):
        for change in (dict(completed=True),dict(completed=2),dict(total=1),dict(cell={}),
                       dict(actual_restart_qualified=True),dict(integrated_N4_cells=1)):
            f=fixture();f['progress'][0].update(change)
            with self.assertRaisesRegex(ValueError,'Progress receipt'):subject.validate_population(**f)
    def test_bad_candidate_census_and_plan_claims_rejected(self):
        for count in (0,7):
            with self.assertRaises(ValueError):subject.validate_population(**fixture(count))
        for change in (dict(required=True),dict(required_sessions=7),dict(actual_restart_qualified=True),dict(N4_accepted=True),
                       dict(candidates=['A1_D0_E1','A1_D0_E1'])):
            f=fixture();f['plan'].update(change)
            with self.assertRaises(ValueError):subject.validate_population(**f)
    def test_fixed_pair_order_threshold_and_zero_collection_credit(self):
        for change in (dict(stop_after_samples=31680),dict(repeat=True),dict(kind='panel'),dict(collection_credit=1),dict(cell_id='foreign')):
            f=fixture();f['plan']['rows'][0].update(change)
            with self.assertRaises(ValueError):subject.validate_population(**f)
        f=fixture();f['plan']['rows'].reverse()
        with self.assertRaises(ValueError):subject.validate_population(**f)
    def test_same_tap_job_must_remain_identical_across_candidates(self):
        f=fixture();f['plan']['rows'][2]['job']['audio_sha256']='1'*64
        with self.assertRaisesRegex(ValueError,'saved tap job'):subject.validate_population(**f)
    def test_directory_census_refuses_wrong_entry_types(self):
        (self.folder/'cells').mkdir();(self.folder/'progress').mkdir();(self.folder/'cells/foreign.txt').write_text('fixture')
        with self.assertRaisesRegex(ValueError,'non-directory'):subject.directory_names(self.folder)

    def stopped_fixture(self):
        parent,child,exe,script,q=subject.qualified_runner();f=fixture(1);folder=self.folder/'run';folder.mkdir()
        freeze(self.folder/'PLAN.json',f['plan']);pb=bind(self.folder/'PLAN.json')
        a=dict(schema=subject.RUN_SCHEMA,status=subject.PREPARED,actual_application_started=False,
            owner=dict(pid=987654321,create_time=1.),output=str(folder),state=str(subject.LOCAL/'supervision'),
            code=parent,child_code=child,executable=exe,child_script=script,qualification=q,plan=pb,required=2,required_sessions=4)
        freeze(folder/'ADMISSION.json',a);ab=bind(folder/'ADMISSION.json');owner=dict(pid=987654322,create_time=1.)
        freeze(folder/'RUN_OWNER.json',dict(owner=owner,admission=ab));f['terminal'].update(owner=owner,admission=ab)
        freeze(folder/'RESULT.json',f['terminal'])
        argv=[exe['path'],'-B',str(subject.HERE/'restart_application_runner.py'),'run','--admission',str(folder/'ADMISSION.json')]
        freeze(folder/'worker.json',dict(argv=argv,cwd=str(subject.HERE)))
        return folder,pb,f['plan']
    def stopped(self,folder,pb,plan):
        with patch.object(subject,'admit_plan',return_value=(pb,plan)),patch.object(subject,'exact_process',return_value=None):
            return subject.stopped_run(folder)
    def test_stopped_run_joins_real_manifests_with_mocked_plan_admission(self):
        folder,pb,plan=self.stopped_fixture();r=self.stopped(folder,pb,plan)
        self.assertEqual(r['plan'],plan);self.assertEqual(r['plan_binding'],pb);self.assertEqual(len(r['code']),122)
        self.assertEqual(len(r['parent_code']),148);self.assertGreater(len(r['bindings']),3)
        freeze(self.folder/'SYNTHETIC_STOPPED_RUN.json',dict(plan_binding=pb,run_records=r['bindings'],production_plan_admitted=False))
    def test_stopped_run_rejects_wrong_command_and_foreign_plan_binding(self):
        folder,pb,plan=self.stopped_fixture()
        with self.assertRaises(ValueError):self.stopped(folder,dict(pb,sha256='0'*64),plan)
        worker=load(folder/'worker.json');worker['argv'][3]='child';(folder/'worker.json').write_text(json.dumps(worker))
        with self.assertRaisesRegex(ValueError,'coordinator command'):self.stopped(folder,pb,plan)
    def test_stopped_run_refuses_active_owner_before_reconstruction(self):
        folder,pb,plan=self.stopped_fixture()
        with patch.object(subject,'exact_process',return_value=object()),patch.object(subject,'admit_plan') as admit:
            with self.assertRaisesRegex(ValueError,'active'):subject.stopped_run(folder)
            admit.assert_not_called()
