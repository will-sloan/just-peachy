# Windows Nemotron English preview

Purpose: make the functioning N3 A2 Windows source easy to open, with its local
CPU models and a separate private data store. `Start-N5-NEMOTRON.cmd` selects
Nemotron Speech Streaming English 0.6B in the existing 480x800 shared GUI.
This is an engineering preview. N4 full application/resource acceptance and
N5 release qualification are incomplete; this launcher does not change that.

`Start-N5-NEMOTRON-SPEAKERS.cmd` selects anonymous speaker separation with the
same A2 ASR and Nemotron D1 diarizer. Both variants use the same data store;
open only one at a time. It does not attach personal names to speakers.

The launcher requires the separately verified PASS receipt for its selected mode,
rehashes the immutable source and required assets, and refuses while a campaign
worker still exists. It uses CPU4, one numerical thread, below-normal priority
and no GPU. It opens idle unless you explicitly supply `--wav`. The campaign
does not launch this visible window automatically. The separate private-desktop
lifecycle harness checks actual GUI rendering and save/reopen/delete behavior.

Inputs: the existing qualified Windows Python environment, accepted source at
`local/releases/n3-common-a1controllerv2/prototype`, external baseline and NeMo
models, the private lifecycle admission and public PASS receipt. No downloads
or training are performed. Paths are local to this workstation; it is not a
portable installer. Checkouts and original personal profiles are not changed.

Output: the visible GUI when explicitly invoked, plus private text sessions and
preferences under `G:\Just_Peachy_N1\20260924_campaign\local\Windows Nemotron Preview\data`.
The first GUI invocation copies the two already-qualified runtime path files
there. Changed runtime files and an existing runtime lock are refused, not
overwritten. Use the application's normal Close control. No microphone device
is enumerated/opened, and no audio is played. Live capture/enrollment remains
disabled. Prepared O0 WAVs must already have their intended gain applied once.

Caption-only/fast is the default. Anonymous-conversation/balanced also passed
the separate one-file lifecycle check, with every identity sample consumed and
zero final speaker lag. Other backend/mode entries remain in
the shared UI; their visibility does not give them this preview's acceptance.
In particular, the larger N4 D1 speaker-processing test has an unresolved
finalization failure. No calibrated personal-name recognition is promised.
The preserved baseline remains available through `Start-N5-BASELINE.cmd`.

## PowerShell

```powershell
cd G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
# Read-only file verification, no visible app:
.\Start-N5-NEMOTRON.cmd --check-only
# When you choose to open the preview (idle, saved-audio-only):
.\Start-N5-NEMOTRON.cmd
# Or explicitly process your already-prepared saved WAV:
.\Start-N5-NEMOTRON.cmd --wav 'G:\your-prepared-input\O0.wav'
# Same ASR, adding anonymous Nemotron speaker separation:
.\Start-N5-NEMOTRON-SPEAKERS.cmd --wav 'G:\your-prepared-input\O0.wav'
```

## CMD / Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
Start-N5-NEMOTRON.cmd --check-only
rem The following explicitly opens the GUI:
Start-N5-NEMOTRON.cmd
rem Optional prepared saved WAV; replace the example path:
Start-N5-NEMOTRON.cmd --wav "G:\your-prepared-input\O0.wav"
Start-N5-NEMOTRON-SPEAKERS.cmd --wav "G:\your-prepared-input\O0.wav"
```

No environment activation is needed: the CMD wrapper uses the existing explicit
interpreter. The Raspberry Pi remains off; Windows success does not prove ARM64,
2-GB RAM suitability, CM5 installation, live latency or device integration.
