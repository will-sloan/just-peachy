"""Restore the retained portrait frontend over the current runtime manager.

See README_CLASSIC_FRONTEND.md. This module owns presentation only; speech,
capture, storage, admission and closure remain in the current worker/manager.
"""
from __future__ import annotations

from dataclasses import replace
import ast
import importlib
import json
import math
from pathlib import Path
import sys
import time
import types

from profiles import RuntimeSelection, catalog, get_profile
from runtime_support import digest, publish, strict


def selection_label(selection):
    diarizer = 'Pyannote' if selection.diarizer == 'pyannote' else 'Nemotron-3 ' + get_profile(selection.nemotron_profile).label
    embedding = {'redimnet': 'ReDimNet', 'titanet': 'NeMo TitaNet', 'anonymous': 'Anonymous'}[selection.embedding]
    return diarizer + ' + ' + embedding


def fullscreen_after_map(root):
    """Retain the post-map fullscreen request that avoids compositor clipping."""
    requested = [False]
    def request(event=None):
        if event is not None and event.widget is not root:
            return
        if not requested[0]:
            requested[0] = True
            root.after_idle(lambda: root.attributes('-fullscreen', True))
    root.geometry('480x800+0+0')
    root.bind('<Map>', request, add='+')
    if root.winfo_ismapped():
        request()


def caption_row(row, mode):
    """Project recorded labels/text; never infer a new identity in the GUI."""
    identifier = row['caption_id']
    projected = row.get('provenance', {}).get('ui_projection')
    if isinstance(projected, dict):
        return dict(projected, id=identifier, speaker_revision=row.get('revision'))
    # The speaker's provisional flag is not ASR finality. Older recordings
    # lack an explicit ASR-final field; keep that distinction conservative.
    final = row.get('provenance', {}).get('asr_final') is True
    text = str(row.get('text') or '')
    return dict(id=identifier, caption_key=identifier, utterance_id=identifier,
                raw_asr_text=text, provisional_display_text=text,
                final_punctuated_display_text=text if final else None,
                label='Transcription' if mode == 'caption_only' else str(row.get('speaker') or 'Unknown'),
                final=final, selected=False, visible=True,
                source_start_sec=row['start_sample']/16000,
                source_end_sec=row['end_sample']/16000,
                speaker_revision=row.get('revision'),
                profile_id=row.get('provenance', {}).get('profile_id'),
                identity_status='supported' if row.get('provenance', {}).get('speaker_supported') else 'collecting')


