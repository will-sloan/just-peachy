"""Private single-cell application primitive; no standalone launch. README_PACED_APPLICATION_CELL.md."""
from dataclasses import replace
import ctypes
from pathlib import Path
import shutil
import threading
import time
import traceback
from common import audio_only,bind,freeze,load,verify
from application_resources import ApplicationResources


def private_desktop():
    from prototype.tests.run_private_desktop import desktop_name,setup_api
    user=setup_api();name=desktop_name(user.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId()))
    if not name.startswith('codex-n1-'):raise ValueError('Actual Tk requires the admitted private desktop')
    return name


class ApplicationCell:
    """One fresh GUI/Controller, fixed gallery, source clock and bounded observers.

    This is an internal primitive. The campaign launcher must first admit the
    reviewed shortlist, audio/profile/source hashes and exclusive resource slot.
    Development qualification calls prepare/close only and forbids acquisition.
    """
    def __init__(self, output, job, contract):
        self.desktop=private_desktop();self.output=Path(output);self.output.mkdir(parents=True,exist_ok=False)
        self.job=audio_only(job);self.contract=contract;self.root=self.ui=self.c=None
        self.clock=self.viewport=None;self.engine=self.consumer=None;self.errors=[];self.started=False;self.closed=False
        self.resources=ApplicationResources(self.output/'resources').start()
        self.began=time.perf_counter();self.result=None;self.run_completed=False;self.run_error=None

    def prepare(self, *, source, models_root, runtimes, gallery_preparation):
        if self.c is not None or self.closed:raise ValueError('Fresh application cell required')
        from app.controller import Controller
        from app.backends import backend_catalog
        from app.ui import PrototypeUI,prepare_dpi_awareness
        from mode_galleries import backend_contract
        from paced_adapters_v3 import ConsumerSourceClock,PacedResearchPeople
        from paced_viewport import PacedViewport
        import app.ui as ui_module
        import tkinter as tk
        if Path(ui_module.__file__).resolve()!=Path(source).resolve()/'app/ui.py':raise ValueError('Wrong common frontend source')
        verify(gallery_preparation);g=load(gallery_preparation['path']);verify(g['catalog'])
        if bind(Path(source)/'config/backends.json')!=g['catalog']:raise ValueError('Gallery/source catalog differs')
        expected=backend_contract(load(g['catalog']['path']),self.contract['backend_key'],self.contract['mode'])
        if expected!=self.contract:raise ValueError('Backend/mode contract changed')
        data=self.output/'data';data.mkdir()
        if {Path(b['path']).name for b in runtimes}!={'n2_runtime.json','n3_runtime.json'} or len(runtimes)!=2:
            raise ValueError('Both exact runtime metadata files required')
        for b in runtimes:
            verify(b);target=data/Path(b['path']).name;shutil.copyfile(b['path'],target)
            if bind(target)['sha256']!=b['sha256']:raise ValueError('Runtime copy changed')
        self.c=Controller(data,models_root,saved_audio_only=True)
        self.c.config=replace(self.c.config,asr_threads=1,speaker_threads=1,punctuation_threads=1)
        prepare_dpi_awareness();self.root=tk.Tk()
        self.root.report_callback_exception=self._callback_error
        self.ui=PrototypeUI(self.root,self.c,allow_auto_start=False);self.root.update()
        if (self.root.winfo_width(),self.root.winfo_height())!=(480,800) or self.ui.active_region.winfo_height()!=184:
            raise ValueError('Common frontend geometry changed')
        self.resources.mark('gui_ready')
        backend=next(row['id'] for row in backend_catalog() if row['key']==self.contract['backend_key'])
        self.c.select_backend(backend);self.wait_commands()
        self.c.store=PacedResearchPeople(gallery_preparation,self.contract,data/'research-roster',self.job['tap'])
        selected=[p['id'] for p in self.c.store.list()] if self.contract['mode'] in ('selected_focus','selected_closed') else []
        self.c.switch(mode=self.contract['mode'],recipe='balanced',tap=self.job['tap'],selected_ids=selected,strict=False)
        self.wait_commands()
        if self.c.route()!=self.c.store.expected_route() or self.c.collect_references or self.c.use_references:
            raise ValueError('Primary route or adaptation state changed')
        if self.c.settings.get('text_assistance',False) or self.c.settings.get('text_aware_references',False):
            raise ValueError('Primary text/reference assistance must remain off')
        self.clock=ConsumerSourceClock(self.job).install(self.c)
        self.viewport=PacedViewport(self.ui,self.clock,self.output/'viewport')
        self.resources.mark('gallery_ready');self.ui.poll();self.root.update()
        self.check()
        receipt=dict(status='PREPARED_NO_SOURCE_OR_MODELS_STARTED',desktop=self.desktop,backend_id=backend,
            contract=self.contract,job=self.job,gallery_condition=self.c.store.condition,
            logical_client=[480,800],active_height_px=184,selected_ids=selected,
            source=bind(Path(source)/'app/ui.py'),runtimes=runtimes,gallery_preparation=gallery_preparation,
            no_auto_start=True,integrated_N4_cells=0)
        freeze(self.output/'PREPARED.json',receipt);return receipt

    def _callback_error(self,kind,value,tb):
        if len(self.errors)<8:self.errors.append(''.join(traceback.format_exception(kind,value,tb))[:4096])

    def check(self):
        if self.errors:raise RuntimeError(self.errors[0])
        if self.c is not None and self.c.error:raise RuntimeError(self.c.error)
        if self.viewport is not None:self.viewport.check()
        if self.resources.error is not None:raise RuntimeError(self.resources.error)

    def wait_commands(self,timeout=180,*,check=True):
        deadline=time.perf_counter()+timeout
        while self.c.commands.unfinished_tasks:
            if time.perf_counter()>deadline:raise TimeoutError('Application command did not finish')
            if self.root is not None:self.root.update()
            time.sleep(.01)
        if check:self.check()

    def run_source(self, *, admission_check):
        # No CLI bypass: the future reviewed campaign launcher supplies its
        # binding/resource/deadline check immediately before the real command.
        # No fabricated admission is created by the model-free probe.
        if self.c is None or self.clock is None or self.started or self.closed:raise ValueError('Prepared fresh application required')
        admission_check(self.job,self.contract)
        self.check();self.resources.mark('starting');self.started=True
        try:
            self.c.start_file(self.job['audio_path']);self.wait_commands()
            self.engine=self.c.engine;self.consumer=self.c.consumer
            if self.engine is None or self.consumer is None:raise RuntimeError('Actual source session did not start')
            (self.engine.session_dir/'PINNED').touch(exist_ok=False)
            self.resources.mark('running')
            timeout=min(3500,self.job['frames']/16000*25+180)
            next_guard=time.perf_counter()+1.
            while self.c.state in ('RUNNING','STARTING','STOPPING'):
                if time.perf_counter()-self.began>timeout:raise TimeoutError('Actual source cell deadline reached')
                if time.perf_counter()>=next_guard:
                    admission_check(self.job,self.contract);next_guard=time.perf_counter()+1.
                self.root.update();self.check();time.sleep(.01)
            self.resources.mark('draining')
            settle=time.perf_counter()+1.4
            while time.perf_counter()<settle:self.root.update();self.check();time.sleep(.01)
            self.ui.poll();self.root.update();self.check()
            if self.c.state!='STOPPED':raise RuntimeError('Application did not stop cleanly')
            freeze(self.output/'FINAL_SNAPSHOT.json',self.c.snapshot())
            self.run_completed=True
        except Exception as exc:
            self.run_error=repr(exc);raise
        finally:
            # Startup can fail after constructing an engine or consumer.
            self.engine=self.engine or self.c.engine;self.consumer=self.consumer or self.c.consumer

    def close(self):
        if self.closed:return self.result
        errors=[];closure=None
        if self.run_error:errors.append('Source execution: '+self.run_error)
        if self.started and not self.run_completed:errors.append('Source execution did not complete')
        if self.errors:errors.append('Tk callback failed')
        if self.c is not None and self.c.error:errors.append('Controller error: '+str(self.c.error))
        if self.c is not None:
            self.engine=self.engine or self.c.engine;self.consumer=self.consumer or self.c.consumer
            try:
                self.c.close();self.wait_commands(130,check=False);self.c.worker.join(10)
                if self.c.worker.is_alive() or not self.c.closed:raise RuntimeError('Controller owner did not exit')
            except Exception as exc:errors.append('Controller: '+repr(exc))
        if self.started:
            try:
                from application_closure_v2 import capture_engine,capture_archive,validate_complete
                observed=capture_engine(self.engine,self.consumer,self.clock,self.job)
                freeze(self.output/'ENGINE_CLOSURE.json',observed)
                archive=capture_archive(self.c,self.engine);freeze(self.output/'ARCHIVE_INTEGRITY.json',archive)
                closure=validate_complete(observed,archive)
                if self.resources.phase=='draining':self.resources.mark('closed')
            except Exception as exc:errors.append('Application closure: '+repr(exc))
        if self.viewport is not None:
            try:
                viewport=self.viewport.close()
                if viewport['failure'] is not None:raise RuntimeError(str(viewport['failure']))
            except Exception as exc:errors.append('Viewport: '+repr(exc))
        if self.clock is not None:
            freeze(self.output/'SOURCE_CLOCK.json',self.clock.snapshot())
            try:self.clock.detach()
            except Exception as exc:errors.append('Source clock: '+repr(exc))
        if self.ui is not None:self.ui._closed=True
        if self.root is not None:
            try:self.root.destroy()
            except Exception as exc:errors.append('Tk: '+repr(exc))
        resources=self.resources.close()
        if resources['status']!='OBSERVED_HOST_RESOURCES':errors.append('Resources: '+str(resources['error']))
        self.closed=True
        self.result=dict(status='CELL_CLOSED_REQUIRES_REVIEW' if self.started and closure is not None and not errors else
            'PREPARED_ONLY_CLOSED' if not self.started and not errors else 'FAILED_PRESERVED',
            source_start_requested=self.started,closure=closure,errors=errors,callback_errors=self.errors,
            controller_closed=self.c.closed if self.c is not None else None,
            controller_worker_exited=not self.c.worker.is_alive() if self.c is not None else None,
            resources=bind(self.output/'resources/RESULT.json'),source_to_widget_latency_qualified=False,
            complete_N4_acceptance=False,integrated_N4_cells=0)
        freeze(self.output/'RESULT.json',self.result);return self.result
