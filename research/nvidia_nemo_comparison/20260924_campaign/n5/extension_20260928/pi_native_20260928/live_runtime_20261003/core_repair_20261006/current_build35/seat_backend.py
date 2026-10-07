"""Backend-bound seat decisions without cross-encoder calibration. See README_SEAT_BACKENDS.md."""
from collections import OrderedDict
from copy import deepcopy
import ast
import hashlib
import json
import math
from pathlib import Path
import threading
import time
import types


BACKENDS = {('pyannote', 'redimnet'), ('pyannote', 'titanet'),
            ('nemotron', 'redimnet'), ('nemotron', 'titanet')}
SEAT_MODES = {'assigned_direction', 'assigned_hybrid'}
MAX_ASSIGNMENTS = 4096


def _code_shape(code):
    return (code.co_code, code.co_names, code.co_varnames, code.co_freevars,
            code.co_cellvars, code.co_argcount, code.co_posonlyargcount,
            code.co_kwonlyargcount, tuple(_code_shape(value) if isinstance(value, types.CodeType)
                                       else value for value in code.co_consts))


def install_factory_hook(pipeline, expected_source_sha256):
    """Derive one method from exact loaded source; original disk bytes stay intact.

    Only the SeatIdentityResolver constructor callee changes. The original
    globals, defaults and closure cells are reused, including __class__ for
    zero-argument super if that appears in a future admitted exact source.
    """
    if (not isinstance(expected_source_sha256, str) or len(expected_source_sha256) != 64 or
            any(value not in '0123456789abcdef' for value in expected_source_sha256)):
        raise ValueError('Exact manifest pipeline source SHA256 required')
    source = Path(pipeline.__file__)
    if source.is_symlink() or not source.is_file() or source.stat().st_size > 128*1024:
        raise ValueError('Bounded real loaded pipeline source required')
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_source_sha256:
        raise ValueError('Loaded pipeline source differs from the manifest pin')
    original = pipeline.PrototypeEngine.begin
    prior = getattr(original, '_just_peachy_seat_hook_receipt', None)
    if prior is not None:
        if prior.get('source_sha256') != expected_source_sha256 or prior.get('source') != str(source.resolve()):
            raise ValueError('Different seat hook already installed in this process')
        return deepcopy(prior)
    if (original.__globals__ is not pipeline.__dict__ or
            original.__module__ != pipeline.__name__ or
            set(original.__code__.co_freevars)-{'__class__'}):
        raise ValueError('Pipeline begin globals/origin/closure are not the reviewed method')
    if '__class__' in original.__code__.co_freevars:
        cell = original.__closure__[original.__code__.co_freevars.index('__class__')]
        if cell.cell_contents is not pipeline.PrototypeEngine:
            raise ValueError('Pipeline begin class closure differs')
    tree = ast.parse(raw, filename=str(source))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'PrototypeEngine']
    if len(classes) != 1:
        raise ValueError('Exactly one original PrototypeEngine class required')
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name == 'begin']
    if len(methods) != 1 or methods[0].decorator_list:
        raise ValueError('Exactly one undecorated original begin method required')
    before = methods[0]
    changed = deepcopy(before)
    calls = [node for node in ast.walk(changed) if isinstance(node, ast.Call) and
             isinstance(node.func, ast.Name) and node.func.id == 'SeatIdentityResolver']
    if len(calls) != 1:
        raise ValueError('Exactly one retained seat constructor target required')
    call = calls[0]
    old_target = deepcopy(call.func)
    call.func = ast.copy_location(ast.Call(func=ast.Name(id='getattr', ctx=ast.Load()),
        args=[ast.Name(id='self', ctx=ast.Load()), ast.Constant(value='_seat_identity_factory'),
              ast.Name(id='SeatIdentityResolver', ctx=ast.Load())], keywords=[]), old_target)
    # Exhaustive structural comparison: reverting this one callee must recover
    # the original method AST, including every guard, argument and statement.
    restored = deepcopy(changed)
    targets = [node for node in ast.walk(restored) if isinstance(node, ast.Call) and
        isinstance(node.func, ast.Call) and isinstance(node.func.func, ast.Name) and
        node.func.func.id == 'getattr' and len(node.func.args) == 3 and
        isinstance(node.func.args[1], ast.Constant) and node.func.args[1].value == '_seat_identity_factory']
    if len(targets) != 1:
        raise ValueError('Seat derivative contains additional factory changes')
    targets[0].func = old_target
    dump = lambda value: ast.dump(value, annotate_fields=True, include_attributes=False)
    if dump(restored) != dump(before):
        raise ValueError('Seat factory derivative changes more than the constructor target')
    def compile_method(node, filename):
        container = deepcopy(classes[0])
        container.bases, container.keywords, container.decorator_list = [], [], []
        container.body = [deepcopy(node)]
        module = ast.fix_missing_locations(ast.Module(body=[container], type_ignores=[]))
        namespace = {}
        exec(compile(module, filename, 'exec'), original.__globals__, namespace)
        return namespace['PrototypeEngine'].begin
    reference = compile_method(before, str(source))
    if _code_shape(reference.__code__) != _code_shape(original.__code__):
        raise ValueError('Loaded begin implementation differs from the pinned source AST')
    derived = compile_method(changed, '<just-peachy-seat-factory:'+expected_source_sha256+'>')
    if derived.__code__.co_freevars != original.__code__.co_freevars:
        raise ValueError('Seat derivative closure shape differs')
    method = types.FunctionType(derived.__code__, original.__globals__, original.__name__,
                                original.__defaults__, original.__closure__)
    method.__kwdefaults__ = deepcopy(original.__kwdefaults__)
    method.__annotations__ = deepcopy(original.__annotations__)
    method.__module__, method.__qualname__, method.__doc__ = original.__module__, original.__qualname__, original.__doc__
    receipt = dict(schema='just-peachy.seat-constructor-hook.v1', source=str(source.resolve()),
        source_sha256=expected_source_sha256, before_ast_sha256=hashlib.sha256(dump(before).encode()).hexdigest(),
        after_ast_sha256=hashlib.sha256(dump(changed).encode()).hexdigest(),
        constructor_targets_changed=1, only_constructor_callee_changed=True,
        source_disk_changed=False, model_thresholds_changed=False,
        original_globals_reused=method.__globals__ is original.__globals__,
        original_closure_reused=method.__closure__ is original.__closure__,
        original_default_factory='SeatIdentityResolver', per_instance_override='_seat_identity_factory')
    method._just_peachy_seat_hook_receipt = deepcopy(receipt)
    pipeline.PrototypeEngine.begin = method
    return receipt


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def track_domain(diarizer, embedding):
    if (diarizer, embedding) not in BACKENDS:
        raise ValueError('Assigned seats require a supported named encoder backend')
    return ('pyannote-online-track' if diarizer == 'pyannote' else
            'nemotron-native-session-slot') + ':' + embedding


