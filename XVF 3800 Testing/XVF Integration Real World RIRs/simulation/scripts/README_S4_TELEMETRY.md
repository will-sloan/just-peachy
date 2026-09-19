# S4 telemetry, causal availability and nominal geometry

These new S4 files extend the existing recorder architecture without changing historical S3 code. The physical S4 orchestrator remains the sole XVF owner. The logger is a library used inside that owner's existing byte-range lease; the commands below are offline and do not open USB or audio devices.

Files and purpose:

- `s4_telemetry.py`: persistent three-field logger, strict normalized records, a causal spatial reader and callback availability map.
- `s4_geometry.py`: nominal lab-to-linear-array transform, complete manual ±5° interval folding, separate nominal and interval errors.
- `s4_native/S4QueuedTelemetry.cs` and `Run-S4-Telemetry.ps1`: official Win32 DLL transport in one persistent 32-bit PowerShell process.
- `test_s4_telemetry.py` and `s4_native/Test-S4-Native-Offline.ps1`: offline regression tests and command-map-only verification.

PowerShell — run offline Python tests:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest -v test_s4_telemetry
```

Anaconda Prompt / Command Prompt — the same tests:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -m unittest -v test_s4_telemetry
```

PowerShell — compile and verify official DLL metadata and native NaN parsing, without initializing USB:

```powershell
& 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -NonInteractive -File 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_native\Test-S4-Native-Offline.ps1' -DllDirectory 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\tools\xvf321\binary\host_v3.0.0\win32'
```

Anaconda Prompt / Command Prompt — native offline verification:

```bat
"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_native\Test-S4-Native-Offline.ps1" -DllDirectory "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\tools\xvf321\binary\host_v3.0.0\win32"
```

The native offline test calls `Inspect` and `DecodeForTest` only. `Inspect` reads DLL metadata; it does not call `control_init_usb`. The three contracts are AEC angles (resource 0x21, command 75, four radians), AEC energy (0x21, command 80, four floats), selected angles (0x23, command 11, two radians). Every physical process repeats this metadata check before USB initialization. Local 3.2.1 `audio_cmds.yaml` describes selected index 0 as processed speaker DoA and index 1 as auto-select DoA; index 0 NaN means no speech on either fixed beam.

Physical integration API, called only from the existing S4 owner after configuration:

```python
from s4_telemetry import create_telemetry_logger
logger = create_telemetry_logger(HOST, case_folder / "telemetry",
                                 duration_s=scene_seconds + 15,
                                 rate_hz_per_field=20).start()
if not logger.wait_ready(10):
    raise RuntimeError("All three telemetry fields did not become available")
# Owner captures audio here. No other XVF control process may run concurrently.
logger.stop("case_finished")
result = logger.wait(20)
if result is None:
    raise RuntimeError("Telemetry owner has not released its handle")
```

The caller must stop/wait in its finally cleanup even if readiness or capture fails. The logger performs no firmware/parameter writes. Read warmup drains previously outstanding known telemetry requests; it is not audio warmup. Native shutdown drains pending reads and closes USB. Forced termination invalidates that telemetry run; the physical owner retains responsibility for restoration and lease release.

Inputs: exact vendor host path (used to bind its two companion DLLs), a new output directory, duration 0–3600 seconds, and requested per-field rate 1–30 Hz (default 20). The requested rate is a maximum target, not a fixed DSP sampling promise. Pending polls sleep at least 1 ms and native cycles are rate-limited.

Outputs in each telemetry directory:

- `received_telemetry.jsonl`: every complete measurement, native sequence and separate receipt sequence, all array values, units, raw reply/base64, request-start/response-end/line-receipt timestamps.
- `normalized_observations.jsonl`: strict JSON records with value/transaction validity, explicit non-finite reasons, separate transaction duration/delivery latency and unknown DSP freshness.
- `native/transactions.tsv`: every attempt including retries, compact columns for sequence/cycle/phase/field/attempt, start/end nanoseconds, transport/status, and raw response bytes.
- `native/samples.jsonl`, both result JSONs, command-map inspection, raw stdout/stderr and consumed source snapshots/hashes.

The original NaN bytes remain in base64. JSON values become null with a reason; no-speech NaN, zero, infinity, malformed replies and transport failure remain distinct. Both selected values are preserved. A native measurement sequence can start above zero because warmup records are preserved separately.

Causal adapter usage:

```python
from s4_telemetry import CausalSpatialReader
reader = CausalSpatialReader()
reader.ingest(raw_received_row)
decision = reader.at(actual_host_monotonic_ns)
```

Only rows received by the decision time are usable. The default selected processed value must be finite and in range, transaction duration ≤250 ms, stdout delivery ≤250 ms, and receipt age ≤250 ms. New invalid/no-speech replies mask old valid ones. A missing/late/invalid primary value gives `spatial_unavailable`; audio/text continue. An unchanged bearing does not become stale merely because its value is constant, and a newly received copy never proves a newly computed DSP frame. The adapter accepts no scene truth, source identity or seat labels. It is a candidate availability layer, not a demonstrated S6 benefit.

`TIMING_TELEMETRY_POLICY` declares these development thresholds independently of manual ±5° labels. It also freezes coarse-sector first-hit and 0.5-second sustained-acquisition definitions for the owner's scorer. Physical observation time remains unknown; no angle/energy shift is fitted to known turns.

`CallbackAvailabilityMap(callback_times, startup_native_frames, capture_minus_source_offset_samples)` provides `written_source_sample`, `recaptured_source_sample`, `decoded_sample` and `processed_source_sample`. It requires contiguous callback frame ranges and nondecreasing host times. Packed logical samples map through all three native frames. Queries outside captured ranges return unavailable instead of clamping to an edge. Callback block span and preceding gap describe timing granularity; they are not calibrated acoustic/device latency bounds. Dry scheduling, retained RIR pre-onset, exact input offset, output delay and host metadata availability remain separate.

Geometry usage:

```python
from s4_geometry import source_label, angle_error
label = source_label(-80)
errors = angle_error(measured_native_degrees, label)
```

The transform is `degrees(acos(-sin(radians(lab))))`, nominally supported by MIC0 left/MIC3 right and vendor Figure 3.3. It maps forward 0° to native 90°, left +75° to 165°, right −80° to 10°. `source_label` preserves the signed input, wraps the entire manual uncertainty interval and includes interior extrema at endfire. It never implies independently calibrated source coordinates, front/rear resolution or device accuracy within 5°. Nominal and interval errors are separate.

Offline regeneration of normalized JSONL (replace INPUT and OUTPUT with actual absolute paths; OUTPUT must be new):

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_telemetry.py' --normalize-input 'INPUT\received_telemetry.jsonl' --normalized-output 'OUTPUT\normalized_observations.jsonl'
```

```bat
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s4_telemetry.py" --normalize-input "INPUT\received_telemetry.jsonl" --normalized-output "OUTPUT\normalized_observations.jsonl"
```

Physical evidence must be generated/resumed by the S4 owner using compatible scene bytes, frozen policies and a new attempt directory. These helpers do not independently resume or repeat hardware cases.

