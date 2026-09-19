# Bounded S3 physical XVF proof

This stage binds the Revision 6 workbook and S3 pack, reuses selected canonical RIRs,
and checks the physical XVF transport and two processed outputs. It does not regenerate
RIRs, modify H2, train models, or run the full simulation campaign.

## Read-only preflight

Inputs: the existing S3 pack, Downloads Revision 6 workbook, working recorder and
connected XVF. Outputs: workbook text, checked source bindings, read-only device
snapshot and raw command receipts in the specified new S3 report directory.
No audio stream, playback, or device setter is used. The existing hardware lease
prevents conflicting recorder ownership.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs'
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' simulation\scripts\s3_preflight.py --report simulation\reports\S3\20260908T214914Z
```

Anaconda Prompt / Command Prompt (uses the qualified recorder interpreter explicitly):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" simulation\scripts\s3_preflight.py --report simulation\reports\S3\20260908T214914Z
```

Use a new timestamped report directory for a fresh preflight; preserve prior receipts.
Physical playback remains gated on explicit confirmation that every analog speaker
connected to XVF LINE OUT is off or disconnected.

## Offline fixture preparation and transport checks

`s3_prepare.py` reads the S3 manifest, only three selected RIR WAVs, the existing
LibriSpeech recording index, and three clean utterances with their transcripts/license.
It creates five fixed vectors (the conversation is replayed twice), a common source
level policy, separately quantized 16/24-bit expected arrays and packed files, and an
input manifest. The speaker IDs/utterances are reserved for development. This uses
Anaconda for NumPy/SciPy/PyArrow; no corpus scan, downloads, or RIR extraction occurs.

`s3_checks.py` uses the recorder interpreter and tests ordering, common alignment,
single errors, signs, per-mic delay, dropped/duplicated groups, and framing boundaries.
Neither command opens a device. Existing input directories are refused.

PowerShell, after the Set-Location above:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' simulation\scripts\s3_prepare.py --report simulation\reports\S3\20260908T214914Z
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' simulation\scripts\s3_checks.py --report simulation\reports\S3\20260908T214914Z
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" simulation\scripts\s3_prepare.py --report simulation\reports\S3\20260908T214914Z
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" simulation\scripts\s3_checks.py --report simulation\reports\S3\20260908T214914Z
```

## Physical runner (requires explicit speaker confirmation)

`s3_hardware.py` uses only the unique XVF WDM-KS pair, the recorder's existing
hardware lock, Control, raw duplex capture, decoding, and queued telemetry. It
snapshots the exposed configuration, tries USB24, resets/reapplies the frozen
configuration between cases, gates continuation on exact quantized input recovery,
and restores the initial static settings and USB width in `finally`. Telemetry is
stopped before other control calls. It never routes to another audio endpoint.
Adaptive DSP history is reset and cannot be restored from settings.

Create `speaker_safety.json` **only after the operator confirms** all analog monitors
are off or disconnected. Required JSON fields: `all_analog_monitors_off_or_disconnected`
must be true, `user_confirmation_text` must contain the actual confirmation, and
`confirmed_utc` should record receipt time. A software volume setting is insufficient.

PowerShell:

```powershell
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' simulation\scripts\s3_hardware.py --report simulation\reports\S3\20260908T214914Z --speaker-safety-receipt simulation\reports\S3\20260908T214914Z\speaker_safety.json
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" simulation\scripts\s3_hardware.py --report simulation\reports\S3\20260908T214914Z --speaker-safety-receipt simulation\reports\S3\20260908T214914Z\speaker_safety.json
```

Outputs under `hardware_initial/`: raw packed capture (never listen as stereo),
decoded MIC0–3/O0/O1, explicit mono O0/O1 WAVs, full telemetry/callback timings,
command receipts, per-attempt integrity results, and `restoration.json`. Status
updates occur every 15 seconds. Core playback totals 123 seconds; an integrity
failure stops subsequent cases. One diagnosed retry requires `retry_diagnosis.json`
and `--attempt retry1`; it must not conceal the first failure. No automatic retry.
Never rerun a completed directory or run alongside a recorder. If restoration fails,
keep playback stopped and inspect `initial_state.json`, the command receipts, and
the current device before a controlled recovery; do not flash or reinstall drivers.

## Pre-playback checkpoint package

`s3_checkpoint.py` reads completed preflight/fixture/check receipts and packages a
small analysis-first ZIP labelled BLOCKED/NOT_TESTED while speaker confirmation is
pending. It refuses any report with a physical hardware attempt. Inputs and raw
command logs stay local; the packet includes their path/hash index, concise reports,
planned cases and explicit null reasons. It validates ZIP CRC and every listed hash.
It does not create the completed physical-results handoff.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' simulation\scripts\s3_checkpoint.py --report simulation\reports\S3\20260908T214914Z
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" simulation\scripts\s3_checkpoint.py --report simulation\reports\S3\20260908T214914Z
```

Output: `simulation\handoffs\S3_CHATGPT_HANDOFF_20260908T214914Z_PREFLIGHT.zip`
plus `preflight_packet/` and `preflight_package_receipt.json` in the report directory.
Existing packets and archives are refused so prior evidence remains intact.

