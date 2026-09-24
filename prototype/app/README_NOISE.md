# Optional noise / model routing (task10)

Purpose: reuse existing model evidence and add one stateful DPDFNet branch to
post-XVF mono16k. This is an experimental field option; default is **Bypass**.
It does not improve every recording. See `../docs/UIITER2_10_HANDOFF.md` for
measured examples, regressions, licences and target-readiness limits.

From the repository root, PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt (no environment activation or package install needed):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

Settings → Advanced → **Noise / model routing**. Choose Bypass, Enhance for ASR,
Enhance for identity, or Enhance for both. Selection drains the old epoch;
press Start explicitly for a fresh capture. A selection/load failure leaves
the old setting intact and displays the reason. Select Bypass to recover.
Normal microphone participation/consent, profiles, roster modes, recipes,
seats, spatial diagnostics and O0/O1 rules still apply.

Inputs: the existing once-gained post-XVF mono16k stream; optional artifact in
`config/enhancement.json`; existing Sherpa1.13.4, Pyannote and ReDimNet models.
Outputs: selected ASR/identity streams, ordinary captions and Unknown/names,
bounded coordinator observations, and exact optional consented session files.
No neural inference, USB call, archive write or UI update runs in the callback.

| Route | ASR | Voice / Pyannote | Compatible reference |
|---|---|---|---|
| Bypass | Original | Original | Existing same-tap/domain reference |
| ASR | Enhanced | Original | Existing same-tap/domain reference |
| Identity | Original | Enhanced | Enhanced, same model SHA/tap/domain |
| Both | Enhanced | Enhanced | Enhanced, same model SHA/tap/domain |

Enhanced enrollment stores its exact domain and helper SHA; original references
are preserved. New enhanced references set `enhanced-reference-v1` in the
personal-data reader guard. A legacy reader must not silently load them.
Do not record a reference with another person talking. In the fixed overlap
example, enhancement made some mixed speech pass the unchanged quality gate;
quality admission is not proof of a single speaker. There is no automatic
personal-reference update from ordinary conversations.

`enhancement.py` uses installed **OnlineSpeechDenoiser**, not repeated offline
denoising. DPDFNet has a160-sample hop,320-sample window and persistent recurrent
and STFT state. First160 output samples require320 input samples. Steady
algorithmic buffering is160samples/10ms;20ms source dispatch and actual compute
add availability delay. Native `flush()` supplies its own internal boundary
padding and returns exactly the remaining source samples. Output indices retain
input indices. The wrapper never normalizes, applies gain, trims excess output,
or pads a mismatch into a PASS. Reset occurs at safe epochs. No offline/online
boundary equivalence or calibrated acoustic-delay claim is made.

One optional worker reads the bounded raw ring. At more than0.5s backlog or a
helper exception, it resumes raw ASR at the exact next unpublished sample;
late helper output is discarded. ASR state is retained to avoid replaying words.
Enhanced identity ends at that boundary, future names are cleared, and a fresh
Start is required. A still-running worker prevents model reuse. Capture errors
remain errors. The original ring remains available; enhanced routes add one
120s float32 ring (~7.68MB at the default horizon), plus the helper runtime.
At source closure a0.5s flush deadline also releases raw ASR if the helper stalls
without further input callbacks; it does not pretend that worker has exited.

`noise_coordination.py` retains only the latest five evidence categories:
waveform, speech/overlap, ASR progress, voice quality and beam. Each has source
sample bounds, monotonic publication availability, provenance, freshness and
unknown/invalid state. It reuses existing events and mapped beam buffers, with
no new USB polling or embeddings. It reports existing overlap vetoes, clipping
uncertainty and optional-work fallback. Correlated scores are not independent
probabilities; quiet speech, missing words and accent are not noise detectors.
The ordinary identity scheduler remains authoritative.

Create **Sessions → New transcript + audio**, explicitly consent, then Start.
After Stop, save/reopen the session. Listening choices are Original, ASR,
Identity and Enhanced/fallback, using an explicitly chosen output. The raw
`model_input.f32le`, optional `enhanced.f32le`, `transforms.jsonl`, `windows.jsonl`
and epoch manifest bind exact streams, source intervals and availability.
Internal decoder/segmentation padding is recorded separately. Identity windows
after a helper-failure boundary cannot be exported as valid enhanced identity.
Text-only sessions never write either audio stream. Quotas include both streams;
archive failure is visible and does not stop captions.

The source change is portable Python and ONNX. The helper is outside releases,
under the existing model root:
`debaf0e8893479fca91b8b4c1eae8db195aa8980ccc9012f5809fde2b738151a/dpdfnet_baseline.onnx`.
Only that hash,8,791,035bytes, Sherpa1.13.4 and native16k/hop160 are accepted.
No model auto-download occurs on launch. Missing models block optional selection,
not Bypass. Task08's ZIP has not been rebuilt; future exports need current source,
this hash directory, and the Apache notices. Native ARM64/CM5 full-pipeline
speed, memory, thermals and human/XVF field tests remain NOT_TESTED.

Tests and reproduction: `../tests/README_NOISE.md`, `../tools/README_NOISE.md`.
