# XVF3800 Windows testing starter

This project runs repeatable XVF3800 tests on Windows: setup checks, device listing, baseline recordings, packed six-output capture, normal processed digital mono injection, and optional ASR-output injection.

The scripts use the Python interpreter inside this project directly. You do not need to activate a virtual environment, and the scripts do not depend on a globally available `python` command.

## Where the files are

On the current computer, the starter project is here:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF_3800_Testing_Starter
```

The important files and folders are:

```text
XVF_3800_Testing_Starter\
  README.md                    This guide
  SETUP_REPORT.md              Detailed setup and test report
  XVF3800_Install_and_Test_Guide.docx  Word installation and validation guide
  generate_setup_guide.ps1     Regenerates the Word guide
  setup_environment.ps1        First-run/rebuild setup script
  requirements.txt             Python dependencies
  config.json                  Local portable configuration
  config.example.json          Configuration template
  xvf_test_runner.py            Main Python test runner
  run_baseline.ps1              Baseline test
  run_casual_test.ps1           Profile-based recording
  run_packed_capture.ps1        Six-output packed capture
  run_asr_capture.ps1           Packed automatic speech-recognition capture
  run_digital_mono.ps1          Default processed duplicate/single substitute-mic injection
  select_wav_file.ps1           Windows WAV file-picker helper
  test_profiles\                Existing JSON test profiles
  .venv\Scripts\python.exe     Project-local Python after setup

XVF 3800 Testing\
  SampleAudio\test.wav          Safe project-provided mono test input
  XVF3800-Binary_v3_2_1\        XMOS host executable release files
  xvf3800_source_external_*\    XMOS Python source and tuning modules
  runs\                          Timestamped results; never delete automatically
```

The XMOS files currently discovered by setup are:

```text
XVF3800-Binary_v3_2_1\host_v3.0.0\win32\xvf_host.exe
xvf3800_source_external_241029_121941\sources\xvf_tools.py
```

The configuration stores these as project-relative paths. Therefore a different Windows username, drive letter, or clone location does not require manual path editing. Setup searches below the `XVF 3800 Testing` folder and fails clearly if a required release file is missing or ambiguous.

Generated `.venv`, setup logs, environment snapshots, config backups, Python caches, and `runs` are ignored by the repository-level `.gitignore`; they remain on the local computer but are not required in a GitHub copy.

## Copying the project to another computer

Copy the complete `just-peachy` folder, preserving the folders shown above. Do not copy only `XVF_3800_Testing_Starter` unless the XMOS binary and source release folders are copied beside it as well.

If the GitHub repository does not contain the XMOS release folders because of licensing or repository-size rules, copy those two release folders into the new computer’s `XVF 3800 Testing` directory before running setup. Setup cannot download or invent those vendor files.

Do not rely on copying `.venv` between computers. The setup script checks the copied environment and moves a stale or incomplete one to a timestamped backup before creating a new environment. It never deletes that backup.

The other computer also needs:

- Windows PowerShell.
- Python 3.10 available through `py -3.10`.
- The XVF3800 connected over USB, with its Windows audio devices installed.
- The XMOS release folders included in the copied project.

If Python 3.10 is missing, install Python 3.10 from python.org with the Python Launcher enabled. Do not use the Microsoft Store Python alias. Confirm it with:

```powershell
py -0p
py -3.10 --version
```

The required version is Python 3.10.x.

## First-time setup

Open a VS Code PowerShell terminal and paste:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF_3800_Testing_Starter"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_environment.ps1
```

On another computer, replace only the `Set-Location` path with the copied project location. The script then:

1. Verifies Python 3.10.
2. Creates or repairs `.venv` with `py -3.10 -m venv .venv`.
3. Moves incomplete or stale copied environments to timestamped backups.
4. Discovers `xvf_host.exe`, `xvf_tools.py`, and the XMOS `tuning` module.
5. Backs up an existing `config.json` and normalizes its machine-specific paths to relative paths.
6. Installs `requirements.txt` into `.venv`.
7. Writes `environment_freeze.txt` and setup logs under `setup_logs`.

NumPy is intentionally constrained below version 2 because the XMOS release packer is not compatible with NumPy 2.x.

## Verify software and audio devices

Run these commands from the starter project directory:

```powershell
& ".\.venv\Scripts\python.exe" --version
& ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" --help
& ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" devices --config ".\config.json"
```

The device command prints every PortAudio device and the selected XVF3800 input/output pair. It matches the configured `XVF3800 Voice Processor` text, prefers a common Windows API such as WDM-KS, prints the selected indices and complete names, and refuses to silently use the normal PC microphone or speakers.

For USB control checks, the setup report records the resolved `xvf_host.exe` path and direct host commands. An available XTAG can additionally be checked with the resolved `xflash.exe -l`; an XTAG is not required for the USB audio/control tests, and this project does not flash firmware.