def load_retained_ui(binding):
    """Hash-check the small presentation graph, without loading model graphs."""
    base = Path(binding['installed_release']).resolve()
    manifest_path = base/'RELEASE_MANIFEST.json'
    if digest(manifest_path) != binding['installed_manifest_sha256']:
        raise ValueError('Retained portrait UI release manifest changed')
    manifest = strict(manifest_path.read_bytes())
    selected = [row for row in manifest['files'] if row['path'].startswith('app/') or row['path'] in ('config/ui.json', 'config/backends.json')]
    for row in selected:
        path = base/row['path']
        if path.is_symlink() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Retained portrait presentation source changed: '+row['path'])
    required = {'app/ui.py', 'config/ui.json', 'config/backends.json'}
    if not required.issubset({row['path'] for row in selected}):
        raise ValueError('Complete retained portrait UI/config pins required')
    existing = sys.modules.get('app')
    if existing is not None and Path(existing.__file__).resolve().parent != base/'app':
        raise ValueError('Another application package is already loaded in this GUI process')
    sys.path.insert(0, str(base))
    # Three unused advanced-page helpers normally import NumPy or spatial
    # engine packages just to supply display constants. Project only those
    # exact verified constants and the pure collision function for this GUI.
    # These temporary modules never reach the separate model worker process.
    projections = {'app.enhancement': ('ROUTES',),
                   'app.script_evidence': ('MATCHED_UNAVAILABLE',),
                   'app.seats': ('DEFAULT_TOLERANCE', 'collisions')}
    temporary = {}
    for name, fields in projections.items():
        if name in sys.modules:
            raise ValueError('Unexpected preloaded inference helper in portrait GUI: '+name)
        source = base/(name.replace('.', '/')+'.py')
        tree = ast.parse(source.read_bytes())
        projected = types.ModuleType(name)
        projected.__file__ = '<portrait-ui-readonly:'+name+'>'
        for field in fields:
            values = [node.value for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == field for target in node.targets)]
            if values:
                if len(values) != 1:
                    raise ValueError('Ambiguous retained UI constant: '+field)
                setattr(projected, field, ast.literal_eval(values[0]))
            else:
                nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == field]
                if len(nodes) != 1 or field != 'collisions':
                    raise ValueError('Unexpected retained UI function projection: '+field)
                exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                             projected.__file__, 'exec'), projected.__dict__)
        temporary[name] = projected
    sys.modules.update(temporary)
    try:
        prototype = importlib.import_module('app.ui').PrototypeUI
    finally:
        for name, module in temporary.items():
            if sys.modules.get(name) is module:
                del sys.modules[name]
            package = sys.modules.get('app')
            if getattr(package, name.rsplit('.', 1)[1], None) is module:
                delattr(package, name.rsplit('.', 1)[1])
    if Path(sys.modules['app.ui'].__file__).resolve() != base/'app/ui.py':
        raise ValueError('Unexpected portrait frontend origin')
    return prototype, strict((base/'config/ui.json').read_bytes())


