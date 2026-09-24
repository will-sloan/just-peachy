# Actual N3 GUI panel

`gui.py` adapts N2's reviewed isolated-desktop panel. It starts the real common
480x800 Tk interface and Controller, selects the actual A2/A3 backend through
the existing catalog, and uses D1/E0 research identity inference. It runs the
same boundary/interruption, short-turn and returning-speaker files for each
ASR. Closed-roster labels are explicitly assumed; open-query names retain the
uncalibrated Unknown behavior. It captures only its own known private window.
No desktop switch, input injection, microphone enumeration or playback occurs.

Inputs: frozen N3 prototype, N1 common UI source, exact CPU ASR/N2 bindings,
audio-only manifests and previously published E galleries. Outputs: GUI reports,
actual Tk presentation times, source/sample/drain/archive checks and private PNGs.
The panel uses one numerical CPU core and does not run alongside the N2 workers.
It measures applied Tk text, not physical scanout or microphone/CM5 latency.

PowerShell example (CMD/Anaconda use the same command without the initial `&`):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n3/gui.py --source G:/Just_Peachy_N1/20260924_campaign/local/releases/n3-common-v2/prototype --common-source G:/Just_Peachy_N1/20260924_campaign/local/releases/n1-common-v1/prototype --models-root C:/Users/amiri/JustPeachy/shared/models --runtime-config <N2_CPU_BINDING.json> --n3-runtime-config <N3_CPU_CATALOG.json> --regression-manifest G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/REGRESSION_AUDIO_ONLY.json --screen-manifest G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/AUDIO_ONLY.json --e0-gallery <PUBLISHED_E0_GALLERY.json> --e1-gallery <PUBLISHED_E1_GALLERY.json> --output <FRESH_PRIVATE_GUI_DIRECTORY> --cpu 4
```

Replace angle-bracket inputs with the hash-bound paths in the generated N3 plan.
Use `--prepare-only` to verify inputs without loading models or creating Tk.
`--cell A2_boundary` selects an explicit smoke cell; omission requests all six.
The inherited N2 IO helper is immutable and separately bound. The new panel has
its own module, environment admission and output directories; no N2 live source
or existing result is edited. An unused E1 gallery input is retained to preserve
the shared admission checks; this panel invokes only E0.
