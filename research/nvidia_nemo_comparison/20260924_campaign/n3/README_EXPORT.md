# A1 stateful ONNX investigation

`export_a1.py` uses NeMo's supported `set_export_config({'cache_support': True})`
and normal RNNT export. It preserves the encoder's three cache inputs/outputs,
the recurrent predictor/joint graph, source configuration and frontend buffers.
Inputs: pinned A1 `.nemo` and a fresh output directory. Outputs: ONNX artifacts,
full error evidence if blocked, and `EXPORT_RESULT.json`. A failed export is not
an accuracy result and must not cause substitution with offline Parakeet TDT.

The exporter tests encoder batches 1 and 2 and variable feature-window widths
through three carried-cache steps against FP32 NeMo. Every cache/output is
compared, with integer outputs exact and float tolerances 2e-4. This by itself is
not full portable ASR qualification: frontend, recurrent decoder, EOU/tail,
real-audio parity and ARM64 measurements remain separate acceptance gates.

PowerShell:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n3/export_a1.py --model G:/Just_Peachy_N1/20260924_campaign/local/n3/assets/parakeet_realtime_eou_120m-v1.nemo --source G:/Just_Peachy_N1/20260924_campaign/local/n2/source/Speech-cf724ac337d1ebc7d0dda1e23fb80916f52927a5 --output G:/Just_Peachy_N1/20260924_campaign/local/n3/a1-export-v2 --cpu 4
```

CMD or Anaconda Prompt:

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe" research/nvidia_nemo_comparison/20260924_campaign/n3/export_a1.py --model G:/Just_Peachy_N1/20260924_campaign/local/n3/assets/parakeet_realtime_eou_120m-v1.nemo --source G:/Just_Peachy_N1/20260924_campaign/local/n2/source/Speech-cf724ac337d1ebc7d0dda1e23fb80916f52927a5 --output G:/Just_Peachy_N1/20260924_campaign/local/n3/a1-export-v2 --cpu 4
```

Run under the campaign resource supervisor after N2 releases ownership. The
program records a blocked export as data and exits normally so the independent
A2/A3 comparisons can continue. Inspect its status, not just process exit code.