def calibration_receipt(gallery, embedding):
    """Inspect the existing gallery's gate; never invent or transfer a threshold."""
    if embedding not in ('redimnet', 'titanet'):
        raise ValueError('A separate named encoder gallery is required')
    receipt = getattr(gallery, 'receipt', {}) if gallery is not None else {}
    namespace = getattr(gallery, 'namespace', None) if gallery is not None else None
    gate = getattr(gallery, 'calibration', {}) if gallery is not None else {}
    encoder_matches = bool(isinstance(namespace, dict) and namespace.get('dimension') == 192 and
        namespace.get('normalization') == 'L2' and
        ((embedding == 'redimnet' and namespace.get('preprocessing') == 'mono-float32-16k-redimnet2-native-l2-v1') or
         (embedding == 'titanet' and all(isinstance(namespace.get(key), str) and len(namespace[key]) == 64
             for key in ('onnx_sha256', 'frontend_sha256')))))
    calibrated = (isinstance(namespace, dict) and isinstance(gate, dict) and
        encoder_matches and
        gate.get('status') == 'CALIBRATED' and gate.get('namespace') == namespace and
        gate.get('schema') == 'just-peachy.n2.calibrated-gate.v1' and
        gate.get('fit_role') == 'C' and receipt.get('loader') == 'N2Gallery actual runtime cosine' and
        isinstance(receipt.get('expected_query_domain'), str) and
        gate.get('query_domain') == receipt['expected_query_domain'] and
        isinstance(gate.get('profile_ids'), list) and
        set(gate['profile_ids']) == set(getattr(gallery, 'ids', [])) and
        len(gate['profile_ids']) == len(getattr(gallery, 'ids', [])) and
        _finite(gate.get('score_threshold')) and -1 <= gate['score_threshold'] <= 1.000002 and
        _finite(gate.get('margin_threshold')) and 0 <= gate['margin_threshold'] <= 2 and
        gate.get('gate_sha256') == _sha({k:v for k,v in gate.items() if k != 'gate_sha256'}))
    return dict(schema='just-peachy.seat-calibration-domain.v1', embedding=embedding,
        gallery_id=getattr(gallery, 'gallery_id', receipt.get('gallery_id')),
        namespace=deepcopy(namespace), backend_sha256=receipt.get('backend_sha256'),
        preprocessing=receipt.get('preprocessing'), query_domain=receipt.get('expected_query_domain'),
        calibrated=bool(calibrated), gate_sha256=gate.get('gate_sha256') if calibrated else None,
        score_threshold=gate.get('score_threshold') if calibrated else None,
        margin_threshold=gate.get('margin_threshold') if calibrated else None,
        reason='existing model/domain/roster C gate' if calibrated else
            'No independently calibrated C gate for this exact encoder, query domain and roster; hybrid names stay Unknown')


