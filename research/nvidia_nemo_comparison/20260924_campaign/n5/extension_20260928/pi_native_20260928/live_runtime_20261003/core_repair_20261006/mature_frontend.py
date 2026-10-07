"""Selective reuse of the original portrait UI. See README_STARTUP_REPAIR.md and README_MANUAL_START.md."""
from pathlib import Path
import time
import types

from application_contract import compatibility
from caption_paragraphs import paragraph_rows


def operator_mode_menu(method):
    """Keep original UI code with a presentation-only anonymous menu filter."""
    modes = method.__globals__.get('MODES')
    if not isinstance(modes, dict) or 'open_with_names' not in modes:
        raise ValueError('Exact mature Mode menu constants required')
    namespace = dict(method.__globals__, MODES={key: value for key, value in modes.items()
                                               if key != 'anonymous_conversation'})
    projected = types.FunctionType(method.__code__, namespace, method.__name__,
                                   method.__defaults__, method.__closure__)
    projected.__kwdefaults__ = method.__kwdefaults__
    return projected


def frontend_type(prototype, Portrait):
    class MatureUI(Portrait):
        show_modes = operator_mode_menu(prototype.show_modes)
        show_advanced = operator_mode_menu(prototype.show_advanced)

        def _render_rows(self, rows, force=False):
            self._follow_live = self.controller.caption_follow
            if not self._follow_live:
                # A previously scheduled smoothing frame cannot restore an old
                # live tail over a page the operator has started reading.
                rows = self.controller.rows
            mode = self.snapshot.get('mode', 'caption_only')
            if self.snapshot.get('strict'):
                rows = [row for row in rows if row.get('selected')]
            paragraphs = paragraph_rows(rows, mode)
            formatter = Portrait._display_row.__globals__['provisional_case']
            names = [str(person.get('name','')) for person in self.snapshot.get('people',[])]
            for paragraph in paragraphs:
                if paragraph.pop('_needs_group_casing',False):
                    paragraph['provisional_display_text'] = formatter(paragraph['raw_asr_text'],names,self.config['acronyms'])
                    if paragraph['final']:
                        paragraph['final_punctuated_display_text'] = paragraph['provisional_display_text']
            return super()._render_rows(paragraphs, force=force)

        def _scroll_caption(self, units):
            self.controller.set_caption_follow(False)
            self._follow_live = False
            if units < 0 and self.caption_text.yview()[0] <= .001:
                if self.controller.captions_older():
                    self._render_rows(self.controller.rows)
            return super()._scroll_caption(units)

        def _drag_caption(self, event):
            self.controller.set_caption_follow(False)
            return super()._drag_caption(event)

        def back_to_live(self):
            if self._display_handle:
                self.root.after_cancel(self._display_handle)
                self._display_handle = None
            self._pending_rows = None
            self.controller.set_caption_follow(True)
            super().back_to_live()
            self._render_rows(self.controller.rows)

        def _choose_mode(self, mode):
            if mode == 'anonymous_conversation':
                self._notice = 'Choose a named Mode. Unrecognized speakers remain Unknown internally.'
                self._show_status()
                return
            reason = compatibility(self.controller.selection, mode)
            if reason:
                self._notice = reason
                self._show_status()
                return
            return prototype._choose_mode(self, mode)

        def show_settings(self):
            # A previous page may have left destroyed widgets in this map.
            for key in ('microphone_permission', 'auto_listening'):
                self.actions.pop(key, None)
            prototype.show_settings(self)
            for key in ('microphone_permission', 'auto_listening'):
                button = self.actions.pop(key, None)
                if button is not None:
                    button.master.destroy()

        def show_people(self):
            prototype.show_people(self)
            if self.controller.selection.embedding == 'anonymous':
                for key in ('add_person', 'import_people', 'export_people'):
                    button = self.actions.get(key)
                    if button is not None:
                        button.configure(state='disabled')
                self._notice = 'Anonymous mode has no voice gallery. Return to combinations to choose ReDimNet or TitaNet.'
                self._show_status()

        def _page(self, title, *args, **kwargs):
            frame = super()._page(title, *args, **kwargs)
            if title == 'Settings':
                self.button(frame, 'Return to backend combinations', self.return_modes,
                    key='combinations').pack(fill='x', padx=self.px(12), pady=self.px(4))
                self.button(frame, 'Exit to desktop', self.close,
                    key='exit_desktop').pack(fill='x', padx=self.px(12), pady=self.px(4))
                self._paragraph_label(frame,
                    'The app opens with the microphone off. Press Start to listen and Stop to release capture. '
                    'Live conversations continue until Stop. Storage, backlog and hardware faults can stop safely. '
                    'After processing drains, choose Save session or Discard.', True)
            return frame

        def poll(self):
            super().poll()
            # Keep the bounded pending label readable without a luminance pulse.
            if not self._closed:
                self.caption_text.tag_configure('pending', foreground=self.color('muted'))
            readiness = bool(getattr(self.controller.manager, 'readiness_pending', False))
            if readiness and not self._closing:
                for key in ('mode', 'people', 'settings', 'backend'):
                    self.actions[key].configure(state='disabled')
                self.actions['start_stop'].configure(state='normal')
                self._readiness_controls_disabled = True
            elif getattr(self, '_readiness_controls_disabled', False) and not self._closing:
                for key in ('mode', 'people', 'settings', 'backend'):
                    self.actions[key].configure(state='normal')
                self._readiness_controls_disabled = False
            identifier = self.snapshot.get('pending_save')
            if identifier and identifier != getattr(self, '_save_prompt_id', None) and not self._closing and not readiness:
                self._save_prompt_id = identifier
                self.show_save_prompt(identifier)

        def show_save_prompt(self, identifier):
            self.page = 'save_session'
            frame = self._page('Save this session?', back=self.home)
            row = self.controller.manager.store.read(identifier)
            self._paragraph_label(frame,
                'Capture has stopped and processing has drained. Save the transcript, processed replay audio, '
                'configuration and available beam/motion timelines. Voice galleries remain separately protected.', True)
            raw = row['spec'].get('mode') == 'raw_processed' and row.get('raw_samples', 0) > 0
            self.button(frame, 'Save session'+(' · raw + processed' if raw else ''),
                lambda: self._recording_action('save', identifier, include_raw=raw),
                key='save_session', height=60).pack(fill='x', padx=self.px(12), pady=self.px(6))
            if raw:
                self.button(frame, 'Save without physical raw audio',
                    lambda: self._recording_action('save', identifier, include_raw=False),
                    key='save_processed', height=60).pack(fill='x', padx=self.px(12), pady=self.px(6))
            self.button(frame, 'Discard this temporary session', lambda: self.confirm(
                'Discard session?', 'Remove this unsaved session audio, transcript and spatial/motion data? '
                'Saved recordings and voice profiles remain.', 'Discard',
                lambda: self._recording_action('discard', identifier),
                cancel=lambda: self.show_save_prompt(identifier)),
                key='discard_session', height=60).pack(fill='x', padx=self.px(12), pady=self.px(6))

        def show_sessions(self, older=False):
            super().show_sessions(older)
            self._notice = 'Recordings: '+str(self.controller.manager.store.root)
            self._show_status()

        def show_session(self, identifier):
            super().show_session(identifier)
            # Reuse the original detail page and add the historical rename action.
            frame = self._session_detail_frame
            row = self.controller.manager.store.read(identifier)
            if row['status'] == 'kept':
                self.button(frame, 'Rename recording', lambda: self.keyboard(
                    'Recording name', row['spec'].get('title', ''),
                    lambda value: self._recording_action('rename', identifier, title=value),
                    cancel=lambda: self.show_session(identifier)),
                    key='rename_recording').pack(fill='x', padx=self.px(12), pady=self.px(4))
            self._paragraph_label(frame, 'Local folder: '+str(self.controller.manager.store.root/'sessions'/identifier)+
                '\nPrivate export folder: '+str(self.controller.manager.data_root/'recording_exports'), True)

        def _recording_action(self, action, identifier, **values):
            if self._call('session_action', action, identifier=identifier, **values):
                self.home() if action == 'replay' else self.show_sessions()

        def browse_file(self, action, directory=None):
            if action in ('import', 'export'):
                return prototype.browse_file(self, action, directory)
            return super().browse_file(action, directory)

    return MatureUI
