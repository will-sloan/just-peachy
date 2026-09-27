# Baseline ARM64 ASR: preserved empty-output failure

The paired check failed. Windows passed empty, 1,281-frame short-tail and two
715,127-frame full-source streams. Each full pass had three nonempty finals and
13 endpoint resets; repeat text and source positions matched exactly. ARM64
under QEMU consumed and closed all four streams, but each full pass had zero
finals and 17 resets. The required nonempty full-source output check rejected
the run. Equal empty final lists are not a meaningful state-parity pass.

BASELINE_ARM64_ASR_CHECK_V1.json binds the independent private audit. The native
command returned 1 after 470.358 seconds, below its 1,200-second timeout. Its
process group was empty. The exact supervisor, driver, WSL launcher and Windows
reference owner identities are absent. Windows reference job closure was
normal and unforced, with unchanged input desktop. All 14 admitted code records,
model files, saved input and wheel hashes were rechecked. Failed evidence stays
in local/n5/baseline-arm64-asr-v1; the independent audit is in the adjacent
baseline-arm64-asr-v1-audit-v1 directory. Neither is a public transcript package.

The compiler and C API model loading succeeded; all eight invalid-WAV checks
rejected before loading models. The Sherpa core wheel supplies a matching header,
C API and ARM64 ONNX Runtime. This establishes an executable diagnostic route,
not correct transcription. No runtime conversion, model replacement, new audio,
added gain, endpoint change or relaxed gate was used. The single-thread probe
is explicitly scoped; it does not redefine the baseline's normal thread recipe.

## Narrow follow-up investigation

The [v1.13.4 C API source](https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.13.4/sherpa-onnx/c-api/c-api.cc)
maps the same explicit endpoint, decoder and feature-size fields used here.
Its [feature defaults](https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v1.13.4/sherpa-onnx/csrc/features.h)
match the installed Python reference for low/high frequency, no dither,
normalized samples and snip-edges. This source inspection has not verified the
effective configuration inside the particular ARM64 binary and does not prove
why it returned empty text. The stderr CPU-vendor warning alone is not a cause.

A new derivative should first record effective C-API/runtime versions and debug
configuration, verify decoded sample statistics against the Windows reference,
and capture whether token logits/features remain finite on a small existing
saved prefix. Compare runtime behavior before selecting a repair. Do not change
gain, quantization, thread count or endpoint settings merely to obtain words;
such a change would require separate source/precision parity and accuracy scope.
No unchanged retry is scheduled. Any execution needs a fresh complete resource
census, exact prior-owner closure, bounded allocation and new output directory.
Keep the original 14 bindings frozen and preserve the reserve/deadline.

Purpose, source files, admitted inputs/outputs and PowerShell/CMD/Anaconda run
instructions are in README_BASELINE_ARM64_ASR_V1.md. That version's run is now
closed and failed; its instructions do not authorize reuse of the old admission.
The Windows reference passes only raw ASR component checks. ARM64 Python/Tk,
punctuation, speaker/gallery, full application and physical CM5 checks remain
unverified. No new backend release is accepted from this result.
