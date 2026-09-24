# N3 NeMo reference route

`reference_asr.py` uses reviewed NVIDIA NeMo source cf724ac337d1ebc7d0dda1e23fb80916f52927a5
in the existing isolated Python 3.12 environment. It validates the exact A1/A2/A3
`.nemo` checksum before loading. Inputs are the variant, immutable model path,
source directory, supported right context and finite mono audio blocks. Outputs
are raw partial/final events and exact input counts; no truth/bias text is used.

A1 uses NVIDIA's actual EOU streaming service: [70,1] recurrent encoder caches,
80-ms steps, persistent RNNT decoder hypotheses, predicted EOU/EOB probabilities
and the official service's reset behavior. All token-piece deltas are retained,
including text following an EOU token. Tail policy: pad the last partial step,
then 16 explicit 80-ms zero steps (1.28 s) without counting them as captured audio.
This is an adapter flush policy to test, not a model-card latency claim. An empty
stream returns no text and does not invoke artificial speech. The official EOU
service resets its feature/encoder caches on predicted endpoints; correctness at
that boundary must be measured and is not established by importing this wrapper.

A2/A3 use the current official cache-aware pipeline, FP32 CPU, greedy decoding,
no ITN/NMT/boosting, and explicit English. A3 uses the trained left context 56;
A2 uses 70. Nominal right context 1 matches the native comparison; 0 is the sole
lower-buffer contrast. This reference holds one input chunk to mark the actual
last frame and preserve the short tail. Report that additional reference buffer.
Do not confuse this with the native GGUF route or target-device performance.

PowerShell syntax check:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe' -m py_compile research/nvidia_nemo_comparison/20260924_campaign/n3/reference_asr.py
```

CMD or Anaconda Prompt:

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe" -m py_compile research/nvidia_nemo_comparison/20260924_campaign/n3/reference_asr.py
```

Run actual inference only through the admitted N3 saved-audio runner after N2
releases numerical ownership. Do not change the original application environment.
