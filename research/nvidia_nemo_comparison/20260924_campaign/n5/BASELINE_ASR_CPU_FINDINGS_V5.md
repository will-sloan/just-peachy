# ARM64 emulation CPU-selection diagnosis

2026-09-28: Explicit `-cpu cortex-a76` restores the baseline ASR's output in
the controlled one-stream diagnostic. The independently reviewed final records
match the retained Windows C-API reference exactly, including text, source
positions and phase. This is an emulation result, not a physical CM5 test.

| Same 715,127-sample saved input | Final utterances | Endpoint resets | Emulated command wall time |
|---|---:|---:|---:|
| Retained Windows C-API reference | 3 | 13 | Not an emulated measurement |
| Retained QEMU default CPU (V3) | 0 | 17 | 231.334s |
| Explicit QEMU Cortex-A76 (V5) | 3 | 13 | 170.958s |

The experiment reused the exact V3 ARM64 executable, four models, runtime
libraries, input WAV, gain, precision and recognizer configuration. Only the
two CPU-selection arguments were inserted into the model invocation. All
715,127 decoded samples have the same float fingerprint as Windows and V3;
Sherpa 1.13.4 revision 14280725 is unchanged. The measured wall time is QEMU
on the Windows host and cannot predict native CM5 throughput.

`BASELINE_ASR_CPU_CHECK_V5.json` binds the independent private audit. It
reverified 24 admitted source records, exact argv difference, binary and input
bindings, terminal output, Windows PID/creation identities and fresh Linux
PID/start-tick/group absence. The host, supervisor and Linux groups closed
normally. Five command/help-parser tests pass; the original strict model
reader was not weakened. See `README_BASELINE_ASR_CPU_V5.md` and
`README_BASELINE_ASR_CPU_REVIEW_V5.md` for reproduction.

The first V4 attempt stopped before inference: this pinned QEMU lists CPUs
with exit 1, and the original preflight expected exit 0. V4 output and code
remain preserved. V5 admits help exit 0/1 only with the exact advertised CPU
token, expected header, empty stderr, no cancellation and an empty process
group. Inference still requires normal exit 0 and all original semantic checks.

This localizes the failure to behavior affected by the emulator's CPU model
or feature dispatch. It does not identify a particular faulty kernel, establish
an ONNX model defect, or justify changing model precision/endpoint thresholds.
It also does not imply that the actual Pi would reproduce the default-QEMU
failure. Use explicit Cortex-A76 for this baseline emulation qualification.

The required full-protocol retest subsequently **passed**, independently
reviewed at 01:02:57 UTC. `BASELINE_ARM64_CPU_RETEST_V2.json` binds the new
audit. It reuses the original V1 full-protocol executable and all original
model/settings/input bytes, adding only explicit Cortex-A76 selection.

All four cases match Windows exactly: empty and 1,281-sample short tail close
with zero finals/resets; each 715,127-sample full stream closes with three
finals and 13 endpoint resets. The fresh stream on the resident recognizer
reproduces the first, establishing this limited state-parity check. Eight
malformed-WAV cases are refused correctly. The original strict reader and
comparison gates remain unchanged; 11 focused reader/parser tests passed.

The whole model command, including loading and both full streams, took
339.372 seconds under emulation. This is not native Pi throughput. The audit
reverified 32 admitted source bindings and fresh exact Windows and Linux
process/group closure. Reproduction is documented in
`README_BASELINE_ARM64_CPU_V2.md` and
`README_BASELINE_ARM64_CPU_REVIEW_V2.md`. The earlier V5 diagnostic receipt
retains its historical requirement for this later retest; it is not rewritten.

This passes the emulated **baseline Sherpa C-API ASR component** comparison.
It does not accept token timestamps, punctuation, speaker models, Python/Tk,
GUI execution, the A2/A3 native harness or a complete installable Pi release.

N4/N5 remain partial. Full ARM64 Python/Tk, speaker and punctuation execution,
integrated application/resource validation and native CM5 installation and
performance still require their own evidence. Windows previews, old failures,
immutable releases and the campaign reserve/deadline remain unchanged.
