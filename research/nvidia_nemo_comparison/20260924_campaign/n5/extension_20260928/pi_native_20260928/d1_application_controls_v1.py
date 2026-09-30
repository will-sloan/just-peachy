"""Explicit diarizer control adapter; README_D1_APPLICATION_CONTROLS_V1.md."""
from copy import deepcopy
import threading
import tkinter as tk
import d1_modes_v1 as modes


LABELS = {
    'delayed': ('Delayed', 'Native selection tested. First activity needs about 21.3 seconds of input.'),
    'streaming': ('Streaming', 'Shorter input context. New selection path still needs a native check; prior processing was slower than real time.'),
    'chunk52': ('Chunk 52 · experimental', 'Intermediate input context. New selection path still needs a native check; no real-time guarantee.'),
}


class D1Controls:
    """Mixin for the pinned Controller command loop, not a model/source owner.

    Selection prepares the next process. A selected ID does not authorize Start.
    The missing application worker binding is explicitly blocked, not routed to
    the old profile-only N2ResidentModels loader.
    """
    def initialize_d1_controls(self):
        if hasattr(self, '_d1_lock'):
            raise RuntimeError('Diarizer controls already initialized')
        self._d1_lock = threading.RLock()
        self._d1_selected = None
        self._d1_pending = False
        self._d1_error = None

    def _d1_can_select(self):
        if self.closed:
            raise RuntimeError('Application closed')
        if self.state not in ('IDLE', 'STOPPED'):
            raise RuntimeError('Stop the session before selecting a diarizer mode')
        if self.engine is not None:
            raise RuntimeError('Previous engine still owns the session')
        if self.consumer is not None and self.consumer.is_alive():
            raise RuntimeError('Previous caption worker still owns the session')
        if self.enrollment.get('state') == 'RECORDING':
            raise RuntimeError('Finish enrollment before selecting a diarizer mode')
        if (self._n2_components or {}).get('diarization') != 'D1':
            raise RuntimeError('Select a Nemotron diarizer backend first')
        if getattr(self.models, 'diarizer', None) is not None:
            raise RuntimeError('Resident diarizer requires a fresh process')
        modes.require_fresh_runtime(modes.mapped_paths())

    def select_d1_mode(self, mode_id):
        modes.select(mode_id)
        with self._d1_lock:
            self._d1_can_select()
            if self._d1_pending:
                raise RuntimeError('Diarizer selection is already queued')
            self._d1_pending = True
            try:
                self._enqueue('select_d1_mode', mode_id)
            except BaseException:
                self._d1_pending = False
                raise

    def _do_select_d1_mode(self, mode_id):
        with self._d1_lock:
            try:
                self._d1_can_select()  # State may change after the button click.
                selected = modes.select(mode_id)
                self._d1_selected = dict(id=mode_id, catalog_sha256=modes.CATALOG_SHA256,
                                        geometry=selected['geometry'], retained_run=selected['retained_run'])
                self._d1_error = None
                self.status = LABELS[mode_id][0]+' selected for the next fresh process. Application launch is not connected.'
            except Exception as exc:
                self._d1_error = str(exc)[:512]
                raise
            finally:
                self._d1_pending = False

    def d1_snapshot(self):
        with self._d1_lock:
            reason = None
            try:
                self._d1_can_select()
            except Exception as exc:
                reason = str(exc)[:512]
            return dict(selected=deepcopy(self._d1_selected), pending=self._d1_pending,
                        can_select=reason is None and not self._d1_pending, blocked_reason=reason,
                        error=self._d1_error, launch_available=False,
                        launch_reason='Application worker binding is not connected. No model starts from this control.',
                        modes=[dict(id=k, label=v[0], description=v[1], native_factory_checked=k=='delayed')
                               for k,v in LABELS.items()])

    def d1_launch_request(self):
        with self._d1_lock:
            self._d1_can_select()
            if self._d1_pending or self._d1_selected is None:
                raise RuntimeError('Complete an explicit diarizer selection first')
            return dict(schema='d1-application-selection.v1', selection=deepcopy(self._d1_selected),
                        requires_fresh_process=True, requires_independent_session=True,
                        launchable=False, reason=self.d1_snapshot()['launch_reason'])

    def _start_session(self):
        # Always intercept D1 before the old loader can substitute its configured
        # runtime/profile. Other backend behavior remains with the base class.
        if (self._n2_components or {}).get('diarization') == 'D1':
            raise RuntimeError('Diarizer application worker binding is not connected; Start is unavailable')
        return super()._start_session()


class D1ModePanel(tk.Frame):
    def __init__(self, parent, controller, command):
        super().__init__(parent)
        self.controller = controller
        self.command = command
        tk.Label(self, text='Nemotron diarizer', font=('DejaVu Sans', 18, 'bold')).pack(fill='x', pady=8)
        self.summary = tk.Label(self, wraplength=420, justify='left')
        self.summary.pack(fill='x', padx=12, pady=6)
        self.choices = {}
        for mode, (label, description) in LABELS.items():
            button = tk.Button(self, text=label, command=lambda value=mode:self.choose(value), height=2)
            button.pack(fill='x', padx=12, pady=4)
            self.choices[mode] = button
            tk.Label(self, text=description, wraplength=420, justify='left').pack(fill='x', padx=12)
        self.launch = tk.Button(self, text='Start diarizer · unavailable', state='disabled', height=2)
        self.launch.pack(fill='x', padx=12, pady=8)
        self.refresh()

    def choose(self, mode_id):
        self.command('select_d1_mode', mode_id)
        self.refresh()  # Only controller completion may mark a choice selected.

    def refresh(self):
        snap = self.controller.d1_snapshot()
        chosen = None if snap['selected'] is None else snap['selected']['id']
        for mode, button in self.choices.items():
            button.configure(text=LABELS[mode][0]+(' · selected' if mode == chosen else ''),
                             state='normal' if snap['can_select'] else 'disabled')
        state = 'Selection queued.' if snap['pending'] else 'Choose a mode for a fresh process.'
        self.summary.configure(text='\n'.join(x for x in [state, snap['error'], snap['blocked_reason'], snap['launch_reason']] if x))
        self.launch.configure(state='disabled')


def controller_class(base):
    class Controlled(D1Controls, base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.initialize_d1_controls()
    return Controlled


def ui_class(base):
    class ControlledUI(base):
        def show_diarizer_modes(self):
            self.page = 'diarizer_modes'
            frame = self._page('Nemotron diarizer', back=self.show_modes)
            panel = D1ModePanel(frame, self.controller, self._call)
            panel.pack(fill='both', expand=True)
            self._page_update = panel.refresh
            return panel

        def _page(self, title, *, scroll=True, back=None):
            frame = super()._page(title, scroll=scroll, back=back)
            if title == 'Mode':
                self._d1_navigation = tk.Button(frame, text='Nemotron diarizer settings',
                                               command=self.show_diarizer_modes, height=2)
                self._d1_navigation.pack(fill='x', padx=12, pady=6)
            return frame
    return ControlledUI
