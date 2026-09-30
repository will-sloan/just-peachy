"""Actual controller archive-failure binding; README_FIELD_CONTROLLER_STOP_V1.md."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import queue
import threading
from field_archive_stop_v1 import archive_class, ArchiveStopped
from field_sidecar_budget_v1 import encoded


def controller_class(module, sessions, outputs, policy, expected_controller_sha):
    source=Path(module.__file__)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected_controller_sha:
        raise ValueError('Installed controller source changed')
    tree=ast.parse(source.read_bytes())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Controller')
    method=deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_start_session'))
    handlers=[n for n in ast.walk(method) if isinstance(n,ast.ExceptHandler) and isinstance(n.type,ast.Name) and n.type.id=='OSError']
    if len(handlers)!=1 or 'Archive unavailable; live captions continue:' not in ast.unparse(handlers[0]):
        raise ValueError('Unexpected archive preparation handler')
    handlers[0].body=[ast.Raise()]
    starts=[(i,n) for i,n in enumerate(method.body) if isinstance(n,ast.Try) and 'engine.start_prepared_file' in ast.unparse(n)]
    if len(starts)!=1:raise ValueError('Unexpected source start boundary')
    method.body[starts[0][0]:starts[0][0]]=ast.parse("if self._archive_failure is not None:raise RuntimeError('Archive failed before source start')").body
    namespace=dict(module.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(source)+':archive-required','exec'),namespace)
    selected_start=namespace['_start_session'];Base=module.Controller
    OriginalArchive=sessions.EpochArchive

    class RequiredArchiveController(Base):
        def __init__(self,*args,**kwargs):
            self._archive_failure_lock=threading.RLock()
            self._archive_failure=None;self._archive_stop_pending=threading.Event()
            self._archive_stop_processed=False;self._archive_stop_observations=[]
            self._archive_cleanup_error=None
            super().__init__(*args,**kwargs)

        def _sessions_initialize(self):
            super()._sessions_initialize()
            if self.session_store.active:raise RuntimeError('Fresh inactive archive store required')
            sessions.EpochArchive=archive_class(OriginalArchive,outputs,self.request_archive_stop)
            self.session_store.policy.update(deepcopy(policy))
            self.session_store.archive_budget=deepcopy(policy['archive_budget'])
            # Explicit no-delete policy for this candidate.
            def no_delete(exclude=None):
                if len(self.session_store.list())>=self.session_store.policy['draft_limit']:
                    raise OSError('Manage history explicitly before another draft')
                if self.session_store.usage()['bytes']>=self.session_store.policy['quota_mib']*1024**2:
                    raise OSError('Archive quota reached; history preserved')
            self.session_store.enforce=no_delete

        def request_archive_stop(self,reason='ARCHIVE_WORKER_FAILED'):
            # No controller lock, queue put, filesystem write, join or hardware call here.
            # Archive worker can call while command worker is joining it.
            with self._archive_failure_lock:
                if self._archive_failure is not None:return
                self._archive_failure='ARCHIVE_REQUIRED: '+str(reason)[:512]
                source=getattr(getattr(self,'engine',None),'_source',None)
                event=getattr(source,'stop_event',None)
                signaled=isinstance(event,threading.Event)
                if signaled:event.set()
                self._archive_stop_observations.append(dict(caller=threading.current_thread().name,
                    source_event_signaled=signaled,source_present=source is not None))
                self._archive_stop_pending.set()
                self._reassert_archive_failure()

        def _reassert_archive_failure(self):
            if self._archive_failure is not None:
                self.error=self._archive_failure
                self.status=self._archive_failure
                if not getattr(self,'closed',False):self.state='ERROR'

        def _archive_prepare(self,profile):
            try:
                value=super()._archive_prepare(profile)
                if value is None:raise OSError('Archive preparation returned no owner')
                return value
            except Exception as exc:
                self.request_archive_stop(type(exc).__name__+': '+str(exc))
                outputs.fail('entry',exc,self.request_archive_stop,encoded({'error':str(exc)[:1024]}))
                raise

        def _start_session(self):
            if self._archive_failure is not None:raise RuntimeError('Failed run cannot restart in this process')
            try:return selected_start(self)
            except BaseException:
                if self._archive_failure is not None:
                    try:self._stop_session()
                    except Exception as exc:self._archive_cleanup_error=repr(exc)[:512]
                    self._reassert_archive_failure()
                raise

        def _archive_end(self,archive):
            try:return super()._archive_end(archive)
            except ArchiveStopped:
                self.request_archive_stop()
                if archive.thread.is_alive() or not archive.closed:raise
                # Worker physically closed; retain failed primary and independent closure.
                identifier=archive.metadata['conversation_id']
                if self.session_store.active.get(identifier) is archive:self.session_store.active.pop(identifier)
                if self.archive is archive:self.archive=None
                self.metrics['last_archive']=dict(archive.snapshot(),failed=True,worker_joined=True)
                self._refresh_sessions()
                self._reassert_archive_failure()

        def _do_stop(self):
            try:
                super()._do_stop()
                if self.archive is not None:self._archive_end(self.archive)
            finally:self._reassert_archive_failure()

        def _commands(self):
            while True:
                if self._archive_stop_pending.is_set() and not self._archive_stop_processed:
                    self._archive_stop_processed=True
                    try:self._do_stop()
                    except Exception as exc:self._archive_cleanup_error=repr(exc)[:512]
                    self._reassert_archive_failure()
                try:item=self.commands.get(timeout=.05)
                except queue.Empty:continue
                try:
                    if item is None:return
                    action,args,kwargs=item
                    if self._archive_failure is not None and action not in ('stop','close'):
                        raise RuntimeError('Failed run permits only Stop and Close')
                    self.error=self._archive_failure
                    getattr(self,'_do_'+action)(*args,**kwargs)
                except Exception as exc:
                    self.error=f'{type(exc).__name__}: {exc}';self.status=self.error
                    if self.state not in ('RUNNING','ENROLLING'):self.state='ERROR'
                finally:
                    self._reassert_archive_failure()
                    self.commands.task_done()
    return RequiredArchiveController
