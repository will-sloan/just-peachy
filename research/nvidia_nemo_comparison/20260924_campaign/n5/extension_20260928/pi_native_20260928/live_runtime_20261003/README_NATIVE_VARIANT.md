# Explicit experimental native thread variant

Purpose: compare the independently built two-thread Chunk52 core against the
retained one-thread reference without relaxing normal runtime library pins.
`native_variant.py` verifies a caller-pinned descriptor, its build/source/closure
receipts and every isolated dependency before the existing adapter may load it.
The new `chunk52_threads2` profile is a distinct experimental opt-in. Existing
profiles/defaults keep their original core pins. The new option additionally
requires exact completed component evidence. It does not authorize production
or qualify ground-truth accuracy, whole-pipeline performance or sustained use.

## Inputs and admission

Supply both `--native-variant` and `--native-variant-sha256` to
`native_benchmark.py`. The path must be exactly
`/home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/LABEL/RUNTIME_VARIANT.json`.
Derive its SHA256 from the actual successful build after the independent exact
owner/cgroup closure and complete mirrored-file review. A source-preparation
receipt or proposed hash cannot substitute for that review.

The original `--profile chunk52 --experimental` saved anonymous benchmark route
remains available. The distinct `chunk52_threads2` selection also accepts live or
saved input with ReDimNet, TitaNet or anonymous labels after measured-core
verification. Whole-pipeline trial/production authorization remains separate.
The existing normal deployment binding is still required and verified.
The verifier additionally requires:

* The exact source patch SHA `9d83b3c063f7cd0c56362648f0b8f8b5a9962e884f9a533631074c59f47c895c`,
  actual `session.cpp` bytes and matching `SOURCE_VARIANT.json`.
* A successful `BUILD_RESULT.json` identifying the exact retained input manifest,
  all 2,436 verified inputs, requested graph threads2, unchanged LRU8, the new core
  hash, descriptor hash and complete runtime-file hashes.
* Matching successful `OWNER.json` / `JOB_EXIT.json` identities and lease-release
  receipt. These local checks supplement the operator's independent closure review.
* Geometry52/1/0/80/264/40, original model pin, original C-ABI wrapper, original A76
  CPU/base/GGML dependencies and an isolated regular-file runtime directory with
  no unexpected members. The build core and runtime copy must match.
* A fresh benchmark process with no previously loaded D1/GGML libraries and no
  `LD_PRELOAD` / `LD_LIBRARY_PATH` override that could select a different binary.

Any missing half of the path/SHA pair, changed source/library, unrelated path,
different geometry, unreviewed old-format build or failed receipt is rejected
before model creation. Without the optional arguments, the retained LRU1/LRU8
core checks remain unchanged. An arbitrary dictionary is not accepted as the
binder's verified argument.

## Native command inside the admitted unit

Use a fresh process, the same pinned 715,127-sample WAV, and the same native
resource envelope as the retained Chunk52 benchmark. Replace the uppercase
placeholders with the actual reviewed files/pins, not proposed values:

```sh
python3 -B N/native_benchmark.py \
  --execute-native --unit UNIT.service \
  --binding BINDING.json --binding-sha256 BINDING_SHA256 \
  --input MATCHED.wav --input-sha256 MATCHED_WAV_SHA256 \
  --profile chunk52 --experimental --wall-paced \
  --native-variant /home/peachyprototype/JustPeachy/research/nemotron-20260928/live-runtime-tests-20261003/BUILD_LABEL/RUNTIME_VARIANT.json \
  --native-variant-sha256 REVIEWED_DESCRIPTOR_SHA256 \
  --output FRESH_PRIVATE_OUTPUT
```

The four numerical-library environment variables stay1; the separately built
core requests two native graph threads. This distinction is recorded explicitly.
The process CPU2/3/shared200% limit is unchanged. See the complete resource and
input policy in [README_NATIVE_BENCHMARK](README_NATIVE_BENCHMARK.md).

## PowerShell, Command Prompt and Anaconda dispatch

Prepare the normal fresh private benchmark payload described in
[README_BENCHMARK_DISPATCH](README_BENCHMARK_DISPATCH.md), then add
`native_variant` with the exact native path and `native_variant_sha256` with the
reviewed descriptor SHA. `profile` must be `chunk52` and `experimental` true.
The injected action validates/passes both arguments; it cannot silently ignore
the requested variant. A fresh staged package must include this verifier and
the updated benchmark/binder. Do not modify a frozen package in place.

PowerShell:

```powershell
$n='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$n/host_operations.py" --label thread2-compare-launch-01 --action "$n/launch_benchmark_action.py" --payload 'G:/PRIVATE/FRESH_THREAD2_COMPARE_PAYLOAD.json' --writes
```

Command Prompt / Anaconda Prompt:

```bat
set "N=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%/host_operations.py" --label thread2-compare-launch-01 --action "%N%/launch_benchmark_action.py" --payload "G:/PRIVATE/FRESH_THREAD2_COMPARE_PAYLOAD.json" --writes
```

The host wrapper registers CPU14 ownership, reserves the independent mirror and
performs current ownership/backup checks. The separate native build and its
actual mirrored-byte validation are recorded in
[README_NATIVE_THREADS_BUILD](README_NATIVE_THREADS_BUILD.md); neither is an
inference comparison. Only the authorized root operator dispatches.

