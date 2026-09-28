# Nemotron ARM64 Cortex-A76 retest: full source remains partial

The independently audited V2 retest timed out after 1,800.60 seconds during
A2's fresh repeat. Explicit Cortex-A76 did not clear this blocker. The first
715,127-frame (44.695-second) source completed with five final events and
exact final text/word parity against the earlier default-CPU first pass.
Empty, one-sample and short-tail cases also closed. The repeat reached
413,440 frames (25.84 seconds); repeat closure and forced endpoint were not
completed. A3 was not attempted because timeout ends the allocation.

`NATIVE_STREAM_CPU_CHECK_V2.json` binds the private independent review, which
verified 20 source bindings, models/audio/runtime, receipts and exact Windows
creation identities plus Linux boot/PID/start-tick closure. Zero complete
model passes are accepted. The older default-CPU attempt reached 377,600
repeat frames before its same cap; this partial progress comparison does not
establish a reliable speedup or native CM5 throughput.

A fresh V3 test uses only the declared first 16 seconds of the same PCM source
and tighter 1,500-second per-model caps, with the unchanged six-case reader.
Its purpose is narrower saved-input functional coverage, explicitly allowed
by N5. Any short-clip success cannot clear the original full-source failure.
See README_NATIVE_STREAM_SHORT_V3.md for inputs, outputs and commands.

Windows saved-file A2/D1 previews and baseline Sherpa ARM64 C-API parity remain
separate verified evidence. Full ARM64 Python/Tk, speaker/punctuation/GUI,
integrated resources, N4 application acceptance and N5 release acceptance
remain open. No Raspberry Pi was contacted.
