"""Actual source-paced Controller/Tk panel on a private desktop. See README_GUI.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import unittest
import uuid
import wave

IO_HELPER=Path(__file__).resolve().parents[1]/'n2/io_utils.py'
_io_spec=importlib.util.spec_from_file_location('_n3_gui_atomic_io',IO_HELPER)
_io=importlib.util.module_from_spec(_io_spec);_io_spec.loader.exec_module(_io)

MODULE = 'research.nvidia_nemo_comparison.20260924_campaign.n3.gui_twocore'
SCOPE = 'Actual source-paced saved audio; Tk text applied, not physical scanout or acoustic latency'
COMMON_FILES = ('app/ui.py','app/caption_display.py','app/backends.py','app/mode_policy.py',
                'vendor/edge_speech_pipeline/research_n1_spans.py',
                'vendor/edge_speech_pipeline/research_s7_presentation.py')
AUDIO_KEYS = {'job_id','audio_path','audio_sha256','frames','sample_rate_hz','gain','reset_between_scenes','tap'}
SCENES = (('boundary','S45_08_07','selected_closed'),
          ('short','S45_03_03','enrolled_names'),
          ('returning','S45_06_07','selected_closed'),
          ('noise','S45_12_20','enrolled_names'),
          ('silence','S45_12_15','enrolled_names'))


def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def bound(path):
    path=Path(path).resolve(strict=True)
    return dict(path=str(path),sha256=digest(path),bytes=path.stat().st_size)


def atomic(path,value):
    _io.atomic(Path(path),value)


def source_bindings(source):
    return {str(p.relative_to(source)).replace('\\','/'):digest(p)
            for folder in ('app','vendor','config','release_tools')
            for p in sorted((source/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo')}


def audio_jobs(regression,screen,tap='O0'):
    rows=regression['jobs']+screen['jobs']
    if any(set(row)!=AUDIO_KEYS or row['reset_between_scenes'] is not True for row in rows):
        raise ValueError('Strict audio-only manifests required')
    jobs=[]
    for variant in ('A2','A3'):
        for example,scene,mode in SCENES[:3]:
            matches=[r for r in rows if r['job_id'].endswith(scene+'_'+tap)]
            unique={(r['audio_sha256'],r['frames'],r['audio_path']) for r in matches}
            if len(unique)!=1:raise ValueError('Missing/conflicting admitted N3 GUI scene')
            audio=deepcopy(matches[0])
            if set(audio)!=AUDIO_KEYS or audio['gain']!=1 or audio['sample_rate_hz']!=16000:
                raise ValueError('N3 audio-only firewall failed')
            jobs.append(dict(cell_id=variant+'_'+example,variant=variant,combination='D1_E0',
                mode=mode,example=example,audio=audio))
    return jobs


def validate_audio(row):
    if digest(row['audio_path'])!=row['audio_sha256']:raise ValueError('Prepared audio hash changed')
    with wave.open(row['audio_path'],'rb') as stream:
        if (stream.getnchannels(),stream.getframerate(),stream.getsampwidth(),stream.getnframes(),stream.getcomptype())!=(1,16000,2,row['frames'],'NONE'):
            raise ValueError('Prepared audio must be the exact admitted mono16k PCM16 waveform')


def admit_gallery(document):
    """Only explicitly published research E galleries; no normal personal-store import."""
    if document.get('schema')!='just-peachy.n2.gallery.v1' or document.get('research_only') is not True:
        raise ValueError('An explicitly published research-only gallery is required')
    publication=document.get('publication_provenance',{})
    if publication.get('vectors_changed') is not False or not publication.get('component_result') or not publication.get('source_gallery'):
        raise ValueError('Missing published component/extraction provenance')
    if document.get('calibration',{}).get('status')!='UNCALIBRATED_REJECT_ALL':
        raise ValueError('This bounded panel is declared for uncalibrated XVF-query rejection')
    rows=document.get('profiles',[])
    if not rows or len(rows)>256:raise ValueError('A nonempty bounded E roster is required')
    for row in rows:
        if str(uuid.UUID(row['profile_id']))!=row['profile_id'] or row['name']!='Research '+row['profile_id'][:8]:
            raise ValueError('Only generic published research UUID names are allowed')
        provenance=row.get('provenance',{})
        if not provenance.get('window_ids') or len(provenance.get('window_manifest_sha256',''))!=64:
            raise ValueError('E extraction window provenance is required')
    return document


def require_cpu_runtime(document):
    device=document.get('native_device',{'kind':'cpu','gpu_index':-1})
    if device.get('kind')!='cpu' or device.get('gpu_index',-1)!=-1:
        raise ValueError('This GUI panel is CPU-only; a CUDA runtime binding is not admitted')


ARCHIVE_EPOCH_FIELDS=('epoch_id','state','closed','source_samples','recorded_samples',
    'audio_enabled','audio_recording','archive_error','loss','queue_items','queue_bytes',
    'accepted_items','completed_items','pipeline_terminal_state')


def archive_integrity_receipt(controller,engine):
    """Capture the joined archive owner, UI state and persisted final checkpoint."""
    snapshot=controller.snapshot();sessions=snapshot.get('sessions',{})
    archive=getattr(engine,'archive',None);epoch_path=archive.path/'epoch.json' if archive is not None else None
    epoch=load(epoch_path) if epoch_path is not None and epoch_path.is_file() else {}
    return dict(schema='n2-gui-archive-integrity-v1',controller_closed=controller.closed,
        controller_worker_alive=controller.worker.is_alive(),sessions=deepcopy(sessions),
        metrics_last_archive=deepcopy(controller.metrics.get('last_archive')),
        owner=archive.snapshot() if archive is not None else None,
        accepted_items=getattr(archive,'accepted',None),completed_items=getattr(archive,'completed',None),
        worker_alive=archive.thread.is_alive() if archive is not None else None,
        active_archive_owners=len(controller.session_store.active),
        epoch=bound(epoch_path) if epoch else None,
        persisted={name:epoch.get(name) for name in ARCHIVE_EPOCH_FIELDS},
        persisted_worker_clock='epoch checkpoint is written inside worker before return; joined owner below is authoritative')


def validate_archive_integrity(receipt,expected_samples):
    """Fail on a silent archive warning, dropped metadata or incomplete teardown."""
    def require(ok,reason):
        if not ok:raise ValueError('Archive integrity failed: '+reason)
    require(receipt.get('schema')=='n2-gui-archive-integrity-v1','missing receipt')
    require(receipt.get('controller_closed') is True and receipt.get('controller_worker_alive') is False,'Controller still active')
    require(receipt.get('worker_alive') is False and receipt.get('active_archive_owners')==0,'archive owner still active')
    sessions=receipt.get('sessions',{});owner=receipt.get('owner');last=sessions.get('last_archive')
    require(sessions.get('archive') is None,'sessions archive still active')
    require(isinstance(owner,dict) and isinstance(last,dict),'missing owner/last_archive')
    require(last==receipt.get('metrics_last_archive'),'last_archive differs from Controller metrics')
    require(owner==last,'joined archive differs from last_archive')
    for name,row in (('owner',owner),('last_archive',last),('persisted',receipt.get('persisted',{}))):
        require(row.get('archive_error') is None and row.get('loss') is None,name+' archive_error/loss')
        require(row.get('closed') is True and row.get('audio_recording') is False,name+' not closed')
        require(row.get('queue_items')==0 and row.get('queue_bytes')==0,name+' queue not drained')
        require(type(row.get('source_samples')) is int and row['source_samples']==expected_samples,name+' source samples differ')
        require(row.get('audio_enabled') in (True,False),name+' missing audio policy')
        require(row.get('recorded_samples')==(expected_samples if row['audio_enabled'] else 0),name+' recorded samples differ')
    require(owner.get('worker_alive') is False,'archive thread still alive')
    accepted=receipt.get('accepted_items');completed=receipt.get('completed_items')
    require(type(accepted) is int and accepted>0 and type(completed) is int and accepted==completed,'accepted/completed items differ or absent')
    persisted=receipt['persisted']
    require(persisted.get('state')=='CLOSED' and persisted.get('pipeline_terminal_state')=='COMPLETED','persisted archive not successfully closed')
    require(persisted.get('accepted_items')==accepted and persisted.get('completed_items')==completed,'persisted counters differ')
    require(persisted.get('epoch_id')==owner.get('epoch_id'),'epoch identity differs')
    current=[row for row in sessions.get('library',[]) if row.get('id')==sessions.get('current_id')]
    require(len(current)==1 and not current[0].get('issues'),'current session reports archive issues or is missing')
    require(isinstance(receipt.get('epoch'),dict),'missing persisted epoch binding')
    verify_bound(receipt['epoch'])
    document=load(receipt['epoch']['path'])
    require({name:document.get(name) for name in ARCHIVE_EPOCH_FIELDS}==persisted,'persisted evidence differs')


class ResearchStore:
    """Read-only facade; returns the actual N2Gallery consumed by the main engine."""
    def __init__(self,document,namespace,root,gallery_type):
        self.document=deepcopy(admit_gallery(document));self.namespace=deepcopy(namespace)
        self.root=Path(root);self.epoch=0;self.preprocessing=namespace['preprocessing'];self.gallery_type=gallery_type
        self._gallery(None)  # Enforce model namespace and vector validity immediately.

    def _gallery(self,ids):
        return self.gallery_type(self.document,self.namespace,ids,expected_query_domain='XVF_query')

    def list(self,refresh=False):
        return [dict(id=r['profile_id'],name=r['name'],references=[]) for r in self.document['profiles']]

    def summaries(self,route=None):
        return [dict(id=r['profile_id'],name=r['name'],references=1,compatible_references=1,
                     environment_references=0,enrichment_undo=False,research_only=True) for r in self.document['profiles']]

    def gallery(self,route,person_ids=None,alternate_advisory=False):
        if route['sample_rate']!=16000 or route['waveform_domain']!='xvf_ua' or route['preprocessing']!=self.preprocessing:
            raise ValueError('Unexpected research gallery query route')
        if route['gain_policy']!={'O0':'O0_host_plus3dB_once','O1':'O1_unity'}.get(route['tap']):
            raise ValueError('Unexpected prepared tap/gain declaration')
        if alternate_advisory:raise ValueError('Text-assisted research enrollment is outside this panel')
        gallery=self._gallery(person_ids)
        gallery.receipt.update(research_store_facade=True,query_route=deepcopy(route),personal_store_imported=False)
        return gallery


class ClockObserver:
    """Small publication observer; does no identity work or counterfactual rendering."""
    def __init__(self):self.origin=None;self.events=[]
    def event(self,kind,source,payload):
        if kind=='source_started':
            if self.origin is not None:raise ValueError('Source origin changed within a panel cell')
            self.origin=float(payload['source_epoch_monotonic_sec'])
        if kind in {'source_started','fatal','failure'}:
            self.events.append(dict(event_type=kind,source_sec=source,payload=deepcopy(payload)))


class PresentationAudit:
    def __init__(self,observer):self.observer=observer;self.receipts=[];self.final_observations=[];self.spans={}

    def value(self,receipt,row,*,kind):
        value=deepcopy(receipt);origin=self.observer.origin;end=row.get('source_end_sec')
        value.update(audit_kind=kind,source_epoch_monotonic_sec=origin,
            applied_source_elapsed_sec=receipt['applied_monotonic_sec']-origin if origin is not None else None,
            source_start_sec=row.get('source_start_sec'),source_end_sec=end,
            timing_kind=row.get('timing_kind'),final=bool(row.get('final')),display_profile_id=row.get('display_profile_id'),
            naming_state=row.get('naming_state'),identity_assignment=row.get('identity_assignment'),
            verified_profile_id=row.get('profile_id'),scope=SCOPE)
        elapsed=value['applied_source_elapsed_sec']
        value['source_end_to_tk_applied_sec']=elapsed-end if elapsed is not None and end is not None else None
        if elapsed is not None and elapsed<0:raise ValueError('GUI application precedes source origin')
        return value

    def observe(self,receipt,row,*,kind='record_presentation'):
        value=self.value(receipt,row,kind=kind)
        target=self.receipts if kind=='record_presentation' else self.final_observations
        target.append(value)
        for span in receipt['span_ids']:
            state=self.spans.setdefault(str(span),dict(first_applied=None,first_final=None,latest=None,label_revisions=0))
            prior=state['latest']
            if kind=='record_presentation' and state['first_applied'] is None:state['first_applied']=value
            if row.get('final') and state['first_final'] is None:state['first_final']=value
            if prior is not None and prior['label']!=value['label']:state['label_revisions']+=1
            state['latest']=value
        return value


def wait_commands(controller,root,seconds=180):
    end=time.perf_counter()+seconds
    while controller.commands.unfinished_tasks:
        if time.perf_counter()>end:raise TimeoutError('Controller command timeout')
        if root is not None:root.update()
        time.sleep(.01)
    if controller.error:raise RuntimeError(controller.error)


def check_binding(admission):
    if admission.get('io_helper')!=bound(IO_HELPER) or admission.get('io_version')!=_io.IO_VERSION:
        raise ValueError('GUI atomic IO helper changed')
    source=Path(admission['source'])
    if source_bindings(source)!=admission['source_bindings']:raise ValueError('Frozen source changed')
    for row in admission['inputs'].values():
        if digest(row['path'])!=row['sha256']:raise ValueError('Panel input changed: '+row['path'])
    require_cpu_runtime(load(admission['inputs']['runtime_config']['path']))
    asr_runtime=load(admission['inputs']['n3_runtime_config']['path'])
    if asr_runtime.get('schema')!='just-peachy.n3.runtime.v1':raise ValueError('N3 runtime catalog required')
    for job in admission['jobs']:
        variant=asr_runtime['variants'][job['variant']]
        if variant.get('gpu')!=-1 or variant.get('right_context')!=1:
            raise ValueError('GUI panel requires explicit nominal native CPU ASR')
    if digest(admission['runner']['path'])!=admission['runner']['sha256']:raise ValueError('GUI runner changed')
    if digest(source/'tests/test_n1_capture.py')!=admission['capture_helper_sha256']:raise ValueError('Capture helper changed')
    for name,expected in admission['common_ui_sha256'].items():
        if digest(source/name)!=expected or digest(Path(admission['common_source'])/name)!=expected:
            raise ValueError('Common frozen frontend changed: '+name)
    if digest(source/'config/ui.json')!=admission['common_layout_sha256'] or digest(Path(admission['common_source'])/'config/ui.json')!=admission['common_layout_sha256']:
        raise ValueError('Common portrait layout configuration changed')


def single_cell_admission(parent,job,output):
    if job not in parent['jobs']:raise ValueError('Cell is not in the parent admission')
    child=deepcopy(parent)
    child.update(output=str(Path(output).resolve()),jobs=[deepcopy(job)],full_panel=False,job_count=1,
                 execution_policy='one private process and one Tk root per cell',parent_admission=bound(Path(parent['output'])/'ADMISSION.json'))
    return child


def verify_bound(row):
    if bound(row['path'])!=row:raise ValueError('Bound cell evidence changed: '+row['path'])


def aggregate_cell_reports(admission,runs,*,require_all=True):
    """Accept every exact requested cell once, with successful private-process exit."""
    expected={job['cell_id']:job for job in admission['jobs']};seen=set();cells=[];verified=[]
    if len(expected)!=len(admission['jobs']):raise ValueError('Duplicate requested cells')
    for run in runs:
        key=run['cell_id']
        if key in seen or key not in expected:raise ValueError('Duplicate or unexpected completed cell')
        seen.add(key)
        if run['launcher_returncode']!=0:raise ValueError('Private cell process failed: '+key)
        folder=Path(run['output']).resolve();child_path=folder/'ADMISSION.json';child=load(child_path)
        if child['jobs']!=[expected[key]] or child['job_count']!=1 or child['output']!=str(folder):
            raise ValueError('Private child admission differs from requested cell')
        verify_bound(child['parent_admission'])
        if child['parent_admission']!=bound(Path(admission['output'])/'ADMISSION.json'):
            raise ValueError('Private child belongs to another panel')
        for field in ('source','source_bindings','inputs','common_ui_sha256','common_layout_sha256','runner','cpu','cpu_affinity','io_helper','io_version'):
            if child[field]!=admission[field]:raise ValueError('Private child contract differs: '+field)
        isolation=load(folder/'isolation.json');tests=load(folder/'tests.json');report=load(folder/'GUI_PANEL_REPORT.json')
        if isolation.get('exit_code')!=0 or isolation.get('timed_out') is not False or isolation.get('input_desktop_unchanged') is not True:
            raise ValueError('Private cell did not finish cleanly and preserve the input desktop')
        if isolation.get('switch_desktop_called') is not False or isolation.get('input_injection') is not False:
            raise ValueError('Unexpected desktop operation in private cell')
        if tests.get('successful') is not True or tests.get('tests')!=1 or tests.get('skipped')!=0:
            raise ValueError('Private GUI test failed or was skipped')
        if report.get('status')!='COMPLETE' or len(report.get('cells',[]))!=1:
            raise ValueError('Private GUI report is not one complete cell')
        verify_bound(report['admission'])
        if report['admission']!=bound(child_path):raise ValueError('Private GUI report admission mismatch')
        cell=report['cells'][0]
        if any(cell.get(k)!=v for k,v in expected[key].items()):raise ValueError('Completed cell does not match requested input/mode')
        if cell.get('status')!='COMPLETE' or not all(cell.get(k) is True for k in ('controller_closed','all_samples','writers_drained','main_engine_gallery','archive_integrity_passed')):
            raise ValueError('Actual Controller cell is incomplete')
        actual=folder/'cells'/key/'RESULT.json'
        if load(actual)!=cell:raise ValueError('Cell report/result mismatch')
        for evidence in cell.get('evidence',[]):verify_bound(evidence)
        archive_path=folder/'cells'/key/'ARCHIVE_INTEGRITY.json'
        if bound(archive_path) not in cell.get('evidence',[]):raise ValueError('Missing bound archive integrity evidence')
        validate_archive_integrity(load(archive_path),expected[key]['audio']['frames'])
        for screenshot in cell.get('screenshots',[]):
            if digest(screenshot['path'])!=screenshot['sha256']:raise ValueError('Cell screenshot changed')
        cells.append(cell)
        verified.append(dict(cell_id=key,output=str(folder),report=bound(folder/'GUI_PANEL_REPORT.json'),
            isolation=bound(folder/'isolation.json'),tests=bound(folder/'tests.json'),result=bound(actual)))
    missing=[job['cell_id'] for job in admission['jobs'] if job['cell_id'] not in seen]
    if require_all and missing:raise ValueError('Missing requested GUI cells: '+', '.join(missing))
    return dict(schema='n2-actual-source-paced-gui-panel-v2',scope=SCOPE,
        status='COMPLETE' if not missing else 'RUNNING',full_panel=admission['full_panel'],
        requested_cells=len(expected),full_panel_cells=6,completed=len(cells),missing_cells=missing,
        cells=cells,private_processes=verified,execution_policy='one private process and one Tk root per cell',
        admission=bound(Path(admission['output'])/'ADMISSION.json'))


def run_isolated_cells(admission,timeout_seconds):
    output=Path(admission['output']);runs=[];started=time.perf_counter()
    report=aggregate_cell_reports(admission,[],require_all=False)
    atomic(output/'GUI_PANEL_REPORT.json',report)
    for job in admission['jobs']:
        folder=output/'private_cells'/job['cell_id'];folder.mkdir(parents=True)
        child=single_cell_admission(admission,job,folder);atomic(folder/'ADMISSION.json',child)
        environment=dict(os.environ,N3_GUI_ADMISSION=str(folder/'ADMISSION.json'),CUDA_VISIBLE_DEVICES='',
            PYTHONPATH=str(Path(__file__).resolve().parents[4]))
        for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):environment[name]='1'
        remaining=timeout_seconds-(time.perf_counter()-started)
        try:
            check_binding(admission)
            if remaining<=0:raise TimeoutError('GUI panel total wall-clock bound reached')
            atomic(output/'PROGRESS.json',dict(status='RUNNING',active=job['cell_id'],completed=len(report['cells']),total=len(admission['jobs'])))
            command=[sys.executable,'-B',str(Path(admission['source'])/'tests/run_private_desktop.py'),'--receipt-dir',str(folder),
                     '--timeout-seconds',str(remaining),MODULE]
            with (folder/'LAUNCH_OUTPUT.log').open('xb') as log:
                process=subprocess.run(command,cwd=Path(admission['source']).parent,env=environment,
                    stdout=log,stderr=subprocess.STDOUT,check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            runs.append(dict(cell_id=job['cell_id'],output=str(folder),launcher_returncode=process.returncode))
            report=aggregate_cell_reports(admission,runs,require_all=False)
            report['elapsed_seconds']=time.perf_counter()-started
            atomic(output/'GUI_PANEL_REPORT.json',report)
        except BaseException as exc:
            report.update(status='FAILED',active=job['cell_id'],error=repr(exc),runs=runs,elapsed_seconds=time.perf_counter()-started)
            atomic(output/'GUI_PANEL_REPORT.json',report);atomic(output/'PROGRESS.json',dict(status='FAILED',completed=len(report['cells']),total=len(admission['jobs']),active=job['cell_id'],error=repr(exc)))
            if isinstance(exc,(KeyboardInterrupt,SystemExit)):raise
            return 2
    check_binding(admission);report=aggregate_cell_reports(admission,runs)
    report['elapsed_seconds']=time.perf_counter()-started
    atomic(output/'GUI_PANEL_REPORT.json',report);atomic(output/'PROGRESS.json',dict(status='COMPLETE',completed=len(report['cells']),total=len(admission['jobs'])))
    return 0


class ActualPanelTests(unittest.TestCase):
    def test_actual_saved_audio_panel(self):
        if not os.environ.get('N3_GUI_ADMISSION'):self.skipTest('Use panel.py with explicit source/config/audio/gallery inputs')
        import ctypes
        from prototype.tests.run_private_desktop import desktop_name,setup_api
        user=setup_api();desktop=desktop_name(user.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId()))
        self.assertTrue(desktop.startswith('codex-n1-'),'Refuse execution on the user input desktop')
        admission=load(os.environ['N3_GUI_ADMISSION']);check_binding(admission)
        self.assertEqual(len(admission['jobs']),1,'Only one actual Tk/neural cell is allowed per private process')
        source=Path(admission['source']);output=Path(admission['output'])
        # Bind native diagnostics to this known private process before importing
        # model runtimes. Keep the handle alive through process shutdown.
        import faulthandler
        self._native_log=(output/'NATIVE_OUTPUT.log').open('ab',buffering=0)
        os.dup2(self._native_log.fileno(),1);os.dup2(self._native_log.fileno(),2)
        faulthandler.enable(self._native_log,all_threads=True)
        sys.path[:0]=[str(source),str(source/'vendor')]
        import psutil
        process=psutil.Process();process.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);process.cpu_affinity(admission['cpu_affinity'])
        self.assertEqual(process.nice(),psutil.BELOW_NORMAL_PRIORITY_CLASS)
        from app.controller import Controller
        from app.backends import backend_catalog
        from app.n2_models import redim_namespace
        from app.n2_identity import N2Gallery
        from app.ui import PrototypeUI,prepare_dpi_awareness
        import app.ui as app_ui
        self.assertEqual(Path(app_ui.__file__).resolve(),source/'app/ui.py')
        import tkinter as tk
        spec=importlib.util.spec_from_file_location('_n2_private_capture',source/'tests/test_n1_capture.py')
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        self.assertEqual(digest(source/'tests/test_n1_capture.py'),admission['capture_helper_sha256'])
        prepare_dpi_awareness()
        report=dict(schema='n3-actual-source-paced-gui-panel-v1',scope=SCOPE,desktop=desktop,status='RUNNING',cells=[],
                    admission=bound(os.environ['N3_GUI_ADMISSION']),cpu_affinity=process.cpu_affinity(),priority=int(process.nice()),
                    full_panel=admission['full_panel'],requested_cells=len(admission['jobs']),full_panel_cells=6)
        for job in admission['jobs']:
            check_binding(admission);validate_audio(job['audio'])
            for drive,reserve in (('C:/',50),('G:/',75)):
                self.assertGreater(shutil.disk_usage(drive).free,reserve*1024**3,'Disk reserve breached')
            cell=output/'cells'/job['cell_id'];cell.mkdir(parents=True)
            c=root=ui=engine=None;observer=ClockObserver();audit=PresentationAudit(observer);screenshots=[]
            result=dict(**job,status='FAILED',scope=SCOPE);started=time.perf_counter();samples=[];render_errors=[]
            cpu_started=sum(process.cpu_times()[:2])
            try:
                data=cell/'data';data.mkdir()
                shutil.copyfile(admission['inputs']['runtime_config']['path'],data/'n2_runtime.json')
                shutil.copyfile(admission['inputs']['n3_runtime_config']['path'],data/'n3_runtime.json')
                c=Controller(data,admission['models_root'],saved_audio_only=True)
                c.config=replace(c.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
                root=tk.Tk();root.report_callback_exception=lambda kind,value,tb:render_errors.append(''.join(traceback.format_exception(kind,value,tb)))
                ui=PrototypeUI(root,c,allow_auto_start=False);root.update()
                self.assertEqual((root.winfo_width(),root.winfo_height()),(480,800))
                self.assertEqual(ui.active_region.winfo_height(),184)
                backend_key='nemotron_600m' if job['variant']=='A2' else 'nemotron_35_600m'
                selected=next(r['id'] for r in backend_catalog() if r['key']==backend_key)
                c.select_backend(selected);wait_commands(c,root)
                encoder=job['combination'][-2:]
                document=load(admission['inputs'][encoder+'_gallery']['path'])
                namespace=c.models.document['embedding_namespace'] if encoder=='E1' else redim_namespace(c.config)
                c.store=ResearchStore(document,namespace,data/'research_gallery_read_only',N2Gallery)
                c.n2_observer_factory=lambda session_id:observer
                original_record=c.record_presentation;currently_applied={}
                def record(receipt):
                    original_record(receipt)
                    row=currently_applied[receipt['row_id']]
                    audit.observe(receipt,row)
                c.record_presentation=record
                # The common UI intentionally suppresses duplicate receipts when
                # finality changes but text/label do not. Audit that real render
                # completion separately; do not invent a record_presentation call.
                original_present=ui._record_presentations
                def applied(rows,current,active):
                    currently_applied.clear();currently_applied.update({str(r['id']):r for r in rows})
                    original_present(rows,current,active)
                    for row in rows:
                        rid=str(row['id']);spans=[str(s) for s in row.get('span_ids') or [rid]]
                        self.assertIn(current[rid][1],ui.caption_text.get(*ui._marks[rid]))
                        if row.get('final') and any(audit.spans.get(s,{}).get('first_final') is None for s in spans):
                            receipt=dict(row_id=rid,span_ids=spans,label=current[rid][0] or ui._display_row(row)[0],
                                applied_monotonic_sec=time.perf_counter(),pane='active' if rid in active else 'history')
                            audit.observe(receipt,row,kind='verified_Tk_final_state_after_render')
                ui._record_presentations=applied
                from .final_state_audit import observe_final_rows
                original_render=ui._render_rows
                def rendered(rows,force=False):
                    value=original_render(rows,force=force)
                    observe_final_rows(ui,rows,audit)
                    return value
                ui._render_rows=rendered
                c.switch(mode=job['mode'],recipe='balanced',tap=job['audio']['tap'],
                         selected_ids=[r['id'] for r in c.store.list()],strict=False)
                wait_commands(c,root);c.start_file(job['audio']['audio_path']);wait_commands(c,root)
                engine=c.engine;self.assertIsNotNone(engine);(engine.session_dir/'PINNED').touch()
                next_sample=0.;captured=set()
                while c.state in ('RUNNING','STARTING','STOPPING'):
                    root.update();elapsed=time.perf_counter()-started
                    if render_errors:raise RuntimeError(render_errors[0])
                    if elapsed>job['audio']['frames']/16000*25+180:raise TimeoutError('GUI cell timeout')
                    if elapsed>=next_sample:
                        samples.append(dict(elapsed_sec=elapsed,rss_bytes=process.memory_info().rss,
                            cpu_seconds=sum(process.cpu_times()[:2])-cpu_started,source_samples=engine._journal.committed_samples))
                        atomic(output/'PROGRESS.json',dict(active=job['cell_id'],completed=len(report['cells']),elapsed_sec=elapsed))
                        next_sample=elapsed+2
                    milestones=(['FIRST_APPLIED'] if audit.receipts else [])+(['FIRST_FINAL'] if any(v['first_final'] for v in audit.spans.values()) else [])
                    for milestone in milestones:
                        if milestone in captured:continue
                        capture_start=time.perf_counter();shot=helper.render_client(root,cell/(milestone+'.png'))
                        screenshots.append(dict(milestone=milestone,capture_monotonic_sec=capture_start,
                            receipt_count_at_capture=len(audit.receipts),capture_seconds=time.perf_counter()-capture_start,**shot));captured.add(milestone)
                    time.sleep(.01)
                # Let the unchanged common pending-label timer apply its last
                # state. This remains real elapsed time after source drainage.
                settle=time.perf_counter()+1.4
                while time.perf_counter()<settle:root.update();time.sleep(.01)
                snapshot=c.snapshot();ui.poll();root.update()
                self.assertFalse(render_errors);self.assertEqual(c.state,'STOPPED');self.assertFalse(c.error)
                self.assertEqual(engine._journal.committed_samples,job['audio']['frames'])
                self.assertTrue(all(w.accepted==w.completed and not w.error for w in engine.text_writers))
                self.assertEqual(snapshot['backend_id'],selected);self.assertEqual(ui.snapshot['backend_id'],selected)
                self.assertIsNotNone(observer.origin)
                spans={str(s) for r in snapshot['rows'] for s in r.get('span_ids') or [r['id']]}
                self.assertTrue(spans.issubset(audit.spans))
                self.assertTrue(all(audit.spans[s]['first_applied'] for s in spans))
                self.assertTrue(all(audit.spans[str(s)]['first_final'] for r in snapshot['rows'] if r.get('final') for s in r.get('span_ids') or [r['id']]))
                self.assertTrue(all(r.get('profile_id') is None for r in snapshot['rows']),'Uncalibrated names cannot become verified')
                if job['example'] in {'boundary','short','returning'}:self.assertTrue(snapshot['rows'],'Missing speech-caption denominator')
                if job['mode']=='selected_closed':
                    choices=[r for r in snapshot['rows'] if r.get('display_profile_id')]
                    self.assertTrue(choices,'Actual closed main-engine names never reached Controller/Tk')
                    self.assertTrue(all(r['label'].endswith(' \u00b7 assumed') and r['display_profile_id'] in {p['id'] for p in c.store.list()} for r in choices))
                    self.assertTrue(any(' \u00b7 assumed' in r['label'] for r in audit.receipts),'No actual assumed-name Tk receipt')
                else:
                    self.assertTrue(all(r['label']=='Unknown' and r.get('display_profile_id') is None for r in snapshot['rows']))
                capture_start=time.perf_counter();shot=helper.render_client(root,cell/'LATEST.png')
                screenshots.append(dict(milestone='LATEST',capture_seconds=time.perf_counter()-capture_start,**shot))
                atomic(cell/'FINAL_SNAPSHOT.json',snapshot)
                result.update(status='COMPLETE',session=str(engine.session_dir),row_count=len(snapshot['rows']),
                    stable_span_count=len(spans),gui_receipt_count=len(audit.receipts),logical_client=[480,800],active_height_px=184,
                    all_samples=True,writers_drained=True,backend_id=selected,source_epoch_monotonic_sec=observer.origin,
                    calibration_status=engine.prototype_identity.gallery.calibration['status'],
                    gallery_id=engine.prototype_identity.gallery.gallery_id,main_engine_gallery=True,
                    no_truth_oracle=True,telemetry=engine.telemetry())
            except BaseException as exc:result.update(error=repr(exc),traceback=traceback.format_exc())
            finally:
                if c is not None:
                    try:
                        c.close();wait_commands(c,root,130);c.worker.join(10)
                        if c.worker.is_alive() or not c.closed:raise RuntimeError('Controller did not close')
                        result['controller_closed']=True
                    except BaseException as exc:result.update(status='FAILED',cleanup_error=repr(exc))
                    try:
                        archive_receipt=archive_integrity_receipt(c,engine)
                        atomic(cell/'ARCHIVE_INTEGRITY.json',archive_receipt)
                        validate_archive_integrity(archive_receipt,job['audio']['frames'])
                        result['archive_integrity_passed']=True
                    except BaseException as exc:
                        result.update(status='FAILED',archive_integrity_passed=False,archive_integrity_error=repr(exc))
                if ui is not None:
                    try:ui._closed=True;root.destroy()
                    except tk.TclError:pass
                for name,rows in (('PRESENTATION_RECEIPTS',audit.receipts),('FINAL_STATE_APPLIED',audit.final_observations)):
                    with (cell/(name+'.jsonl')).open('w',encoding='utf-8') as stream:
                        for row in rows:stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
                atomic(cell/'SPAN_PRESENTATION_SUMMARY.json',audit.spans);atomic(cell/'SOURCE_CLOCK.json',observer.events)
                atomic(cell/'PROCESS_SAMPLES.json',samples)
                result.update(elapsed_seconds=time.perf_counter()-started,screenshots=screenshots,
                    peak_sampled_rss_bytes=max((r['rss_bytes'] for r in samples),default=None),physical_scanout='NOT_MEASURED',
                    evidence=[bound(p) for p in sorted(cell.glob('*.json*')) if p.name!='RESULT.json'])
                atomic(cell/'RESULT.json',result);report['cells'].append(result);atomic(output/'GUI_PANEL_REPORT.json',report)
            if result['status']!='COMPLETE':break
        check_binding(admission)
        report.update(status='COMPLETE' if len(report['cells'])==len(admission['jobs']) and all(r['status']=='COMPLETE' for r in report['cells']) else 'FAILED')
        atomic(output/'GUI_PANEL_REPORT.json',report)
        self.assertEqual(report['status'],'COMPLETE',str([(r['cell_id'],r.get('error'),r.get('cleanup_error')) for r in report['cells'] if r['status']!='COMPLETE']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','common-source','models-root','runtime-config','n3-runtime-config','regression-manifest','screen-manifest','e0-gallery','e1-gallery','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--cpu',type=int,choices=[4],default=4);parser.add_argument('--tap',choices=['O0','O1'],default='O0')
    parser.add_argument('--cell',action='append',help='Explicit smoke subset; full panel is six cells')
    parser.add_argument('--timeout-seconds',type=float,default=2400)
    parser.add_argument('--prepare-only',action='store_true',help='Bind inputs without starting Tk or loading models')
    args=parser.parse_args();source=args.source.resolve(strict=True);output=args.output.resolve()
    if output.exists() or output.is_relative_to(source):raise ValueError('Output must be fresh and outside frozen source')
    common=args.common_source.resolve(strict=True)
    inputs={name:bound(getattr(args,name)) for name in ('runtime_config','n3_runtime_config','regression_manifest','screen_manifest','e0_gallery','e1_gallery')}
    inputs['E0_gallery']=inputs.pop('e0_gallery');inputs['E1_gallery']=inputs.pop('e1_gallery')
    for encoder in ('E0','E1'):admit_gallery(load(inputs[encoder+'_gallery']['path']))
    jobs=audio_jobs(load(args.regression_manifest),load(args.screen_manifest),args.tap)
    if args.cell:
        if set(args.cell)-{j['cell_id'] for j in jobs}:raise ValueError('Unknown requested panel cell')
        jobs=[j for j in jobs if j['cell_id'] in args.cell]
    for job in jobs:validate_audio(job['audio'])
    admission=dict(schema='n2-actual-gui-admission-v1',scope=SCOPE,source=str(source),common_source=str(common),output=str(output),
        models_root=str(args.models_root.resolve(strict=True)),inputs=inputs,source_bindings=source_bindings(source),
        common_ui_sha256={name:digest(common/name) for name in COMMON_FILES},common_layout_sha256=digest(common/'config/ui.json'),jobs=jobs,
        full_panel=len(jobs)==6,job_count=len(jobs),cpu=args.cpu,cpu_affinity=[4,14],threads=1,saved_audio_only=True,gain=1.,
        runner=bound(__file__),capture_helper_sha256=digest(source/'tests/test_n1_capture.py'),io_helper=bound(IO_HELPER),io_version=_io.IO_VERSION,
        identity_scope='Actual main engine; explicit research E roster, no calibrated XVF query names; closed choices assumed',
        screenshot_scope='PrintWindow of private known application only',no_input_injection=True,no_switch_desktop=True)
    check_binding(admission);atomic(output/'ADMISSION.json',admission)
    if args.prepare_only:print(json.dumps(dict(status='PREPARED_NOT_EXECUTED',admission=str(output/'ADMISSION.json'))));return 0
    return run_isolated_cells(admission,args.timeout_seconds)


if __name__=='__main__':raise SystemExit(main())
