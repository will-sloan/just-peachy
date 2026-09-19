# XVF3800 telemetry timing and the optional queued reader

This adapter is a version-specific, read-only host implementation. It makes no firmware or parameter writes. Its telemetry protocol passed the finite hardware benchmarks below; the first 300-second concurrent audio soak exposed a separate continuity failure that requires a repeat. The ordinary `measurement_app/telemetry.py` logger remains the simpler fallback using the unmodified official executable.

## Completed hardware benchmarks

The parent operator ran these tests on the connected board. An independent auditor verified every transport response, raw float32 payload, QPC conversion, retry sequence, successful sample, complete pair, and cleanup. Each run retained two warm-up replies and excluded them from measurement counts. At most two distinct read requests were pending.

| Test | Complete angle/energy pairs | Angle rate | Energy rate | Median revisit interval | Largest angle / energy gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| 15-second queued benchmark | 930 | 61.974 Hz | 61.977 Hz | 16.00 ms | 49.98 / 53.27 ms |
| Queued telemetry beside 60-second PCM24 packed audio | 3,781 | 62.269 Hz | 62.254 Hz | 16.00 ms | 65.89 / 105.32 ms |
| First 300-second PCM24 soak, telemetry only passed | 18,850 | 62.042 Hz | 62.042 Hz | 16.00 ms | 280.16 / 224.09 ms |

The second telemetry interval lasted 60.736 seconds, including the surrounding audio-start/stop interval. Its 95th-percentile revisit intervals were 16.639 ms for angle and 16.647 ms for energy. The run retained 200,058 individual USB attempts and 7,564 successful replies, including warm-up; no transport, status, payload, timestamp, sequence or cleanup errors were found. The two arrays' median host completion separation was 0.339 ms, with a maximum of 36.247 ms. This separation is not proof of one common DSP frame.

The 60-second scene produced positive speech energy in 99 of 3,781 energy reads, with zero arrays in the others. The earlier 15-second run produced 590 distinct energy arrays. These observations verify working readout and response, while illustrating that **62 Hz readout does not mean 62 fresh speech estimates per second**. Speech detection and tracking depend on the acoustic scene; zero speech energy is not a failed microphone reading or an absolute sound-pressure measurement.

The first 300-second take (`TAKE_20260905T224242_536556Z_01f622`) **failed audio continuity**, despite a telemetry protocol pass. The independent streaming audit checked 898,515 transfers and 37,702 valid samples including two warm-up replies; all 18,850 measurement pairs were complete and cleanup left no pending reads. Raw audio had 2,942 continuity mismatches near decoded 77.68 seconds, with temporary shifts of one 40 ms WDM buffer. During the associated 84.41 ms audio callback gap, telemetry still completed 245 transfers and 12 field replies, with a maximum transfer duration of 1.24 ms. That is evidence against a simultaneous control-USB outage, not proof of a particular host scheduling cause. The take is not a qualified 300-second acquisition. Audits are outside its frozen directory: `tmp/queued300_independent_audit.json` and `tmp/queued300_timing_correlation.json`. A larger explicitly requested WDM buffer requires a full repeat before acceptance.

Evidence resides under `XVF_MEASUREMENT_WORK/experiments/CAPABILITIES_20260905T221801_419147Z/QUEUED_15S` and `APP_QUEUED_PCM24_60S/telemetry/native`. Independent audit outputs are `tmp/queued15_streaming_audit.json` and `tmp/queued60_independent_audit.json`. For longer runs, use `audit_capture_streaming.py`; it parses each retry record once and retains only pending request state and successful-measurement statistics, avoiding an in-memory copy of the large retry log.

## What the firmware source actually establishes

The supplied XVF3800 3.2.1 software archive contains `precompiled/xshf/inc/BeClearCommon.h`. Lines 67–68 define `BECLEAR_SAMPLES_PER_FRAME = 256` and `BECLEAR_SAMPLE_FREQUENCY = 16000.0f`. Thus the processing block is **16 ms, or 62.5 blocks/s**. These are processing blocks, not a promise of 62.5 independent new direction estimates each second.

