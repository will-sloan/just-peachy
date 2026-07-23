# XVF3800 setup and validation report

Validation date: 2026-07-22 12:50 America/Toronto

Project: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF_3800_Testing_Starter`

## Environment

- Python was initially absent at 3.10. `py -0p` showed Python 3.14 and Anaconda Python 3.12. The exact Python 3.10 runtime was installed with `py install 3.10 --yes`.
- Installed runtime: Python 3.10.11.
- Virtual environment: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF_3800_Testing_Starter\.venv\Scripts\python.exe`
- `xvf_test_runner.py --help` and `py_compile` both completed successfully.
- Validated packages: NumPy 1.26.4, SciPy 1.15.3, sounddevice 0.5.5, soundfile 0.14.0, matplotlib 3.10.9. The NumPy upper bound `<2.0` is required by the XMOS release packer.
- Full package output is in `environment_freeze.txt`; pip logs are under `setup_logs`.

## Discovered tools and hardware

- Host tool: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF3800-Binary_v3_2_1\host_v3.0.0\win32\xvf_host.exe`
- XMOS dispatcher: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\xvf3800_source_external_241029_121941\sources\xvf_tools.py`
- XMOS Python module path: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\xvf3800_source_external_241029_121941\sources\modules\fwk_xvf\modules\tuning`
- `xvf_host.exe --help` and `--list-commands` returned exit code 0.
- USB `VERSION` returned `3 2 1` and `AEC_NUM_MICS` returned `4`.
- `AEC_MIC_ARRAY_TYPE` returned `2` (squarecular). Geometry returned four points at ±0.0333 m in X/Y.
- `USB_BIT_DEPTH` returned `16 16`; `I2S_INPUT_PACKED` and `AUDIO_MGR_OP_PACKED` were restored to `0` after tests.
- Windows exposed XVF3800 input index 34 and output index 33 as a common `Windows WDM-KS` pair. This is the pair selected by the runner and by the XMOS packed recorder.
- `xflash.exe` was discovered at `C:\Program Files\XMOS\XTC\15.3.1\bin\xflash.exe` but is not on PATH. Running it with `-l` returned exit code 0 and `No Available Devices Found`; no `P[0]` XTAG was exposed. No firmware was flashed.

The source release required a temporary process-level `PYTHONPATH` for `from tuning import packing`. The runner sets it only for the XMOS subprocess. The exact resolved import path is recorded in each run’s `logs\environment.txt` and `logs\commands.txt`.

## Project inventory

| File or directory | Purpose and result |
|---|---|
| `requirements.txt` | Runner dependencies; changed NumPy to `>=1.26,<2.0` after a reproducible XMOS packer failure under NumPy 2.2.6. |
| `setup_environment.ps1` | Python 3.10 check, incomplete-venv backup, venv creation, pip installation, freeze snapshot; now path-independent and uses the venv interpreter directly. |
| `config.json` / `config.example.json` | Project-relative workspace, host, tools, Python, audio, timeout, telemetry, XMOS module, API preference, and packed-output settings. The runner resolves paths from the config file location. |
| `xvf_test_runner.py` | Baseline, device selection, profiles, telemetry, packed capture, three digital modes, statistics, run metadata, restoration, and repeatability comparison. |
| `run_baseline.ps1` | Baseline wrapper; resolves its own project directory and checks the Python exit code. |
| `run_casual_test.ps1` | Profile recorder; resolves relative profiles against the project directory and checks prerequisites and exit code. |
| `run_packed_capture.ps1` | Six-output packed capture with `-Duration`; calls the venv directly. |
| `run_digital_mono.ps1` | Default normal processed duplicate-mic and `SingleMic -MicIndex 0..3` workflows; optional `-ASROutput`. |
| `test_profiles\*.json` | Existing routing profiles; preserved. |
| `SampleAudio\test.wav` | Existing project test input; copied into digital run folders, never overwritten. |
| `README.md` | Updated purpose, inputs/outputs, setup, commands, packed order, limitations, and troubleshooting. |

All project PowerShell wrappers resolve `$ProjectRoot`, set `$ErrorActionPreference = "Stop"`, call `.venv\Scripts\python.exe` directly, and fail on non-zero native exit codes.

The preserved profiles are `asr_vs_processed.json`, `casual_asr_vs_raw_mic0.json`, `processed_vs_raw_mic0.json`, `raw_mics_0_1.json`, and `raw_mics_2_3.json`. They use `AUDIO_MGR_OP_*` routing commands and do not assume packed input. `setup_environment.ps1` is the only script that invokes `py`, and it invokes only `py -3.10`; no test script calls a global `python` or `python3` command. The XMOS release’s own dispatcher is invoked with the configured `.venv` interpreter.

## Confirmed packed mapping

The release command `AUDIO_MGR_OP_ALL "12 0 3 0 3 2 6 3 3 1 3 3"` is ordered by the source as `(L_PK0, L_PK1, L_PK2, R_PK0, R_PK1, R_PK2)`. The unpacker emits `(L_PK0, R_PK0, L_PK1, R_PK1, L_PK2, R_PK2)`, producing:

`far_end_reference`, `processed_auto_selected`, `amplified_mic0`, `amplified_mic1`, `amplified_mic2`, `amplified_mic3`.

The input vector is `far_end_reference`, packing-convention silence, MIC0, MIC1, MIC2, MIC3. Digital vector generation prepends one common zero frame so the source unpacker’s independent leading-zero trim cannot shift the two USB channels relative to one another.

## Targeted modifications

Starter project files changed:

- `requirements.txt`
- `setup_environment.ps1`
- `config.json`
- `config.example.json`
- `xvf_test_runner.py`
- `run_baseline.ps1`
- `run_casual_test.ps1`
- `run_packed_capture.ps1`
- `run_digital_mono.ps1`
- `run_asr_capture.ps1`
- `select_wav_file.ps1`
- `README.md`
- `generate_setup_guide.ps1`
- `XVF3800_Install_and_Test_Guide.docx`

New project files:

- `SETUP_REPORT.md`
- setup and tool logs under `setup_logs`
- `environment_freeze.txt`

Portability follow-up completed after the hardware validation:

- `config.json` and `config.example.json` now use paths relative to the starter project instead of the original user profile.
- `xvf_test_runner.py` resolves relative config paths from the location of `config.json`, not from the current PowerShell directory.
- `setup_environment.ps1` searches the copied `XVF 3800 Testing` tree for unique XMOS release files, discovers the actual tuning module, and rewrites only the machine-specific config paths.
- `setup_environment.ps1` backs up `config.json` before normalization and moves stale or incomplete copied `.venv` directories to timestamped backups.
- `README.md` now documents the folder layout, copy requirements, setup, test commands, input/output behavior, and portability limitations.
- `generate_setup_guide.ps1` and `XVF3800_Install_and_Test_Guide.docx` provide a printable Word installation and validation guide with copy-paste commands and expected outputs. The DOCX is generated directly as a standard Word package and does not require Word automation to be running.
- `run_packed_capture.ps1` now prints a clear message immediately before recording begins.
- `run_digital_mono.ps1` opens a Windows WAV file picker when `-MonoFile` is omitted; explicit paths remain supported.
- The default substitute-microphone digital test uses the normal processed auto-selected route (`AUDIO_MGR_OP` category 6/source 3) and produces `02_processed_auto_selected.wav`.
- Adding `-ASROutput` enables `AEC_ASROUTONOFF=1` and uses the verified ASR route (`AUDIO_MGR_OP` category 7/source 3), producing `02_asr_processed_auto_selected.wav`.
- Added `run_asr_capture.ps1` and the `asr-capture` runner command for packed automatic speech-recognition output capture.

ASR packed-channel correction:

- The prior ASR command placed category 7/source 3 in `L_PK1`, which unpacked to output channel 3 while the files were labeled as though it were output channel 2.
- The ASR command is now `12 0  3 0  3 2  7 3  3 1  3 3`. Category 7/source 3 is placed in `R_PK0`, which unpacks to the second output channel and matches `02_asr_processed_auto_selected.wav`.

Targeted XMOS source-release compatibility changes:

- Added the existing `packing.py` to the `xvf_tools.py` dispatcher.
- Made `packed_recorder.py` and `doa_plot.py` return normal exit codes for `--help`.
- Made `host_utils.py` invoke Windows host commands without `shell=True` path splitting, and retry transient USB re-enumeration failures.
- Made `packed_recorder.py` avoid rebooting the device when `USB_BIT_DEPTH` already matches, and wait ten seconds after PortAudio/WDM restart.

No firmware files or firmware parameters were permanently changed. Temporary packed input/output settings were recorded before each test and restored afterward. Existing failed and successful run folders were retained.

## Commands and results

Key commands executed, with complete output in setup logs and run logs:

```powershell
py -0p
py -3.10 --version
py install 3.10 --yes
py -3.10 -m venv ".\.venv"
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
& ".\.venv\Scripts\python.exe" -m pip install -r ".\requirements.txt"
& ".\.venv\Scripts\python.exe" -m pip freeze > ".\environment_freeze.txt"
& ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" --help
& ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" devices --config ".\config.json"
& ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" compare-runs "<run-a>" "<run-b>"
```

The portability validation was run from this project and completed successfully. The normalized config contains `..`, `../XVF3800-Binary_v3_2_1/...`, and `../xvf3800_source_external_.../...` paths; Python resolved them to the expected current files. Python imports, runner help, device listing, `xvf_host.exe --help`, all three XMOS tool help commands, and USB `VERSION`, `AEC_NUM_MICS`, and `USB_BIT_DEPTH` checks all returned exit code 0. The XVF3800 audio pair selected was input index 34 and output index 33 through Windows WDM-KS.

The initial requirements install exposed a NumPy 2.2.6 overflow in XMOS `packing.py`; the requirements constraint was added, NumPy 1.26.4 installed, and the digital workflows then passed.

Hardware workflow results:

- Baseline passed: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_124903_windows_baseline`
- Portable wrapper baseline passed when launched from the parent directory: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_130657_windows_baseline`. Its metadata, parameter snapshots, command logs, stdout/stderr logs, environment, and configuration snapshot were verified.
- Six-output packed capture passed for 10 seconds: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_123916_packed_six_channel_capture`. Raw output is 48 kHz stereo; canonical unpacked output is 16 kHz, six channels; all six named channels exist and MIC channels are non-zero.
- Historical far-end/reference validation passed: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_124940_digital_far_end_reference_final`. This retained run is not part of the current wrapper workflow.
- Duplicated substitute microphones passed: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_124341_digital_mono_duplicate_4mic`. Channel map duplicates the mono input to MIC0–MIC3 and explicitly records the spatial-testing limitation.
- Repeat duplicate run passed: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_124515_digital_mono_duplicate_4mic_repeat`.
- Single MIC0 substitution passed: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_125027_digital_mono_single_mic0_final`.
- ASR packed capture validation passed for 5 seconds: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_151027_asr_capture_validation`. It produced `02_asr_processed_auto_selected.wav` at 16 kHz, with non-zero audio and `asr_output_enabled: true`. The follow-up metadata route is recorded by the current code as `AEC_ASROUTONOFF=1`, category 7/source 3.
- ASR route-metadata validation passed for 3 seconds: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_151319_asr_capture_route_metadata_validation`. Metadata explicitly records `AEC_ASROUTONOFF=1`, category 7/source 3, the `--asr_output` flag, the ASR output filename, and exit status 0.
- Substitute-microphone ASR-output validation passed: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_151113_digital_mono_asr_output_validation`. It used duplicate MIC0-MIC3 input, produced the ASR-named output, exited 0, and restored parameters with no warnings.
- Packed start-message validation passed for 3 seconds: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_151208_packed_start_message_validation`. The terminal printed `Starting packed six-output recording for 3 seconds...` before completion.
- Repeatability comparison: `C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\runs\2026-07-22_124515_digital_mono_duplicate_4mic_repeat\repeatability_comparison.json`. The two hardware-in-the-loop outputs were not bit-identical: sample counts differed by one frame and maximum overlapping sample differences were approximately 1.99994 for the unpacked/processed files and 1.37994 for amplified MIC0. This is reported numerically, not classified as an automatic failure.

Failed attempts were retained for diagnosis, including the initial quoted-path failure, a transient USB re-enumeration failure, a marker-alignment failure before the common-zero-frame fix, and the NumPy 2.x packer failure.

## How to run next time

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF_3800_Testing_Starter"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_environment.ps1
& ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" devices --config ".\config.json"
.\run_baseline.ps1
.\run_packed_capture.ps1 -Duration 10
.\run_digital_mono.ps1 -MonoFile "..\SampleAudio\test.wav"
.\run_digital_mono.ps1 -MonoFile "..\SampleAudio\test.wav" -Mode SingleMic -MicIndex 0
.\run_digital_mono.ps1 -MonoFile "..\SampleAudio\test.wav" -ASROutput
```
