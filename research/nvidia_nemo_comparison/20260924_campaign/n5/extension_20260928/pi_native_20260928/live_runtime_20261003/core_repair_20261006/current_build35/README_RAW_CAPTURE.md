# Prepared packed microphone adapter

`raw_capture.py` derives the retained v28 raw route for the new segmented session
spool. `installed_source.py` transports it through the isolated source child.
`raw_qualification.py` is the separate five-second source-only native harness;
it is prepared here but has not been executed by these host checks.
The source-only path verifies the installed release manifest and every Python
source hash before adding its application/vendor paths. It does not import the
model pipeline base class or construct models. A preserved first native trial
failed before capture because that application import path was missing; the
new focused test covers this boundary without importing a native application.
`test_raw_capture.py` checks decoding, framing, source pins, explicit admission,
and durable acknowledgements using synthetic data. **No native qualification
is claimed by these tests. Normal raw remains disabled until a real passed
adapter qualification is admitted.** The retained v27/v28 files are not edited.

## Exact format and preserved behavior

The route is four microphone channels, signed PCM32 little endian, at **16 kHz**.
Its USB transport is stereo S32LE at 48 kHz, with each three transport frames
carrying six slots. The retained converter clears marker bit zero, takes slots
0/1 for processed O0/O1, and slots 2–5 for MIC0–MIC3. Markers must be `[0,1,1]`
on both transport channels. This is not four-channel 48 kHz PCM16.

`derive_factory(path, expected_sha256)` verifies the pinned
`field_live_source_factory_v6.py` bytes and extracts only `raw_source_type` and
`install_packed_route`. It keeps the route and callback AST unchanged. That
preserves the exact I2C/480-frame guard, packed routing and
restoration registration, ring overflow/error checks, two-frame carry, prefix
priming, source clocks, raw channel order, existing O0 gain metadata, and lack of
an equal-acoustic-latency claim. It substitutes only:

- The fixed 2,080,000-sample limit with the explicit session duration at 16 kHz.
- The old standalone 33,280,000-byte file sink with bounded parent-spool RPC.
- The finish sink/readback step with durable-parent extent and independent spool
  readback, with explicit consumed and unconverted transport accounting.
- Two accounting counters at startup and a final-read fence before conversion:
  only the remaining complete three-frame groups enter either raw or processed
  publication. The retained read still supplies the exact native/model start,
  native extent, callback clocks and calibration. The selected prefix is never
  trimmed after raw publication.

The derivation receipt includes factory SHA256, route/source AST hashes and an
unchanged-AST assertion outside those enumerated converter/read-fence edits. AST proof is source
evidence; it does not qualify native routing or physical cleanup.
`derive_stop_base` additionally extracts the exact pinned retained bounded Stop
and actual Start override. The Stop overlay and receipt-error file hashes must
be present in the binding's `reference_files`; their AST hashes are retained.

## Admission and inputs

Normal live capture uses raw only when the binding has `raw_adapter_enabled:
true` and an explicitly admitted `raw_qualification_evidence` object with
`qualified: true`, `adapter_native_qualified: true`, an absolute `evidence` receipt
path and its `evidence_sha256`. The receipt must report
`RAW_NATIVE_QUALIFICATION_PASSED`, actual `native_executed: true`, source-clock,
raw and processed independent readback, route restoration, closed stream,
released lease and exact source-owner closure. It must identify four raw
channels, matching positive processed/raw sample counts and exact byte counts,
plus the current `installed_source.py`, `raw_capture.py` and `source_batch.py`
SHA256s. Boolean
enablement alone is insufficient. The binding must also supply `raw_factory_path` and
`raw_factory_sha256`. Missing or invalid evidence fails closed. Disabled raw
falls back explicitly to processed-only storage. Saved processed WAVs stay
processed only. Actual qualification evidence must come from the separate
native admission workflow, never these synthetic tests.

The worker describes this route to storage with `mode: raw_processed` and raw
fields `sample_rate: 16000`, `channels: 4`, `sample_width_bytes: 4`,
`encoding: PCM_S32LE`, channel order, transport rate/channels, shared clock, and
the qualification metadata. Disk admission includes both raw and processed
audio for the full chosen duration. Normal Stop then offers processed-only,
raw plus processed, or discard. Processed-only retention explicitly removes raw.

An explicit fresh **source-only qualification** is separate from normal use.
Its spool specification sets `raw_qualification: true`, and its qualification
metadata is `{qualified: false, qualification_run: true, evidence: <fresh
admission receipt>}`. The source config sets `raw_qualification: true` and uses
the same pinned factory. Storage preserves the unqualified flag in retained or
exported evidence. The qualification harness calls
`create_source(journal, config, callback, spatial_provider, policy, spool)`
without loading the full model pipeline. The normal worker rejects this
qualification flag; unqualified raw never silently enters full ASR/diarization.
The existing source owner/ACK and authorized consent boundaries still apply.

## Prepared native qualification interface

Run only on the CM5 through the owned native scope after fresh admission. The
scope supplies the pinned binding and exact owned unit; do not invoke this
entrypoint from PowerShell, CMD or Anaconda on the PC. Those host environments
are for the synthetic commands below. No ASR or diarization model is loaded.

```text
raw_qualification.py --binding /absolute/BINDING.json --binding-sha256 <sha256> --admission /absolute/RAW_ADMISSION.json --admission-sha256 <sha256> --unit <owned-unique-unit> --unit-ownership /absolute/UNIT_OWNERSHIP.json --owner-directory /absolute/fresh-qualification-worker
```