class ClassicController:
    """Lightweight UI API facade; current Manager remains the sole worker owner."""
    def __init__(self, manager, selection, config, *, clock=time.monotonic):
        self.manager, self.selection, self.config, self.clock = manager, selection, config, clock
        self.mode = 'anonymous_conversation' if selection.embedding == 'anonymous' else 'open_with_names'
        self.settings_path = manager.data_root/'PORTRAIT_SETTINGS.json'
        self.settings = dict(config['defaults'], microphone_preapproved=False, auto_start_listening=False)
        if self.settings_path.exists():
            saved = strict(self.settings_path.read_bytes())
            self._validate_settings(saved)
            self.settings.update(saved)
        self.settings['auto_start_listening'] = False
        self.current_id = None
        self.opened_id = None
        self.rows = []
        self.revision = None
        self.last_caption_read = -math.inf
        self.closed = self.closing = False
        self.notice = 'Microphone off. Press Start when ready.'
        self.error = None
        self.history_page = dict(items=[], next_cursor=None)
        self.last_closure = None

    def _validate_settings(self, values):
        choices = {'caption_size': self.config['caption_sizes_px'], 'theme': self.config['themes'],
                   'preview_zoom': (1.0,), 'display_smoothing_ms': self.config['display_smoothing_ms'],
                   'spatial_visualization': (True, False), 'numbered_unknowns': (True, False),
                   'microphone_preapproved': (True, False), 'auto_start_listening': (False,)}
        for key, value in values.items():
            if key not in choices or value not in choices[key]:
                raise ValueError('Unsupported portrait setting: '+str(key))
            if key in ('spatial_visualization', 'numbered_unknowns', 'microphone_preapproved', 'auto_start_listening') and type(value) is not bool:
                raise ValueError('Exact boolean portrait setting required')

    def settings_update(self, values):
        self._validate_settings(values)
        merged = {key: value for key, value in self.settings.items() if key != 'direction'}
        merged.update(values)
        self._validate_settings(merged)
        publish(self.settings_path, merged, replace=True)
        self.settings.update(values)
        self.manager.show_spatial(bool(self.settings['spatial_visualization']))

    def _policy(self):
        from launcher import gui_session_policy
        return gui_session_policy(self.manager.binding, self.selection)

    def _start(self, path=None, session_id=None):
        self.manager.start(self.selection, self._policy(), path, saved_session_id=session_id)
        self.current_id = self.opened_id = None
        self.rows, self.revision = [], None
        self.last_caption_read = -math.inf
        self.error = None
        self.last_closure = None
        self.notice = 'Loading selected models. Capture starts after initialization.'
        self.manager.show_spatial(bool(self.settings['spatial_visualization']))

    def start_live(self, *, consent=False):
        if consent is not True:
            raise ValueError('Microphone consent is required')
        if self.selection.input_source != 'live':
            raise ValueError('This selection uses saved audio; choose a WAV or replay a recording')
        self._start()

    def start_file(self, path):
        if self.selection.input_source != 'saved':
            raise ValueError('Return to combinations and choose Saved WAV first')
        self._start(path=path)

    def stop(self):
        self.manager.stop()
        self.notice = 'Stopping capture and draining pending words…'

    def close(self):
        self.closing = True
        self.stop()

    def switch(self, *, mode=None, strict=None, **values):
        if values:
            raise ValueError('Backend source/recipe is pinned; return to combinations to change it')
        allowed = ('caption_only', 'anonymous_conversation') if self.selection.embedding == 'anonymous' else ('caption_only', 'open_with_names')
        if mode is not None and mode not in allowed:
            raise ValueError('This display mode is unavailable for the selected backend')
        if strict not in (None, False):
            raise ValueError('Selected-person filtering is not enabled by this runtime frontend')
        if mode is not None:
            self.mode = mode
            self.revision = None
            self.last_caption_read = -math.inf

    def history(self, *, older=False):
        self.history_page = self.manager.store.history(limit=25,
            before=self.history_page['next_cursor'] if older else None)
        return self.history_page

    def session_action(self, action, **values):
        identifier = values.get('identifier') or self.current_id
        if action in ('open', 'replay', 'save', 'discard', 'delete', 'export') and not identifier:
            raise ValueError('Choose a recording first')
        if self.manager.process is not None:
            raise RuntimeError('Stop and wait for capture, drain and worker closure first')
        if action == 'open':
            self.manager.store.read(identifier)
            self.current_id = self.opened_id = identifier
            self.revision = None
            self.last_caption_read = -math.inf
            self.notice = 'Saved transcript opened. Microphone off.'
        elif action == 'replay':
            if self.selection.input_source != 'saved':
                raise ValueError('Choose Saved WAV input in the combination selector before replay')
            self._start(session_id=identifier)
        elif action == 'save':
            self.manager.store.keep(identifier, include_raw=values.get('include_raw') is True)
            self.notice = 'Recording saved.'
        elif action == 'discard':
            self.manager.store.discard(identifier)
            self.notice = 'Temporary audio discarded. Transcript/evidence retained.'
        elif action == 'delete':
            self.manager.store.delete(identifier, confirm=values.get('confirmed') is True)
            if self.current_id == identifier:
                self.current_id = self.opened_id = None
                self.rows, self.revision = [], None
            self.notice = 'Selected recording deleted.'
        elif action == 'export':
            self.manager.export_recordings([identifier], Path(values['path']))
            self.notice = 'Exporting selected recording; originals are retained.'
        else:
            raise ValueError('This recording action is unavailable: '+str(action))
        self.history()

    def _read_captions(self):
        now = self.clock()
        if not self.current_id or now-self.last_caption_read < .25:
            return
        page = self.manager.store.latest_captions(self.current_id, limit=40, after_revision=self.revision)
        self.last_caption_read = now
        if page['changed']:
            self.rows = [caption_row(row, self.mode) for row in page['items']]
            self.revision = page['revision_cursor']

    def snapshot(self):
        closure = self.manager.poll()
        export = self.manager.poll_export()
        active_id = self.manager.active_session_id()
        if active_id and active_id != self.current_id and self.manager.process is not None:
            self.current_id, self.opened_id, self.revision = active_id, None, None
            self.last_caption_read = -math.inf
        if export:
            self.notice = 'Export completed.' if export.get('success') else 'Export closed; see diagnostics.'
        health = self.manager.latest_health or {}
        measured = health.get('value') or {}
        if self.manager.process is not None:
            state = 'STOPPING' if self.manager.stop_requested is not None else 'RUNNING' if measured.get('source_samples', 0) else 'STARTING'
            if state == 'RUNNING':
                self.notice = 'Listening locally' if self.selection.input_source == 'live' else 'Replaying saved audio'
        elif closure is not None:
            result = closure.get('result') or {}
            failure = result.get('failure') or closure.get('output_error')
            if closure.get('returncode') != 0 and not failure:
                failure = self.failure_detail() or 'Worker exited before completing this session'
            if failure:
                self.error = str(failure)
                state = 'ERROR'
                self.notice = 'Session failed. Evidence retained; '+('microphone never opened.' if (closure.get('nested_source') or {}).get('state') == 'SOURCE_NOT_STARTED' else 'capture closed.')
            else:
                state = 'STOPPED'
                if closure is not self.last_closure and not self.opened_id:
                    self.notice = 'Stopped. Choose whether to save or discard audio in Recordings.'
        else:
            state = 'IDLE'
        self.last_closure = closure
        if self.closing and self.manager.process is None and self.manager.export_task is None:
            self.closed = True
            state = 'CLOSED'
        self._read_captions()
        spatial = self.manager.latest_spatial or {}
        view = dict(spatial.get('spatial') or {})
        if self.clock()-spatial.get('published_monotonic', -math.inf) > 1.5 or self.manager.process is None:
            view = dict(state='OFF', arrows=[], associations=[], message='Live directions unavailable while idle/saved.')
        elif view.get('association_reference_frame') != 'device':
            # The retained drawing expects device angles; anchor associations
            # must never be silently painted as device-relative bearings.
            view['associations'] = []
        backend = dict(id='selected-runtime', key='selected-runtime', label=selection_label(self.selection), available=True)
        return dict(state=state, status=self.notice, error=self.error, rows=self.rows,
            mode=self.mode, recipe='balanced', tap='O0', backend_id=backend['id'], backend=backend,
            backends=[backend], strict=False, settings=dict(self.settings), people=[], selected_ids=[], display_ids=[],
            sessions=dict(current_id=self.current_id, opened_id=self.opened_id),
            motion=dict(view.get('motion') or {}, enabled=self.selection.input_source == 'live'),
            spatial_view=view, beam_diagnostics=view, metrics=dict(measured), pending_actions=0,
            enrollment=dict(state='IDLE'), closed=self.closed)

    def failure_detail(self):
        diagnostic = (self.manager.latest_diagnostic or {}).get('value') or {}
        if diagnostic.get('error') or diagnostic.get('reason'):
            return str(diagnostic.get('error') or diagnostic.get('reason'))
        if self.manager.run_dir is None:
            return ''
        path = self.manager.run_dir/'WORKER.log'
        if not path.is_file():
            return ''
        with path.open('rb') as stream:
            stream.seek(max(0, path.stat().st_size-8192))
            lines = stream.read(8192).decode('utf-8', errors='replace').strip().splitlines()
        return lines[-1][:500] if lines else ''

    def diagnostics(self):
        try:
            policy = self._policy().validate()
        except Exception as exc:
            policy = dict(unavailable=str(exc))
        return json.dumps(dict(selection=self.selection.validate(), policy=policy,
            latest_health=self.manager.latest_health, latest_diagnostic=self.manager.latest_diagnostic,
            worker_closure=self.manager.last, failure=self.failure_detail()), indent=2, ensure_ascii=False, default=str)[-16384:]


