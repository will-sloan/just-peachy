"""Attach the qualified viewport ledger to actual rendering. README_PACED_APPLICATION_CELL.md."""
from copy import deepcopy
from pathlib import Path
import threading
import time
from common import bind,freeze
from viewport_ledger_v2 import ViewportLedger
from widget_visibility import snapshot


class PacedViewport:
    def __init__(self, ui, clock, output, *, interval_ms=100):
        if type(interval_ms) is not int or not 50<=interval_ms<=1000:raise ValueError('Bounded viewport interval required')
        if getattr(ui,'_n4_viewport_observer',None) is not None:raise ValueError('Duplicate viewport observer')
        self.ui=ui;self.clock=clock;self.output=Path(output);self.interval=interval_ms
        self.thread=threading.get_ident();self.ledger=ViewportLedger(self.output)
        self.original=ui._render_rows;self.had_instance='_render_rows' in vars(ui)
        self.rows=None;self.strict=None;self.timer=None;self.closed=False;self.failure=None
        self.render_calls=0;self.periodic_calls=0;self.deferred_context=0;self.elapsed=0.;self.capturing=False
        def rendered(rows,force=False):
            try:value=self.original(rows,force=force)
            except Exception as exc:
                self._fail('original_render',exc);raise
            self.render_calls+=1;self.rows=deepcopy(rows);self.strict=bool(ui.snapshot.get('strict'))
            self._capture('render')
            return value
        self.wrapper=rendered;ui._render_rows=rendered;ui._n4_viewport_observer=self
        self.timer=ui.root.after(self.interval,self._tick)

    def _fail(self,where,exc):
        if self.failure is None:self.failure=dict(where=where,type=type(exc).__name__,message=str(exc)[:2048])

    def _capture(self,kind):
        if threading.get_ident()!=self.thread:raise ValueError('Observe widgets only on their original Tk thread')
        if self.closed or self.failure is not None or self.rows is None or self.capturing:return
        # Poll may update snapshot before its smoothed render. Never combine the
        # new strict-filter setting with the previous displayed rows/widgets.
        if bool(self.ui.snapshot.get('strict'))!=self.strict:
            self.deferred_context+=1;return
        began=time.perf_counter();self.capturing=True
        try:
            self.ui.root.update_idletasks()
            source=self.clock.snapshot();available=source['source_event_clock_available']
            origin=source['source_epoch_monotonic_sec'] if available else None
            seen=snapshot(self.ui,self.rows,source_origin=origin,
                source_clock='ACTUAL_SOURCE_MONOTONIC' if available else 'UNAVAILABLE')
            self.ledger.add(seen)
            if kind=='timer':self.periodic_calls+=1
        except Exception as exc:self._fail('viewport',exc)
        finally:self.elapsed+=time.perf_counter()-began;self.capturing=False

    def _tick(self):
        self.timer=None
        if self.closed:return
        self._capture('timer')
        if self.failure is None:self.timer=self.ui.root.after(self.interval,self._tick)

    def check(self):
        if self.failure is not None:raise RuntimeError('Viewport observer failed: '+str(self.failure))

    def close(self):
        if threading.get_ident()!=self.thread:raise ValueError('Close on the original Tk thread')
        if self.closed:raise ValueError('Viewport observer already closed')
        self._capture('final')
        if self.timer is not None:
            self.ui.root.after_cancel(self.timer);self.timer=None
        if self.ui._render_rows is not self.wrapper or self.ui._n4_viewport_observer is not self:
            self._fail('ownership',ValueError('Render hook changed; foreign hook retained'))
        else:
            if self.had_instance:self.ui._render_rows=self.original
            else:del self.ui._render_rows
            del self.ui._n4_viewport_observer
        self.closed=True;ledger=self.ledger.close()
        result=dict(status='FAILED_PRESERVED_PREFIX' if self.failure else 'RECORDED_RENDER_AND_TIMER_OBSERVATIONS',
            failure=self.failure,render_calls=self.render_calls,periodic_calls=self.periodic_calls,
            deferred_context=self.deferred_context,observer_elapsed_sec=self.elapsed,
            timer_cancelled=self.timer is None,ledger=bind(self.output/'SUMMARY.json'),
            samples=ledger['samples'],actual_source_delivery_verified=False,
            source_to_widget_latency_qualified=False,physical_scanout_measured=False,integrated_N4_cells=0)
        freeze(self.output/'RESULT.json',result);return result
