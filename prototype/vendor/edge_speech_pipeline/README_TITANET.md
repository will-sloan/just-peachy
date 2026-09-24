# TitaNet-Large E1 runtime

`titanet_embedding.py` provides real CPU embeddings from NVIDIA's pinned TitaNet-Large checkpoint. Its input is a mono float32 waveform at 16,000 Hz (at least 8,000 samples). Its output is an L2-normalized 192-element float32 vector and measured `last_embed_ms`. The minimum is an application policy, not a vendor quality guarantee. No padding/repetition adds speaker evidence. It does not open audio devices or perform enrollment itself.

The runtime accepts an exported bundle directory or `titanet_manifest.json`. It verifies the checkpoint identity, ONNX hash, frontend buffers, dimensions, preprocessing version, and normalization. The `namespace` property belongs in every gallery receipt; ReDimNet vectors are incompatible even though both have 192 elements. Thresholds require separate calibration.

The bundle is generated and tested by `research/nvidia_nemo_comparison/20260924_campaign/n2/embeddings/export_titanet.py`; see that folder's README for environment creation, exact export commands, inputs and receipts. The original `.edge-speech-env` requires no modifications: NumPy and ONNX Runtime are already available.

PowerShell, from the campaign worktree:

```powershell
$env:PYTHONPATH='G:\Just_Peachy_N1\20260924_campaign\worktree\prototype\vendor'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -c "from edge_speech_pipeline.titanet_embedding import TitanetEmbedding; import soundfile as sf; m=TitanetEmbedding(r'G:\Just_Peachy_N1\20260924_campaign\local\n2\titanet\export'); x,sr=sf.read(r'PATH_TO_PERMITTED_MONO_WAV',dtype='float32'); print(m.embed(x,sr).shape,m.last_embed_ms,m.namespace)"
```

Anaconda Prompt or Command Prompt:

```bat
set PYTHONPATH=G:\Just_Peachy_N1\20260924_campaign\worktree\prototype\vendor
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -c "from edge_speech_pipeline.titanet_embedding import TitanetEmbedding; import soundfile as sf; m=TitanetEmbedding(r'G:\Just_Peachy_N1\20260924_campaign\local\n2\titanet\export'); x,sr=sf.read(r'PATH_TO_PERMITTED_MONO_WAV',dtype='float32'); print(m.embed(x,sr).shape,m.last_embed_ms,m.namespace)"
```

Replace `PATH_TO_PERMITTED_MONO_WAV` with saved permitted audio. No conversion, gain adjustment, recording, playback, or personal gallery migration occurs. `close()` releases the session. The runtime is CPU-only; ARM64 hardware speed and memory remain untested until measured there.
