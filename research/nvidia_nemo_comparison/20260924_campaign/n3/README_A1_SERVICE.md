# Package-free official A1 reference service

`a1_service.py` and `a1_features.py` are an attributed extraction of NVIDIA's
Apache-2.0 streaming ASR service and feature-cache helper from NeMo revision
cf724ac337d1ebc7d0dda1e23fb80916f52927a5. Exact original and local hashes are in
A1_SOURCE_EXTRACTION.json; LICENSE_NVIDIA_NEMO.txt preserves the license.
Original NVIDIA copyright/license headers remain in both files.

Changes: one service import now resolves the adjacent feature helper; a local
provenance comment was added. Encoder/feature-cache handling, RNNT hypotheses,
token-piece output and predicted EOU/EOB resets are unchanged. The original
parent package requires the separate Pipecat voice-agent client even though
these two files use only NeMo, Torch, NumPy and OmegaConf. No Pipecat/server/audio
stack is installed. This extraction is not a claim of supported native GGUF A1.

Inputs are the exact local A1 `.nemo` and waveform chunks, through
`reference_asr.py`; outputs are the official ASRResult with deltas and EOU/EOB
metadata. These helper files have no standalone command-line entry point.

PowerShell import-only check, no model loaded:

```powershell
$env:PYTHONPATH='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n3;G:\Just_Peachy_N1\20260924_campaign\local\n2\source\Speech-cf724ac337d1ebc7d0dda1e23fb80916f52927a5'
& 'G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe' -B -c 'from a1_service import NemoStreamingASRService; print("imported; no model loaded")'
```

CMD / Anaconda Prompt:

```bat
set PYTHONPATH=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n3;G:\Just_Peachy_N1\20260924_campaign\local\n2\source\Speech-cf724ac337d1ebc7d0dda1e23fb80916f52927a5
"G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe" -B -c "from a1_service import NemoStreamingASRService; print('imported; no model loaded')"
```

Actual inference must use the bound N3 plan. These imports alone do not establish
reference correctness, export support, quality, throughput or target performance.