## Run the tests

Run in this order when the XVF3800 is connected and visible in the device list:

```powershell
.\run_baseline.ps1
.\run_packed_capture.ps1 -Duration 10
.\run_asr_capture.ps1 -Duration 10
.\run_digital_mono.ps1
.\run_digital_mono.ps1 -Mode SingleMic -MicIndex 0
.\run_digital_mono.ps1 -ASROutput
```

The digital scripts now open a Windows file picker when `-MonoFile` is omitted. Browse to a folder and click a WAV file. A path can still be supplied directly, for example `-MonoFile "..\SampleAudio\test.wav"`. The original input is copied into the run folder and is not modified.

### What the tests mean

- Baseline records ordinary two-channel USB audio and saves firmware, geometry, parameters, device metadata, and logs.
- Packed capture records two 48 kHz USB channels, then unpacks six internal 16 kHz signals. The confirmed current output order is `far_end_reference`, `processed_auto_selected`, and amplified `mic0` through `mic3`. The order is recorded in each run’s metadata and channel map.
- ASR capture records the packed output with `AEC_ASROUTONOFF=1` and routes category 7/source 3 to the packed auto-selected output. Its second output is `02_asr_processed_auto_selected.wav`, the verified automatic speech-recognition output. This is ASR speech processing, not speaker-identity recognition.
- The default digital mono test places the same mono signal in MIC0, MIC1, MIC2, and MIC3 and captures the normal non-ASR processed auto-selected output as `02_processed_auto_selected.wav`. This is useful for data-path, gain, routing, normal processed-output, and firmware-regression testing. It is not genuine four-microphone spatial data and must not be used as a beamforming, DoA, dereverberation, geometry, or spatial-rejection test.
- Single-microphone injection places the mono signal in only the selected substitute microphone channel, captures the normal non-ASR processed output, and leaves the other substitute microphones silent.
- Add `-ASROutput` to `run_digital_mono.ps1` when the ASR-processed auto-selected waveform is required. It produces `02_asr_processed_auto_selected.wav`. `run_asr_capture.ps1` remains the dedicated packed ASR-output test. ASR here means speech-signal processing, not speaker-identity recognition.

The scripts save each run under:

```text
<copied project>\XVF 3800 Testing\runs\YYYY-MM-DD_HHMMSS_<test-name>\
```

Run folders contain `input`, `output`, `logs`, `metadata.json`, configuration and parameter snapshots, audio statistics, and SHA-256 data. Failed runs are retained for diagnosis.

## Repeatability comparison

Run the duplicate-microphone test twice, then compare the two run directories:

```powershell
& ".\.venv\Scripts\python.exe" ".\xvf_test_runner.py" compare-runs `
  "C:\full\path\to\first_run" `
  "C:\full\path\to\second_run"
```

The comparison reports duration, frame counts, peak, RMS, SHA-256, bit-identical status, and the maximum absolute difference over overlapping samples. Hardware-in-the-loop output can vary slightly; non-identical output is reported numerically rather than automatically treated as a failure.

## Existing profile recordings

To run a profile-based casual recording:

```powershell
.\run_casual_test.ps1 -Duration 30 -Profile ".\test_profiles\casual_asr_vs_raw_mic0.json"
```

Other profiles are in `test_profiles`. The runner resolves a relative profile path from the project directory, even when the wrapper is launched from another current directory.

## Troubleshooting

- `Python 3.10 is required`: install Python 3.10 and confirm `py -3.10 --version`.
- `xvf_host.exe was not found`: copy the XMOS binary release folder into the `XVF 3800 Testing` folder.
- `xvf_tools.py` or `tuning` was not found: copy the complete XMOS source release, not just the top-level script.
- The packed six-output wrapper prints a start-of-recording message before invoking the recorder. `run_asr_capture.ps1` does the same for the dedicated ASR capture.
- The digital mono script opens a WAV file picker when no `-MonoFile` is supplied. If the picker cannot open, provide the path explicitly.
- No XVF3800 audio device: reconnect the board, check Windows sound-device installation, then rerun `devices`.
- Multiple XMOS release files found: setup stops rather than selecting unpredictably; keep the intended release or update the discovery rule after reviewing the printed paths.
- XMOS Python imports are run with a process-local `PYTHONPATH` pointing at the discovered release tuning module. No unrelated PyPI package named `tuning` is installed.
- Do not change Windows volume to alter digital reference amplitude. Digital tests use numerical WAV data for repeatability.

For the detailed command history, hardware results, modified files, and known limitations, open `SETUP_REPORT.md`.

For a printable Word version of the setup and test instructions, open `XVF3800_Install_and_Test_Guide.docx`. If the guide needs to be regenerated after changing the workflow, run:

```powershell
.\generate_setup_guide.ps1
```