The framework source is available locally at `tmp/hardware_research/sources/modules/fwk_xvf/modules/xvf/src/`:

- `data_plane/audio_task.c:195` exchanges a block with the AEC when 256 samples have accumulated.
- `data_plane/shf_wrapper.c:549` calls `do_aec_control()` once per AEC loop, before the next audio block exchange and `SHF_Main_AEC()`.
- `data_plane/shf_wrapper.c:337–372` drains queued control packets, up to the queue depth, in that control window.
- `data_plane/shf_wrapper.c:130–140` reads angles and energies through the same library function, `SHF_Get_azimuths()`. Each standard control command returns one of the two arrays and discards the other.
- `data_plane/shf_wrapper.c:594–595` refreshes the output block's angle/energy arrays and smoothed direction after the AEC library call.
- `control_plane/servicer_init.c:50` sets the AEC queue depth to eight.
- `control_plane/servicer.c:278–311` implements the read handshake: enqueue a new command and return `SERVICER_COMMAND_RETRY`; return retry while that packet is waiting; copy the completed payload and free its packet when the host retries after completion.
- `control_plane/packet_queue.c` identifies pending reads by command ID, keeps their order, and can reclaim completed packets when the queue is reused. The adapter therefore keeps at most two distinct AEC reads outstanding and drains both before starting another pair. Concurrent control clients are unsupported during this test.

The public user guide §3.5.2 says the focused beams change relatively slowly and the free-running beam follows changes more quickly. There is no public per-value fresh-frame counter or device timestamp in these commands. Library smoothing/tracking and the content being played also govern how often a value changes. Reading a repeated value faster does not make it new information.

## Why an unmodified command list commonly gives about 31 pairs/s

The official host source `tmp/hardware_research/telemetry_host_source/src/command/command.cpp:100–145` completes a read before issuing the next command. It retries status 64 (`SERVICER_COMMAND_RETRY`) up to its bounded attempt count. It does not contain a deliberate 16 ms sleep. `device_access_usb.c` uses a synchronous vendor control transfer with a 500 ms transport timeout, not a 500 ms polling interval.

A first AEC request waits for a control window. After its successful response reaches the host, the next AEC request will normally reach the firmware after that window has finished and wait for the next 16 ms window. Therefore two serialized AEC reads tend toward one complete pair per 32 ms: about **31.25 pairs/s**. Existing completed captures measured approximately 31 Hz each for angles, energy, and selected direction, consistent with this explanation. This is an inference from code plus measured timing, not a universal rate specification.

`AUDIO_MGR_SELECTED_AZIMUTHS` belongs to the audio manager, a different resource. It often completes between AEC frame boundaries. Omitting that third command may not materially accelerate the two AEC commands. An unmodified list containing only `AEC_SPENERGY_VALUES` and `AUDIO_MGR_SELECTED_AZIMUTHS` needs only one AEC command per cycle and is worth benchmarking as a fast stock fallback. It supplies four beam energies and two selected directions, but not every individual beam direction.

## What the queued adapter changes

The adapter issues the first read for both distinct AEC commands before retrying either. Both may then be handled in one AEC control window. The source therefore supports testing a target near **62.5 pairs/s**, with actual throughput determined by host and USB timing. An occasional control window may split a pair. The adapter does not label pairs as atomic or assert they came from the same DSP block.

The adapter uses the actual official 32-bit `device_usb.dll` C functions:

```c
control_ret_t control_init_usb(int vendor_id, int product_id, int interface_num);
control_ret_t control_read_command(uint8_t resid, uint8_t cmd,
                                  uint8_t payload[], size_t payload_len);
control_ret_t control_cleanup_usb(void);
```

