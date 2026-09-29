"""Guarded saved-file preview controls. See README_B01_PREVIEW_V1.md."""
import hashlib
from pathlib import Path
import threading
import time
import wave

from app.controller import Controller
from app.ui import PrototypeUI


class PreviewController(Controller):
    """Restrict the shared controller at its command boundary, not just in menus."""
    def __init__(self, data_root, models_root, *, admission):
        self.preview_policy = admission
        self.preview_selected = None
        self.preview_starts = 0
        self.preview_deadline = time.monotonic() + 145
        self.preview_guard = threading.RLock()
        self.preview_rejections = []
        super().__init__(data_root, models_root, saved_audio_only=True)

    def reject(self, reason):
        self.preview_rejections.append(reason)
        self.preview_rejections = self.preview_rejections[-32:]
        raise ValueError(reason)

    def validate_file(self, path):
        candidate = Path(path).resolve(strict=True)
        allowed = Path(self.preview_policy['saved_file']['path']).resolve(strict=True)
        if candidate != allowed:
            self.reject('Choose the admitted saved sample. Other files need a new admission.')
        with candidate.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != self.preview_policy['saved_file']['sha256']:
            self.reject('Saved sample changed; preview stopped.')
        with wave.open(str(candidate), 'rb') as stream:
            actual = (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getnframes())
        if actual != (16000, 1, 2, 715127):
            self.reject('Saved sample format or duration changed.')
        return candidate

    def choose_file(self, path):
        with self.preview_guard:
            if self.state in ('RUNNING', 'STARTING', 'STOPPING') or self.commands.unfinished_tasks:
                self.reject('Stop and finish draining before choosing a file.')
            self.preview_selected = self.validate_file(path)

    def _enqueue(self, action, *args, **kwargs):
        with self.preview_guard:
            if action not in ('select_backend', 'switch', 'start_file', 'stop', 'close'):
                self.reject('This preview allows saved-file Start, Stop and Close only.')
            if action == 'select_backend' and args != (self.preview_policy['backend_manifest_id'],):
                self.reject('This preview is fixed to B01 retained-ReDimNet delayed labels.')
            if action == 'switch':
                mode, recipe, tap, selected_ids, strict = args
                if (mode or self.mode, recipe or self.recipe, tap or self.tap) != ('open_with_names', 'balanced', 'O0') or selected_ids or strict:
                    self.reject('Other naming, filtered and anonymous modes are not available in this preview.')
            if action == 'start_file':
                if self.commands.unfinished_tasks or self.state in ('RUNNING', 'STARTING', 'STOPPING'):
                    self.reject('A session is already starting, running or draining.')
                if self.preview_selected is None or self.validate_file(args[0]) != self.preview_selected:
                    self.reject('Choose the saved sample before Start.')
                if self.preview_starts >= 2 or self.preview_deadline-time.monotonic() < 75:
                    self.reject('Preview time/session allowance reached. Close and launch a new admitted preview.')
                if self.backend_id != self.preview_policy['backend_manifest_id'] or self.mode != 'open_with_names':
                    self.reject('Unexpected backend or mode; no fallback is allowed.')
                self.preview_starts += 1
            return super()._enqueue(action, *args, **kwargs)


class PreviewUI(PrototypeUI):
    """Retain the shared caption widgets; expose only the admitted preview controls."""
    def __init__(self, root, controller):
        super().__init__(root, controller, allow_auto_start=False)
        self.root.title('Just Peachy - retained-ReDimNet saved-file preview')
        self.actions['people'].configure(text='File', command=self.show_files)
        self.preview_label.configure(text='Experimental B01')

    def _show_status(self):
        super()._show_status()
        self.mode_label.configure(text='ReDimNet retained - delayed speaker labels')
        self.actions['backend'].configure(text='B01: Sherpa captions + delayed Nemotron labels')
        chosen = self.controller.preview_selected is not None
        state = str(self.snapshot.get('state', 'IDLE'))
        self.status_label.configure(text=('Saved sample - ' if chosen else 'Choose File, then Start - ') + state + ' - microphone off')
        self.actions['start_stop'].configure(text='Stop' if self._running() else 'Start file')

    def toggle_listening(self):
        if self._running():
            self._call('stop')
        elif self.controller.preview_selected is None:
            self._notice = 'Choose the saved sample first. Selecting a file does not start it.'
            self._show_status()
        elif self._call('start_file', self.controller.preview_selected):
            self.home()

    def show_files(self):
        self.page = 'preview_files'
        frame = self._page('Saved-file preview')
        self._paragraph_label(frame, 'Functional sample: 44.7 seconds. Audio is processed silently at its original pace. Captions appear first; anonymous labels arrive later.')
        self.button(frame, 'Choose saved sample', self.choose_sample, key='preview_choose').pack(fill='x')
        self._paragraph_label(frame, 'Only this checked sample is admitted. Other recordings and live microphone testing need separate validation.', True)

    def choose_sample(self):
        if self._call('choose_file', self.controller.preview_policy['saved_file']['path']):
            self.home()

    def show_modes(self):
        self.page = 'preview_mode'
        frame = self._page('Delayed labels with ReDimNet')
        self._paragraph_label(frame, 'B01 uses Sherpa captions, one Nemotron diarizer and ReDimNet voice embeddings. This preview has an empty research gallery. Labels can lag by about 25 seconds on this sample. Speaker numbers belong to this session; they are not personal names.')
        self._paragraph_label(frame, 'This is a bounded experimental preview. Personal naming, other backends, microphone, playback and enrollment are unavailable.', True)

    show_backends = show_modes
    show_people = show_files
    show_advanced = show_modes
    show_recipes = show_modes
    show_all_captions = show_modes
    browse_file = lambda self, *args, **kwargs: self.show_files()

    def show_settings(self):
        self.page = 'preview_settings'
        frame = self._page('Preview controls')
        self.button(frame, 'Choose saved sample', self.show_files, key='preview_files').pack(fill='x')
        self.button(frame, 'Close preview', self.close, key='preview_close').pack(fill='x')
        self._paragraph_label(frame, 'The preview starts idle and closes within three minutes. It allows at most two starts, including a restart after Stop. A new launch checks resources again. The original app stays installed and unchanged.', True)