def frontend_type(prototype):
    """Keep the original caption layout/navigation and touch styling."""
    class PortraitUI(prototype):
        def __init__(self, root, controller, return_modes):
            self.return_modes = return_modes
            self._history_cursor = None
            self._debug_zero = 0.
            super().__init__(root, controller, allow_auto_start=False)
            self.root.title('Just Peachy')
            fullscreen_after_map(self.root)

        def _show_status(self):
            super()._show_status()
            self.preview_label.configure(text='Live mic' if self.controller.selection.input_source == 'live' else 'Saved WAV')

        def toggle_listening(self):
            if self._running():
                return super().toggle_listening()
            if self.controller.selection.input_source == 'saved':
                return self.browse_file('replay', Path.home()/'JustPeachy/data')
            return super().toggle_listening()

        def show_backends(self):
            self.page = 'backends'
            frame = self._page('Selected backend')
            self._paragraph_label(frame, selection_label(self.controller.selection))
            self._paragraph_label(frame, 'The selected models run in a separate worker. Return to combinations to choose another backend or Live/Saved input.', True)
            self.button(frame, 'Return to combinations', self.return_modes, height=60).pack(fill='x', padx=self.px(12), pady=self.px(6))

        def show_modes(self):
            self.page = 'modes'
            frame = self._page('Caption display mode')
            self._paragraph_label(frame, 'Display choices keep the selected inference backend. Model/source combinations are selected before this application opens.', True)
            choices = [('caption_only', 'Just transcription')]
            choices += [('anonymous_conversation', 'Anonymous conversation')] if self.controller.selection.embedding == 'anonymous' else [('open_with_names', 'Open with names')]
            for mode, title in choices:
                self.button(frame, title, lambda value=mode: self._choose_mode(value), height=60).pack(fill='x', padx=self.px(12), pady=self.px(6))
            self.button(frame, 'Choose another backend combination', self.return_modes, height=60).pack(fill='x', padx=self.px(12), pady=self.px(6))

        def show_people(self):
            self.page = 'people'
            frame = self._page('People & voice references')
            model = self.controller.selection.embedding
            self._paragraph_label(frame, 'Anonymous mode does not match saved voice profiles.' if model == 'anonymous' else ('Selected voice model: '+{'redimnet': 'ReDimNet', 'titanet': 'NeMo TitaNet'}[model]))
            self._paragraph_label(frame, 'Existing compatible galleries stay separate and are loaded by the worker. Voice matches appear in captions. This frontend does not create, replace or mix voice galleries.', True)
            self._paragraph_label(frame, 'Enrollment and gallery editing are unavailable in this runtime iteration.', True)

        def show_settings(self):
            self.page = 'settings'
            frame = self._page('Settings')
            self.button(frame, 'Recordings & saved transcripts', self.show_sessions, key='sessions').pack(fill='x', padx=self.px(12), pady=self.px(4))
            self.button(frame, 'Return to backend combinations', self.return_modes).pack(fill='x', padx=self.px(12), pady=self.px(4))
            self.button(frame, 'Exit to desktop', self.close).pack(fill='x', padx=self.px(12), pady=self.px(4))
            self._paragraph_label(frame, 'Starts idle. No automatic listening or boot launch. Normal live tests last at most five minutes; audio is disk-spooled and kept only after your post-Stop choice.', True)
            self._paragraph_label(frame, 'Caption size · display only')
            self._choices(frame, 'caption_size', [(name, name) for name in self.config['caption_sizes_px']])
            self._paragraph_label(frame, 'Text smoothing · display only')
            self._choices(frame, 'display_smoothing_ms', [(0, 'Immediate'), (150, '150 ms'), (300, '300 ms')])
            self._paragraph_label(frame, 'Contrast')
            self._choices(frame, 'theme', [(theme, theme) for theme in self.config['themes']])
            enabled = bool(self.preferences.get('spatial_visualization'))
            self.button(frame, 'Live sound directions: '+('On' if enabled else 'Off'),
                lambda: self._preference('spatial_visualization', not enabled)).pack(fill='x', padx=self.px(12), pady=self.px(4))
            self.button(frame, 'Orientation troubleshooting', self.show_motion).pack(fill='x', padx=self.px(12), pady=self.px(4))
            self.button(frame, 'Diagnostics', self.show_diagnostics, key='diagnostics').pack(fill='x', padx=self.px(12), pady=self.px(4))
            if self.controller.selection.input_source == 'saved':
                self.button(frame, 'Open a saved WAV…', lambda: self.browse_file('replay')).pack(fill='x', padx=self.px(12), pady=self.px(4))

        def show_sessions(self, older=False):
            self.page = 'sessions'
            frame = self._page('Recordings', back=self.show_settings)
            page = self.controller.history(older=older)
            identifier = self.controller.current_id
            if identifier:
                self.button(frame, 'Current recording · save / discard', lambda: self.show_session(identifier), height=60).pack(fill='x', padx=self.px(12), pady=self.px(4))
            self._paragraph_label(frame, 'Saved recordings persist across restarts. Capacity controls admission; there is no small recording-slot count.', True)
            for row in page['items']:
                title = row.get('spec', {}).get('title') or time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(row['created']))
                text = '%s\n%s · %.1fs · %s' % (title, row['status'], row['duration_seconds'], row['session_id'][:8])
                self.button(frame, text, lambda value=row['session_id']: self.show_session(value), height=68).pack(fill='x', padx=self.px(12), pady=self.px(4))
            if page['next_cursor']:
                self.button(frame, 'Older recordings', lambda: self.show_sessions(True)).pack(fill='x', padx=self.px(12), pady=self.px(4))
            self.button(frame, 'Refresh newest', self.show_sessions).pack(fill='x', padx=self.px(12), pady=self.px(4))

        def show_session(self, identifier):
            self.page = 'session_detail'
            frame = self._page('Recording', back=self.show_sessions)
            self._session_detail_frame = frame
            row = self.controller.manager.store.read(identifier)
            self._paragraph_label(frame, '%s\n%s · %.1fs' % (identifier[:12], row['status'], row['duration_seconds']))
            self.button(frame, 'Open transcript', lambda: self._open_recording(identifier)).pack(fill='x', padx=self.px(12), pady=self.px(4))
            stopped = self.controller.manager.process is None and row['status'] in ('stopped', 'kept')
            if row['status'] == 'stopped':
                self.button(frame, 'Save processed audio', lambda: self._recording_action('save', identifier)).pack(fill='x', padx=self.px(12), pady=self.px(4))
                if row['spec'].get('mode') == 'raw_processed' and row.get('raw_samples', 0):
                    self.button(frame, 'Save physical raw + processed', lambda: self._recording_action('save', identifier, include_raw=True)).pack(fill='x', padx=self.px(12), pady=self.px(4))
                self.button(frame, 'Discard temporary session', lambda: self.confirm('Discard session?', 'Remove this unsaved session, including its audio, transcript and spatial data? Saved recordings and galleries remain.', 'Discard session', lambda: self._recording_action('discard', identifier), cancel=lambda: self.show_session(identifier))).pack(fill='x', padx=self.px(12), pady=self.px(4))
            if row['status'] == 'kept':
                self.button(frame, 'Export recording…', lambda: self._export_recording(identifier)).pack(fill='x', padx=self.px(12), pady=self.px(4))
                if self.controller.selection.input_source == 'saved':
                    self.button(frame, 'Replay with selected backend', lambda: self._recording_action('replay', identifier)).pack(fill='x', padx=self.px(12), pady=self.px(4))
                else:
                    self._paragraph_label(frame, 'To compare this recording, return to combinations and choose Saved WAV input.', True)
            if row['status'] != 'active':
                self.button(frame, 'Delete this recording…', lambda: self.confirm('Delete recording?', 'Permanently delete only this selected recording? Other recordings and voice galleries remain.', 'Delete selected', lambda: self._recording_action('delete', identifier, confirmed=True), cancel=lambda: self.show_session(identifier))).pack(fill='x', padx=self.px(12), pady=self.px(4))
            if not stopped:
                self._paragraph_label(frame, 'Wait for Stop, drain and worker closure before saving/exporting. Failed recordings retain diagnostic evidence.', True)
            if row.get('reason'):
                self._paragraph_label(frame, str(row['reason']), True)

        def _recording_action(self, action, identifier, **values):
            if self._call('session_action', action, identifier=identifier, **values):
                self.home() if action == 'replay' else self.show_sessions() if action == 'delete' else self.show_session(identifier)

        def _open_recording(self, identifier):
            if self._call('session_action', 'open', identifier=identifier):
                self.home()

        def _export_recording(self, identifier):
            destination = self.controller.manager.data_root/'recording_exports'/('%s_%d.zip' % (identifier, time.time_ns()))
            self.keyboard('Private export ZIP path', str(destination),
                lambda path: self._recording_action('export', identifier, path=path), cancel=lambda: self.show_session(identifier))

        def show_motion(self):
            self.page = 'motion'
            frame = self._page('Orientation troubleshooting', back=self.show_settings)
            import tkinter as tk
            canvas = tk.Canvas(frame, height=130, bg=self.color('background'), highlightthickness=0)
            canvas.pack(fill='x', padx=self.px(12), pady=self.px(8))
            self._paragraph_label(frame, 'The fixed BMI270 streams in the capture worker. This drawing is diagnostic; tapping it changes visual zero only. Speaker association keeps its calibrated reference.', True)
            def zero(event):
                motion = self.snapshot.get('motion') or {}
                if motion.get('valid') is True:
                    self._debug_zero = float(motion.get('yaw_deg', 0))
            canvas.bind('<Button-1>', zero)
            def update():
                canvas.delete('all')
                motion = self.snapshot.get('motion') or {}
                valid = motion.get('valid') is True
                angle = math.radians(-(float(motion.get('yaw_deg', 0))-self._debug_zero)) if valid else 0
                c, s = math.cos(angle), math.sin(angle)
                cx = max(220, canvas.winfo_width())/2
                def point(x, y): return cx+x*c-y*s, 52+x*s+y*c
                corners = [point(x, y) for x, y in ((-16,-27),(16,-27),(16,27),(-16,27))]
                color = self.color('accent' if valid else 'muted')
                canvas.create_polygon(*[v for p in corners for v in p], outline=color, fill='', width=2)
                canvas.create_line(*point(0,18), *point(0,-20), arrow='last', fill=color, width=2)
                canvas.create_text(cx, 112, text=str(motion.get('state') or 'Waiting for live capture'), fill=color)
            self._page_update = update
            update()

        def show_diagnostics(self):
            self.page = 'diagnostics'
            frame = self._page('Diagnostics', back=self.show_settings)
            self._paragraph_label(frame, self.controller.diagnostics(), True)
            self.button(frame, 'Refresh', self.show_diagnostics).pack(fill='x', padx=self.px(12), pady=self.px(4))

        def show_advanced(self):
            self.show_diagnostics()

    return PortraitUI


