"""Pinned packed-route derivation and bounded raw evidence; README_RAW_CAPTURE.md."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
from pathlib import Path

RAW_FRAME_BYTES = 16
RAW_PACKET_BYTES = 65536


def admission(config, *, qualification_run=False):
    """Normal use needs passed evidence; qualification has its own explicit gate."""
    evidence = config.get('raw_qualification_evidence', {})
    if not isinstance(evidence, dict) or not evidence.get('evidence'):
        raise ValueError('Explicit raw admission/evidence receipt is required')
    if qualification_run:
        if config.get('raw_qualification') is not True or evidence.get('qualification_run') is not True or evidence.get('qualified') is not False:
            raise ValueError('Fresh experimental raw qualification admission required')
    elif config.get('raw_adapter_enabled') is not True or evidence.get('qualified') is not True or evidence.get('adapter_native_qualified') is not True:
        raise ValueError('Raw adapter is unavailable until native qualification passes')
    if not qualification_run:
        proof_path = Path(evidence['evidence'])
        if not proof_path.is_absolute() or proof_path.is_symlink() or any(parent.is_symlink() for parent in proof_path.parents) or not proof_path.is_file() or proof_path.stat().st_size > 1024*1024:
            raise ValueError('Immutable bounded raw qualification receipt required')
        proof_bytes = proof_path.read_bytes()
        if hashlib.sha256(proof_bytes).hexdigest() != evidence.get('evidence_sha256'):
            raise ValueError('Raw qualification receipt hash changed')
        proof = json.loads(proof_bytes)
        required = ('source_clock_checked', 'raw_readback_checked', 'processed_readback_checked', 'route_restored',
                    'stream_closed', 'lease_released', 'source_owner_closed')
        if proof.get('status') != 'RAW_NATIVE_QUALIFICATION_PASSED' or proof.get('native_executed') is not True or any(proof.get(key) is not True for key in required):
            raise ValueError('Actual successful raw native qualification checks required')
        if proof.get('raw_channels') != 4 or type(proof.get('raw_samples')) is not int or proof['raw_samples'] <= 0 or proof.get('processed_samples') != proof['raw_samples'] or proof.get('raw_bytes') != proof['raw_samples']*16 or proof.get('processed_bytes') != proof['processed_samples']*4:
            raise ValueError('Raw qualification frame/channel evidence differs')
        for filename, key in (('installed_source.py', 'installed_source_sha256'), ('raw_capture.py', 'raw_capture_sha256'),
                              ('source_batch.py', 'source_batch_sha256')):
            if hashlib.sha256(Path(__file__).with_name(filename).read_bytes()).hexdigest() != proof.get(key):
                raise ValueError('Raw qualification belongs to a different candidate module')
    return evidence


def storage_raw_spec(config, input_source):
    """Only an enabled, previously qualified live route changes normal storage."""
    if input_source != 'live' or config.get('raw_adapter_enabled') is not True:
        return None
    evidence = admission(config)
    return dict(sample_rate=16000, channels=4, sample_width_bytes=4,
                encoding='PCM_S32LE', qualification=dict(evidence),
                channel_order=['MIC0', 'MIC1', 'MIC2', 'MIC3'],
                transport_sample_rate=48000, transport_channels=2,
                packing='v28_s32le_six_slots_lsb_marker', shared_sample_clock=True)


def validate_block(start_sample, payload, accepted_samples, maximum_samples):
    if type(start_sample) is not int or start_sample != accepted_samples:
        raise ValueError('Raw source frame cursor is non-contiguous')
    if not payload or len(payload) > RAW_PACKET_BYTES or len(payload) % RAW_FRAME_BYTES:
        raise ValueError('Raw packet exceeds the 64 KiB bound or PCM32 frame alignment')
    end = accepted_samples + len(payload)//RAW_FRAME_BYTES
    if end > maximum_samples:
        raise ValueError('Raw source exceeds its allocated duration')
    return end


class RawSink:
    """Small adapter passed into the reviewed converter instead of disk files."""
    def __init__(self, maximum_samples, emit, proof, *, native_qualified=False):
        self.maximum_raw_samples = maximum_samples
        self.emit = emit
        self.proof = proof
        self.accepted_samples = 0
        self.stop_requested = False
        self.receipt = None
        self.stop_receipt = None
        self.native_qualified = native_qualified is True

    def write(self, start_sample, data):
        end = validate_block(start_sample, data, self.accepted_samples, self.maximum_raw_samples)
        ack = self.emit(start_sample, data)
        if ack.get('kind') != 'ACK_RAW' or ack.get('accepted_samples') != end:
            raise ValueError('Exact durable raw acknowledgement missing')
        self.stop_requested = self.stop_requested or ack.get('stop') is True
        self.accepted_samples = end

    def source(self, name, row):
        if name == 'ROUTE_STOP.json':
            self.stop_receipt = row
            return
        if name != 'RAW_CAPTURE.json' or self.receipt is not None:
            raise ValueError('One raw capture receipt per source required')
        self.receipt = dict(row, derivation=self.proof, adapter_native_qualified=self.native_qualified)


def _digest(node):
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def transport_accounting(source, maximum_samples):
    """After physical Stop, distinguish the chosen prefix from queued capture."""
    if not source._stopped or source._route_ready:
        raise ValueError('Packed transport accounting requires physical Stop')
    pending = source._write_seq - source._read_seq
    if not 0 <= pending <= source._capacity:
        raise ValueError('Packed pending ring extent is invalid')
    queued = sum(int(source._frames[index % source._capacity])
                 for index in range(source._read_seq, source._write_seq))
    consumed = source._packed_read_transport_frames
    suffix = source._packed_policy_suffix_transport_frames
    if (consumed != source._model_samples * 3 or consumed <= 0 or
            any(value < 0 or value % 3 for value in (queued, consumed, suffix)) or
            source._native_frames != consumed + suffix + queued or
            not 0 <= source._packed_tail_count < 3 or
            not 0 < source._model_samples <= maximum_samples or
            (suffix and source._model_samples != maximum_samples)):
        raise ValueError('Packed consumed/queued transport accounting differs')
    return dict(accepted_transport_frames=consumed,
        callback_complete_transport_frames=source._native_frames,
        unconverted_queued_transport_frames=queued, unconverted_queued_blocks=pending,
        final_read_suffix_transport_frames=suffix,
        unconverted_after_capture_boundary_transport_frames=queued + suffix,
        terminal_incomplete_transport_frames=source._packed_tail_count,
        capture_boundary_sample=source._model_samples,
        capture_boundary_reason='allocated_duration' if source._model_samples == maximum_samples else 'explicit_stop',
        transport_partition_checked=True)


def derive_factory(path, expected_sha256):
    """Keep route/callback/calibration exact; fence reads before raw publication."""
    path = Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError('Real pinned raw factory required')
    raw = path.read_bytes()
    if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Pinned v28 raw source factory changed')
    tree = ast.parse(raw)
    selected = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in ('raw_source_type', 'install_packed_route')}
    if len(selected) != 2:
        raise ValueError('Exact raw source and route definitions required')
    original = copy.deepcopy(selected['raw_source_type'])
    derived = copy.deepcopy(original)
    converter = next(node for node in derived.body if isinstance(node, ast.ClassDef) and node.name == 'PackedConverter')
    original_converter = next(node for node in original.body if isinstance(node, ast.ClassDef) and node.name == 'PackedConverter')
    methods = {node.name: node for node in converter.body if isinstance(node, ast.FunctionDef)}
    old_methods = {node.name: node for node in original_converter.body if isinstance(node, ast.FunctionDef)}
    bound_nodes = [node for node in ast.walk(methods['convert']) if isinstance(node, ast.Constant) and node.value == 2080000]
    if len(bound_nodes) != 1:
        raise ValueError('Exact retained fixed sample bound required')
    class DurationBound(ast.NodeTransformer):
        def visit_Constant(self, node):
            if node.value == 2080000:
                return ast.copy_location(ast.Attribute(ast.Name('routes', ast.Load()), 'maximum_raw_samples', ast.Load()), node)
            return node
    methods['convert'] = DurationBound().visit(methods['convert'])
    # Keep the retained read path, including its LiveBlock timing metadata.
    # Fence the packed input before conversion emits either raw or processed data.
    assignments = {node.targets[0].attr: node for node in derived.body
                   if isinstance(node, ast.Assign) and len(node.targets) == 1
                   and isinstance(node.targets[0], ast.Attribute)
                   and isinstance(node.targets[0].value, ast.Name)
                   and node.targets[0].value.id == 'RawSource'}
    if set(assignments) != {'_start_owned', 'read'}:
        raise ValueError('Exact retained source derivation boundaries required')
    start_replacements = assignments['_start_owned'].value.args[1]
    start_text = start_replacements.elts[-1].elts[1]
    if not isinstance(start_text, ast.Constant) or not start_text.value.endswith('self._packed_prefix=None'):
        raise ValueError('Exact retained packed converter initialization required')
    start_text.value += '\n        self._packed_read_transport_frames=0\n        self._packed_policy_suffix_transport_frames=0'
    read_call = assignments['read'].value
    if len(read_call.args) != 2 or len(read_call.args[1].elts) != 1:
        raise ValueError('Exact retained stereo read replacement required')
    replacements = [
        ('n = int(self._frames[slot])', '''n = int(self._frames[slot])
    remaining = routes.maximum_raw_samples - self._model_samples
    if remaining <= 0:
        return None
    bounded_n = min(n, remaining * 3)
    if bounded_n <= 0 or bounded_n % 3 or int(self._native_start[slot]) != self._packed_read_transport_frames:
        raise ValueError('Packed bounded read source extent differs')
    self._packed_policy_suffix_transport_frames += n - bounded_n
    n = bounded_n''', 1),
        ('self._model_samples += len(audio)', '''self._model_samples += len(audio)
    self._packed_read_transport_frames += n''', 1),
    ]
    read_call.args[1].elts.extend(ast.parse(repr(replacements), mode='eval').body.elts)
    read_call.args.append(ast.Dict(keys=[ast.Constant('routes')], values=[ast.Name('routes', ast.Load())]))
    flush = ast.parse('''def flush(self):
    if self.pending:
        raw = bytes(self.pending)
        routes.write(self.written // 16, raw)
        self.written += len(raw)
        self.pending.clear()
''').body[0]
    finish = ast.parse('''def finish(self):
    if self.finished:
        raise ValueError('Raw publication already attempted')
    self.finished = True
    self.flush()
    source = self.source
    if self.samples != source._model_samples or self.samples <= 0:
        raise ValueError('Raw/model source frame count differs')
    if self.written != self.samples * 16 or routes.accepted_samples != self.samples:
        raise ValueError('Raw parent durable extent differs')
    actual = self.digest.hexdigest()
''').body[0]
    # Preserve the original route/channel/calibration/source-clock metadata.
    row = copy.deepcopy(next(node for node in old_methods['finish'].body if isinstance(node, ast.Assign)
                             and any(isinstance(target, ast.Name) and target.id == 'row' for target in node.targets)))
    for keyword in row.value.keywords:
        if keyword.arg == 'file':
            keyword.value = ast.Constant('parent_session_raw_segments')
        elif keyword.arg == 'complete_source_readback':
            keyword.value = ast.Constant(False)
    row.value.keywords.append(ast.keyword('parent_durable_spool_ack', ast.Constant(True)))
    finish.body.append(row)
    finish.body.extend(ast.parse('row.update(transport_accounting(source, routes.maximum_raw_samples))').body)
    tail = old_methods['finish'].body[-3:]
    if not isinstance(tail[0], ast.If) or not isinstance(tail[1], ast.Expr) or not isinstance(tail[2], ast.Return):
        raise ValueError('Raw finish clock check/publication boundary changed')
    finish.body.extend(copy.deepcopy(tail))
    converter.body = [flush if isinstance(node, ast.FunctionDef) and node.name == 'flush' else
                      finish if isinstance(node, ast.FunctionDef) and node.name == 'finish' else node
                      for node in converter.body]
    # Restore only the enumerated permitted edits for an exact AST comparison.
    restored = copy.deepcopy(derived)
    restored_converter = next(node for node in restored.body if isinstance(node, ast.ClassDef) and node.name == 'PackedConverter')
    restored_converter.body = [copy.deepcopy(old_methods[node.name]) if isinstance(node, ast.FunctionDef)
                              and node.name in ('convert', 'flush', 'finish') else node for node in restored_converter.body]
    original_assignments = {node.targets[0].attr: node for node in original.body
                            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Attribute)}
    restored.body = [copy.deepcopy(original_assignments[node.targets[0].attr])
                     if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Attribute)
                     and node.targets[0].attr in original_assignments else node for node in restored.body]
    if _digest(restored) != _digest(original):
        raise ValueError('Raw source changed outside permitted sink/read-fence edits')
    original_route = selected['install_packed_route']
    proof = dict(factory_sha256=expected_sha256, route_ast_sha256=_digest(original_route),
                 retained_source_ast_sha256=_digest(original), unchanged_outside_sink_bounds_and_read_fence=True,
                 changed_methods=['PackedConverter.convert duration bound', 'PackedConverter.flush disk sink',
                                  'PackedConverter.finish readback and transport partition',
                                  'RawSource._start_owned accounting counters only',
                                  'RawSource.read exact final transport prefix and consumed counter'], native_execution=False)
    module = ast.fix_missing_locations(ast.Module(body=[derived, copy.deepcopy(original_route)], type_ignores=[]))
    namespace = {'transport_accounting': transport_accounting}
    exec(compile(module, str(path)+'<bounded-spool-derivative>', 'exec'), namespace)
    return namespace['raw_source_type'], namespace['install_packed_route'], proof


def derive_stop_base(config, live):
    """Extract the exact retained bounded Stop and actual Start override."""
    root = Path(config['raw_factory_path']).parent
    references = config.get('reference_files', {})
    def pinned(name):
        if isinstance(references, list):
            rows = [row for row in references if row['path'] in (name, 'code/'+name)]
            expected = rows[0]['sha256'] if len(rows) == 1 else None
        else:
            row = references.get(name, references.get('code/'+name))
            expected = row.get('sha256') if isinstance(row, dict) else row
        path = root/name
        if not expected or path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError('Exact retained Stop/receipt source pins required')
        raw = path.read_bytes()
        if len(raw) > 262144 or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('Retained Stop/receipt source pin changed')
        return ast.parse(raw), expected
    receipts, receipt_hash = pinned('field_source_receipt_routes_v1.py')
    receipt_class = next(node for node in receipts.body if isinstance(node, ast.ClassDef) and node.name == 'ReceiptFailure')
    stop, stop_hash = pinned('field_live_stop_overlay_v1.py')
    stop_function = next(node for node in stop.body if isinstance(node, ast.FunctionDef) and node.name == 'source_class')
    namespace = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(receipt_class), copy.deepcopy(stop_function)], type_ignores=[])), '<pinned-raw-stop>', 'exec'), namespace)
    bounded = namespace['source_class'](live)
    factory_bytes = Path(config['raw_factory_path']).read_bytes()
    if hashlib.sha256(factory_bytes).hexdigest() != config['raw_factory_sha256']:
        raise ValueError('Retained raw Start source pin changed')
    factory = ast.parse(factory_bytes)
    create = next(node for node in factory.body if isinstance(node, ast.FunctionDef) and node.name == 'create')
    actual = next(node for node in create.body if isinstance(node, ast.ClassDef) and node.name == 'ActualSource')
    namespace.update(BoundedStop=bounded, original_source=live.XVFLiveSource)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(actual)], type_ignores=[])), '<pinned-raw-actual-start>', 'exec'), namespace)
    return namespace['ActualSource'], dict(stop_overlay_sha256=stop_hash,
        receipt_error_sha256=receipt_hash, stop_ast_sha256=_digest(stop_function),
        actual_start_ast_sha256=_digest(actual))