The supplied 32-bit DLL exports those three symbols. There is no need to replace the USB driver, compile firmware, or assume a C++ `std::string` ABI. C# P/Invoke uses the C calling convention and 32-bit process-compatible `UIntPtr` for `size_t`.

Command IDs are derived from the release's `aec_cmds.yaml` and the official command generator. Dedicated AEC commands start at offset 70, putting angles at 75 and energy at 80. The resource ID is 0x21. Every run independently searches the actual `command_map.dll` through its C metadata exports and checks each resource/ID/value type/read-only flag/count. The wire IDs are 203 and 208 after setting the read bit. Each response requests 17 bytes: one status plus four little-endian IEEE float32 values. Only transport success and device status zero produce a sample. Status 64 is retried; other statuses fail the run.

Offline inspection on this machine verified:

| Item | Verified value |
| --- | --- |
| device_usb.dll SHA-256 | `b42ca0ae704ef78be6a9468961b86dc2221a1d399b2d7b4158367dda2900afbf` |
| command_map.dll SHA-256 | `79c285d8a99544d5455da9a1cba94e29eb5aaef3f4b4155ad8da8a8415e659ba` |
| Angle map entry | resource 33, command 75, type 5 (radians), read only, 4 values, index 6 |
| Energy map entry | resource 33, command 80, type 3 (float), read only, 4 values, index 11 |
| Selected device | USB VID 0x20b1, PID 0x4f00, control interface 3 |
| QueryPerformanceCounter frequency | 10,000,000 ticks/s on this host |

`-InspectOnly` compiles and validates these library metadata exports without initializing or reading the USB device. No hardware test was performed by the implementation agent.

## Timing and evidence

`transactions.jsonl` retains **every** transfer attempt, its monotonic host request start/end, transport return, device status, and all 17 response buffer bytes. Buffer contents after a transport error are not treated as valid payload. `samples.jsonl` retains successful four-value replies, logical request bounds including retries, raw bytes and finite-value flags. NaN is preserved in raw bytes and represented as null with a false finite flag in JSON.

These timings improve on stdout line-arrival times by bracketing calls to the official C USB transport. They still include host scheduling and USB stack delays. They are not DSP sample timestamps or calibrated acoustic timestamps, and float32 text serialization does not add precision to the underlying measurements.

A warm-up pair is retained but excluded from measurement statistics, so an unfinished telemetry read left by an earlier forcibly stopped official batch cannot silently become the first measurement. At the requested duration or a stop-file request, the adapter completes the current pair before closing the official transport. Each pair is bounded by 1,000 attempts per command and two seconds, checked between transfers; one synchronous transfer can additionally consume its 500 ms timeout. Error cleanup retries only known pending reads, for a bounded interval. A failed cleanup is recorded and must not be counted as qualified acquisition.

## Commands for the parent operator

Run from the workspace; the new output directory must not already exist. Do not run another XVF control process concurrently.

```powershell
& 'C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe' `
  -NoProfile -NonInteractive `
  -File '.\measurement_app\experimental_queue\Run-Queued-Telemetry.ps1' `
  -OutputDirectory 'C:\absolute\new\queued15' -Seconds 15
```

Add `-Sequential` to benchmark the same official C transport with serialized reads. Add `-StopFile 'C:\absolute\new\stop.request'` to support a graceful external stop; create that file when stopping. The process also stops after its requested duration. The stdout includes live successful rows and a final result. Redirect or drain stdout and stderr when launching it beside an audio recording.

Use `-InspectOnly` instead of the output and duration arguments for an offline library inspection. The ordinary fallback is:

```powershell
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  -X utf8 -m measurement_app.telemetry --output 'C:\absolute\new\official30' --seconds 30
```

Acceptance requires matching command-map contracts, no transfer/device errors, successful cleanup, no pending reads at exit, full pairs, and no degradation of concurrent audio continuity. Report rates and worst gaps rather than a promised uniform frequency.
