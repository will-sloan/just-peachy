# Prepare the small Pi reconnection companion

Purpose: collect the separately required read-only storage preflight, exact
baseline archive identity, current limitations and installation/rollback guide
in one small ZIP. This makes the later baseline transfer easier without changing
the immutable model-containing baseline ZIP or calling new backends Pi-ready.

Inputs: the existing ARTIFACT_INDEX.json, qualified preflight sources/receipt,
the eight fixed documentation/code files in the builder, and the original
310,867,595-byte baseline ZIP. The builder requires a clean campaign worktree
whose selected bytes match the exact authorized remote HEAD. It rehashes the
baseline and all 31 declared members using the unchanged qualified preflight.
No download, extraction, model load, target connection or OS change occurs.

Outputs: a fresh private directory containing a companion ZIP and RESULT.json.
The ZIP contains eight small source documents/tools, a generated baseline
inventory and a manifest: ten files, under 1 MiB uncompressed. Every member is
read back exactly. Models/audio/profiles are excluded. The baseline stays in
its existing directory; copy both archives later using the quickstart. An
archive hash proves integrity, not target installation or runtime acceptance.

The full ARM64 Python/Tk/speaker/punctuation/GUI path remains unverified. N4/N5
are partial. The companion preserves the six-case short A2/A3 result and its
limits, but does not install those candidates. Storage must be measured later
on the actual Pi; estimated fit is not measured RAM or conversational speed.

PowerShell, after committing/pushing the selected sources:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
$jpPy='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPy -B prepare_pi_reconnect_companion_v1.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\pi-reconnect-companion-v1
```

CMD / Anaconda Prompt (existing interpreter; no environment activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_pi_reconnect_companion_v1.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\pi-reconnect-companion-v1
```

Use a new output directory for any repeat; existing evidence is refused rather
than replaced. Only the builder process is pinned to CPU14/BelowNormal, GPU off.
C:50/G:75-GiB floors remain. The underlying preflight's 11 prior fixture tests
are reused with unchanged hashes; this packaging change is checked by actual
archive/member verification and readback, without repeating numerical work.

The later user-operated process is in PI_RECONNECT_QUICKSTART_V1.md. No commands
from its target section are run during the offline campaign. Preserve previous
releases, external personal data, fixed campaign limits and held-out real-world
validation requirements.
