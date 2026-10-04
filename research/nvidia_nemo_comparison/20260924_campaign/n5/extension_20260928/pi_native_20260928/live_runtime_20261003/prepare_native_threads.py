"""Prepare a pinned native graph-thread source variant, without compiling. README_NATIVE_OPTIMIZATION.md."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile

BUNDLE_SHA256 = "58780becc87dfc0d2dc985bb7a6e338af6e7a0e6bb12422e3417be66171f24fb"
ORIGINAL_SHA256 = "9583306947a8a0cb92d68da94c1803cb5caa064e112face5123e1f94e959251a"
SCHEDULER_SHA256 = "b88e2ba3e4bd4f55a909e9898f5580fc559c222f3e9a257387540a21366a60c3"
METADATA_SHA256 = "679ce2e01202723e7f94233df362ad38751f5380882a6e0964db63270dac4726"
MEMBER = "source/src/runtime/ggml/session.cpp"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_once(raw, old, new):
    if raw.count(old) != 1:
        raise ValueError("Exact retained source context required")
    return raw.replace(old, new)


def variant(original, native_threads=1):
    """Reproduce the retained metadata source exactly before changing one integer."""
    if type(native_threads) is not int or native_threads not in (1, 2):
        raise ValueError("Only explicit native graph thread counts 1 or 2 are admitted")
    if sha(original) != ORIGINAL_SHA256:
        raise ValueError("Original session source pin mismatch")
    scheduler = replace_once(original, b"static constexpr size_t kSchedGraphSize = 65536;",
                             b"static constexpr size_t kSchedGraphSize = 8192;")
    if sha(scheduler) != SCHEDULER_SHA256:
        raise ValueError("Retained scheduler reconstruction pin mismatch")
    metadata = replace_once(scheduler, b"static constexpr size_t kSchedGraphSize = 8192;",
                            b"static constexpr size_t kSchedGraphSize = 2048;")
    helper = b"""static TensorContainer::ArenaSizes d1_bounded_metadata_arenas() {
    TensorContainer::ArenaSizes sizes;
    sizes.temp_ctx_bytes = 8 * 1024 * 1024;
    sizes.default_buft_bytes = 8 * 1024 * 1024;
    return sizes;
}
"""
    if metadata.count(b"TensorContainer::ArenaSizes{}") != 3:
        raise ValueError("Retained metadata arena contexts differ")
    metadata = metadata.replace(b"TensorContainer::ArenaSizes{}", b"d1_bounded_metadata_arenas()")
    metadata = replace_once(metadata, b"static constexpr size_t kSchedGraphSize = 2048;",
                            helper + b"\nstatic constexpr size_t kSchedGraphSize = 2048;")
    metadata = replace_once(metadata, b"constexpr size_t kProbeArenaBytes = 64 * 1024 * 1024;",
                            b"constexpr size_t kProbeArenaBytes = 8 * 1024 * 1024;")
    if sha(metadata) != METADATA_SHA256:
        raise ValueError("Retained metadata reconstruction pin mismatch")
    before = b"ggml_graph_compute_helper_async(sched.get(), cr.gf, 1)"
    after = b"ggml_graph_compute_helper_async(sched.get(), cr.gf, " + str(native_threads).encode() + b")"
    changed = replace_once(metadata, before, after)
    return changed, dict(schema="just-peachy.native-thread-source-variant.v1",
        original_sha256=ORIGINAL_SHA256, scheduler_sha256=SCHEDULER_SHA256,
        retained_metadata_sha256=METADATA_SHA256, source_sha256=sha(changed),
        native_graph_threads_requested=native_threads, native_graph_threads_observed=None,
        change="none" if native_threads == 1 else "one graph-helper argument: 1 to 2",
        native_build=False, native_execution=False, numerical_equivalence_evaluated=False,
        performance_qualified=False, quality_evaluated=False,
        preserved=dict(scheduler_nodes=2048, scheduler_error_fraction=.95,
                       metadata_arena_mib=8, geometry=True, model=True, c_abi=True),
        required_runtime_cpu_sha256="f12ac1b3912855a88bdc899fb468297d940c8730ee5942a991cc45ddf825a557",
        runtime_cpu_implementation="retained Cortex-A76 pthread backend; no OpenMP build flag",
        envelope=dict(cpus=[2, 3], aggregate_cpu_percent=200, numerical_library_environment=1))


def read_original(bundle):
    bundle = Path(bundle)
    if bundle.is_symlink() or not bundle.is_file() or bundle.stat().st_size != 7402245:
        raise ValueError("Exact retained 7,402,245-byte regular bundle required")
    hasher = hashlib.sha256()
    with bundle.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            hasher.update(block)
    if hasher.hexdigest() != BUNDLE_SHA256:
        raise ValueError("Retained build bundle pin mismatch")
    with tarfile.open(bundle, "r:gz") as archive:
        member = archive.getmember(MEMBER)
        if not member.isfile() or member.size != 41109:
            raise ValueError("Retained session member type/size mismatch")
        with archive.extractfile(member) as stream:
            original = stream.read(41110)
    if len(original) != 41109 or sha(original) != ORIGINAL_SHA256:
        raise ValueError("Retained source member pin mismatch")
    return original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--native-threads", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    import psutil
    process = psutil.Process()
    process.cpu_affinity([14])
    output = Path(args.output).absolute()
    if any(path.is_symlink() for path in (output, *output.parents)):
        raise ValueError("Fresh real private output path required")
    output.mkdir(parents=False, exist_ok=False)
    with (output / "REGISTERED_OWNER.json").open("x") as stream:
        json.dump(dict(pid=process.pid, create_time=process.create_time(), affinity=process.cpu_affinity()), stream)
        stream.flush(); os.fsync(stream.fileno())
    source, receipt = variant(read_original(args.bundle), args.native_threads)
    receipt["bundle_sha256"] = BUNDLE_SHA256
    receipt["bundle_member"] = MEMBER
    with (output / "session.cpp").open("xb") as stream:
        stream.write(source)
    with (output / "SOURCE_VARIANT.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(dict(output=str(output), **receipt), sort_keys=True))


if __name__ == "__main__":
    main()
