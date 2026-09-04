# H2 ARM64 Linux handoff

## Current classification

`PORT_REQUIRES_WORK`

The common factory and headless service launch now support the explicit
`H2_PORTABLE_ONNX_FP32` profile. Windows/x86-64 component and bounded
full-pipeline parity pass. No Raspberry Pi or Compute Module has been tested,
so this is not `LINUX_ARM64_READY` and not a production-hardware claim.

## Package inputs and outputs

The package is `deployment/h2_arm64`. Inputs are a 64-bit Raspberry Pi OS or
Debian host, Python 3.12, the source checkout, checksum-matching Sherpa/ReDimNet/
Pyannote assets from `asset_manifest.json`, and optional ALSA/PipeWire audio.
Outputs are a lean virtual environment, local model directory, session results,
validation JSON, and systemd journal records. It never bundles or downloads
model weights.

The lean Python pins are in `requirements-linux-arm64.txt`. Native Torch
reference-only pins are separate and must not be loaded alongside the 2 GiB
service. The official PyPI simple indexes were checked on 2026-08-27: all eight
lean pins currently publish a CPython 3.12 Linux ARM64 wheel or a compatible
platform-independent wheel. ONNX Runtime and SoundFile set the highest observed
glibc floor at `manylinux_2_28`; the exact target image still has to resolve and
load them. This availability check is supporting preparation evidence, not an
installation or hardware result. Dependency status is:

| Area | Classification before hardware test |
|---|---|
| NumPy/SciPy/PyYAML/soundfile/psutil | `LIKELY_PORTABLE`, exact pinned ARM64 wheels are published |
| ONNX Runtime ARM64 wheel | `LIKELY_PORTABLE`, pinned CPython 3.12 ARM64 wheel is published; target graph loading remains unverified |
| Sherpa ONNX ARM64 wheel/runtime | `LIKELY_PORTABLE`, pinned CPython 3.12 ARM64 wheel is published; target model loading/performance remain unverified |
| sounddevice/PortAudio + ALSA/PipeWire | `PORT_REQUIRES_WORK`, device/permissions test required |
| Tkinter demo | `PORT_REQUIRES_WORK`, X11/Wayland image test required |
| H2 application/profile code | `LIKELY_PORTABLE`, desktop parity only |

## CM5 and Arduino UNO Q deployment targets

The final augmented package generates
`supplements/H2_HARDWARE_PLATFORM_ASSESSMENT.md` only after the serial resource
jobs have measured peak RSS, total RTF, checksum-bound model bytes, and run-cache
bytes. That report is deployment analysis; it does not alter the frozen desktop
scientific ranking.

Before target-hardware testing, the expected classifications are:

| Target | Expected classification | Intended role |
|---|---|---|
| Raspberry Pi Compute Module 5, 2 GB | `PORT_REQUIRES_WORK` for the lean FP32 ONNX candidate | Conditional first sizing target when final serial peak RSS is at or below 1700 MiB; exact no-swap audio/UI/RTF/soak proof required |
| Raspberry Pi Compute Module 5, 4 GB or greater | `LIKELY_PORTABLE` for the lean FP32 ONNX candidate | Safe fallback and development target; initial target if final serial peak RSS exceeds the 2 GB risk boundary |
| Arduino UNO Q, 4 GB RAM / 32 GB eMMC | `PORT_REQUIRES_WORK` | Secondary headless portability prototype |
| Arduino UNO Q, 2 GB RAM / 16 GB eMMC | `PLATFORM_BLOCKER` for the complete native pipeline; `PORT_REQUIRES_WORK` for a constrained lean-ONNX experiment | High-risk experiment only |

CM5 provides four Cortex-A76 cores at 2.4 GHz and broader RAM, eMMC, USB, I2S,
HDMI, and DSI options. The intended graphics workload is a simple 2D
transcript/status UI, so the CM5 2 GB versus 4 GB decision is driven primarily
by whole audio-pipeline RSS, model/runtime loading, audio services, queues,
startup/restart spikes, and sustained no-swap operation. Final desktop serial
RSS can keep 2 GB eligible, but only the exact CM5 2 GB image can prove that
4 GB is unnecessary. UNO Q provides four Cortex-A53 cores at 2.0 GHz, Debian
Linux, and an STM32U585 real-time microcontroller. The microcontroller may later
assist deterministic control or I/O, but it is not treated as a host for the
ASR, segmentation, or speaker models.

UNO Q documents USB microphone/headphone and HDMI operation through a powered
USB-C dongle plus carrier access to MIPI-DSI and analog audio. Concurrent power,
display, audio, reconnect, and sustained streaming behavior still require an
integrated board test. Generic Linux AArch64 Sherpa/ONNX execution is plausible,
but exact Debian ABI, wheels, graph operators, and end-to-end RTF remain
unverified.

