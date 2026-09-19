"""Actual Tk execution adapter; the original GUI remains the sole consumer."""
from pathlib import Path
import threading
import time
import WidgetProof


class ObservedInbox:
    def __init__(self, inbox, receipt):
        self.inbox, self.receipt = inbox, receipt

    def get(self, *args, **kwargs):
        event = self.inbox.get(*args, **kwargs)
        self.receipt(event, time.perf_counter())
        return event

    def __getattr__(self, name):
        return getattr(self.inbox, name)


class GuiEngineView:
    """Delegate to the real engine; observe only GUI reads, including a new session inbox."""
    def __init__(self, engine, receipt):
        self._engine, self._receipt, self._inbox = engine, receipt, None

    @property
    def events(self):
        inbox = self._engine.events
        if self._inbox is None or self._inbox.inbox is not inbox:
            self._inbox = ObservedInbox(inbox, self._receipt)
        return self._inbox

    def __getattr__(self, name):
        return getattr(self._engine, name)


def execute_gui(n, engine, job, output, protocol, completion_errors, timeout):
    import psutil
    import tkinter as tk
    from tkinter import messagebox
    from edge_speech_pipeline.gui import EdgeSpeechWindow

    if job['s7_settings']['availability_clock'] != 'observed' or not job['s7_settings']['presentation_enabled']:
        raise ValueError('GUI qualification requires the observed presentation path')
    actions = job.get('gui_actions', [])
    if any(set(action) != {'at_source_sec', 'action', 'value'} or action['at_source_sec'] < 0 for action in actions):
        raise ValueError('Explicit source-time user action records required; no evaluator fields')
    if [a['at_source_sec'] for a in actions] != sorted(a['at_source_sec'] for a in actions):
        raise ValueError('GUI actions must be in declared order')
    consumer = n.AsyncRows(output / 'consumer_events.jsonl')
    resource = n.AsyncRows(output / 'resources.jsonl', 256)
    acknowledgments = n.AsyncRows(output / 'gui_acknowledgments.jsonl')
    process = psutil.Process()
    halted = threading.Event()
    observer_errors, callback_errors, startup_events, action_receipts = [], [], [], []
    counters = {'consumed': 0, 'frames': 0, 'actions': 0}
    started = time.perf_counter()
    startup = None
    failure = None
    trace_closed = None
    root = window = None
    mapped = False
    startup_widgets = None

    def receipt(event, received):
        nonlocal startup
        row = event.to_jsonable()
        row['actual_consumed_monotonic_sec'] = received
        consumer.submit(row)
        counters['consumed'] += 1
        if event.event_type in {'research_models_ready', 'source_started', 'research_input_route'}:
            startup_events.append(row)
        if event.event_type == 'source_started':
            startup = received - started
        trace = getattr(engine, '_s7_trace', None)
        if trace is not None:
            payload = row.get('payload') or {}
            trace.record('consumer_receipt', event_type=event.event_type, source_end_sec=event.source_time_sec,
                         receipt_monotonic_sec=received, publication_sequence=payload.get('publication_sequence'),
                         utterance_id=payload.get('utterance_id'), event_id=payload.get('event_id'))
        protocol.advance('GUI_RUNNING')

    def observe():
        last = time.perf_counter()
        try:
            while not halted.is_set():
                now = time.perf_counter()
                memory = process.memory_full_info()
                resource.submit(dict(monotonic_sec=now, sampling_gap_sec=now-last, pid=process.pid,
                    creation_time=process.create_time(), rss=memory.rss, uss=getattr(memory, 'uss', None),
                    cpu_percent=process.cpu_percent(), threads=process.num_threads(),
                    telemetry=n.compact_telemetry(engine), consumer_writer=consumer.snapshot(),
                    gui_ack_writer=acknowledgments.snapshot()))
                last = now
                halted.wait(1.)
        except BaseException as exc:
            observer_errors.append(repr(exc))

    def callback_failed(kind, value, tb):
        callback_errors.append(f'{kind.__name__}: {value}')
        if root is not None:
            root.quit()

    # Avoid an unattended modal error waiting forever; retain its exact content as a failed run.
    original_showerror = messagebox.showerror
    def showerror(title, message, **kwargs):
        raise RuntimeError(f'Actual GUI error dialog: {title}: {message}')

    def check():
        protocol.check()
        if observer_errors:
            raise RuntimeError('GUI resource observer failed: ' + repr(observer_errors))
        if time.perf_counter() - started > timeout:
            raise TimeoutError('Bound native GUI cell deadline')
        frames = round(engine.telemetry().get('source_duration_sec', 0.)*16000)
        if frames > counters['frames']:
            protocol.advance('GUI_RUNNING', frames-counters['frames'])
            counters['frames'] = frames
        clock = getattr(engine, '_s7_observed_clock', None)
        origin = getattr(clock, 'origin', None)
        now = time.perf_counter()
        while origin is not None and counters['actions'] < len(actions):
            action = actions[counters['actions']]
            if now < origin + action['at_source_sec']:
                break
            applied = window.s7_user_action(action['action'], action['value'])
            if applied is None:
                raise RuntimeError('Declared GUI action rejected')
            record = dict(kind='s7_scripted_action', planned=action, origin_monotonic_sec=origin,
                          deadline_monotonic_sec=origin+action['at_source_sec'],
                          dispatch_monotonic_sec=now, action_receipt=applied)
            acknowledgments.submit(record)
            action_receipts.append(record)
            counters['actions'] += 1
        finalizer = engine._finalization_thread
        backgrounds = getattr(window, '_s6d_background_jobs', ())
        if finalizer is not None and not finalizer.is_alive() and engine.events.empty() and not window._s7_pending_acks and not any(t.is_alive() for t in backgrounds) and window.ui_messages.empty():
            if counters['actions'] != len(actions):
                raise RuntimeError('Source ended before all declared GUI actions ran')
            root.quit()
            return
        root.after(25, check)

    watcher = threading.Thread(target=observe, name='s7-gui-resource-observer', daemon=True)
    try:
        protocol.check()
        protocol.advance('GUI_CONSTRUCTION')
        messagebox.showerror = showerror
        root = tk.Tk()
        root.report_callback_exception = callback_failed
        view = GuiEngineView(engine, receipt)
        window = EdgeSpeechWindow(root, engine.config, engine=view)
        startup_widgets = WidgetProof.startup(window, job['s7_settings']['mode'])
        window.set_s7_ack_sink(WidgetProof.sink(window, acknowledgments.submit))
        window.wav_path = Path(job['audio']['path'])
        window.realtime_var.set(True)
        root.update_idletasks()
        mapped = bool(root.winfo_ismapped())
        if not mapped:
            raise RuntimeError('Native GUI window failed to map')
        watcher.start()
        protocol.advance('MODEL_AND_SOURCE_STARTUP')
        window._start_wav()
        root.after(25, check)
        root.mainloop()
        if callback_errors:
            raise RuntimeError('Tk callback failed: ' + repr(callback_errors))
        if engine._finalization_thread is None or engine._finalization_thread.is_alive():
            raise RuntimeError('GUI closed before native finalization')
        engine.wait_for_completion(60.)
        errors = completion_errors(engine, engine.telemetry())
        if errors:
            raise RuntimeError('; '.join(errors))
        if not engine.events.empty() or window._s7_pending_acks:
            raise RuntimeError('GUI event/idle acknowledgments not drained')
        consumer.close()
        acknowledgments.close()
        engine.record_s6d_consumer_closure('S7 actual mapped Tk GUI consumer')
        trace = getattr(engine, '_s7_trace', None)
        if trace is not None:
            trace.close()
            trace_closed = trace.snapshot()
        protocol.advance('SOURCE_AUDIT')
    except BaseException as exc:
        failure = repr(exc)
        engine.stop()
        try:
            engine.wait_for_completion(60.)
        except BaseException as close_exc:
            failure += '; wait: ' + repr(close_exc)
    finally:
        halted.set()
        if watcher.ident is not None:
            watcher.join(5.)
        # No Tk callbacks run after mainloop returns; close GUI-owned file before destroying widgets.
        if window is not None and window._s6d_render_handle is not None:
            window._s6d_render_handle.close()
            window._s6d_render_handle = None
        if root is not None:
            try:
                root.destroy()
            except tk.TclError as exc:
                failure = (failure or '') + '; GUI destruction: ' + repr(exc)
        messagebox.showerror = original_showerror
        for writer in (consumer, resource, acknowledgments):
            try:
                writer.close()
            except BaseException as exc:
                failure = (failure or '') + '; writer: ' + repr(exc)
        trace = getattr(engine, '_s7_trace', None)
        if trace is not None and trace_closed is None:
            try:
                trace.close()
                trace_closed = trace.snapshot()
            except BaseException as exc:
                failure = (failure or '') + '; trace: ' + repr(exc)
    errors = completion_errors(engine, engine.telemetry())
    if watcher.is_alive():
        errors.append('Resource observer thread not closed')
    errors.extend(observer_errors)
    errors.extend(callback_errors)
    if errors:
        failure = failure or '; '.join(errors)
    return dict(failure=failure, completion_errors=errors, telemetry=engine.telemetry(),
        session_dir=str(engine.session_dir), event_consumer_drained=engine.events.empty(),
        consumer_writer=consumer.snapshot(), resource_writer=resource.snapshot(),
        resource_observer_closed=not watcher.is_alive(), s7_trace_closure=trace_closed,
        consumed_events=counters['consumed'], startup_events=startup_events,
        start_file_model_and_source_startup_sec=startup,
        startup_scope='GUI launch request through source_started receipt; includes actual GUI poll delay',
        execution_elapsed_sec=time.perf_counter()-started, gui_window_mapped=mapped,
        gui_ack_writer=acknowledgments.snapshot(), gui_actions=action_receipts,
        gui_startup_widgets=startup_widgets,
        gui_scope='Real mapped Tk window, original polling/render path, actual receipt/application/idle; not physical scanout')
