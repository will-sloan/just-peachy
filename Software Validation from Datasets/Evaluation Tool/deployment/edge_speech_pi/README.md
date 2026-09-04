# Raspberry Pi Edge Speech Deployment Handoff

This directory documents the generated ARM64 bundle for the clean Sherpa Giga + Pyannote Segmentation + ReDimNet2 pipeline. The runtime design, commands, inputs, outputs, Windows setup, and test procedure are maintained in `app/edge_speech_pipeline/README.md`.

Generate the local bundle from PowerShell or Anaconda Prompt:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
.\scripts\run_edge_speech_pipeline.ps1 export-pi ".\JustPeachyResearchSummaries\edge_speech_pi_bundle_v1"
```

On Raspberry Pi OS 64-bit, after copying the bundle and installing PortAudio and the optional Tk GUI (`sudo apt install libportaudio2 portaudio19-dev libsndfile1 python3-tk`), create a Python 3.11 virtual environment and install `requirements-linux-arm64.txt`. Run asset validation before any microphone test.

The bundle is currently `PORT_REQUIRES_WORK`, not ARM64-qualified. Required target tests are: package/wheel installation, hashes, ONNX numerical parity, Sherpa model load, ALSA/PipeWire device capture, 30-minute no-drop streaming, CPU/RAM/thermal telemetry, restart/recovery, and service startup. The Pi deployment must preserve the PCM16 journal and independent inference-lane design.

Inputs are microphone PCM or WAV audio plus optional local speaker profiles. Outputs are the PCM16 session journal, JSONL events, labelled transcript JSONL/Markdown, summary telemetry, and failures. Nothing uploads data.

Do not redistribute the staged graphs until all upstream licenses and the gated Pyannote provenance have been reviewed.