The official UNO Q datasheet identifies ABX00162 as the 2 GB RAM / 16 GB eMMC
variant and ABX00173 as the 4 GB RAM / 32 GB eMMC variant. These are separate
sizing targets; a pass on the 4 GB board does not prove the 2 GB board. For CM5,
the sustained-stream qualification must use the intended production cooler and
enclosure. Raspberry Pi documents thermal throttling under heavy continuous
Raspberry Pi 5 loads, so an uncooled short run is not sufficient long-session
evidence.

No Qualcomm GPU, DSP, or HTP acceleration is credited. ONNX Runtime currently
documents QNN device execution for Android and Windows Qualcomm systems, not
the UNO Q Debian image. Any accelerated UNO Q path would need a separately
supported runtime, driver and operator audit, conversion/quantization study,
and end-to-end parity evaluation.

Official platform references:

- [Arduino UNO Q documentation](https://docs.arduino.cc/hardware/uno-q)
- [Arduino UNO Q datasheet and variant identifiers](https://docs.arduino.cc/resources/datasheets/ABX00162-datasheet.pdf)
- [Arduino UNO Q 2 GB / 16 GB eMMC specifications](https://store.arduino.cc/products/uno-q)
- [Arduino UNO Q 4 GB / 32 GB eMMC specifications](https://store.arduino.cc/products/uno-q-4gb)
- [Raspberry Pi Compute Module 5 specifications](https://www.raspberrypi.com/products/compute-module-5/)
- [Raspberry Pi 5 sustained-load cooling guidance](https://www.raspberrypi.com/news/heating-and-cooling-raspberry-pi-5/)
- [Sherpa-ONNX Linux AArch64 installation](https://k2-fsa.github.io/sherpa/onnx/install/index.html)
- [ONNX Runtime QNN execution provider](https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html)

## Install and validate

```bash
cd "/opt/just-peachy/Software Validation from Datasets/Evaluation Tool"
chmod +x deployment/h2_arm64/install_linux_arm64.sh
chmod +x deployment/h2_arm64/run_h2_service.sh
deployment/h2_arm64/install_linux_arm64.sh --system-deps

/opt/just-peachy-h2/venv/bin/python \
  deployment/h2_arm64/validate_arm64_package.py \
  --asset-root /opt/just-peachy-h2/models \
  --require-linux-arm64 \
  --output /tmp/h2-arm64-validation.json
```

The installer fails on a non-ARM64 host, wrong Python, or unresolved exact
binary wheel. For offline installation, create a wheelhouse on an equivalent
ARM64 system and use `--wheelhouse`. Record the resolved package versions,
Python/kernel/glibc identity, installer inputs, and wheelhouse SHA-256 values as
part of the target-hardware qualification. Retain that compact reconstruction
map; the environment and wheel payloads do not belong in the research ZIP.

## Runtime and service

`run_h2_service.sh` validates assets and launches
`python -m app.h2_portability runtime-live`, not the native reference. It passes
both graph paths and expected hashes explicitly and routes both ASR and the H2
ONNX worker through the lean ARM64 interpreter. `H2_REFERENCE` remains the
desktop/native default when the portable profile is not requested.

```bash
deployment/h2_arm64/run_h2_service.sh

sudo install -D -m 0644 deployment/h2_arm64/h2-pipeline.service \
  /etc/systemd/system/h2-pipeline.service
sudo systemctl daemon-reload
sudo systemctl enable --now h2-pipeline.service
journalctl -u h2-pipeline.service -f
```

Use `JP_H2_AUDIO_DEVICE`, `JP_H2_SESSION_SECONDS`, and the documented roots as
non-secret settings. Do not put credentials in the environment file.

## Required real-hardware gates

- resolve and record every exact ARM64 wheel or Sherpa build hash;
- validate both graph loads and numerical parity against native reference;
- repeat transcript/RTTM/cluster/identity/event parity on ARM64;
- validate ALSA and PipeWire enumeration, capture, disconnect/reconnect, sample
  rate handling, permissions, silence, and file replay;
- validate Linux multiprocessing, case-sensitive paths, service startup,
  restart, stop-during-inference, and clean shutdown;
- run one pipeline at a time for RTF, CPU, peak RSS, dropped frames, deadline
  misses, startup/warmup, and thermal drift;
- run sustained streaming and repeated sessions on the exact 2 GiB target;
- validate headless operation and, separately, Tkinter/GUI behavior;
- verify the XVF timestamp/energy/AoA interface remains no-effect until a later
  explicitly versioned integration.

Only after these gates may classification change from `PORT_REQUIRES_WORK`.