The admission is immutable, SHA256 pinned, and must contain
`status: RAW_NATIVE_QUALIFICATION_ADMITTED`, `duration_seconds: 5`, the exact
binding SHA256, installed-source, raw-capture and source-batch module SHA256s, unit and actual
InvocationID. The reviewed scope issues it after verifying this fresh owned
service, using a separately pinned admission template. The owner directory must
not exist; bootstrap creates it and registers the owner before source imports.
The service and independent watchdog impose finite closure deadlines. Disk
allocation preserves the configured floor.

The scope interface is `--entrypoint raw_qualification.py
--raw-admission-template <path> --raw-admission-template-sha256 <sha256>`.
The reviewed template has schema `just-peachy.raw-qualification-template.v1`,
`reviewed: true`, duration 5, target, binding/package-manifest hashes, boot ID,
expiry Unix time and all three module hashes. The wrapper binds it to the newly
verified invocation and forwards the generated admission to the harness.

Success requires exactly 80,000 processed and four-channel raw frames, 240,000
consumed transport frames, ordered MIC0–MIC3, matching raw SHA256 against an independent
disk readback, and matching processed float32 SHA256 against a separate
streaming readback. Every route-restoration entry must be restored, the stream
and hardware lease must be closed, and the exact source process must be gone.
Outputs are the private experimental audio session, source/route/clock receipts,
`FILE_ALLOCATION.json` and immutable `RAW_QUALIFICATION.json`. Failure retains
diagnostics and never enables normal raw. A passed native receipt must still be
explicitly pinned into a new authorized binding; this harness does not enable it.

## RPC and outputs

`RAW` messages have `start_sample`, `samples`, and at most 65,536 bytes aligned
to complete 16-byte four-channel frames. Processed `AUDIO` retains its separate
16,384-byte bound. A raw packet is acknowledged with `ACK_RAW` and the exact
accepted frame count only after `SessionSpool.append_raw` has fsynced and
committed it. Failed appends cannot receive a successful ACK. One packet is
outstanding at a time; queue/backpressure failures remain explicit.

Physical Stop occurs before final raw publication. The child checks raw count
equals processed model count and consumed transport count is three times that
count. Callback-enqueued complete frames are partitioned exactly into consumed
frames, the unused suffix of the final read slot, and remaining queued slots.
The terminal incomplete carry (0–2 frames), start-prefix priming and restoration
frames stay separately reported. These excluded frames are an explicit end
boundary, with no claim that they contain no speech. The final receipt includes
the boundary sample/reason and each counter; inconsistent accounting fails.

Native trial02 reached79,999 samples because initial packed alignment yielded
159 samples and subsequent blocks yielded160. The next full conversion exceeded
80,000. This repair admits only the final one sample before raw publication.
That trial also had195 queued blocks and roughly1.95 seconds of source lag.
Actual native trial03 using frozen build04 passed the exact80,000 raw/processed
samples,240,000 consumed transport frames, independent raw/processed readbacks,
source-owner closure, route restoration, stream closure and lease release. Its
private receipt is
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/raw-qualification-03-monitor-01/closed-output/qualification/RAW_QUALIFICATION.json`.
It still measured1.927258052 seconds maximum source lag and192 queued blocks
over five seconds. That short correctness result does not qualify sustained
throughput. The optional100ms path described in `README_SOURCE_BATCH.md` changes
the source module hash and needs its own native qualification before production
raw use. The preserved previous failures and frozen build04 remain unchanged.

The parent independently
streams the stored raw segments through SHA256 using at most 64 KiB reads,
checks its hash against the child and packet hashes, and checks raw/processed
accepted counts. `source_closed` and `raw_capture_verified` events retain these
results. A process/stream/lease failure remains a failure, even when a raw prefix
was durably stored.

No full recording is loaded into memory. Output is the session's segmented raw
PCM32, exact processed float32, replay WAVs, SQLite counts/events, source-close
receipt, and selected ZIP export. Qualification metadata remains attached.

## Run the synthetic checks in PowerShell

These commands pin CPU 14 and register the actual Python owner before reading
project code. They execute no native capture, route control, model, network, or
Pi operation. Inputs are the exact retained factory and a fresh private evidence
directory. Outputs are `REGISTERED_OWNER.json`, `TEST_RESULT.json`, and the
unittest log. Temporary synthetic stores are removed within their owned test
directories.

```powershell
$run = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\raw-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $run | Out-Null
$env:LIVE_RAW_EVIDENCE = $run
$env:LIVE_RAW_TEST_ROOT = Join-Path $run 'tests'
$env:LIVE_RAW_FACTORY = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\reference-v28\code\field_live_source_factory_v6.py'
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_RAW_EVIDENCE']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_raw_capture')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,errors=len(r.errors),failures=len(r.failures)))); raise SystemExit(not r.wasSuccessful())"
```

## Command Prompt and Anaconda Prompt

```bat
set "LIVE_RAW_EVIDENCE=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\raw-%RANDOM%-%RANDOM%"
mkdir "%LIVE_RAW_EVIDENCE%"
set "LIVE_RAW_TEST_ROOT=%LIVE_RAW_EVIDENCE%\tests"
set "LIVE_RAW_FACTORY=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\reference-v28\code\field_live_source_factory_v6.py"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_RAW_EVIDENCE']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_raw_capture')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,errors=len(r.errors),failures=len(r.failures)))); raise SystemExit(not r.wasSuccessful())"
```

The eleven checks exercise exact source pins/AST proof, retained Start/Stop,
the verified source-only application import boundary,
marker and slot decoding,
shared source-count assertions, storage readback, duration exhaustion beyond the
old fixed sample boundary, the exact79,999→80,000 final read with195 queued blocks,
refusal of missing transport accounting, experimental versus normal admission, ACK ordering
and failure, and distinct raw/processed packet bounds. They deliberately make
no native execution, microphone quality, routing-restoration, or throughput claim.
