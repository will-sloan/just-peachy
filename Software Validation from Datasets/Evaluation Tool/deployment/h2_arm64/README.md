# H2 Linux ARM64 preparation package

## Status and purpose

This directory prepares the AG-H2 primary pipeline for 64-bit Raspberry Pi OS
or Debian. It contains a lean pinned runtime, asset hashes, installation and
service scripts, a container recipe, audio/headless checks, and a conservative
2 GiB memory design.

Current classification: `PORT_REQUIRES_WORK`.

The ONNX component graphs and two fresh bounded full-pipeline pairs pass
Windows/x86-64 parity. The common factory now has an explicit
`H2_PORTABLE_ONNX_FP32` profile, and `run_h2_service.sh` launches that profile
through the headless microphone CLI. No Raspberry Pi was tested. Therefore
this package must not be described as `LINUX_ARM64_READY` or production-ready.

## Inputs

- a 64-bit ARM Linux host and Python 3.12;
- this source checkout;
- six manually staged, checksum-matching assets listed in
  `asset_manifest.json`;
- ALSA or PipeWire microphone access;
- optional X11/Wayland display for Tkinter.

Model weights are not included and are never downloaded at inference time.

## Outputs

- `/opt/just-peachy-h2/venv`: lean runtime environment;
- `/opt/just-peachy-h2/models`: operator-staged model assets;
- `/var/lib/just-peachy/h2_sessions`: local session output when systemd is used;
- JSON asset/platform diagnostics; and
- systemd logs under the local journal.

## Install on Raspberry Pi OS (ARM64)

```bash
cd "/opt/just-peachy/Software Validation from Datasets/Evaluation Tool"
chmod +x deployment/h2_arm64/install_linux_arm64.sh
chmod +x deployment/h2_arm64/run_h2_service.sh
deployment/h2_arm64/install_linux_arm64.sh --system-deps
```

The installer stops if the OS is not Linux ARM64, Python is not 3.12, or an
exact binary wheel cannot resolve. It does not build a different dependency or
download a model silently. If the Sherpa wheel does not resolve, use the
official embedded ARM64 build procedure, record that build identity, then
repeat validation.

For an offline install, pre-populate a wheelhouse on another ARM64-compatible
system and pass `--wheelhouse /path/to/wheels`.

## Stage and validate assets

Place files under this exact layout:

```text
/opt/just-peachy-h2/models/
├── sherpa_giga/
│   ├── encoder-epoch-99-avg-1.int8.onnx
│   ├── decoder-epoch-99-avg-1.onnx
│   ├── joiner-epoch-99-avg-1.int8.onnx
│   └── tokens.txt
└── h2_onnx/
    ├── redimnet2_b2_fp32.onnx
    └── pyannote_segmentation_3_0_fp32.onnx
```

Then run:

```bash
/opt/just-peachy-h2/venv/bin/python \
  deployment/h2_arm64/validate_arm64_package.py \
  --asset-root /opt/just-peachy-h2/models \
  --require-linux-arm64 \
  --output /tmp/h2-arm64-validation.json

/opt/just-peachy-h2/venv/bin/python -m app.h2_portability arm64-diagnostic \
  --require-linux-arm64 --require-graphs --probe-audio \
  --redim-onnx /opt/just-peachy-h2/models/h2_onnx/redimnet2_b2_fp32.onnx \
  --segmentation-onnx /opt/just-peachy-h2/models/h2_onnx/pyannote_segmentation_3_0_fp32.onnx
```

## ALSA, PipeWire, file, and headless checks

```bash
arecord -l
arecord -D plughw:CARD,DEVICE -f S16_LE -r 16000 -c 1 -d 10 /tmp/h2-capture.wav
aplay /tmp/h2-capture.wav
pactl list short sources
pw-cli ls Node

/opt/just-peachy-h2/venv/bin/python -m app.full_pipeline_demo devices
/opt/just-peachy-h2/venv/bin/python -m app.full_pipeline_demo file \
  --pipeline-id fullpipe_v1_ag_dr_ir --input /tmp/h2-capture.wav --pace 1
```

The scientifically relevant portable file path is the explicit ONNX profile:

```bash
mkdir -p /tmp/h2-enrollment /tmp/h2-file-result
/opt/just-peachy-h2/venv/bin/python -m app.h2_portability runtime-file \
  --pipeline-id fullpipe_v1_ag_dr_ir \
  --input /tmp/h2-capture.wav --duration-sec 10 --realtime \
  --output-root /tmp/h2-file-result \
  --enrollment-root /tmp/h2-enrollment \
  --redim-onnx /opt/just-peachy-h2/models/h2_onnx/redimnet2_b2_fp32.onnx \
  --redim-sha256 5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609 \
  --segmentation-onnx /opt/just-peachy-h2/models/h2_onnx/pyannote_segmentation_3_0_fp32.onnx \
  --segmentation-sha256 b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a
```

For headless use, do not launch Tkinter. Use the live/file CLI or systemd. For
GUI use, verify `DISPLAY` or `WAYLAND_DISPLAY`, `python3-tk`, scaling, and that
model work never blocks UI events. A container needs explicit audio-device and
socket mounts; a successful image build does not prove microphone access.

## systemd

Create the dedicated user and configuration deliberately, then install the
unit:

```bash
sudo useradd --system --home /var/lib/just-peachy --groups audio justpeachy
sudo install -D -m 0644 deployment/h2_arm64/h2-pipeline.service \
  /etc/systemd/system/h2-pipeline.service
sudo systemctl daemon-reload
sudo systemctl enable --now h2-pipeline.service
systemctl status h2-pipeline.service
journalctl -u h2-pipeline.service -f
```

Use `/etc/just-peachy/h2.env` for non-secret settings such as
`JP_H2_AUDIO_DEVICE`. Never put credentials there. The unit enforces a 1.65 GiB
soft and 1.85 GiB hard memory boundary and restarts on failure. Those limits
are design guards, not evidence that the pipeline fits.

## Container build

From the repository root:

```bash
docker buildx build --platform linux/arm64 \
  -f "Software Validation from Datasets/Evaluation Tool/deployment/h2_arm64/Dockerfile.arm64" \
  -t just-peachy-h2:arm64 --load .
```

The Dockerfile-specific ignore file excludes datasets, results, caches,
credentials, environments, and model weights. Mount `/models` and `/results`
at runtime. Real audio generally works more reliably as a host systemd service
than inside a container.

## Two-GiB design

The nominal 2048 MiB allocation is:

| Area | MiB |
|---|---:|
| OS/background services | 384 |
| Sherpa Giga ASR graph + working memory | 620 |
| Pyannote segmentation ONNX + working memory | 160 |
| one shared ReDimNet2 ONNX session | 240 |
| Python control, GUI, telemetry | 180 |
| bounded audio queues/session cache | 128 |
| safety headroom | 336 |

Required rules: use one shared ReDim session for diarization and identity; do
not load native Torch/Pyannote beside the lean service; keep queues bounded;
measure serial RSS, RTF, deadline misses, and thermal drift on the real Pi.

## Remaining qualification gates

- resolve all exact ARM64 wheels or record a reproducible Sherpa build;
- repeat numerical and E2E parity on ARM64;
- validate ALSA/PipeWire capture, device reconnect, and permissions;
- validate multiprocessing, filesystem paths, systemd restart, and shutdown;
- measure serial RTF/RSS on a real 2 GiB target and run a sustained stream;
- validate Tkinter behavior on the chosen desktop image.
