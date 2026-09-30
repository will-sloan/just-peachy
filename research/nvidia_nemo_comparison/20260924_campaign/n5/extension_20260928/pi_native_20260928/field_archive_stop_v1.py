"""Archive failure latch and shared sidecars; README_FIELD_ARCHIVE_STOP_V1.md."""
import threading
from field_sidecar_budget_v1 import encoded


class ArchiveStopped(RuntimeError):pass


def archive_class(Base,outputs,request_stop):
    class StoppingArchive(Base):
        def __init__(self,*args,**kwargs):
            self._publication_failure=None;self._archive_stop=False;self._sidecar_closed=False;self._close_failure=None
            self._failure_lock=threading.RLock()
            super().__init__(*args,**kwargs)

        def _stop_for_failure(self,reason):
            with self._failure_lock:
                if self._archive_stop:return
                self._archive_stop=True
                if hasattr(self,'stop_event'):self.stop_event.set()
                outputs.fail('archive',reason,request_stop,encoded(dict(error=str(reason)[:1024])))

        def fail(self,reason,start=None):
            # Signal external source Stop before the retained failure bookkeeping.
            self._stop_for_failure(reason)
            return super().fail(reason,start)

        def offer(self,*args,**kwargs):
            accepted=super().offer(*args,**kwargs)
            if not accepted and self.error is not None:self._stop_for_failure(self.error)
            return accepted

        def _remember_publication_failure(self,exc):
            if self._publication_failure is None:
                self._publication_failure=dict(error=type(exc).__name__+': '+str(exc)[:512],
                    replaced=getattr(exc,'replaced',None),temporary=getattr(exc,'temporary',None))
            self._stop_for_failure(exc)
            super().fail('ARCHIVE_PUBLICATION_FAILED: '+str(exc)[:512],getattr(self,'written_samples',None))

        def _publish(self,path,value):
            if self._publication_failure is not None:raise ArchiveStopped('Publication failed; no retry')
            try:return super()._publish(path,value)
            except Exception as exc:
                self._remember_publication_failure(exc)
                raise

        def _checkpoint(self,state):
            if self._publication_failure is not None:raise ArchiveStopped('Checkpoint publication disabled after failure')
            try:return super()._checkpoint(state)
            except Exception as exc:
                self._remember_publication_failure(exc)
                raise

        def close(self):
            self.stop_event.set();self.thread.join(10)
            if self.thread.is_alive():raise TimeoutError('Archive worker still owns files')
            if not self._sidecar_closed:
                self._sidecar_closed=True
                if self._publication_failure is None:
                    try:super().close()
                    except Exception as exc:self._remember_publication_failure(exc)
                value=dict(worker_joined=not self.thread.is_alive(),closed=self.closed,
                    source_samples=self.source_samples,recorded_samples=self.written_samples,
                    accepted_items=self.accepted,completed_items=self.completed,
                    pending_items=self.queue.qsize(),pending_bytes=self.pending_bytes,
                    publication_failure=self._publication_failure,error=self.error,
                    logical_success=self.error is None and self._publication_failure is None)
                try:outputs.finish('archive',value)
                except Exception as exc:
                    self._close_failure=type(exc).__name__+': '+str(exc)[:512]
                    self._stop_for_failure(exc)
                    raise
            if self.error is not None or self._publication_failure is not None or self._close_failure is not None:
                raise ArchiveStopped('Archive stopped with preserved failure; inspect shared closure')
            return self.snapshot()
    return StoppingArchive
