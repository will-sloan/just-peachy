"""Reconnect mature presentation workflows to the isolated v29 owner. See README.md."""
from copy import deepcopy
import math
from pathlib import Path
import time

from application_contract import default, validate, compatibility, MODES, SELECTED, SEATS, SPATIAL, capacity_seconds
from runtime_support import publish, strict


def controller_type(Base):
    class ApplicationController(Base):
        def __init__(self, manager, selection, config, *, clock=time.monotonic):
            super().__init__(manager, selection, config, clock=clock)
            self.intent = default(selection.embedding)
            self.application_path = manager.data_root/('APPLICATION_'+selection.embedding+'.json')
            self.seat_template = {}
            self.seats = None
            self.people_cache = []
            self.gallery_revision = None
            self.refresh_people()
            if self.application_path.exists():
                saved = strict(self.application_path.read_bytes())
                # A persisted seat template is never a physical anchor.
                if saved['mode'] in SEATS:
                    self.seat_template = deepcopy(saved.get('seating') or {})
                    saved = default(selection.embedding)
                try:
                    self.intent = validate(saved, selection, people=[p['id'] for p in self.people_cache])
                except ValueError:
                    self.notice = 'Saved Mode needs a compatible source or participant selection; choose Mode again.'
            self.mode = self.intent['mode']
            self.pending_save = None
            self.last_completed_choice = None
            self.enrollment = dict(state='IDLE', can_save=False)
            self.gallery_service = None
            self.gallery_exit_requested = False
            from app.text_assistance import TextAssistance
            self.text_assistance = TextAssistance(manager.data_root/'vocabulary.json')
            from retained_ui_data import recipes
            self.recipe_rows = recipes(manager.binding, selection)
            template_path = manager.data_root/('SEATS_'+selection.embedding+'.json')
            if template_path.exists():
                self.seat_template = strict(template_path.read_bytes())

        def refresh_people(self):
            from personal_gallery import summaries
            self.people_cache = summaries(self.manager.binding, self.selection, self.manager.data_root)
            return self.people_cache

        def _persist_intent(self):
            self.intent['settings'] = deepcopy(self.settings)
            publish(self.application_path, self.intent, replace=True)

        def _validate_settings(self, values):
            extra = {'highlight_selected', 'ram_horizon_sec', 'preview_zoom', 'text_aware_references'}
            super()._validate_settings({k:v for k,v in values.items() if k not in extra})
            if 'highlight_selected' in values and type(values['highlight_selected']) is not bool:
                raise ValueError('Explicit highlighting flag required')
            if 'ram_horizon_sec' in values and values['ram_horizon_sec'] not in (60, 120):
                raise ValueError('Bounded audio history must be 60 or 120 seconds')
            if 'preview_zoom' in values and values['preview_zoom'] not in self.config['preview_zooms']:
                raise ValueError('Unknown retained preview zoom')
            if 'text_aware_references' in values and type(values['text_aware_references']) is not bool:
                raise ValueError('Explicit paragraph evidence flag required')

        def _ensure_idle(self):
            if self.manager.process is not None:
                raise ValueError('Stop and drain the current session before changing its processing Mode or gallery')
            if self.enrollment.get('state') not in ('IDLE', 'SAVED', 'ERROR', 'CANCELLED'):
                raise ValueError('Save or cancel the enrollment first')
            if self.gallery_service is not None and not self.gallery_service.closed:
                raise ValueError('Waiting for the enrollment/gallery owner to close')

        def _policy(self):
            from profiles import SessionPolicy
            if self.selection.optional_d1_refiner:
                return super()._policy()
            import shutil
            usage = shutil.disk_usage(self.manager.data_root)
            raw_rate = 0
            if self.selection.input_source == 'live' and self.manager.binding.get('raw_qualification_evidence'):
                raw_rate = 4*16000*4
            seconds = capacity_seconds(usage.free, self.manager.store.policy.reserve(usage.total), raw_bytes_per_second=raw_rate)
            return SessionPolicy(maximum_session_seconds=seconds, manual_stop=True)

        def _start(self, path=None, session_id=None):
            self._ensure_idle()
            if self.pending_save:
                raise ValueError('Save or discard the completed temporary session before another Start')
            self.refresh_people()
            self.intent['settings'] = deepcopy(self.settings)
            intent = validate(self.intent, self.selection, people=[p['id'] for p in self.people_cache])
            self.manager.start(self.selection, self._policy(), path,
                               saved_session_id=session_id, application=intent)
            self.current_id = self.opened_id = None
            self.rows, self.revision = [], None
            self.last_caption_read = -math.inf
            self.error = self.last_closure = self.pending_save = None
            self.notice = 'Loading selected models; capture begins after initialization.'
            self.manager.show_spatial(bool(self.settings.get('spatial_visualization')))

        def switch(self, *, mode=None, recipe=None, tap=None, selected_ids=None, strict=None, **values):
            if values:
                raise ValueError('Unknown application selection')
            proposal = deepcopy(self.intent)
            if strict is not None and all(v is None for v in (mode, recipe, tap, selected_ids)):
                proposal['strict'] = strict
            else:
                self._ensure_idle()
                for key, value in (('mode', mode), ('recipe', recipe), ('tap', tap), ('selected_ids', selected_ids)):
                    if value is not None:
                        proposal[key] = value
                if strict is not None:
                    proposal['strict'] = strict
                if proposal['mode'] not in SEATS:
                    proposal['seating'] = None
                if proposal['mode'] in ('caption_only', 'anonymous_conversation'):
                    proposal['strict'] = False
            self.intent = validate(proposal, self.selection, people=[p['id'] for p in self.refresh_people()])
            self.mode = self.intent['mode']
            self._persist_intent()
            self.revision = None
            self.last_caption_read = -math.inf
            self.notice = 'Mode selected. Press Start when ready.'

        def display_roster(self, ids):
            proposal = deepcopy(self.intent)
            proposal['display_ids'] = list(ids)
            if not ids:
                proposal['strict'] = False
            self.intent = validate(proposal, self.selection, people=[p['id'] for p in self.refresh_people()])
            self._persist_intent()
            self.revision = None

        def seats_apply(self, rows, mode, strength='soft', acknowledged=False):
            self._ensure_idle()
            from retained_seats import load
            recovered = load(self.manager.binding)
            SeatSession, validate_layout = recovered.SeatSession, recovered.validate_layout
            reason = compatibility(self.selection, mode)
            if mode not in SEATS or reason:
                raise ValueError(reason or 'Choose an assigned-seat Mode')
            rows = validate_layout(rows, {p['id'] for p in self.refresh_people()})
            if not rows or type(acknowledged) is not bool:
                raise ValueError('Assign participants and explicitly acknowledge any ambiguity')
            if mode == 'assigned_direction' and strength != 'soft':
                raise ValueError('Direction-only uses the retained soft setting')
            self.seats = SeatSession(rows, strength=strength, acknowledged=acknowledged)
            proposal = deepcopy(self.intent)
            proposal.update(mode=mode, recipe='balanced', selected_ids=[r['person_id'] for r in rows],
                            seating=self.seats.snapshot(), strict=False)
            self.intent = validate(proposal, self.selection, people=[p['id'] for p in self.people_cache])
            self.mode = mode
            self._persist_intent()
            self.notice = 'Seats anchored at this location for the next session. Direction names are assumptions.'

        def seats_save_template(self, rows, strength='soft'):
            from retained_seats import load
            validate_layout = load(self.manager.binding).validate_layout
            if strength not in ('soft', 'strong'):
                raise ValueError('Use retained soft/strong seat settings')
            self.seat_template = dict(rows=validate_layout(rows, {p['id'] for p in self.refresh_people()}), strength=strength, valid=False)
            publish(self.manager.data_root/('SEATS_'+self.selection.embedding+'.json'), self.seat_template, replace=True)

        def reset_spatial(self):
            self._ensure_idle()
            if self.seats:
                self.seats.invalidate('manual_device_moved; apply_at_current_location_required')
                self.intent['seating'] = self.seats.snapshot()
            self.notice = 'Position anchors cleared. Fresh motion reference starts with the next session.'

        def identity_parameters(self, values=None):
            self._ensure_idle()
            from app.mode_policy import validate_overrides
            proposal = deepcopy(self.intent)
            proposal['identity_overrides'] = validate_overrides(values or {})
            self.intent = validate(proposal, self.selection, people=[p['id'] for p in self.people_cache])
            self._persist_intent()

        def settings_update(self, values):
            self._validate_settings(values)
            if 'preview_zoom' in values and values['preview_zoom'] not in self.config['preview_zooms']:
                raise ValueError('Unknown retained preview zoom')
            if 'highlight_selected' in values and type(values['highlight_selected']) is not bool:
                raise ValueError('Explicit display highlighting flag required')
            if 'ram_horizon_sec' in values and values['ram_horizon_sec'] not in (60, 120):
                raise ValueError('Use the retained bounded audio history')
            self.settings.update(values)
            publish(self.settings_path, self.settings, replace=True)
            self._persist_intent()
            self.manager.show_spatial(bool(self.settings.get('spatial_visualization')))

        def snapshot(self):
            if self.gallery_service is not None:
                service = self.gallery_service
                self.enrollment = deepcopy(service.poll())
                if self.enrollment.get('last_command') in ('enrollment_save','enrollment_cancel','rename_person','delete_person','import_people','export_people'):
                    service.close()
                if service.closed:
                    self.refresh_people()
                    if self.enrollment.get('error'):
                        self.notice = str(self.enrollment['error'])
                    if self.gallery_exit_requested:
                        super().close()
                    self.gallery_service = None
            value = super().snapshot()
            from app.mode_policy import MODE_METADATA
            from app.backends import backend_catalog
            if self.selection.diarizer == 'pyannote':
                key = 'baseline'
            else:
                key = 'd1-'+('delayed' if self.selection.nemotron_profile == 'current_delayed' else 'streaming')
            if self.selection.embedding == 'titanet':
                key += '-titanet'
            if key.startswith('d1-streaming'):
                key += '-saved'
            backend = next((b for b in backend_catalog() if b['key'] == key), backend_catalog()[0])
            backend = dict(backend, label=value['backend']['label'])
            view = self.manager.latest_spatial or {}
            spatial = view.get('spatial') or {}
            seating = deepcopy(spatial.get('seating') or (self.seats.snapshot() if self.seats else {}))
            if self.seat_template:
                seating['template'] = deepcopy(self.seat_template)
            # Applying seats is a session anchor; after any Stop it must be explicit again.
            if value['state'] in ('STOPPED', 'ERROR') and self.seats and self.seats.valid:
                self.seats.invalidate('session_stopped; re_anchor_required')
                self.intent['seating'] = self.seats.snapshot()
            if value['state'] == 'STOPPED' and self.current_id and not self.opened_id and self.current_id != self.last_completed_choice:
                self.pending_save = self.current_id
            selected = set(self.intent['display_ids'])
            for row in value['rows']:
                pid = row.get('profile_id')
                row['selected'] = pid in selected
                row['visible'] = not self.intent['strict'] or row['selected']
                if self.mode == 'enrolled_names' and not pid:
                    row['label'] = 'Unknown'
            value.update(mode=self.mode, recipe=self.intent['recipe'], tap='O0',
                backend_id=backend['id'], backend=backend, backends=[backend],
                people=deepcopy(self.people_cache), roster_compatibility=deepcopy(self.people_cache),
                selected_ids=list(self.intent['selected_ids']), display_ids=list(self.intent['display_ids']),
                strict=self.intent['strict'], seating=seating, mode_metadata=deepcopy(MODE_METADATA),
                identity_overrides=deepcopy(self.intent['identity_overrides']), enrollment=deepcopy(self.enrollment),
                recorded_spatial_available=self.selection.input_source == 'live',
                application_intent=deepcopy(self.intent), pending_save=self.pending_save)
            value['recipes'] = deepcopy(self.recipe_rows)
            value['text_assistance'] = self.text_assistance.snapshot(self.people_cache)
            value.setdefault('metrics', {}).update(deepcopy(self.enrollment.get('metrics') or {}))
            return value

        def text_assistance_action(self, action, **values):
            self.text_assistance.change(action, values, self.people_cache)
            self.notice = 'Text preference saved. Raw speech and speaker matching are unchanged.'

        def noise_route(self, value):
            if value != 'bypass':
                raise ValueError('Optional DPDFNet routing is not admitted by this package: its old in-memory journal cannot preserve the exact durable model-input timeline. Current XVF acquisition stays selected.')
            self.notice = 'Current XVF route selected; no additional enhancement model.'

        def adaptation_action(self, action, **values):
            raise ValueError('Session reference promotion is not connected to the isolated worker. Persistent original personal references remain active; no thresholds or gallery entries are changed.')

        def review_action(self, action, **values):
            if action == 'cancel':
                return
            raise ValueError('The recovered transcript review model requires Windows x86-64. It is unavailable in this offline CM5 package; original transcript and corrections remain exportable.')

        def mark_problem(self, save_audio=False):
            if save_audio:
                raise ValueError('Save the completed session to retain its exact audio; the old RAM-excerpt writer is not connected to the isolated source.')
            from datetime import datetime, timezone
            import uuid
            folder = self.manager.data_root/'problems'/uuid.uuid4().hex
            folder.mkdir(parents=True)
            receipt = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                session_id=self.current_id, selection=self.selection.validate(),
                application=deepcopy(self.intent), rows=deepcopy(self.rows[-20:]),
                audio_saved=False, user_requested=True, private=True)
            publish(folder/'PROBLEM.json', receipt)
            self.notice = 'Private problem marker saved: '+str(folder)

        def script_review(self, identifier): self._gallery('script_review', identifier)

        def _gallery(self, command, *args, **kwargs):
            if self.selection.embedding == 'anonymous':
                raise ValueError('Anonymous processing has no personal gallery; choose ReDimNet or TitaNet to enroll or manage people')
            if self.manager.process is not None or self.manager.export_task is not None:
                raise ValueError('Stop/drain speech and exports before gallery changes')
            if self.gallery_service is None or self.gallery_service.closed:
                from gallery_service import GalleryService
                self.gallery_service = GalleryService(self.manager, self.selection, deepcopy(self.settings))
            self.gallery_service.command(command, *args, **kwargs)
            self.enrollment = dict(state='LOADING', can_save=False)

        def enrollment_start(self, name, target_sec=30, consent=False, person_id=None, paragraph=None):
            if consent is not True:
                raise ValueError('Explicit consent to this enrollment recording required')
            self._gallery('enrollment_start', name, target_sec, consent=consent, person_id=person_id, paragraph=paragraph)

        def enrollment_stop(self): self._gallery('enrollment_stop')
        def enrollment_save(self): self._gallery('enrollment_save')
        def enrollment_cancel(self): self._gallery('enrollment_cancel')
        def enrollment_script_note(self, text): self._gallery('enrollment_script_note', text)
        def rename_person(self, identifier, name): self._gallery('rename_person', identifier, name)
        def delete_person(self, identifier): self._gallery('delete_person', identifier)
        def import_people(self, path, consent=False): self._gallery('import_people', str(path), consent)
        def export_people(self, path, consent=False): self._gallery('export_people', str(path), consent)

        def close(self):
            if self.gallery_service is not None and not self.gallery_service.closed:
                self.gallery_exit_requested = True
                self.gallery_service.close()
                self.notice = 'Closing enrollment capture and its quality worker before Exit.'
                return
            super().close()

        def session_action(self, action, **values):
            identifier = values.get('identifier') or self.current_id
            if action == 'rename':
                self._ensure_idle()
                self.manager.store.rename(identifier, values['title'])
                self.notice = 'Recording renamed.'
            elif action == 'discard':
                self._ensure_idle()
                row = self.manager.store.read(identifier)
                if row['status'] != 'stopped':
                    raise ValueError('Only a cleanly stopped unsaved session can be discarded here')
                self.manager.store.delete(identifier, confirm=True)
                self.current_id = self.opened_id = None
                self.rows, self.revision = [], None
                self.notice = 'Temporary session removed.'
            else:
                super().session_action(action, **values)
            if action in ('save', 'discard'):
                self.last_completed_choice = identifier
                self.pending_save = None
            self.history()

    return ApplicationController
