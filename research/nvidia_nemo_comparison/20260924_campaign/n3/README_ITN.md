# Verified portable ITN subset

`build_itn_subset.py` compiles a finite restriction of NVIDIA's licensed English
cardinal grammar and checks every exported number form against its FST. It reads
only exact NeMo text-processing revision ddadfb2a38d2bc6b8cc6232c4f915eb60f500688.
It exports numbers 0..99 and a small measurement vocabulary. Numbers below 13
are changed only with an admitted unit, consistent with conservative standalone
cardinal handling. Unsupported large numbers, decimals, currency and names are
left unchanged. `n3_text.py` needs only the verified JSON at application runtime;
WSL/Pynini is a build dependency, not a Windows or ARM64 caption-server dependency.

Inputs: clean pinned NeMo source and output directory. Outputs: a verified JSON
lookup, FST and source/license/hash receipt. Build with the already installed WSL
distribution; do not enable Windows features or install a server. The isolated
WSL environment uses Python 3.14 and the PyPI Pynini 2.1.7 binary wheel, SHA-256
aaf2171cf5d744961d1080a680f1725807b4d179588a6ad3135596c2e0e06bc0,
installed with `python -m pip install --no-index --no-deps <wheel>`. Pynini and
NeMo grammar code use Apache-2.0; preserve their bundled notices.

The command is identical in PowerShell, CMD and Anaconda Prompt:

```bat
wsl.exe -d Ubuntu -- /mnt/g/Just_Peachy_N1/20260924_campaign/local/n3/itn-env/bin/python /mnt/g/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n3/build_itn_subset.py --source /mnt/g/Just_Peachy_N1/20260924_campaign/local/n3/itn/source --output /mnt/g/Just_Peachy_N1/20260924_campaign/local/n3/itn/export
```

For a fresh environment, the setup command is `wsl.exe -d Ubuntu -- python3 -m
venv --copies /mnt/g/Just_Peachy_N1/20260924_campaign/local/n3/itn-env` in all three
Windows shells. The source is an exact Git checkout; the build rejects changes.

`TextLayers.transform` independently toggles ITN. It retains original words and
character ranges for every replacement. Approved mappings require exact alias,
preferred form and independent context; they never use the active speaker.
WD-40 and similar-name cases are synthetic text-only fixtures, not seeded user
preferences or additional acoustic data. Unconstrained missing-word/grammar
rewriting and LLM reconstruction remain deferred.
