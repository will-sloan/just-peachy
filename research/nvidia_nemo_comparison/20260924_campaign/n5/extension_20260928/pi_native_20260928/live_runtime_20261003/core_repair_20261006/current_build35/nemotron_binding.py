"""New native factory, reusing pinned assets. See README_PIPELINES.md.

The source-derived adapter checks are not evidence that a Pi model run passed.
The caller verifies the complete deployment manifest and enforces process limits.
"""
from __future__ import annotations

import ctypes
from dataclasses import asdict
import hashlib
import math
import os
from pathlib import Path
import threading
import time

try:
    from .profiles import Geometry, RuntimeSelection, SessionPolicy, catalog, get_profile, validate_geometry
except ImportError:
    from profiles import Geometry, RuntimeSelection, SessionPolicy, catalog, get_profile, validate_geometry

ADAPTER_SHA256 = "2537162df8ac8ccdd89c45c3f26fa12ef48519867a0474bf4be39e4667d75e37"
WRAPPER_SHA256 = "9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f"
CORE_SHA256 = {
    "delayed": "7db8afef2e37b28c0f9d56690b4c0d5fcd8c85a50fa6034f8e6fb53674ceb45a",
    "streaming": "fa8ecbb66124b62fced485d45dd2ec6018634a35d39dbc143e221b9f7230b622",
}
FIELDS = ("chunk_frames", "right_context_frames", "left_context_frames", "fifo_frames",
          "spkcache_frames", "update_period_frames")


def expected_frames(samples, maximum_samples):
    if type(samples) is not int or not 0 <= samples <= maximum_samples:
        raise ValueError("Source sample count exceeds this session policy")
    return 0 if samples == 0 else samples // 160 + 1


def workspace_allocation_bytes(old_bytes, retained_rows, new_rows, resize):
    """Account the live old buffer and pending full ABI/output/mask allocations."""
    if (any(type(value) is not int or value < 0 for value in (old_bytes, retained_rows, new_rows))
            or type(resize) is not bool or new_rows > retained_rows):
        raise ValueError("Exact observed workspace sizes required")
    workspace_bytes = retained_rows * 8 * 4 if resize else 0
    output_bytes = new_rows * 8 * 4
    mask_bytes = new_rows * 8 * 2
    return dict(old_workspace_bytes=old_bytes, new_workspace_bytes=workspace_bytes,
                output_bytes=output_bytes, mask_bytes=mask_bytes,
                additional_bytes=workspace_bytes + output_bytes + mask_bytes,
                pending_array_bytes=old_bytes + workspace_bytes + output_bytes + mask_bytes)


def workspace_memory_guard(reservation):
    """Preserve the actual AS ceiling and physical 192 MiB floor before allocation."""
    from runtime_support import resource_snapshot
    measured = resource_snapshot()
    if type(reservation) is not int or reservation < 0:
        raise ValueError("Exact pending allocation bytes required")
    available = measured.get("available_ram")
    if type(available) is not int or available < 192*1024**2 + reservation:
        raise MemoryError("Native probability allocation cannot preserve the 192 MiB RAM floor")
    if os.name != "nt":
        import resource
        # resource_snapshot caches detailed VmSize; allocation admission needs
        # the current address space, which already includes the old workspace.
        fields = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines()
                      if ":" in line)
        current = int(fields["VmSize"].split()[0])*1024
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        limits = [value for value in (soft, hard) if value != resource.RLIM_INFINITY]
        maximum = min(limits) if limits else None
        if maximum is not None and current + reservation > maximum:
            raise MemoryError("Native probability allocation exceeds the effective address-space budget")
        measured.update(virtual_bytes=current, address_space_soft=soft, address_space_hard=hard)
    return measured


def copy_new_probabilities(np, api, stream, workspace, *, first, maximum_frames, check,
                           memory_guard=workspace_memory_guard):
    """Copy the full retained ABI output into an observed-size reusable workspace."""
    count = int(api.nemo_speech_diar_frame_count(stream))
    base = int(api.nemo_speech_diar_frame_probs_start(stream))
    if not 0 <= base <= first <= count <= maximum_frames:
        raise RuntimeError("Native timeline regressed, skipped undelivered rows, or exceeded reservation")
    if (workspace.ndim != 2 or workspace.shape[1] != 8 or workspace.shape[0] > maximum_frames
            or workspace.dtype != np.float32 or not workspace.flags.c_contiguous):
        raise ValueError("Contiguous bounded float32 workspace required")
    if count == first:
        values = np.empty((0, 8), dtype=np.float32)
    else:
        rows = count - base
        resize = rows > workspace.shape[0]
        allocation = workspace_allocation_bytes(int(workspace.nbytes), rows, count-first, resize)
        memory_guard(allocation["additional_bytes"])
        if resize:
            # The old allocation remains live until empty() succeeds. Admission
            # accounts that old address space plus the entire pending allocation.
            workspace = np.empty((rows, 8), dtype=np.float32)
        retained = workspace[:rows]
        check(api.nemo_speech_diar_frame_probs(
            stream, retained.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), retained.size))
        # The C ABI still copies the full retained timeline. Only allocation is
        # reused; an immutable copy protects emitted rows from the next update.
        values = retained[first - base:count - base].copy()
        if not np.all(np.isfinite(values)) or np.any(values < 0) or np.any(values > 1):
            raise RuntimeError("Native probability values outside finite [0,1]")
    values.setflags(write=False)
    return count, base, values, workspace


