"""Model-free panel admission/facade/receipt tests. See README.md."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import uuid
import wave

spec=importlib.util.spec_from_file_location('n2_gui_panel_under_test',Path(__file__).with_name('panel.py'))
panel=importlib.util.module_from_spec(spec);spec.loader.exec_module(panel)


def audio(scene,tap='O0'):
    return dict(job_id='N1_REGRESSION_'+scene+'_'+tap,audio_path=str(Path(scene)/(tap+'.wav')),
        audio_sha256='a'*64,frames=16000,sample_rate_hz=16000,gain=1.,reset_between_scenes=True,tap=tap)


def gallery():
    profile=str(uuid.uuid4())
    return dict(schema='just-peachy.n2.gallery.v1',research_only=True,namespace=dict(preprocessing='test'),
        calibration=dict(status='UNCALIBRATED_REJECT_ALL'),
        publication_provenance=dict(vectors_changed=False,component_result={'sha256':'b'*64},source_gallery={'sha256':'c'*64}),
        profiles=[dict(profile_id=profile,name='Research '+profile[:8],vector=[1.]+[0.]*191,
                       provenance=dict(window_ids=['E_window'],window_manifest_sha256='d'*64))])


def archive_receipt(folder,frames=16000):
    owner=dict(epoch_id='fixture_epoch',audio_enabled=False,audio_recording=False,source_samples=frames,
        recorded_samples=0,archive_error=None,loss=None,queue_items=0,queue_bytes=0,closed=True,worker_alive=False)
    epoch={**owner,'state':'CLOSED','accepted_items':12,'completed_items':12,'pipeline_terminal_state':'COMPLETED',
           'worker_alive':True}  # Final checkpoint precedes thread return.
    path=folder/'epoch.json';panel.atomic(path,epoch)
    return dict(schema='n2-gui-archive-integrity-v1',controller_closed=True,controller_worker_alive=False,
        sessions=dict(archive=None,last_archive=deepcopy(owner),current_id='conversation',
                      library=[dict(id='conversation',issues=[])]),metrics_last_archive=deepcopy(owner),owner=owner,
        accepted_items=12,completed_items=12,worker_alive=False,active_archive_owners=0,
        epoch=panel.bound(path),persisted={name:epoch.get(name) for name in panel.ARCHIVE_EPOCH_FIELDS})


class FakeGallery:
    def __init__(self,document,namespace,ids,expected_query_domain):
        if document['namespace']!=namespace:raise ValueError('namespace mismatch')
        self.receipt={};self.document=document;self.ids=ids;self.query_domain=expected_query_domain


class PanelTests(unittest.TestCase):
    def test_gui_refuses_changed_or_missing_atomic_io_binding(self):
        for admission in ({},dict(io_helper=panel.bound(panel.IO_HELPER),io_version='changed'),
                          dict(io_helper={'sha256':'0'*64},io_version=panel._io.IO_VERSION)):
            with self.assertRaisesRegex(ValueError,'IO helper changed'):panel.check_binding(admission)

    def test_cpu_only_runtime_rejects_gpu(self):
        panel.require_cpu_runtime({});panel.require_cpu_runtime(dict(native_device=dict(kind='cpu',gpu_index=-1)))
        for device in (dict(kind='cuda',gpu_index=0),dict(kind='cpu',gpu_index=0)):
            with self.assertRaisesRegex(ValueError,'CPU-only'):panel.require_cpu_runtime(dict(native_device=device))

    def test_panel_exact_six_cells_same_boundary_audio(self):
        rows=[audio(s) for _,s,_ in panel.SCENES]
        jobs=panel.audio_jobs({'jobs':rows[:3]+rows[4:]},{'jobs':[rows[3]]})
        self.assertEqual(len(jobs),6);self.assertEqual(jobs[0]['audio'],jobs[-1]['audio'])
        self.assertEqual(sum(j['mode']=='enrolled_names' for j in jobs),3)
        self.assertEqual({j['example'] for j in jobs},{'boundary','short','returning','noise','silence'})

    def test_firewall_rejects_truth(self):
        row=audio('S45_08_07');row['speaker_truth']='not allowed'
        with self.assertRaisesRegex(ValueError,'firewall'):panel.audio_jobs({'jobs':[row]},{'jobs':[]})

    def test_missing_or_conflicting_audio_rejected(self):
        rows=[audio(s) for _,s,_ in panel.SCENES];other=deepcopy(rows[0]);other['audio_sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'conflicting'):panel.audio_jobs({'jobs':rows},{'jobs':[other]})
        with self.assertRaisesRegex(ValueError,'Missing'):panel.audio_jobs({'jobs':rows[:-1]},{'jobs':[]})

    def test_gain_and_reset_rejected(self):
        for field,value in (('gain',2.),('reset_between_scenes',False),('sample_rate_hz',48000)):
            row=audio('S45_08_07');row[field]=value
            with self.assertRaises(ValueError):panel.audio_jobs({'jobs':[row]},{'jobs':[]})

    def test_waveform_exact_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'O0.wav'
            with wave.open(str(path),'wb') as stream:
                stream.setparams((1,2,16000,0,'NONE','not compressed'));stream.writeframes(b'\0\0'*160)
            row=audio('S45_08_07');row.update(audio_path=str(path),audio_sha256=panel.digest(path),frames=160)
            panel.validate_audio(row);row['frames']=161
            with self.assertRaisesRegex(ValueError,'exact admitted'):panel.validate_audio(row)

    def test_personal_or_non_generic_or_unproven_galleries_rejected(self):
        for mutate in (lambda d:d.pop('research_only'),lambda d:d['profiles'][0].update(name='Actual person'),
                       lambda d:d['publication_provenance'].update(vectors_changed=True),
                       lambda d:d['profiles'][0].pop('provenance'),
                       lambda d:d['calibration'].update(status='CALIBRATED')):
            document=gallery();mutate(document)
            with self.assertRaises(ValueError):panel.admit_gallery(document)

    def test_facade_no_personal_write_or_provenance_leak_in_list(self):
        document=gallery();root=Path('does_not_exist_research_store')
        store=panel.ResearchStore(document,document['namespace'],root,FakeGallery)
        self.assertEqual(set(store.list()[0]),{'id','name','references'})
        self.assertNotIn('vector',store.summaries()[0]);self.assertFalse(hasattr(store,'save'))
        self.assertFalse(root.exists())
        route=dict(sample_rate=16000,waveform_domain='xvf_ua',preprocessing='test',tap='O0',gain_policy='O0_host_plus3dB_once')
        result=store.gallery(route,[document['profiles'][0]['profile_id']])
        self.assertEqual(result.query_domain,'XVF_query');self.assertTrue(result.receipt['research_store_facade'])
        self.assertFalse(result.receipt['personal_store_imported'])
        route['gain_policy']='O1_unity'
        with self.assertRaises(ValueError):store.gallery(route)

    def test_facade_namespace_rejected(self):
        with self.assertRaisesRegex(ValueError,'namespace'):panel.ResearchStore(gallery(),dict(preprocessing='wrong'),'.',FakeGallery)

    def test_first_applied_first_final_latest_are_actual_distinct_states(self):
        clock=panel.ClockObserver();clock.event('source_started',0,dict(source_epoch_monotonic_sec=100.))
        audit=panel.PresentationAudit(clock)
        row=dict(final=False,source_start_sec=0.,source_end_sec=1.,timing_kind='coarse')
        receipt=dict(row_id='r',span_ids=['s'],label='•••',applied_monotonic_sec=102.)
        audit.observe(receipt,row)
        receipt.update(label='Unknown',applied_monotonic_sec=103.);audit.observe(receipt,row)
        row['final']=True;receipt['applied_monotonic_sec']=104.
        audit.observe(receipt,row,kind='verified_Tk_final_state_after_render')
        receipt.update(label='Research test · assumed',applied_monotonic_sec=105.);audit.observe(receipt,row)
        state=audit.spans['s']
        self.assertEqual(state['first_applied']['label'],'•••')
        self.assertEqual(state['first_final']['label'],'Unknown')
        self.assertEqual(state['latest']['label'],'Research test · assumed')
        self.assertEqual(state['label_revisions'],2)
        self.assertEqual(state['first_final']['source_end_to_tk_applied_sec'],3.)
        self.assertEqual(len(audit.receipts),3);self.assertEqual(len(audit.final_observations),1)

    def test_reordered_spans_keep_initial_label(self):
        audit=panel.PresentationAudit(panel.ClockObserver())
        for spans,label in ((['a','b'],'Unknown'),(['b','a'],'Name')):
            audit.observe(dict(row_id='r',span_ids=spans,label=label,applied_monotonic_sec=1.),{})
        self.assertEqual(audit.spans['a']['first_applied']['label'],'Unknown')
        self.assertEqual(audit.spans['b']['latest']['label'],'Name')

    def test_clock_origin_cannot_reset_or_go_backward(self):
        clock=panel.ClockObserver();clock.event('source_started',0,dict(source_epoch_monotonic_sec=100.))
        with self.assertRaises(ValueError):clock.event('source_started',0,dict(source_epoch_monotonic_sec=101.))
        with self.assertRaises(ValueError):panel.PresentationAudit(clock).observe(dict(row_id='r',span_ids=['s'],label='x',applied_monotonic_sec=99.),{})


class AggregationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='N2 GUI aggregation fixture ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        jobs=[dict(cell_id='cell_'+str(i),combination='D1_E1',mode='enrolled_names',example='fixture',audio=audio('fixture_'+str(i))) for i in range(6)]
        self.admission=dict(output=str(self.root),jobs=jobs,job_count=6,full_panel=True,source='fixture_source',source_bindings={},
            inputs={},common_ui_sha256={},common_layout_sha256='a'*64,runner={},cpu=4,
            io_helper=panel.bound(panel.IO_HELPER),io_version=panel._io.IO_VERSION)
        panel.atomic(self.root/'ADMISSION.json',self.admission)

    def child(self,index):
        job=self.admission['jobs'][index];folder=self.root/'private_cells'/job['cell_id'];folder.mkdir(parents=True)
        admission=panel.single_cell_admission(self.admission,job,folder);panel.atomic(folder/'ADMISSION.json',admission)
        cell_root=folder/'cells'/job['cell_id'];cell_root.mkdir(parents=True)
        evidence=cell_root/'evidence.json';panel.atomic(evidence,dict(fixture=True))
        archive_path=cell_root/'ARCHIVE_INTEGRITY.json'
        panel.atomic(archive_path,archive_receipt(cell_root,job['audio']['frames']))
        cell=dict(**job,status='COMPLETE',controller_closed=True,all_samples=True,writers_drained=True,main_engine_gallery=True,
                  archive_integrity_passed=True,evidence=[panel.bound(evidence),panel.bound(archive_path)],screenshots=[])
        panel.atomic(cell_root/'RESULT.json',cell)
        panel.atomic(folder/'GUI_PANEL_REPORT.json',dict(status='COMPLETE',cells=[cell],admission=panel.bound(folder/'ADMISSION.json')))
        panel.atomic(folder/'isolation.json',dict(exit_code=0,timed_out=False,input_desktop_unchanged=True,switch_desktop_called=False,input_injection=False))
        panel.atomic(folder/'tests.json',dict(successful=True,tests=1,skipped=0))
        return dict(cell_id=job['cell_id'],output=str(folder),launcher_returncode=0)

    def test_exact_six_independent_reports_aggregate(self):
        runs=[self.child(i) for i in range(6)];result=panel.aggregate_cell_reports(self.admission,runs)
        self.assertEqual(result['status'],'COMPLETE');self.assertEqual(result['completed'],6)
        self.assertTrue(result['full_panel']);self.assertEqual(len(result['private_processes']),6)

    def test_dropped_duplicate_and_wrong_cells_cannot_complete(self):
        run=self.child(0)
        with self.assertRaisesRegex(ValueError,'Missing requested'):panel.aggregate_cell_reports(self.admission,[run])
        partial=panel.aggregate_cell_reports(self.admission,[run],require_all=False)
        self.assertEqual(partial['status'],'RUNNING');self.assertEqual(len(partial['missing_cells']),5)
        with self.assertRaisesRegex(ValueError,'Duplicate'):panel.aggregate_cell_reports(self.admission,[run,run],require_all=False)
        with self.assertRaisesRegex(ValueError,'unexpected'):panel.aggregate_cell_reports(self.admission,[dict(run,cell_id='not_requested')],require_all=False)

    def test_native_crash_or_skipped_gui_cannot_be_accepted(self):
        run=self.child(0)
        with self.assertRaisesRegex(ValueError,'process failed'):
            panel.aggregate_cell_reports(self.admission,[dict(run,launcher_returncode=2147483651)],require_all=False)
        folder=Path(run['output']);panel.atomic(folder/'tests.json',dict(successful=True,tests=1,skipped=1))
        with self.assertRaisesRegex(ValueError,'skipped'):panel.aggregate_cell_reports(self.admission,[run],require_all=False)

    def test_changed_cell_evidence_or_input_contract_rejected(self):
        run=self.child(0);folder=Path(run['output'])
        path=folder/'cells'/run['cell_id']/'evidence.json';path.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'evidence changed'):panel.aggregate_cell_reports(self.admission,[run],require_all=False)
        child=panel.load(folder/'ADMISSION.json');child['cpu']=9;panel.atomic(folder/'ADMISSION.json',child)
        with self.assertRaisesRegex(ValueError,'contract differs'):panel.aggregate_cell_reports(self.admission,[run],require_all=False)

    def test_each_private_admission_contains_one_exact_parent_job(self):
        job=self.admission['jobs'][2]
        child=panel.single_cell_admission(self.admission,job,self.root/'another')
        self.assertEqual(child['jobs'],[job]);self.assertEqual(child['job_count'],1);self.assertFalse(child['full_panel'])
        self.assertEqual(len(self.admission['jobs']),6)


    def test_aggregate_rechecks_archive_even_if_cell_claims_complete(self):
        run=self.child(0);folder=Path(run['output']);cell_root=folder/'cells'/run['cell_id']
        archive_path=cell_root/'ARCHIVE_INTEGRITY.json';receipt=panel.load(archive_path)
        receipt['owner']['archive_error']='Window source indices unavailable'
        receipt['sessions']['last_archive']=deepcopy(receipt['owner']);receipt['metrics_last_archive']=deepcopy(receipt['owner'])
        panel.atomic(archive_path,receipt)
        result=panel.load(cell_root/'RESULT.json')
        result['evidence']=[panel.bound(row['path']) for row in result['evidence']]
        panel.atomic(cell_root/'RESULT.json',result)
        report=panel.load(folder/'GUI_PANEL_REPORT.json');report['cells']=[result];panel.atomic(folder/'GUI_PANEL_REPORT.json',report)
        with self.assertRaisesRegex(ValueError,'archive_error/loss'):
            panel.aggregate_cell_reports(self.admission,[run],require_all=False)


class ArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='N2 GUI archive fixture ');self.addCleanup(self.temp.cleanup)
        self.receipt=archive_receipt(Path(self.temp.name))

    def test_joined_owner_overrides_checkpoint_thread_still_inside_finally(self):
        self.assertTrue(panel.load(self.receipt['epoch']['path'])['worker_alive'])
        panel.validate_archive_integrity(self.receipt,16000)

    def test_real_metadata_archive_drains_and_is_admitted_without_models(self):
        import sys
        source=Path(__file__).resolve().parents[5]/'prototype'
        sys.path.insert(0,str(source))
        try:
            from app.sessions import EpochArchive
        finally:sys.path.pop(0)
        folder=Path(self.temp.name)/'actual_epoch'
        archive=EpochArchive(folder,{'pipeline_terminal_state':'COMPLETED'},False)
        self.addCleanup(archive.close)
        archive.audio_block(0,[0.]*160)
        self.assertTrue(archive.offer('windows',b'{"fixture":true}\n'))
        last=archive.close()
        controller=SimpleNamespace(closed=True,worker=SimpleNamespace(is_alive=lambda:False),
            session_store=SimpleNamespace(active={}),metrics={'last_archive':last},
            snapshot=lambda:dict(sessions=dict(archive=None,last_archive=last,current_id='actual',library=[dict(id='actual',issues=[])])))
        receipt=panel.archive_integrity_receipt(controller,SimpleNamespace(archive=archive))
        panel.validate_archive_integrity(receipt,160)
        self.assertEqual(receipt['accepted_items'],receipt['completed_items'])
        self.assertGreater(receipt['accepted_items'],0)

    def test_archive_loss_cannot_pass_with_successful_captions(self):
        for field,value in (('archive_error','Window source indices unavailable'),('loss',{'reason':'queue overflow'})):
            receipt=deepcopy(self.receipt)
            for row in (receipt['owner'],receipt['sessions']['last_archive'],receipt['metrics_last_archive']):row[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'archive_error/loss'):
                panel.validate_archive_integrity(receipt,16000)

    def test_missing_items_live_workers_and_source_loss_rejected(self):
        for field,value in (('completed_items',11),('worker_alive',True),('active_archive_owners',1),
                            ('controller_worker_alive',True),('accepted_items',None)):
            receipt=deepcopy(self.receipt);receipt[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):panel.validate_archive_integrity(receipt,16000)
        with self.assertRaisesRegex(ValueError,'source samples differ'):panel.validate_archive_integrity(self.receipt,16001)

    def test_current_session_issues_and_unclosed_snapshot_rejected(self):
        for mutate in (lambda r:r['sessions']['library'][0].update(issues=[{'error':'archive unavailable'}]),
                       lambda r:r['sessions'].update(archive={'closed':False}),
                       lambda r:r['sessions'].update(last_archive=None),
                       lambda r:r['persisted'].update(state='PARTIAL'),
                       lambda r:r['persisted'].update(accepted_items=13)):
            receipt=deepcopy(self.receipt);mutate(receipt)
            with self.assertRaises(ValueError):panel.validate_archive_integrity(receipt,16000)

    def test_persisted_checkpoint_hash_is_required(self):
        Path(self.receipt['epoch']['path']).write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'evidence changed'):panel.validate_archive_integrity(self.receipt,16000)


if __name__=='__main__':unittest.main()