## Offline analysis and unchanged H2 smoke (after hardware closes)

`s3_analyze.py` consumes `hardware_initial` (or the explicitly selected successful
attempt), the prepared input manifest, decoded captures, callback receipts and full
queued telemetry. It writes `analysis_metrics.json`, `analysis/per_case_metrics.csv`,
three PNG plots and the plotted CSV data. It never aligns microphones separately,
fits a telemetry shift, or accesses hardware. Audio is summarized in 20 ms blocks
with exact block peaks retained; plotted telemetry retains all returned samples.
Relative processing lag uses bounded waveform correlation and is not absolute device
latency. Host audio callback windows and missing calibrated timestamp offsets are
reported explicitly. Re-running analysis only refreshes these derived artifacts.

`s3_h2_smoke.py` requires successful handle closure/restoration. It checks unchanged
H2 source against S0, then passes explicit mono O0 and O1 from ABA repeat 1 through
the existing H2 file command, each with a new empty data/profile root. It writes
stdout/stderr, session receipts and `h2_smoke.json`. It refuses an existing smoke
directory. Models, thresholds, private profiles and H2 code are unchanged.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' simulation\scripts\s3_analyze.py --report simulation\reports\S3\20260908T214914Z --hardware simulation\reports\S3\20260908T214914Z\hardware_initial
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' simulation\scripts\s3_h2_smoke.py --report simulation\reports\S3\20260908T214914Z --hardware simulation\reports\S3\20260908T214914Z\hardware_initial
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" simulation\scripts\s3_analyze.py --report simulation\reports\S3\20260908T214914Z --hardware simulation\reports\S3\20260908T214914Z\hardware_initial
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" simulation\scripts\s3_h2_smoke.py --report simulation\reports\S3\20260908T214914Z --hardware simulation\reports\S3\20260908T214914Z\hardware_initial
```

Do not run either inference or substantial numerical analysis alongside physical
capture. Other PC speakers, headphones and microphones may remain connected: the
hardware runner opens only the unique named XVF WDM-KS pair, never a default device.

### Executed one-time initialization retry

The initial six captures passed transport, but their ABA snapshots contained
different current AGC gains (61.38675 / 58.89388). The single diagnosed retry
selects packed input immediately after reset, keeps it selected during setup, and
initializes current AGC gain to the existing maximum 125. It changes no AGC tuning
parameters. Both original and retry evidence remains local. Only the 38-second
conversation pair is repeated (76 seconds; total playback 199 seconds).

PowerShell command used, after writing the evidence-backed `retry_diagnosis.json`:

```powershell
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' simulation\scripts\s3_hardware.py --report simulation\reports\S3\20260908T214914Z --speaker-safety-receipt simulation\reports\S3\20260908T214914Z\speaker_safety.json --attempt retry1 --case-plan conversation_pair
& 'C:\Users\amiri\anaconda3\python.exe' simulation\scripts\s3_analyze.py --report simulation\reports\S3\20260908T214914Z --hardware simulation\reports\S3\20260908T214914Z\hardware_retry1
```

Command Prompt / Anaconda Prompt: use the same quoted executables and arguments
without the leading `&`. These hardware directories already exist and cannot be
reused; the retry budget is exhausted. Do not run a third attempt within S3.

Analysis of `hardware_retry1` includes all eight attempts in its metrics and table,
uses the two retry conversations for the repeat comparison, and retains the original
repeat comparison explicitly. `initial_analysis_metrics.json` is the pre-retry
checkpoint. H2 was run once per mono stream from original ABA repeat 1, after its
handles closed and before the physical retry. It was not repeated or tuned to fit
the later observations. The captured H2 session paths and hashes identify that pair.

## Final compact handoff

`s3_finalize.py` consumes the eight-attempt analysis, H2 receipts, both restoration
receipts, exact source/code bindings and the reviewed Markdown narratives in the
report root. It verifies required proof results, binds only the selected RIRs,
indexes omitted local evidence, and writes an analysis-first ZIP with three figures,
their plotted CSVs, all-attempt metrics, a focused initialization diff, provenance
and checksums. It checks every packaged SHA-256, ZIP CRC, file count and 15 MiB cap.
No raw WAV/NumPy vectors, full telemetry traces, model weights or historical ZIPs
are bundled. It refuses an existing `final_packet` or final archive. This is a
one-time finalizer; preserve the completed packet rather than overwrite evidence.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' simulation\scripts\s3_finalize.py --report simulation\reports\S3\20260908T214914Z
```

Anaconda Prompt / Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" simulation\scripts\s3_finalize.py --report simulation\reports\S3\20260908T214914Z
```

Outputs: `simulation\handoffs\S3_CHATGPT_HANDOFF_20260908T214914Z.zip`,
`final_packet/` and the external `package_receipt.json` containing ZIP hash/size,
timing, storage and verification. The earlier `_PREFLIGHT.zip` remains an immutable
historical checkpoint and is not included in the completed handoff.
