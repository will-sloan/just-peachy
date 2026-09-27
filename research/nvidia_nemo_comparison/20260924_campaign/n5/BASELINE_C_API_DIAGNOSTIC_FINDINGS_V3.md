# Paired C-API investigation: ARM64 still returns empty text

The fresh full-stream diagnostic reproduced the failure. The identical C++
harness produced three finals and 13 endpoint resets on Windows, matching the
earlier Python reference's exact text and source positions. Emulated ARM64
produced zero finals and 17 resets. Both consumed 715,127 frames plus the same
10,560-frame final padding and closed normally. Model time was 3.969 seconds
on Windows and 231.334 seconds under QEMU; these are diagnostic command times,
not source-paced latency or CM5 performance.

BASELINE_C_API_DIAGNOSTIC_CHECK_V3.json binds the independent private audit.
Both sides decoded 208,979 nonzero samples, peak 0.066741943359375 and sum of
squares 5.648533998988569. Their complete decoded float32 fingerprint matched.
Both reported Sherpa 1.13.4, revision 14280725, dated July 7 2026. Effective
recognizer configurations matched exactly after substituting the four platform
file paths, including normalization, dither, feature geometry, CPU/thread count,
endpoint rules, decoding and reset settings. All four model/input identities
were unchanged. Raw text, debug logs and binary/model/audio bytes remain private.

This narrows the investigation: the C++ harness works on Windows, and different
decoded samples or declared recognizer settings do not explain the ARM result.
The failure also occurs with a fresh recognizer and no preceding empty/short
streams. It does not establish that all internal tensors, runtime kernels or
emulated CPU features agree. No runtime defect or QEMU defect is proven yet.

## Preserved attempts and cleanup

V2 configured and compiled successfully, then refused to run because CMake chose
the installed Build Tools compiler instead of the admitted Community location.
Both cl.exe files have identical bytes/hashes, but the path gate was retained.
The owned job closed its remaining vctip helper; that attempt has no inference
evidence. V3 independently verified the actual compiler record, source, successful
commands/logs and x64 PE executable, then reused it in a fresh model-only job.
See README_BASELINE_ASR_DIAGNOSTIC_V3.md and the V2 README for full commands.

The V3 Windows job closed normally and unforced; the input desktop remained
Default. Exact supervisor 55316/1790546704.567945, driver
49408/1790546704.7312312, WSL launcher 45928/1790546710.1320808,
reference 47992/1790546705.075317 and model 2716/1790546705.9158144
are absent. Linux owner 427/start_ticks361, compiler 428/start_ticks535 and
model 433/start_ticks945 are absent, with empty owned groups. Eighteen bound
source records and the runtime/model/input bindings were reverified. Seven
model-free reader/build-reuse checks passed.

The first independent audit stopped on a help-command exit assumption. Its
failure is preserved; audit-v2 performs the completed identity/hash/closure
review. QEMU 10.2.1 reports its version with exit 0 and lists supported CPUs with
exit 1 and empty stderr. The latter is informational help, not a model result.
No success gate for model execution was relaxed. V3's normal terminal says
DIAGNOSTIC_COMPLETED_NO_ACCEPTANCE; it must never be promoted to an ASR pass.

## Bounded next isolation step

The retained QEMU executable lists cortex-a76. Neither inference command used
an explicit CPU selection; the later inspection found QEMU_CPU unset in its
environment, which does not independently prove the earlier child's environment.
A new derivative may compare an explicitly selected cortex-a76 against this
preserved run, keeping executable/model/WAV bytes and configuration fixed.
The [QEMU CPU-feature documentation](https://www.qemu.org/docs/master/system/arm/cpu-features)
explains that CPU models expose different optional feature sets. Investigating
runtime dispatch is a hypothesis, not a diagnosed cause or a claim of CM5 fidelity.

Use fresh resource census, exact prior-owner closure, bounded allocation and
new receipts. If behavior changes, rerun the original complete nonempty/repeat/
state protocol under the explicit environment before claiming component parity.
If it does not, preserve the blocker and investigate internal feature/logit or
runtime-version behavior; do not adjust input gain, precision or acceptance to
obtain words. No unchanged retry is justified by this result.

N4 still has zero accepted new release profiles. ARM64 Python/Tk, speaker/PnC,
full application and all on-device checks remain unverified. The Pi stayed off.
The September 28 02:48:19 UTC packaging reserve and 14:48:19 deadline are unchanged.
