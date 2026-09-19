# Windows live capture and beam diagnostics — 0.1.3

The XVF3800 can connect directly to Windows; a Raspberry Pi is not required for
PC testing. The same source release targets the prepared Linux/CM5 installation,
with separate native dependencies and device configuration. This is a desktop
window, not a browser interface.

## Failure and correction

The user's session reached verified XVF routing, then failed with
`Source-progress watermark is ahead of observed source time`. Windows delivered
a buffered packet as multiple 10 ms callbacks. The old epoch subtracted only
one 10 ms block from the first callback time, so admitted samples appeared to
precede their permitted source time. `Audio arrived after source closure` was
a secondary error that obscured the originating failure.

The adapter now records the callback's high-resolution host clock and PortAudio
ADC/current-time fields. Valid driver timestamps bind one fixed capture epoch.
If those fields cannot support the block, reported input latency is explicitly
used as an estimate. Missing usable timing still fails. Timing guards remain
unchanged: no epoch rebasing, timestamp clamp, audio dropping, artificial pacing,
or substituted microphone was added. Cleanup and the GUI preserve the first error.

Both physical checks used the **reported 110 ms input-latency estimate**. This
is unqualified for acoustic latency measurement. These short checks establish
live capture/inference operation, not long-session clock drift, speech accuracy
or enrollment accuracy.

## Verification on 19 September 2026

| Check | Result |
|---|---|
| Balanced identity / Anonymous, real XVF and native models | PASS; 20.02 s delivered |
| Fast captions / Captions, real XVF and native ASR | PASS; 10.01 s delivered |
| Continuity and cleanup, both runs | Zero dropped frames; native COMPLETED; microphone closed; route restored |
| Default Windows playback endpoints | Unchanged in both runs |
| Beam diagnostics in Balanced check | 36 successful getters, zero getter errors, six valid arrows at final snapshot |
| Focused software contracts | 114 tests passed; no failures/errors/skips |
| Beam page | Visually inspected at 480 × 800 with synthetic display fixtures |

Compact evidence: [WINDOWS_LIVE_FIX_CHECKS.json](WINDOWS_LIVE_FIX_CHECKS.json).
Full private receipts/journals remain under
`G:\Just_Peachy_PROTO1\tests\windows_live_fix_20260919_*`, outside the release.
An initial bare unittest invocation from the nested app directory produced
three import errors; the documented runner then passed all 114 tests with
repository/application import paths. No dependency installation was needed.
Historical S7/PROTO1 results keep their original source bindings; they are not
new soak or accuracy results for 0.1.3.

## Run

Close the old GUI, then reopen the launcher and grant Start's microphone consent.
Windows' default input setting does not replace this app's explicit XVF binding.
Start streams audio for inference; it does not save an ambient WAV archive.

PowerShell from the repository:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt from the repository:

```bat
prototype\Start-Prototype.cmd
```

Inputs are the connected XVF, local configuration/model assets, and optional
private profiles. Outputs are captions, available identity labels, bounded
local journals and diagnostic arrows. Open **Settings → Beam angles · live
diagnostics** during capture. Reproduction commands are in `tools/README.md`
and [BEAM_DIAGNOSTICS.md](BEAM_DIAGNOSTICS.md).

## Spatial support and Pi export

Active recipes use XVF beamformed O0/O1 audio, but software enrollment and
identity do not currently use numerical angles. Diagnostic colors identify
hardware outputs, never people. Multiple arrows may follow one source, music
or reflections; native 0–180° directions fold front and rear together.

Spatial-assisted remains disabled pending verified audio/telemetry alignment
and reliability. Named arrows also need a validated association between voice
evidence and a contemporaneous beam. Voice recognition alone cannot establish
which beam belongs to a person.

`proto1-0.1.3` uses the existing package/stage/activate/rollback workflow. Keep
models and personal data separate. The Pi still needs the native ARM64 XMOS
control tool, ALSA binding, display/touch setup and physical acceptance tests.
**CM5 hardware has not been tested.** See
[PI_DEPLOYMENT_WORKFLOW.md](PI_DEPLOYMENT_WORKFLOW.md).
