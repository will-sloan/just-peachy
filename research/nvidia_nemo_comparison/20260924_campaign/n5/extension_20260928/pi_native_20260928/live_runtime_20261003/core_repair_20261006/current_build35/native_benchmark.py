"""Explicit saved-input native component benchmark. See README_NATIVE_BENCHMARK.md."""
from __future__ import annotations

# No project, array or model imports before CLI bootstrap records the owner.
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import time
import wave

RATE = 16000
PART_BYTES = 16 * 1024**2
CALL_BYTES = 8192  # Includes bounded task affinities and resource observations.


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def pin(value):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        raise ValueError("Explicit lowercase SHA256 required")
    return value


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def publish(path, value):
    raw = canonical(value) + b"\n"
    if len(raw) > 262144:
        raise ValueError("Bounded benchmark receipt required")
    with Path(path).open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def bootstrap(output, execute_native, unit=None):
    """Record a real process identity before reading project or input data."""
    if execute_native:
        if platform.system() != "Linux" or platform.machine() != "aarch64":
            raise RuntimeError("Native benchmark requires the CM5; host execution is plan-only")
        import resource
        os.sched_setaffinity(0, {2, 3})
        for kind, cap in ((resource.RLIMIT_AS, 768*1024**2), (resource.RLIMIT_STACK, 1024**2),
                          (resource.RLIMIT_FSIZE, 32*1024**2), (resource.RLIMIT_CORE, 0)):
            resource.setrlimit(kind, (cap, cap))
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            if os.environ.get(key) != "1":
                raise RuntimeError("All four model thread environment values must already equal 1")
        owner = dict(pid=os.getpid(), start_ticks=int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
                     boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(), affinity=[2, 3])
    else:
        import psutil
        me = psutil.Process()
        me.cpu_affinity([14])
        owner = dict(pid=me.pid, create_time=me.create_time(), affinity=me.cpu_affinity())
    output = Path(output).absolute()
    for parent in (output, *output.parents):
        if parent.is_symlink():
            raise ValueError("Fresh real private output directory required")
    output.mkdir(parents=False, exist_ok=False)
    publish(output / "REGISTERED_OWNER.json", owner)
    sys.dont_write_bytecode = True
    if execute_native:
        if type(unit) is not str or not re.fullmatch(r"[A-Za-z0-9_.@-]+\.(service|scope)", unit):
            raise ValueError("Explicit current benchmark service/scope required")
        import subprocess
        properties = subprocess.run(["systemctl", "--user", "show", unit,
            "--property=ActiveState,AllowedCPUs,CPUQuotaPerSecUSec,TasksMax"],
            capture_output=True, text=True, timeout=5, check=True).stdout
        props = dict(line.split("=", 1) for line in properties.splitlines() if "=" in line)
        if (props.get("ActiveState") != "active" or props.get("AllowedCPUs") not in ("2-3", "2,3") or
                props.get("CPUQuotaPerSecUSec") != "2s" or props.get("TasksMax") != "64"):
            raise RuntimeError("Current unit must enforce CPU2/3, aggregate 200% CPU and 64 tasks")
        if not any(line.rstrip().endswith("/" + unit) for line in Path("/proc/self/cgroup").read_text().splitlines()):
            raise RuntimeError("Benchmark process is not in the supplied resource unit")
        publish(output / "ENVELOPE.json", dict(owner=owner, unit=unit, properties=props,
                                             thread_environment=1, native_graph_threads="unverified",
                                             thread_environment_variables={key: os.environ[key] for key in
                                                 ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
                                             gpu=False, maximum_as_bytes=768*1024**2))
    return owner


def inspect_wav(path, expected_sha256):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4*1024**3:
        raise ValueError("Existing bounded real WAV required")
    before = path.stat()
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError("Matched input must be mono PCM16 16 kHz WAV; no implicit conversion")
        frames = stream.getnframes()
    if frames < 1:
        raise ValueError("Nonempty matched input required")
    actual = digest(path)
    after = path.stat()
    identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if identity(before) != identity(after) or actual != pin(expected_sha256):
        raise ValueError("Matched WAV bytes or identity changed")
    return dict(path=str(path), sha256=actual, source_samples=frames, sample_rate=RATE,
                channels=1, sample_width=2, bytes=before.st_size, identity=list(identity(before)))


def make_plan(info, selection, policy, *, repeat_seconds=None, wall_paced=False, block_samples=1600):
    selection.validate(); policy.validate()
    if selection.diarizer != "nemotron" or selection.input_source != "saved" or selection.provisional_correction:
        raise ValueError("This benchmark is one saved-input Nemotron component; no dual worker")
    if type(wall_paced) is not bool or type(block_samples) is not int or not 160 <= block_samples <= 16000:
        raise ValueError("Explicit pacing flag and 10 ms..1 s input blocks required")
    if repeat_seconds is None:
        target = info["source_samples"]
        repeated = False
    else:
        if type(repeat_seconds) is not int or repeat_seconds < 3600 or not policy.developer_soak:
            raise ValueError("Repeated continuous replay requires explicit >=3600-second developer soak")
        target = repeat_seconds * RATE
        repeated = True
    if not 0 < target <= policy.maximum_samples():
        raise ValueError("Exact input duration exceeds explicit policy; no silent truncation")
    maximum_frames = target // 160 + 1
    maximum_calls = math.ceil(target / block_samples) + 1
    return dict(schema="just-peachy.native-saved-benchmark-plan.v1", input=info,
        selection=selection.validate(), policy=policy.validate(), target_samples=target,
        target_audio_seconds=target/RATE, repeated_input=repeated,
        completed_input_repetitions=target // info["source_samples"],
        final_repetition_samples=target % info["source_samples"], reset_between_repetitions=False,
        wall_paced=wall_paced, block_samples=block_samples, maximum_frames=maximum_frames,
        probability_dtype="little-endian-float32", probability_columns=8,
        maximum_probability_bytes=maximum_frames * 8 * 4,
        maximum_calls=maximum_calls, maximum_timing_bytes=maximum_calls * CALL_BYTES,
        maximum_output_bytes=maximum_frames * 8 * 4 + maximum_calls * CALL_BYTES + 2*1024**2,
        total_deadline_seconds=policy.total_deadline_seconds,
        quality_evaluated=False, realtime_qualification_claimed=False)


def pcm_blocks(path, target_samples, block_samples, *, repeat):
    """Read at most one block; concatenate loop boundaries without audio resets."""
    with wave.open(str(path), "rb") as stream:
        source_samples = stream.getnframes()
        sent = 0
        source_position = 0
        while sent < target_samples:
            count = min(block_samples, target_samples - sent)
            raw = bytearray()
            while len(raw) < count * 2:
                if source_position == source_samples:
                    if not repeat:
                        raise ValueError("Unexpected request beyond matched input EOF")
                    stream.rewind()
                    source_position = 0
                wanted = min(count - len(raw)//2, source_samples - source_position)
                block = stream.readframes(wanted)
                if len(block) != wanted * 2:
                    raise ValueError("Truncated WAV data before declared EOF")
                raw.extend(block)
                source_position += wanted
            yield sent, bytes(raw), dict(source_sample_start=sent % source_samples,
                repetition_start=sent // source_samples,
                repetition_end=(sent + count - 1) // source_samples)
            sent += count


class SegmentedOutput:
    """Append-only bounded private output, fixed-size parts and streaming hashes."""
    def __init__(self, output, stem, maximum_bytes, *, part_bytes=PART_BYTES):
        self.output, self.stem, self.maximum = Path(output), stem, maximum_bytes
        self.part_bytes = part_bytes
        self.total = 0
        self.part = self.stream = None
        self.parts = []
        self.total_hash = hashlib.sha256()

    def write(self, raw):
        if type(raw) is not bytes or self.total + len(raw) > self.maximum:
            raise ValueError("Reserved benchmark output bytes exceeded")
        position = 0
        while position < len(raw):
            if self.stream is None:
                name = f"{self.stem}-{len(self.parts)+1:04d}.bin"
                self.stream = (self.output / name).open("xb")
                self.part = dict(path=name, bytes=0, hash=hashlib.sha256())
            count = min(self.part_bytes - self.part["bytes"], len(raw) - position)
            block = raw[position:position+count]
            if self.stream.write(block) != len(block):
                raise IOError("Short benchmark output write")
            self.part["hash"].update(block); self.total_hash.update(block)
            self.part["bytes"] += count; self.total += count; position += count
            if self.part["bytes"] == self.part_bytes:
                self._close_part()

    def _close_part(self):
        if self.stream is not None:
            self.stream.flush(); os.fsync(self.stream.fileno()); self.stream.close()
            self.parts.append(dict(path=self.part["path"], bytes=self.part["bytes"], sha256=self.part["hash"].hexdigest()))
            self.stream = self.part = None

    def close(self):
        self._close_part()
        return dict(bytes=self.total, sha256=self.total_hash.hexdigest(), parts=self.parts)


_PSS_CACHE = dict(pid=None, sampled_at=-math.inf, pss_bytes=None)
_TASK_CACHE = dict(pid=None, sampled_at=-math.inf, task_count=None, task_affinities=None, truncated=False)


def resource_sample():
    """Actual process/procfs/sysfs measurements; missing fields remain None."""
    result = dict(rss_bytes=None, peak_rss_bytes=None, cpu_seconds=time.process_time(),
                  virtual_bytes=None, peak_virtual_bytes=None, swap_bytes=None,
                  pss_bytes=None, pss_sample_age_seconds=None, pss_sampled_monotonic_sec=None,
                  task_count=None, task_affinities=None, task_sample_age_seconds=None,
                  task_sample_truncated=False, native_graph_threads="unverified",
                  memory_scope="benchmark_process", available_ram_bytes=None,
                  temperatures_celsius={})
    if platform.system() == "Linux":
        import resource
        result["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        try:
            result["rss_bytes"] = int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            memory = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
            result["available_ram_bytes"] = int(memory["MemAvailable"].split()[0]) * 1024
        except (OSError, ValueError, KeyError, IndexError):
            pass
        try:
            status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
            for output, native_key in (("virtual_bytes", "VmSize"), ("peak_virtual_bytes", "VmPeak"), ("swap_bytes", "VmSwap")):
                if native_key in status:
                    result[output] = int(status[native_key].split()[0])*1024
        except (OSError, ValueError, IndexError):
            pass
        sampled_now = time.perf_counter()
        if _PSS_CACHE["pid"] != os.getpid() or sampled_now-_PSS_CACHE["sampled_at"] >= 1.:
            _PSS_CACHE.update(pid=os.getpid(), sampled_at=sampled_now, pss_bytes=None)
            try:
                rollup = dict(line.split(":", 1) for line in Path("/proc/self/smaps_rollup").read_text().splitlines() if ":" in line)
                _PSS_CACHE["pss_bytes"] = int(rollup["Pss"].split()[0])*1024
            except (OSError, ValueError, KeyError, IndexError):
                pass
        result.update(pss_bytes=_PSS_CACHE["pss_bytes"],
                      pss_sample_age_seconds=max(0., sampled_now-_PSS_CACHE["sampled_at"]),
                      pss_sampled_monotonic_sec=_PSS_CACHE["sampled_at"])
        if _TASK_CACHE["pid"] != os.getpid() or sampled_now-_TASK_CACHE["sampled_at"] >= 1.:
            from itertools import islice
            _TASK_CACHE.update(pid=os.getpid(), sampled_at=sampled_now,
                               task_count=None, task_affinities=None, truncated=False)
            try:
                tids = sorted(int(path.name) for path in islice(Path("/proc/self/task").glob("[0-9]*"), 65))
                if tids:
                    affinities = []
                    for tid in tids[:64]:
                        try:
                            affinities.append(dict(tid=tid, cpus=sorted(os.sched_getaffinity(tid))))
                        except (OSError, AttributeError):
                            affinities.append(dict(tid=tid, cpus=None))
                    _TASK_CACHE.update(task_count=len(tids), task_affinities=affinities, truncated=len(tids)>64)
            except (OSError, ValueError):
                pass
        result.update(task_count=_TASK_CACHE["task_count"], task_affinities=_TASK_CACHE["task_affinities"],
                      task_sample_age_seconds=max(0., sampled_now-_TASK_CACHE["sampled_at"]),
                      task_sample_truncated=_TASK_CACHE["truncated"])
        for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))[:16]:
            try:
                result["temperatures_celsius"][path.parent.name] = float(path.read_text().strip()) / 1000
            except (OSError, ValueError):
                pass
    return result


def run_stream(plan, factory, np, output, *, native_execution, guard=lambda: None,
               monotonic=time.perf_counter, process_time=time.process_time, measure=resource_sample):
    """Dependency-injected loop; host tests supply a fake model, never native code."""
    from telemetry import RollingTelemetry
    output = Path(output)
    probabilities = SegmentedOutput(output, "probabilities-f32le", plan["maximum_probability_bytes"])
    timings = SegmentedOutput(output, "calls-jsonl", plan["maximum_timing_bytes"])
    rolling = RollingTelemetry(backlog_limit_seconds=plan["policy"]["max_backlog_seconds"])
    model = None
    sent = frames = calls = 0
    initialized = False
    failure = None
    variant_receipt = getattr(factory, "native_variant_receipt", None)
    pcm_hash = hashlib.sha256()
    init_start, init_cpu = monotonic(), process_time()
    source_origin = None
    total_push_seconds = total_finish_seconds = 0.0
    first_output_seconds = None
    source_completed = None
    previous_cpu, previous_wall = process_time(), monotonic()

    def accept(update, kind, before, before_cpu, provenance):
        nonlocal frames, calls, first_output_seconds, previous_cpu, previous_wall
        after, cpu = monotonic(), process_time()
        values = update.probabilities
        expected = 0 if sent == 0 else sent // 160 + 1
        if (update.frame_start != frames or values.ndim != 2 or values.shape[1] != 8 or
                update.frame_end > expected or update.frame_end > plan["maximum_frames"] or
                not math.isclose(update.seconds_per_frame, .01, abs_tol=1e-6) or
                abs(update.audio_received_sec - sent / RATE) > 1e-9 or
                update.is_final is not (kind == "finish") or
                not np.all(np.isfinite(values)) or np.any(values < 0) or np.any(values > 1)):
            raise RuntimeError("Benchmark frame/sample/probability clock contract failed")
        if update.frame_end != frames + len(values):
            raise RuntimeError("Native returned an inconsistent output interval")
        probabilities.write(np.asarray(values, dtype="<f4").tobytes(order="C"))
        frames = update.frame_end
        if len(values) and first_output_seconds is None:
            first_output_seconds = after - source_origin
        available = min(plan["target_samples"], int(max(0., after-source_origin)*RATE)) if plan["wall_paced"] else sent
        input_backlog = max(0, available-sent) / RATE
        speaker_backlog = max(0, available-min(plan["target_samples"], frames*160)) / RATE
        audio = provenance.get("input_samples", 0) / RATE
        if kind == "push":
            rolling.observe(now=after, audio_seconds=audio, compute_seconds=after-before,
                            backlog_seconds=input_backlog)
        resource = measure()
        cpu_percent = (cpu-previous_cpu) / (after-previous_wall) * 100 if after > previous_wall else None
        previous_cpu, previous_wall = cpu, after
        row = dict(kind=kind, call_index=calls, source_samples=sent,
            frame_start=update.frame_start, frame_end=frames,
            wall_seconds=after-before, process_cpu_seconds=cpu-before_cpu,
            adapter_compute_seconds=update.compute_sec, source_elapsed_seconds=after-source_origin,
            input_backlog_seconds=input_backlog, speaker_backlog_seconds=speaker_backlog,
            rolling_push_rtf=rolling.snapshot(after), resources=resource,
            process_cpu_percent_since_previous_call=cpu_percent, **provenance)
        raw = canonical(row) + b"\n"
        if len(raw) > CALL_BYTES or calls >= plan["maximum_calls"]:
            raise ValueError("Timing row/call reservation exceeded")
        timings.write(raw); calls += 1
        if input_backlog >= plan["policy"]["max_backlog_seconds"]:
            raise RuntimeError("FAILED_BACKLOG_LIMIT: processed prefix retained")
        guard()
        return after-before

    try:
        guard()
        model = factory()
        initialized = True
        init_elapsed = monotonic()-init_start
        publish(output / "MODEL_INIT.json", dict(wall_seconds=init_elapsed,
            process_cpu_seconds=process_time()-init_cpu, resources=measure(), includes_adapter_asset_verification=True,
            native_variant=variant_receipt))
        if init_elapsed > plan["policy"]["model_load_seconds"]:
            raise TimeoutError("Native model initialization deadline exceeded")
        source_origin = monotonic()
        for first, raw, provenance in pcm_blocks(plan["input"]["path"], plan["target_samples"],
                                                  plan["block_samples"], repeat=plan["repeated_input"]):
            count = len(raw)//2
            if first != sent:
                raise RuntimeError("Source sample clock discontinuity")
            if plan["wall_paced"]:
                due = source_origin + (sent+count)/RATE
                while monotonic() < due:
                    guard(); time.sleep(min(.05, max(0., due-monotonic())))
            guard()
            audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.
            before, before_cpu = monotonic(), process_time()
            update = model.push(audio, received_at_monotonic=before)
            sent += count
            pcm_hash.update(raw)
            total_push_seconds += monotonic()-before
            accept(update, "push", before, before_cpu,
                   dict(provenance, input_samples=count, source_sample_start_absolute=first))
            if plan["wall_paced"] and monotonic()-source_origin-plan["target_audio_seconds"] > plan["policy"]["max_drain_seconds"]:
                raise TimeoutError("Wall-paced source backlog exceeded processing drain deadline")
        before, before_cpu = monotonic(), process_time()
        update = model.finish()
        total_finish_seconds = monotonic()-before
        accept(update, "finish", before, before_cpu, dict(input_samples=0))
        source_completed = monotonic()
        if total_finish_seconds > plan["policy"]["max_drain_seconds"]:
            raise TimeoutError("Final native flush exceeded processing drain deadline")
        if sent != plan["target_samples"] or frames != plan["maximum_frames"]:
            raise RuntimeError("Exact final input/EOF frame contract failed")
        if digest(plan["input"]["path"]) != plan["input"]["sha256"]:
            raise RuntimeError("Matched input changed during benchmark")
        after_input = Path(plan["input"]["path"]).stat()
        if [after_input.st_dev, after_input.st_ino, after_input.st_size, after_input.st_mtime_ns] != plan["input"]["identity"]:
            raise RuntimeError("Matched input file identity changed during benchmark")
    except BaseException as exc:
        failure = type(exc).__name__ + ": " + str(exc)[:2048]
    finally:
        closure = dict(attempted=model is not None, model_closed=False, pointers_empty=False)
        if model is not None:
            try:
                model.close()
                closure.update(model_closed=bool(getattr(model, "_closed", False)),
                               pointers_empty=not getattr(model, "_stream", None) and not getattr(model, "_model", None))
                if not closure["model_closed"] or not closure["pointers_empty"]:
                    raise RuntimeError("Model closure/pointer ownership is incomplete")
            except BaseException as exc:
                failure = (failure + "; " if failure else "") + "close: " + str(exc)[:1024]
        probability_receipt, timing_receipt = probabilities.close(), timings.close()
        result = dict(status="MEASURED_COMPONENT_COMPLETED" if failure is None else "FAILED_PREFIX_PRESERVED",
            failure=failure, native_execution=native_execution, initialized=initialized,
            input_sha256=plan["input"]["sha256"], delivered_pcm_sha256=pcm_hash.hexdigest(),
            target_samples=plan["target_samples"], delivered_samples=sent, output_frames=frames,
            expected_final_frames=plan["maximum_frames"], complete_eof=failure is None,
            repeated_input=plan["repeated_input"], reset_between_repetitions=False,
            wall_paced=plan["wall_paced"], model_init_wall_seconds=monotonic()-init_start if not initialized else init_elapsed,
            push_wall_seconds=total_push_seconds, finish_wall_seconds=total_finish_seconds,
            component_rtf=(total_push_seconds+total_finish_seconds)/(sent/RATE) if sent else None,
            first_output_wall_seconds=first_output_seconds,
            source_phase_wall_seconds=(source_completed or monotonic())-source_origin if source_origin is not None else None,
            probabilities=probability_receipt, timings=timing_receipt, closure=closure,
            resources_final=measure(), quality_evaluated=False, sustained_realtime_qualified=False,
            synthetic_host_contract=not native_execution)
        result["native_variant"] = variant_receipt
        publish(output / "RESULT.json", result)
    return result


def load_factory(binding_path, binding_sha256, selection, policy, session_id, *,
                 native_variant_path=None, native_variant_sha256=None):
    from runtime_support import strict, verify_files
    from profiles import get_profile
    from nemotron_binding import bind, ADAPTER_SHA256
    if Path(binding_path).stat().st_size > 262144 or digest(binding_path) != pin(binding_sha256):
        raise ValueError("Pinned existing deployment binding required")
    binding = strict(Path(binding_path).read_bytes())
    base = Path(binding["installed_release"])
    manifest_path = base / "RELEASE_MANIFEST.json"
    if digest(manifest_path) != binding["installed_manifest_sha256"]:
        raise ValueError("Installed deployment manifest changed")
    verify_files(base, strict(manifest_path.read_bytes())["files"])
    key = "d1-delayed" if selection.nemotron_profile == "current_delayed" else "d1-streaming-saved"
    selected = binding["profiles"][key]
    if digest(selected["path"]) != selected["sha256"]:
        raise ValueError("Retained profile descriptor changed")
    document = strict(Path(selected["path"]).read_bytes())["runtime_document"]
    document["streaming_profile"] = get_profile(selection.nemotron_profile).native_name
    for row in document["native_runtime_files"]:
        if digest(row["path"]) != row["sha256"]:
            raise ValueError("Retained native dependency changed")
    verified_variant = None
    if (native_variant_path is None) != (native_variant_sha256 is None):
        raise ValueError("Native variant path and SHA256 must be supplied together")
    if native_variant_path is not None:
        from native_variant import verify_native_variant
        if os.environ.get("LD_PRELOAD") or os.environ.get("LD_LIBRARY_PATH"):
            raise ValueError("Isolated variant requires an unmodified fresh-process library search")
        with Path("/proc/self/maps").open() as maps:
            loaded = maps.read(1024*1024+1)
        if len(loaded) > 1024*1024 or "libnemo_speech_asr" in loaded or "libggml" in loaded:
            raise ValueError("Native variant requires a fresh process without existing D1/GGML libraries")
        verified_variant = verify_native_variant(native_variant_path, native_variant_sha256, selection)
        document = verified_variant.document()
    adapter = base / "vendor/edge_speech_pipeline/nemotron_diarization.py"
    if digest(adapter) != ADAPTER_SHA256:
        raise ValueError("Exact installed adapter source changed")
    spec = importlib.util.spec_from_file_location("benchmark_retained_nemotron", adapter)
    native = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = native
    spec.loader.exec_module(native)
    factory = bind(native, selection, policy, document, verified_variant=verified_variant)
    def construct():
        return factory(document["nemotron_model"], document["nemotron_library"],
            profile=document["streaming_profile"], session_id=session_id,
            expected_library_sha256=document["nemotron_library_sha256"], gpu=-1)
    construct.native_variant_receipt = verified_variant.receipt() if verified_variant else None
    return native.np, construct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--experimental", action="store_true")
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--developer-soak", action="store_true")
    parser.add_argument("--repeat-seconds", type=int)
    parser.add_argument("--wall-paced", action="store_true")
    parser.add_argument("--block-samples", type=int, default=1600)
    parser.add_argument("--drain", type=int, default=120)
    parser.add_argument("--backlog", type=int, default=120)
    parser.add_argument("--execute-native", action="store_true")
    parser.add_argument("--binding", type=Path)
    parser.add_argument("--binding-sha256")
    parser.add_argument("--native-variant", type=Path)
    parser.add_argument("--native-variant-sha256")
    parser.add_argument("--unit")
    args = parser.parse_args()
    owner = bootstrap(args.output, args.execute_native, args.unit)
    from profiles import RuntimeSelection, SessionPolicy
    selection = RuntimeSelection("nemotron", "anonymous", "saved", args.profile, args.experimental)
    policy = SessionPolicy(args.duration, args.developer_soak, args.drain, args.backlog)
    info = inspect_wav(args.input, args.input_sha256)
    plan = make_plan(info, selection, policy, repeat_seconds=args.repeat_seconds,
                     wall_paced=args.wall_paced, block_samples=args.block_samples)
    if (args.native_variant is None) != (args.native_variant_sha256 is None):
        raise ValueError("Native variant path and SHA256 must be supplied together")
    if args.native_variant is not None:
        from native_variant import require_selection
        require_selection(selection)
        plan["requested_native_variant"] = dict(path=str(args.native_variant),
            sha256=pin(args.native_variant_sha256), verified=False)
    publish(args.output / "PLAN.json", plan)
    if not args.execute_native:
        publish(args.output / "RESULT.json", dict(status="HOST_PLAN_ONLY", native_execution=False,
            output=str(args.output), target_samples=plan["target_samples"], maximum_output_bytes=plan["maximum_output_bytes"]))
        print(json.dumps(dict(status="HOST_PLAN_ONLY", output=str(args.output))))
        return 0
    if args.binding is None or args.binding_sha256 is None:
        raise ValueError("Explicit pinned deployment binding required for native execution")
    resource = resource_sample()
    if resource["available_ram_bytes"] is None or resource["available_ram_bytes"] < 850*1024**2:
        raise MemoryError("Native admission needs at least 850 MiB available RAM")
    if shutil.disk_usage(args.output).free < 5*1024**3 + plan["maximum_output_bytes"]:
        raise RuntimeError("Native admission needs full output reservation above 5 GiB free floor")
    import resource as native_resource
    cpu_seconds = math.ceil(policy.total_deadline_seconds * 2)
    native_resource.setrlimit(native_resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    began = time.perf_counter()
    last_guard = 0.
    def guard():
        nonlocal last_guard
        now = time.perf_counter()
        if now-began > policy.total_deadline_seconds:
            raise TimeoutError("Finite benchmark deadline exceeded")
        if now-last_guard >= 1:
            last_guard = now
            metrics = resource_sample()
            if metrics["available_ram_bytes"] is None or metrics["available_ram_bytes"] < 192*1024**2:
                raise MemoryError("Available RAM crossed 192 MiB stop floor")
            if shutil.disk_usage(args.output).free < 5*1024**3:
                raise RuntimeError("Native free storage floor crossed")
    np, factory = load_factory(args.binding, args.binding_sha256, selection, policy,
                               f"benchmark-{owner['boot_id']}-{owner['pid']}-{owner['start_ticks']}",
                               native_variant_path=args.native_variant,
                               native_variant_sha256=args.native_variant_sha256)
    if factory.native_variant_receipt is not None:
        publish(args.output / "NATIVE_VARIANT_ADMISSION.json", factory.native_variant_receipt)
    guard()
    result = run_stream(plan, factory, np, args.output, native_execution=True, guard=guard)
    print(json.dumps(dict(status=result["status"], output=str(args.output), native_execution=True)))
    return 0 if result["failure"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
