# Optional alignment eligibility

`inspect_configs.py` reads only `model_config.yaml` from the three local `.nemo`
archives, without importing a model, extracting weights or running inference.
Input: the verified N3 model directory. Output: small JSON with model class,
encoder/decoder class, configuration hash and top-level CTC configuration keys.
No transcript, gallery or audio enters this check. Configuration inspection
cannot establish runtime forced-alignment compatibility.

PowerShell:

```powershell
& 'G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n3/inspect_configs.py --model-directory G:/Just_Peachy_N1/20260924_campaign/local/n3/assets --output G:/Just_Peachy_N1/20260924_campaign/local/n3/MODEL_HEADS.json
```

CMD / Anaconda Prompt:

```bat
"G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/inspect_configs.py --model-directory G:/Just_Peachy_N1/20260924_campaign/local/n3/assets --output G:/Just_Peachy_N1/20260924_campaign/local/n3/MODEL_HEADS.json
```

The inspected candidates are RNNT models. No compatible CTC head has been
verified. The optional E-only known-script alignment/quality-window ablation
is deferred; this does not stop the essential ASR comparisons. No Q text is
used to select E windows and no phonetic training claim is made.
