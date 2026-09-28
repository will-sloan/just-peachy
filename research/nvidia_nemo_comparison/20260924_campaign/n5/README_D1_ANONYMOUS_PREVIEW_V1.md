# Windows Nemotron D1 paired previews

Purpose: user-invoked saved-audio preview of A2 Nemotron English ASR and D1
Nemotron 3 Diarization with anonymous speaker labels. The REDIMNET launcher
retains the existing E0 encoder; the ANONYMOUS launcher bypasses encoder loads
and calls in this mode. Both sources require the same passing paired check. The same 480x800 shared GUI is used. The launcher
requires D1_ANONYMOUS_WINDOWS_CHECK_V1.json to pass the paired qualification;
it refuses while that receipt is absent, invalid, or a campaign worker remains.
It does not install or automatically open a visible window during the campaign.

Inputs: the local n3-stable-asr-chunks-v1 (ReDimNet) and
d1-stable-asr-chunks-v1 (encoder-free) derivatives, paired lifecycle admissions,
hash-bound CPU models/runtime and Windows Python environment. Optional --wav
accepts an already-prepared mono 16 kHz PCM16 O0 WAV with gain already applied.
No model download, microphone enumeration, capture, playback or training occurs.
No activation is needed. This launcher is workstation-specific, not portable.

Outputs: a visible idle GUI only when the user invokes it, saved captions and
preferences under local/Windows Nemotron Stable redimnet Preview/data or
local/Windows Nemotron Stable none Preview/data. Each fresh
private store is separate from earlier previews and personal data. Native D1
slots provide labels, not automatic personal-name recognition. Close normally
before starting another version. Existing data/runtime locks are not removed.
Other modes remain visible in the shared UI; this check qualifies only anonymous
conversation. The retained catalog composition mentions E0 as a capability for
named modes; the derivative's runtime bypasses it in ordinary anonymous mode.
Model assets remain required by the catalog and are not removed from disk.

PowerShell:

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
.\Start-N5-NEMOTRON-REDIMNET.cmd --check-only
.\Start-N5-NEMOTRON-ANONYMOUS.cmd --check-only
# Only when you choose to open the actual visible application:
.\Start-N5-NEMOTRON-REDIMNET.cmd
.\Start-N5-NEMOTRON-ANONYMOUS.cmd
# Or process an already-prepared saved file (replace the example path):
.\Start-N5-NEMOTRON-ANONYMOUS.cmd --wav 'G:\your-prepared-input\O0.wav'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
Start-N5-NEMOTRON-REDIMNET.cmd --check-only
Start-N5-NEMOTRON-ANONYMOUS.cmd --check-only
rem User chooses to open the visible application:
Start-N5-NEMOTRON-REDIMNET.cmd
Start-N5-NEMOTRON-ANONYMOUS.cmd
Start-N5-NEMOTRON-ANONYMOUS.cmd --wav "G:\your-prepared-input\O0.wav"
```

The launcher uses exactly CPUs 4 and 14, one numerical thread per model,
below-normal priority and GPU off. Its stable-input derivative gathers 100 ms
ASR blocks plus the exact EOF tail; coarse boundaries no longer depend on
fragmented journal reads. This may add up to 100 ms of source buffering.
--check-only performs file/receipt verification without importing the GUI or
running inference. Existing baseline, caption-only and earlier speaker previews
remain available unchanged. This is a one-file Windows engineering preview,
not N4 full-bank acceptance, calibrated naming, a speed claim, or CM5 validation.
The Pi remains off. See README_D1_ANONYMOUS_LIFECYCLE_V4.md for qualification
inputs/outputs and README_D1_ANONYMOUS_REVIEW_V1.md for independent review.

The Python entry point accepts --encoder redimnet (default) or --encoder none.
Both currently qualify anonymous-conversation mode only; retaining embeddings
does not establish calibrated automatic naming. Use the same --wav argument
with either launcher. No existing preview or immutable release is replaced.
