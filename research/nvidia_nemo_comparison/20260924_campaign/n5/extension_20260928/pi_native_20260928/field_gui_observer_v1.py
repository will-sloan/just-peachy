"""Bounded idle GUI instrumentation. See README_FIELD_GUI_LEASE_V1.md."""
import json
from pathlib import Path
import time


class IdleGUIObserver:
    def __init__(self, root, case, owner, token, state_sha, write):
        self.root = root
        self.case = case
        self.owner = owner
        self.token = token
        self.state_sha = state_sha
        self.write = write
        self.ui = None
        self.failure = None
        self.capture_attempts = 0
        self.close_requested = False
        self.ready = None

    def __enter__(self):
        from app.ui import PrototypeUI
        from app.controller import Controller
        self.ui_type, self.controller_type = PrototypeUI, Controller
        self.original_init, self.original_start = PrototypeUI.__init__, Controller.start_live
        observer = self

        def blocked_start(*args, **kwargs):
            observer.capture_attempts += 1
            raise RuntimeError('This admitted GUI ownership check cannot start capture')

        def initialized(ui, *args, **kwargs):
            observer.original_init(ui, *args, **kwargs)
            assert observer.ui is None
            observer.ui = ui
            ui.root.after(700, observer.observe)

        Controller.start_live = blocked_start
        PrototypeUI.__init__ = initialized
        return self

    def observe(self):
        try:
            ui = self.ui
            controller = ui.controller
            snapshot = controller.snapshot()
            assert snapshot['state'] == 'IDLE' and controller.engine is None
            assert controller.models.asr_loads == controller.models.speaker_loads == 0
            assert Path('/proc/asound/card2/pcm1c/sub0/status').read_text().strip() == 'closed'
            assert ui.root.winfo_ismapped() and (ui.root.winfo_width(), ui.root.winfo_height()) == (480, 800)
            lock = json.loads((self.root/'data/runtime.lock').read_text())
            assert lock['pid'] == self.owner['pid'] and lock['token'] == self.token
            self.ready = dict(owner=self.owner, lease_token=self.token, state_sha256=self.state_sha,
                              mapped=True, width=480, height=800, state=snapshot['state'],
                              models_loaded=False, capture_opened=False, physical_touch=False)
            self.write(self.root/(self.case+'-gui-active.json'), self.ready)
            self.deadline = time.monotonic()+8
            self.poll()
        except Exception as exc:
            self.fail(exc)

    def poll(self):
        try:
            gate = self.root/(self.case+'-gui-active-continue.json')
            if gate.exists():
                assert json.loads(gate.read_text()) == dict(continue_phase='gui-active', owner_pid=self.owner['pid'])
                self.close_requested = True
                self.ui.close()
            elif time.monotonic() > self.deadline:
                raise TimeoutError('GUI ownership observation deadline')
            else:
                self.ui.root.after(25, self.poll)
        except Exception as exc:
            self.fail(exc)

    def fail(self, exc):
        self.failure = type(exc).__name__+': '+str(exc)
        self.ui.close()

    def finish(self):
        assert self.failure is None, self.failure
        assert self.ready is not None and self.close_requested and self.capture_attempts == 0
        ui = self.ui
        controller = ui.controller
        assert ui._closed and controller.closed and not controller.worker.is_alive()
        assert controller.commands.unfinished_tasks == 0 and controller.engine is None
        assert controller.models.asr_loads == controller.models.speaker_loads == 0
        try:
            exists = bool(int(ui.root.tk.call('winfo', 'exists', '.')))
        except Exception as exc:
            import tkinter
            if not isinstance(exc, tkinter.TclError):
                raise
            exists = False
        assert not exists
        return dict(status='INSTALLED_GUI_IDLE_CLOSED', ready=self.ready, actual_ui_close=True,
                    root_destroyed=True, controller_closed=True, worker_closed=True,
                    pending_commands=0, capture_attempts=0, models_loaded=False, capture_opened=False)

    def __exit__(self, *unused):
        self.ui_type.__init__ = self.original_init
        self.controller_type.start_live = self.original_start
