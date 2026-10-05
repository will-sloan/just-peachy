"""Selective reuse of the original portrait UI, not a replacement. See README.md."""
from pathlib import Path
import time

from application_contract import compatibility


def frontend_type(prototype, Portrait):
    class MatureUI(Portrait):
        show_modes = prototype.show_modes
        show_advanced = prototype.show_advanced

        def _choose_mode(self, mode):
            reason = compatibility(self.controller.selection, mode)
            if reason:
                self._notice = reason
                self._show_status()
                return
            return prototype._choose_mode(self, mode)

        def show_settings(self):
            prototype.show_settings(self)
            button = self.actions.get('auto_listening')
            if button is not None:
                button.configure(text='Listen when app opens: Off · manual Start', state='disabled')

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
                    'Live conversations continue until Stop. Storage, backlog and hardware faults can stop safely. '
                    'After processing drains, choose Save session or Discard.', True)
            return frame

        def poll(self):
            super().poll()
            identifier = self.snapshot.get('pending_save')
            if identifier and identifier != getattr(self, '_save_prompt_id', None) and not self._closing:
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
            self._paragraph_label(frame, 'Local folder: '+str(self.controller.manager.store.root/identifier)+
                '\nPrivate export folder: '+str(self.controller.manager.data_root/'recording_exports'), True)

        def _recording_action(self, action, identifier, **values):
            if self._call('session_action', action, identifier=identifier, **values):
                self.home() if action == 'replay' else self.show_sessions()

        def browse_file(self, action, directory=None):
            if action in ('import', 'export'):
                return prototype.browse_file(self, action, directory)
            return super().browse_file(action, directory)

    return MatureUI