def _event_valid(event, decision, now):
    start, end, available = (event.get(k) for k in
                            ('source_start_sec', 'source_end_sec', 'available_at_sec'))
    if not all(_finite(v) for v in (start, end, available, now)):
        return False
    if not (0 <= start < end <= available + 1e-6 and 0 <= now-available <= 2):
        return False
    if event.get('speech') is not True or event.get('overlap') is not False:
        return False
    track = decision.get('tracker_id', decision.get('track_id'))
    if track is None or isinstance(track, bool) or decision.get('reason') == 'audio_gate_reject':
        return False
    vector = event.get('vector')
    if not isinstance(vector, (tuple, list)) or len(vector) != 192:
        return False
    if not all(_finite(v) for v in vector) or sum(v*v for v in vector) <= 1e-16:
        return False
    clean = event.get('clean_intervals')
    return bool(isinstance(clean, (list, tuple)) and clean and all(
        isinstance(pair, (list, tuple)) and len(pair) == 2 and
        all(_finite(v) for v in pair) and start <= pair[0] < pair[1] <= end
        for pair in clean))


class BackendSeatResolver:
    """N2 post-association adapter; geometry never establishes verified identity.

    The voice delegate is the existing N2NameMap. Direction-only never calls it.
    Hybrid preserves its exact calibrated acceptance and contradiction reset;
    no C088 threshold, S6C voice score or seat-assisted score promotion is added.
    """
    def __init__(self, voice_map, *, seats, names, provider, diarizer, embedding,
                 direction_only=False, clock=None):
        if seats is None or provider is None or (not direction_only and voice_map is None):
            raise ValueError('An anchored seat session, causal provider and hybrid voice delegate are required')
        if type(direction_only) is not bool:
            raise ValueError('Direction-only selection must be explicit')
        if not isinstance(names, dict) or len(names) > 256:
            raise ValueError('Bounded encoder-specific person names required')
        self.domain = track_domain(diarizer, embedding)
        self.diarizer, self.embedding = diarizer, embedding
        self.voice_map, self.seats, self.names, self.provider = voice_map, seats, dict(names), provider
        self.direction_only, self.clock = direction_only, clock
        self.gallery = getattr(voice_map, 'gallery', None)
        self.assignments = OrderedDict()
        self.lock = threading.RLock()
        self.calls = 0
        self.total_sec = 0.

    def __getattr__(self, name):
        # Preserve delegate snapshot/telemetry interfaces, never replace voice memory.
        if name.startswith('__'):
            raise AttributeError(name)
        return getattr(self.voice_map, name)

    def sync_tracks(self, active_ids, now):
        if self.voice_map is not None:
            self.voice_map.sync_tracks(active_ids, now)

    def _cue(self, event, valid):
        if not valid:
            return None, dict(valid=False, reason='no_admitted_clean_model_speech')
        start, end, available = (event[k] for k in
                                ('source_start_sec', 'source_end_sec', 'available_at_sec'))
        historical = self.diarizer == 'nemotron' or getattr(self.provider, 'historical_source_evidence', False)
        if historical:
            method = getattr(self.provider, 'seat_evidence_for_source', None)
            if method is not None:
                cue, detail = method(start, end)
            else:
                # The preserved provider already maps telemetry to real callbacks,
                # selects only mapped_end <= end, checks source-window coverage,
                # energy/angle receipts, motion generation and the seat anchor.
                # D1 compute delay is reported separately, never clamped away.
                cue, detail = self.provider.seat_evidence(start, end, end)
            detail = deepcopy(detail)
            detail.update(direction_clock_basis='historical source-window/callback evidence',
                model_available_at_sec=available, model_delay_from_source_sec=available-end,
                current_position_claim=False, acoustic_synchronization_claim=False)
        else:
            cue, detail = self.provider.seat_evidence(start, end, available)
            detail = deepcopy(detail)
            detail.update(direction_clock_basis='original Pyannote model-evidence availability',
                          current_position_claim=False, acoustic_synchronization_claim=False)
        if cue is not None and (not _finite(cue.angle_deg) or not 0 <= cue.angle_deg <= 180 or
                                not _finite(cue.reliability) or cue.reliability <= 0):
            return None, dict(detail, valid=False, reason='invalid_direction_projection')
        return cue, detail

    def resolve(self, decision, event):
        began = time.perf_counter()
        now = self.clock() if self.clock else event.get('available_at_sec')
        valid = _event_valid(event, decision, now)
        if self.direction_only:
            result = deepcopy(decision)
            result.update(identity={}, identity_compute_sec=0.)
        else:
            result = self.voice_map.resolve(decision, event if valid else {**event, 'speech':False})
        identity = result['identity']
        cue, detail = self._cue(event, valid)
        seat = self.seats.snapshot()
        released = seat.get('released', {})
        candidates = [row for row in seat['rows'] if cue is not None and
            row['person_id'] not in released and
            abs(row['angle_deg']-cue.angle_deg) <= row['tolerance_deg']]
        calibration = calibration_receipt(self.gallery, self.embedding)
        detail.update(track_domain=self.domain, session_id=seat['session_id'],
            revision=seat['revision'], anchor_valid=seat['valid'], strength=seat['strength'],
            candidate_ids=[row['person_id'] for row in candidates], ambiguous=len(candidates)>1,
            released=deepcopy(released), basis='unavailable', voice_identity_used=not self.direction_only,
            voice_calibration=calibration, voice_threshold_promotion=False,
            geometry='retained linear 0..180 degree projection; front/back ambiguous')
        person = None
        assignment = 'unavailable'
        reason = detail.get('reason', 'no_fresh_direction')
        if self.direction_only and not seat['valid']:
            reason = 're_anchor_required: '+seat['reason']
        elif self.direction_only and valid and cue is not None:
            if len(candidates) == 1:
                person = candidates[0]['person_id']
                assignment, reason = 'seat_assumed', 'closed_seating_direction_assumption_not_verified_identity'
                detail['basis'] = 'explicit unique seat assumption'
            else:
                assignment = 'ambiguous' if candidates else 'unavailable'
                reason = 'overlapping_projected_seats' if candidates else 'outside_assigned_or_released_regions'
        elif not self.direction_only:
            # The caller's actual N2Gallery performed full C provenance/roster
            # validation. Only its actual N2NameMap acceptance may become a name.
            accepted = (valid and calibration['calibrated'] and identity.get('verified') is True and
                identity.get('naming_state') == 'confirmed' and identity.get('known_profile_id') in self.names)
            if accepted:
                person = identity['known_profile_id']
                current = identity.get('current_scores', [])
                strong = bool(current and current[0].get('profile_id') == person and
                    _finite(current[0].get('cosine')) and
                    current[0]['cosine'] >= calibration['score_threshold'] and
                    (len(current) == 1 or (_finite(current[1].get('cosine')) and
                     current[0]['cosine']-current[1]['cosine'] >= calibration['margin_threshold'])))
                own = next((row for row in seat['rows'] if row['person_id'] == person), None)
                other = [row['person_id'] for row in candidates if row['person_id'] != person]
                if seat['valid'] and cue is not None and strong and (other or (own and
                        abs(own['angle_deg']-cue.angle_deg) > own['tolerance_deg'])):
                    self.seats.release([person, *other], 'calibrated_voice_conflict_or_participant_relocation')
                    detail.update(released=deepcopy(self.seats.snapshot()['released']), trust_released=True)
                agreement = (seat['valid'] and len(candidates) == 1 and candidates[0]['person_id'] == person and
                             person not in detail['released'])
                assignment = 'accepted'
                reason = 'calibrated_voice_accepted_with_seat_agreement' if agreement else 'calibrated_voice_only_fallback'
                detail.update(basis='model/domain/roster calibrated voice', voice_only_fallback=not agreement)
            else:
                assignment = 'ambiguous' if len(candidates)>1 else 'rejected' if valid else 'unavailable'
                reason = 'hybrid_unknown: '+(calibration['reason'] if not calibration['calibrated'] else
                    'existing_voice_delegate_rejected_or_insufficient_evidence')
        name = self.names.get(person) if person else None
        if not name:
            person = None
        label = name or 'Unknown'
        identity.update(known_profile_id=person, known_name=name, display_label=label,
            naming_state='confirmed' if person else 'unknown', name_is_displayed=bool(person),
            assignment=assignment, forced=assignment=='seat_assumed', verified=bool(person and not self.direction_only),
            valid_fresh_voice=valid, name_evidence_available_at_sec=now, reason=reason,
            seat=detail, closed_group_assumption=self.direction_only, personal_reference_update=False)
        result.update(known_profile_id=person, known_name=name, display_label=label,
            naming_state=identity['naming_state'], prototype_assignment=assignment,
            seat_identity_verified=identity['verified'], seat_track_domain=self.domain)
        result['name_revision'] = dict(track_id=result.get('tracker_id'), replacement_label=label,
            replacement_known_name=name, replacement_known_profile_id=person,
            replacement_naming_state=identity['naming_state'], reason=reason,
            evidence_id=event.get('event_id'), available_at_sec=event.get('available_at_sec'))
        with self.lock:
            if event.get('event_id'):
                self.assignments[event['event_id']] = dict(assignment=assignment, profile_id=person,
                    available_at_sec=now, source_start_sec=event.get('source_start_sec'),
                    source_end_sec=event.get('source_end_sec'), track_id=result.get('tracker_id'),
                    seat_revision=seat['revision'], seat_session_id=seat['session_id'], seat=deepcopy(detail))
                while len(self.assignments) > MAX_ASSIGNMENTS:
                    self.assignments.popitem(last=False)
            self.calls += 1
            elapsed = time.perf_counter()-began
            self.total_sec += elapsed
        result['identity_compute_sec'] = elapsed
        return result

    def annotate_caption(self, payload):
        """Mark source-linked seat assumptions; missing linkage never inherits a name."""
        row = deepcopy(payload)
        current = self.seats.snapshot()
        with self.lock:
            for part in [row, *row.get('segments', [])]:
                person = part.get('known_profile_id')
                if not person:
                    continue
                ids = list(part.get('evidence_ids') or [])
                ids.extend([part.get('identity_input_event_id'), part.get('identity_event_id')])
                evidence = [self.assignments[e] for e in ids if e in self.assignments and
                            self.assignments[e]['profile_id'] == person]
                latest = max(evidence, key=lambda item:item['available_at_sec']) if evidence else None
                # N2's late label revision uses n2-caption IDs. Its producer must
                # preserve the original embedding evidence ID in evidence_ids.
                if latest is None or (latest['assignment'] == 'seat_assumed' and
                    (not current['valid'] or latest['seat_revision'] != current['revision'] or
                     person in current.get('released', {}))):
                    part.update(known_profile_id=None, known_name=None, naming_state='invalidated',
                                prototype_assignment='unavailable', seat_identity_verified=False)
                else:
                    part.update(prototype_assignment=latest['assignment'], prototype_seat=deepcopy(latest['seat']),
                        seat_identity_verified=latest['assignment']=='accepted', seat_track_domain=self.domain)
        return row

    def snapshot(self):
        return dict(schema='just-peachy.backend-seat-resolver.v1', calls=self.calls,
            compute_sec=self.total_sec, track_domain=self.domain, direction_only=self.direction_only,
            retained_assignments=len(self.assignments), maximum_assignments=MAX_ASSIGNMENTS,
            calibration=calibration_receipt(self.gallery, self.embedding),
            voice_delegate=self.voice_map.snapshot() if self.voice_map is not None else None)


def make_resolver(selection, mode, *, legacy_factory, settings, gallery, seats,
                  names, provider, tracker_config, clock, voice_map=None):
    """Use original C088 unchanged for Pyannote/ReDim; explicit N2 adapter otherwise."""
    if mode not in SEAT_MODES:
        raise ValueError('Seat resolver adapter belongs only to an assigned-seat Mode')
    track_domain(selection.diarizer, selection.embedding)
    if selection.diarizer == 'pyannote' and selection.embedding == 'redimnet':
        return legacy_factory(settings, gallery, seats=seats, names=names, provider=provider,
            tracker_config=tracker_config, direction_only=mode=='assigned_direction', clock=clock)
    return BackendSeatResolver(voice_map, seats=seats, names=names, provider=provider,
        diarizer=selection.diarizer, embedding=selection.embedding,
        direction_only=mode=='assigned_direction', clock=clock)
