"""Operator source composition binding; README_FIELD_OPERATOR_V1.md."""
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import threading
import time
from isolated_live_facade_v8 import IsolatedLiveFacade
from isolated_live_transport_v5 import SourceFault
from app.live_timing import CaptureTimeline, LiveTimingError


@dataclass(frozen=True)
class IsolatedLiveConfig:
    config_path: Path
    prototype: Path


class RemoteLiveStatus:
    """Controller ownership view; the PortAudio handle belongs to the child."""
    stream = None
    beam_diagnostics = None

    def __init__(self, source): self.source = source

    def status(self):
        source = self.source
        terminal = source.facade.terminal or {}
        original = terminal.get('source_close', {}).get('final_status', {})
        return dict(original, started=source.facade.transport is not None,
                    route_started=source.start_metadata is not None,
                    finished=source.facade.closed, converted_samples=source.facade.delivered,
                    pending_source_child=not source.facade.closed)


class IsolatedPipelineSource:
    def __init__(self, journal, live_config, callback, spatial_provider=None):
        if not isinstance(live_config, IsolatedLiveConfig):
            raise ValueError('Isolated source requires an explicitly admitted process configuration')
        if spatial_provider is not None and (getattr(spatial_provider,'enabled',False) or getattr(spatial_provider,'display',False)):
            raise ValueError('Isolated beam telemetry is unavailable; spatial modes are not admitted')
        self.facade = IsolatedLiveFacade(live_config.config_path, live_config.prototype)
        self.live = RemoteLiveStatus(self)
        self.journal, self.callback = journal, callback
        self.spatial_provider = spatial_provider
        self.thread = None; self.stop_event = threading.Event(); self._done = threading.Event()
        self.start_metadata = self.stop_receipt = self.integrity = self.timing = None
        self.clock_metadata = None; self.sent = 0; self.error = None
        self.secondary_errors = []; self.discarded_after_failure_samples = 0
        self.recent_ipc = deque(maxlen=64)

    def _error(self, exc):
        text = str(exc)
        primary = getattr(self.journal,'fatal_error',None)
        if self.error is None: self.error = primary or 'ISOLATED_LIVE_FAILURE: '+text
        elif text not in self.error and text not in self.secondary_errors: self.secondary_errors.append(text)
        self.stop_event.set()
        if isinstance(exc,LiveTimingError):
            self.callback('source_timing',dict(failure=exc.check,evidence=exc.evidence))

    def start(self):
        if self.thread is not None or self._done.is_set(): raise RuntimeError('Source cannot restart; create a fresh epoch')
        try:
            self.start_metadata = self.facade.start()
            self.facade.transport.outputs.request_stop = self.stop_event.set
            self.thread = threading.Thread(target=self._run,name='proto-isolated-live-source',daemon=True)
            self.thread.start()
        except Exception as exc:
            self._error(exc)
            self._finish()
            raise RuntimeError(self.error) from exc

    def _accept(self, block, ipc):
        if self.sent+len(block.audio)>2080000:
            raise SourceFault('ADMITTED_SOURCE_FRAME_LIMIT')
        if self.timing is None:
            self.timing = CaptureTimeline(self.start_metadata,block)
            self.clock_metadata = self.timing.metadata()
            self.callback('source_started',dict(mode='live',route=self.start_metadata['route'],
                endpoint=self.start_metadata['endpoint'],capture_metadata=self.start_metadata,
                clock_not_calibrated_to_acoustic_arrival=True,**self.clock_metadata))
        self.timing.accept(block,time.perf_counter_ns())
        if (self.sent+len(block.audio))/16000 > time.perf_counter()-self.timing.origin:
            raise RuntimeError('Source support ahead of immutable capture timeline')
        if self.spatial_provider is not None: self.spatial_provider.advance_audio(block)
        self.journal.append(block.audio)
        self.sent += len(block.audio)
        from dataclasses import fields
        import hashlib
        row = dict(samples=len(block.audio),
            metadata={f.name:getattr(block,f.name) for f in fields(block) if f.name!='audio'},ipc=ipc,
            audio_sha256=hashlib.sha256(block.audio.astype('<f4',copy=False).tobytes()).hexdigest())
        # On write failure the real source Event is set before diagnostics.
        self.facade.transport.outputs.trace(row)
        self.recent_ipc.append(dict(start_sample=block.model_start_sample,samples=len(block.audio),**ipc))
        if self.sent>=1920000:
            self.stop_event.set()
            self.callback('source_limit',dict(reason='Admitted120s source boundary; draining accepted input'))

    def _run(self):
        stop_deadline = None
        try:
            while self.facade.terminal is None:
                if self.stop_event.is_set() and stop_deadline is None:
                    self.facade.request_stop(); stop_deadline=time.monotonic()+60
                if stop_deadline is not None and time.monotonic()>stop_deadline:
                    raise SourceFault('SOURCE_DRAIN_DEADLINE')
                try: item=self.facade.read(.02)
                except SourceFault as exc:
                    self._error(exc)
                    if self.facade.terminal is not None: break
                    raise
                if item is None: continue
                block,ipc=item
                if self.error:
                    self.discarded_after_failure_samples += len(block.audio)
                    continue
                accepted_before = self.sent
                try: self._accept(block,ipc)
                except Exception as exc:
                    # Input ownership still drains; failed journal/timing support
                    # is explicitly uncredited, never silently marked complete.
                    if self.sent == accepted_before:
                        self.discarded_after_failure_samples += len(block.audio)
                    self._error(exc)
        except Exception as exc: self._error(exc)
        finally: self._finish()

    def _finish(self):
        try:
            if self.facade.transport is not None and self.facade.terminal is None:
                self.facade.request_stop(); deadline=time.monotonic()+60
                while self.facade.terminal is None and time.monotonic()<deadline:
                    try:
                        item=self.facade.transport.read(.02)
                        if item is not None:self.discarded_after_failure_samples+=len(item[1])//4
                    except SourceFault as exc:
                        self._error(exc)
                        if self.facade.terminal is None:break
            if self.facade.terminal is None: raise SourceFault('SOURCE_OWNER_NOT_CLOSED')
            self.stop_receipt = self.facade.finalize()
            t=self.stop_receipt['terminal'];close=t.get('source_close',{})
            reasons=[]
            if t['fault']:reasons.append(t['fault']['code'])
            if self.stop_receipt['child_exit']!=0:reasons.append('CHILD_EXIT')
            if not close.get('stream_closed') or not close.get('lease_released'):reasons.append('SOURCE_CLOSE_UNQUALIFIED')
            if self.sent!=t['sent_samples'] or self.discarded_after_failure_samples:reasons.append('JOURNAL_SOURCE_COVERAGE')
            if self.error:reasons.append('SOURCE_OR_JOURNAL_ERROR')
            self.integrity=dict(ok=not reasons,reasons=reasons,source_samples=t['sent_samples'],
                journal_samples=self.sent,discarded_after_failure_samples=self.discarded_after_failure_samples,
                child_closed=self.facade.closed,source_terminal=close)
            if reasons and not self.error:self.error='ISOLATED_LIVE_INTEGRITY: '+', '.join(reasons)
        except Exception as exc:self._error(exc)
        finally:
            if self.integrity is None and self.facade.physical_closure is not None:
                self.integrity=dict(ok=False,reasons=['SOURCE_FINALIZATION_FAILED'],
                    child_closed=self.facade.closed,physical_closure=self.facade.physical_closure,
                    source_samples=self.facade.terminal['sent_samples'],journal_samples=self.sent,
                    discarded_after_failure_samples=self.discarded_after_failure_samples,
                    original_error=self.error)
            try:
                self.callback('source_stopped',dict(integrity=self.integrity,converted_samples_delivered=self.sent,
                    secondary_errors=self.secondary_errors,timing=self.timing.snapshot() if self.timing else None))
                if self.error:self.callback('fatal',dict(reason=self.error,integrity=self.integrity))
            finally:
                self.journal.finish(self.error);self._done.set()

    def stop(self):
        self.stop_event.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(65)
            if self.thread.is_alive(): raise RuntimeError('Source thread still owns accepted input; ownership retained')
        elif not self._done.is_set(): raise RuntimeError('Source has not started')
        if not self.facade.closed: raise RuntimeError('Source child ownership remains open')
        if self.error: raise RuntimeError(self.error)

    def wait(self,timeout=None):return self._done.wait(timeout)


def bind_pipeline(module):
    """Explicit per-process binding; never edit the installed application."""
    if module.LivePipelineSource is IsolatedPipelineSource:raise RuntimeError('Binding already installed')
    previous=module.LivePipelineSource
    module.LivePipelineSource=IsolatedPipelineSource
    return previous