def bind(native, selection, policy, runtime_document, timing_callback=None, *, verified_variant=None):
    """Return a single-session subclass factory for the exact installed adapter.

    runtime_document retains nemotron_model, nemotron_library,
    nemotron_library_sha256, native_runtime_files and CPU native_device. Its
    streaming_profile must be the selected Profile.native_name. Relative paths
    must already be resolved by the caller against the retained campaign root.
    """
    if not isinstance(selection, RuntimeSelection) or not isinstance(policy, SessionPolicy):
        raise ValueError("Validated independent selection and session policy required")
    selection.validate(); policy.validate()
    if selection.diarizer != "nemotron":
        raise ValueError("Nemotron factory requires Nemotron selection")
    if timing_callback is not None and not callable(timing_callback):
        raise ValueError("Timing callback must be callable")
    profile = get_profile(selection.nemotron_profile)
    validate_geometry(profile.geometry)
    document = dict(runtime_document)
    if document.get("native_device") != {"kind": "cpu", "gpu_index": -1}:
        raise ValueError("Explicit retained CPU device required")
    if document.get("streaming_profile") != profile.native_name:
        raise ValueError("Runtime document must name the selected native profile")
    model_path = Path(document["nemotron_model"])
    library_path = Path(document["nemotron_library"])
    if not model_path.is_absolute() or not library_path.is_absolute():
        raise ValueError("Caller must resolve retained asset paths before binding")
    model_path, library_path = model_path.resolve(), library_path.resolve()
    if document.get("nemotron_library_sha256") != WRAPPER_SHA256:
        raise ValueError("Retained C ABI wrapper pin changed")
    rows = document.get("native_runtime_files")
    if type(rows) is not list or not 1 <= len(rows) <= 32:
        raise ValueError("Bounded complete retained native runtime file pins required")
    core = [r for r in rows if Path(r["path"]).name == "libnemo_speech_asr.so"]
    asset_mode = "delayed" if profile.id == "current_delayed" else "streaming"
    expected_core = CORE_SHA256[asset_mode]
    variant_receipt = None
    if verified_variant is not None:
        try:
            from .native_variant import verified_core_pin
        except ImportError:
            from native_variant import verified_core_pin
        expected_core = verified_core_pin(verified_variant, selection, document)
        variant_receipt = verified_variant.receipt()
    elif "native_variant" in document or profile.id == "chunk52_threads2":
        raise ValueError("Explicit pinned native variant admission required")
    if len(core) != 1 or core[0]["sha256"] != expected_core:
        raise ValueError("Select retained delayed LRU1 or streaming/Chunk52 LRU8 core")
    if Path(core[0]["path"]).resolve().parent != library_path.parent:
        raise ValueError("Core and wrapper must share the selected retained library directory")
    adapter_path = Path(native.__file__)
    if adapter_path.stat().st_size > 65536 or hashlib.sha256(adapter_path.read_bytes()).hexdigest() != ADAPTER_SHA256:
        raise ValueError("Exact retained installed adapter source required")
    if native.MODEL_SHA256 != "08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1":
        raise ValueError("Exact existing model pin required")
    for item in catalog():
        candidate = get_profile(item["id"])
        fields = {key: getattr(candidate.geometry, key) for key in FIELDS}
        descriptor = native.StreamingProfile(candidate.native_name, **fields)
        old = native.PROFILES.get(candidate.native_name)
        if old is not None and asdict(old) != asdict(descriptor):
            raise ValueError("Existing native descriptor cannot be overwritten")
        native.PROFILES[candidate.native_name] = descriptor
    maximum_samples = policy.maximum_samples()
    maximum_frames = expected_frames(maximum_samples, maximum_samples)
    lock = threading.Lock()
    attempted = False
    Base = native.NemotronDiarizer

    class BoundNemotronDiarizer(Base):
        def __init__(self, model, library, *, profile=profile.native_name, session_id=None,
                     expected_library_sha256=None, gpu=-1):
            nonlocal attempted
            with lock:
                if attempted:
                    raise RuntimeError("New independent session requires a fresh process/factory")
                attempted = True
            if (Path(model).resolve() != model_path or Path(library).resolve() != library_path or
                    profile != selected_profile.native_name or type(gpu) is not int or gpu != -1 or
                    expected_library_sha256 != WRAPPER_SHA256 or
                    type(session_id) is not str or not 0 < len(session_id) <= 128):
                raise ValueError("Constructor differs from selected pinned runtime document")
            self._live_reset_attempted = False
            self._live_update_count = 0
            self._live_timing_callback_errors = 0
            self._live_workspace = native.np.empty((0, 8), dtype=native.np.float32)
            self.observed_c_abi = None
            self.loaded_variant_libraries = None
            if verified_variant is not None:
                from native_variant import require_fresh_variant_loader
                require_fresh_variant_loader()
            try:
                super().__init__(model, library, profile=profile, session_id=session_id,
                                 expected_library_sha256=expected_library_sha256, gpu=gpu)
                if verified_variant is not None:
                    from native_variant import verify_loaded_variant_libraries
                    self.loaded_variant_libraries = verify_loaded_variant_libraries(document)
            except BaseException:
                if hasattr(self, "_lock"):
                    self.close()
                self._live_workspace = None
                raise

        def _bind(self):
            if verified_variant is not None:
                from native_variant import verify_loaded_variant_libraries
                self.loaded_variant_libraries = verify_loaded_variant_libraries(document, require_cpu=False)
            super()._bind()
            create = self._api.nemo_speech_diar_create

            def checked_create(pointer, result):
                config = ctypes.cast(pointer, ctypes.POINTER(native._ModelConfig)).contents
                # Set the explicit preset on the actual C struct, before checking
                # all submitted values. Zero FIFO is meaningful only offline.
                config.preset = selected_profile.geometry.preset.encode("ascii")
                observed = {key: int(getattr(config, key)) for key in FIELDS}
                observed.update(preset=config.preset.decode("ascii"), gpu=int(config.gpu))
                if observed != asdict(selected_profile.geometry):
                    raise ValueError("Actual C ABI geometry differs from selected profile")
                validate_geometry(Geometry(**observed))
                if Path(os.fsdecode(config.model_path)).resolve() != model_path:
                    raise ValueError("Actual C ABI model path changed")
                self.observed_c_abi = observed
                return create(pointer, result)
            self._api.nemo_speech_diar_create = checked_create

        def reset(self, *, session_id=None):
            if self._live_reset_attempted:
                raise RuntimeError("Persistent diarizer cannot reset within a recording")
            self._live_reset_attempted = True
            return super().reset(session_id=session_id)

        def _update(self, received_at, started, final):
            first = int(self._frames_delivered)
            try:
                count, base, values, self._live_workspace = copy_new_probabilities(native.np, self._api, self._stream,
                    self._live_workspace, first=first,
                    maximum_frames=min(maximum_frames, expected_frames(int(self._samples_received), maximum_samples)),
                    check=self._check)
                if count > expected_frames(int(self._samples_received), maximum_samples):
                    raise RuntimeError("Native output extends beyond actual audio endpoint")
                if final and count != expected_frames(int(self._samples_received), maximum_samples):
                    raise RuntimeError("Final output disagrees with retained source endpoint rule")
                if not math.isclose(self.seconds_per_frame, .01, abs_tol=1e-6):
                    raise RuntimeError("Native output sample clock changed")
                self._frames_delivered = count
                completed = time.perf_counter()
                update = native.DiarizationUpdate(self.session_id, first, values, self.seconds_per_frame,
                    self._samples_received / self.sample_rate, received_at, completed, completed - started,
                    final, self.track_ids)
                self._live_update_count += 1
                if timing_callback:
                    try:
                        timing_callback(dict(kind="finish" if final else "push", frame_start=first,
                            frame_end=count, native_retained_start=base, sample_end=int(self._samples_received),
                            compute_seconds=completed - started, available_at=completed,
                            received_at=received_at, workspace_bytes=self._live_workspace.nbytes))
                    except Exception:
                        self._live_timing_callback_errors += 1
                return update
            except BaseException:
                self._failed = True
                raise

        def push(self, samples, *, received_at_monotonic=None):
            with self._lock:
                if self._samples_received + len(samples) > maximum_samples:
                    raise ValueError("Session policy audio sample ceiling reached")
                return super().push(samples, received_at_monotonic=received_at_monotonic)

        def close(self):
            super().close()
            self._live_workspace = None

        def manifest(self):
            result = super().manifest()
            result["live_runtime_20261003"] = dict(profile=selected_profile.descriptor(),
                session_policy=asdict(policy), maximum_frames=maximum_frames,
                workspace_bytes=0 if self._live_workspace is None else int(self._live_workspace.nbytes),
                workspace_policy="observed_native_retained_rows", range_api_used=False,
                full_retained_copy_required=True, observed_c_abi=self.observed_c_abi,
                timing_callback_errors=self._live_timing_callback_errors,
                verified_native_variant=variant_receipt,
                loaded_variant_libraries=self.loaded_variant_libraries,
                native_qualification_claimed=False, measured_speedup_claimed=False)
            return result

    selected_profile = profile
    return BoundNemotronDiarizer
