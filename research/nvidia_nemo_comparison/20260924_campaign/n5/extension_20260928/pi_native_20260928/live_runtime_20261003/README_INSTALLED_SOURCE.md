# Isolated installed microphone source

`installed_source.py` is a prepared adapter around the pinned installed v12
`app.live_audio.XVFLiveSource`. It accepts processed O0/O1 audio and preserves
the installed input-only route, gain, decimator, hardware lease and physical
Stop/restoration checks. It does not construct a speech model. **Native
capture and physical closure have not been run with this new adapter.**

Its default processed input uses the installed 48 kHz two-channel route. A
separately gated packed adapter is now prepared for four PCM32 microphone
channels at **16 kHz**, transported within 48 kHz stereo. Normal raw use remains
disabled until an actual native qualification receipt is admitted. See
`README_RAW_CAPTURE.md` for exact routing derivation, source-only qualification,
bounded raw packets, and retained evidence. Synthetic tests are not native
qualification.

## Integration inputs

Call `create_source(journal, config, callback, spatial_provider, policy, spool)`
only from an already registered native runtime process. It creates a source
without capturing; `source.start()` performs the explicit Start. It exposes
`start`, `stop`, `wait`, `sent`, `thread`, `live.status()`, `start_metadata`,
`stop_receipt`, `integrity`, `error` and `timing` for the existing engine.

`policy` accepts the runtime's validated `SessionPolicy` dataclass
(`maximum_session_seconds`); its sample rate is taken from the matching spool.
It also accepts a mapping with integer `duration_seconds` and
`sample_rate=16000`, matching `spool.spec`. Raw requests without explicit
spool/binding admission are rejected.
`config` supplies:

- `installed_release`: the native v12 application directory.
- `installed_manifest_sha256`: exact v12 manifest
  `274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0`.
- `live_config`: actual `LiveConfig` fields, explicit ALSA input endpoint and
  existing `~/JustPeachy/data/xvf-hardware.lock`. Set `evidence_dir=None` because
  receipts are written through the session store.
- `consent=True`: supplied only following the authorized visible Start action.
- `reference_code` and `reference_files`: the pinned extracted v28 capsule.
  The adapter extracts exact unique `BeamQueue`/`BeamReceiver` definitions and
  their support from `field_live_source_bridge_v6.py`, without executing its
  unrelated imports. Reference pins may be a manifest row list or a mapping
  of filenames to SHA strings or `{sha256: ...}`.
- Alternatively, `mounted_spatial_path` and `mounted_spatial_sha256` can name
  the exact reviewed standalone mounted transport derivative.
- Optional `owner_directory`: must equal the fresh
  `spool.directory/work/source`. The runtime prepares the real `work` parent;
  the source child creates its own new `source` directory.

The native parent retains the current mounted IMU provider. Beam readings are
carried through the reviewed queue/receiver using actual callback timestamps;
the parent then advances the existing spatial provider with the audio block.

## Ownership, output and limits

The parent verifies the installed release manifest and all Python source hashes
before adding the exact application/vendor paths. The source-only raw harness
uses the isolated source directly and avoids importing the model pipeline base
class. This covers the missing-app-path boundary found before capture in the
preserved first raw trial; it does not count as physical qualification.

The child runs a fresh interpreter directly on this module. It does not use
`multiprocessing.spawn`, which could re-import a model-loading parent main
before the owner boundary. Before project imports it sets Linux CPU3 affinity,
256 MiB address-space limit, 1 MiB stack, single-thread library environment and
zero core-dump limit, then writes `REGISTERED_OWNER.json` with actual PID,
start ticks and boot ID. It sends that identity and waits for the parent's
persisted acknowledgement before importing the pinned application.

Processed audio packets have explicit lengths, sequence numbers and original
sample/clock metadata. The parent acknowledges a block only after journal
acceptance and source metadata publication. Packet/audio/stderr allocations
and IPC waits are finite. There is only one outstanding audio packet; this
does not replace the installed source's bounded callback ring or its overflow
fault checks. A blocked disk or peer therefore fails explicitly instead of
silently dropping samples.

The child writes `SOURCE_CLOSE.json`; the store receives source owner, start,
block and closure events. A clean result requires installed integrity checks,
stream-closed and lease-released assertions, matching accepted sample counts,
natural child exit and verification that the exact child identity is gone.
Forced reaping is reported as a failure with unqualified physical closure.
Source Stop waits are separately bounded; the model processing/drain lifetime
is owned by the runtime manager, not this microphone process.

## Run hardware-free checks from Anaconda Prompt or cmd.exe

```bat
set "LIVE_SOURCE_TEST_ENTRY=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\source-entry-%RANDOM%-%RANDOM%"
mkdir "%LIVE_SOURCE_TEST_ENTRY%"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json,sys; from pathlib import Path; p=Path(os.environ['LIVE_SOURCE_TEST_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import runpy; sys.argv=['test_installed_source.py','--output-root',str(p),'--mounted-bundle','G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/runtime-capsule-v3/COMMON_BUNDLE.json']; runpy.run_path('test_installed_source.py',run_name='__main__')"
```

## Run hardware-free checks from PowerShell

```powershell
$env:LIVE_SOURCE_TEST_ENTRY = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\source-entry-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $env:LIVE_SOURCE_TEST_ENTRY | Out-Null
Set-Location -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json,sys; from pathlib import Path; p=Path(os.environ['LIVE_SOURCE_TEST_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import runpy; sys.argv=['test_installed_source.py','--output-root',str(p),'--mounted-bundle','G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/imu-integration-20261002/runtime-capsule-v3/COMMON_BUNDLE.json']; runpy.run_path('test_installed_source.py',run_name='__main__')"
```

The wrapper sets CPU14 affinity and publishes an actual numeric owner record
before reading the test file. The test entry then publishes its own unique
owner record before project imports. It preserves an `installed-source-checks-<id>` folder
with owner/result/exit records and the exact mounted source fixture. Nine
checks exercise partial IPC reads/writes, bounded packets, terminal partial
frame failures, exact mounted telemetry transfer/future rejection, changed
source pins, manifest row-list resolution, runtime SessionPolicy construction,
unadmitted-raw rejection and absence of installed-app imports. These
are synthetic protocol checks, not Linux pipe, child lifecycle, native capture
or physical-close qualification. There is no standalone capture command here;
the runtime's explicit Start supplies the session, consent and owner context.
# Optional100ms IPC grouping

A future binding may explicitly set `source_batch_ms: 100` with exact480-frame
source callbacks; omission retains the unbatched path. See
`README_SOURCE_BATCH.md` for bounded audio/metadata, per-block clock preservation,
raw-before-processed durable acknowledgements, focused tests and run commands.
Frozen build04 remains unchanged. Host batching tests make no native throughput
or raw-adapter qualification claim.