## Outputs, API and tests

The benchmark keeps its usual full sample/frame/probability/EOF outputs.
`PLAN.json` records the requested descriptor as unverified at plan time.
After successful admission, `NATIVE_VARIANT_ADMISSION.json` records actual
descriptor/build/source/core pins and configured graph threads2, with observed
graph threads unclaimed. `MODEL_INIT.json` and `RESULT.json` retain the same
admission provenance. Production, quality and sustained qualification remain
false. The distinct integrated option separately records its exact completed
same-geometry component comparison through the pinned review hash.

API: `verify_native_variant(path, sha256, selection)` returns an immutable verified
object; `.document()` returns a separate document copy. Pass that object only via
`bind(..., verified_variant=value)`. The benchmark API accepts keyword arguments
`load_factory(..., native_variant_path=path, native_variant_sha256=sha256)`.

For integrated use, `verify_measured_variant(selection)` resolves the descriptor
from the bundled pinned review, only for explicit `chunk52_threads2`. The binder
requires the sealed object even if a caller supplies the original one-thread
core. Keep separately verified TitaNet/gallery configuration separate from the
sealed D1 document; do not mutate the native document. Verify the installed
adapter/deployment and reject preloaded D1/GGML or library-search overrides before
binding. Keep a fresh process and the shared CPU2/3, 200% envelope; environment
thread limits remain1. Root integration supplies actual selected native fields.

## Actual component evidence

`component_evidence/chunk52_threads2_review.json` is an exact copy of the private
`chunk52-threads2-01-review-01/REVIEW.json`, SHA256
`8ef69dd6333c2a1432cb08fd34a905c60c49044cce869b89b43fc7cb3a926ef6`.
It binds core `210fee955c8728935e28598bffaf618868a9b9d57b76ac124c753f594a6e0f4d`
and descriptor `3fdb0a0699e06a0608ca6cf5676676e3416bf291398271ebd3fd9a5bca41bc57`.
Do not reformat or regenerate it. It contains measurement metadata, no audio or
probability arrays. The complete mirror and independent owner/cgroup closure were
reviewed separately by the root operator.

On the actual2GB CM5, all715,127 samples and4,470 frames completed with EOF and
model closure; all4,470×8 values exactly matched the retained reference. Component
RTF was0.554327206 versus1.081286854 for the one-thread comparison. This does not
establish integrated performance, sustained behavior or labeled accuracy.

Host configuration only, through the early-owner/CPU14 launch from
README_PIPELINES in PowerShell, CMD or Anaconda, may evaluate
`RuntimeSelection('nemotron', 'redimnet', 'live', 'chunk52_threads2', True).validate()`.
It performs no model execution. Native launch remains the reviewed root action.

Run `test_native_variant` using the CPU14/early-owner PowerShell or
Command/Anaconda test commands in
[README_PIPELINES](README_PIPELINES.md#run-the-focused-tests), replacing the test
module name. Set `JP_BENCH_TEST_ROOT` to that private preparation directory to keep
temporary fixture files there. The original synthetic tests cover changed source/model/
libraries/descriptor, closure, selection/path/geometry limits, document mutation,
the verified binder argument and unchanged default core rejection. They create
small fake bytes; no native library/model is compiled or loaded.

Final focused check: 26 variant, benchmark and pipeline host contracts passed;
both dispatch actions and generated native wrappers syntax-checked. Receipt:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-variant-final-c3db25ba5924455f9ab732db7e934db0/RESULT.json`.

After the measured integrated option was added, nine focused variant contracts
passed, including actual read-only review validation, changed-review rejection,
explicit profile combinations and refusal to reuse benchmark-only admission for
integrated selection. Receipt:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-thread2-integration-ed04da841abb4f1c86e02fd6325dc33c/RESULT.json`.
The actual isolated build/model/evidence was also verified over 21 read-only
host-mapped paths with the integrated live+ReDimNet selection, without loading
native code or models:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-measured-thread2-2d78208802104c068bcda73168f4e169/RESULT.json`.

## Actual loader provenance in current07

The integrated two-thread route now calls `require_fresh_variant_loader` before
installed model imports; the binder repeats it immediately before CDLL. Nonempty
LD_PRELOAD/LD_LIBRARY_PATH and already-mapped D1/GGML libraries are rejected.
After CDLL, before C model creation, `verify_loaded_variant_libraries` reads at
most1 MiB of `/proc/self/maps` and requires every mapped D1/GGML path to belong to
the verified isolated inventory. It checks canonical path, actual device/inode
and hash; deleted/replaced/foreign libraries fail. The linked wrapper/core/GGML
set must be present. After initialization it additionally requires the CPU
backend, which may load during backend initialization; no audio has been pushed.
The final actual mapped-library receipt is included in the model manifest.
These checks preserve default one-thread profiles and do not authorize another
core or repair a missing library silently.

`test_review_fixes` covers search overrides/preloads, mapped foreign paths,
inode changes, incorrect bytes, missing dependencies and the bounded live UI
regressions. Use the same early-owner CPU14 PowerShell/CMD/Anaconda wrapper above,
substituting that module. Its five focused tests passed at
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/presets-preparation-review-tests-4352f3f25200401f8a7a16aba22c7c08/RESULT.json`.
No native library or model was loaded by these host tests. Actual current07
integrated loading, throughput and closure remain native gates.