def choose(root, manager, config):
    """One scrollable backend/source chooser; opening never starts capture."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    colors = config['themes']['Dark']
    root.title('Just Peachy · choose combination')
    root.geometry('480x800+0+0')
    root.configure(bg=colors['background'])
    fullscreen_after_map(root)
    tk.Label(root, text='Just Peachy', font=('DejaVu Sans', 24, 'bold'), fg=colors['text'], bg=colors['background']).pack(pady=14)
    tk.Label(root, text='Choose a backend combination', font=('DejaVu Sans', 15), fg=colors['text'], bg=colors['background']).pack(pady=4)
    body = tk.Frame(root, bg=colors['background'])
    body.pack(fill='both', expand=True, padx=14, pady=8)
    rows = []
    for embedding in ('redimnet', 'titanet', 'anonymous'):
        rows.append(RuntimeSelection('pyannote', embedding))
    for preset in catalog():
        for embedding in ('redimnet', 'titanet', 'anonymous'):
            rows.append(RuntimeSelection('nemotron', embedding, nemotron_profile=preset['id'], allow_experimental=preset['experimental']))
    # Keep every currently accepted ordinary variant in the same chooser.
    from release_authorization import authorization, selection_key
    _, approved = authorization(manager.binding)
    seen = {str(sorted(selection_key(row).items())) for row in rows}
    for document in approved.get('allowed_selections', []):
        if document['input_source'] != 'live':
            continue
        row = RuntimeSelection(**document)
        key = str(sorted(selection_key(row).items()))
        if key not in seen:
            rows.append(row); seen.add(key)
    box = tk.Listbox(body, font=('DejaVu Sans', 12), bg=colors['surface'], fg=colors['text'],
                     selectbackground=colors['selected'], selectforeground=colors['text'], exportselection=False)
    scroll = ttk.Scrollbar(body, command=box.yview)
    box.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y'); box.pack(side='left', fill='both', expand=True)
    short_presets = dict(current_delayed='Delayed', chunk52='Chunk52', chunk52_threads2='Chunk52 · 2 threads',
                         streaming='Streaming', official_low='Low latency', official_very_low='Very low latency',
                         official_ultra_low='Ultra low latency', candidate_1_2='1.20s', candidate_2='2.00s',
                         candidate_3='3.04s', candidate_4_5='4.48s', candidate_3_compact='3.04s compact')
    for row in rows:
        label = selection_label(row)
        if row.diarizer == 'nemotron':
            label = 'Nemotron '+short_presets.get(row.nemotron_profile, row.nemotron_profile)+' + '+{'redimnet':'ReDimNet', 'titanet':'TitaNet', 'anonymous':'Anonymous'}[row.embedding]
        if row.embedding_schedule == 'sparse_clean_turn':
            label += ' · sparse turn embeddings'
        if row.speaker_attribution == 'single_d1_late_labels':
            label += ' · ASR-first late labels'
        box.insert('end', label+(' ◇' if row.allow_experimental else ''))
    box.selection_set(0)
    source = tk.StringVar(value='live')
    ttk.Combobox(root, textvariable=source, values=('live', 'saved'), state='readonly', font=('DejaVu Sans', 15)).pack(fill='x', padx=14, pady=7)
    tk.Label(root, text='Live microphone / Saved WAV\nOK opens the familiar caption application, idle.', wraplength=440,
             font=('DejaVu Sans', 12), fg=colors['muted'], bg=colors['background']).pack(pady=5)
    selected = [None]
    def accept():
        choice = box.curselection()
        if not choice:
            return
        row = replace(rows[choice[0]], input_source=source.get())
        if row.allow_experimental and not messagebox.askokcancel('Experimental backend', 'This configuration is available for investigation. Live input availability does not imply sustained real-time performance.', parent=root):
            return
        selected[0] = row
        root.quit()
    tk.Button(root, text='OK · open application', command=accept, height=2, font=('DejaVu Sans', 16),
              bg=colors['accent'], fg=colors['accent_text']).pack(fill='x', padx=14, pady=8)
    tk.Button(root, text='Exit to desktop', command=root.quit, height=2, font=('DejaVu Sans', 14)).pack(fill='x', padx=14, pady=(0, 12))
    root.protocol('WM_DELETE_WINDOW', root.quit)
    root.mainloop()
    return selected[0]


def show(manager):
    import tkinter as tk
    prototype, config = load_retained_ui(manager.binding)
    from application_controller import controller_type
    from mature_frontend import frontend_type as mature_type
    UI = mature_type(prototype, frontend_type(prototype))
    Controller = controller_type(ClassicController)
    while not manager.closed:
        chooser = tk.Tk()
        selection = choose(chooser, manager, config)
        chooser.destroy()
        if selection is None:
            manager.close()
            return
        root = tk.Tk()
        controller = Controller(manager, selection, config)
        transition = {'return': False}
        def return_modes():
            transition['return'] = True
            ui.close()
        ui = UI(root, controller, return_modes)
        root.mainloop()
        if controller.closed and transition['return']:
            continue
        manager.close()
        return
