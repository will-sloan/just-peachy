# Isolated native Windows NeMo reference environment

This environment is shared by the E1 TitaNet and D1 Nemotron reference checks. It is separate from the application Python and frozen N1. Python is the already-installed Anaconda 3.12.7. Official current NeMo is needed for Nemotron V3; PyPI 3.0.0 was inspected but is not the installed code because its older Sortformer implementation lacks the required V3 route.

Source: <https://github.com/NVIDIA-NeMo/Speech/tree/cf724ac337d1ebc7d0dda1e23fb80916f52927a5>. Source ZIP SHA256: `b7484ac574876f3f5ce990c8d3f5335780ac7f002c1534ea73fcf3bcdad521ce`. `setup.py`, `pyproject.toml`, speaker model, feature preprocessing and model imports were reviewed before execution. Source setup uses setuptools; style checker subprocesses run only if explicitly requested. No administrator, editable install, custom remote Hugging Face code or GPU package was needed for Torch. NeMo requires small CUDA Python bindings in its dependency metadata; inference is forced to CPU and the bindings do not imply GPU use.

The two installation JSON reports in `local/n2/logs/torch-install.json` and `nemo-install.json` contain resolved URL/hash/version records. `reference-requirements.txt` pins the final environment, excluding NeMo's separately pinned source. Both TitaNet and Sortformer model classes imported successfully on Windows; `nemo-import.log` records this. No third-party source patches or dependency stubs were used.

PowerShell recreation in a new empty environment path (the example reuses the documented campaign path only if it does not yet exist):

```powershell
$root='G:\Just_Peachy_N1\20260924_campaign'
$local="$root\local\n2"
& 'C:\Users\amiri\anaconda3\python.exe' -m venv "$local\nemo-py312"
Invoke-WebRequest 'https://codeload.github.com/NVIDIA-NeMo/Speech/zip/cf724ac337d1ebc7d0dda1e23fb80916f52927a5' -OutFile "$local\wheels\nemo-speech-cf724ac3.zip"
if ((Get-FileHash "$local\wheels\nemo-speech-cf724ac3.zip").Hash.ToLower() -ne 'b7484ac574876f3f5ce990c8d3f5335780ac7f002c1534ea73fcf3bcdad521ce') { throw 'NeMo source hash mismatch' }
Expand-Archive "$local\wheels\nemo-speech-cf724ac3.zip" "$local\source"
$env:PIP_CACHE_DIR="$local\pip-cache"
& "$local\nemo-py312\Scripts\python.exe" -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
& "$local\nemo-py312\Scripts\python.exe" -m pip install -r "$root\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\embeddings\reference-requirements.txt"
& "$local\nemo-py312\Scripts\python.exe" -m pip install --no-deps "$local\source\Speech-cf724ac337d1ebc7d0dda1e23fb80916f52927a5"
```

Anaconda Prompt / CMD, after the source download and SHA check above (PowerShell can be launched from either prompt):

```bat
set ROOT=G:\Just_Peachy_N1\20260924_campaign
"C:\Users\amiri\anaconda3\python.exe" -m venv "%ROOT%\local\n2\nemo-py312"
set PIP_CACHE_DIR=%ROOT%\local\n2\pip-cache
"%ROOT%\local\n2\nemo-py312\Scripts\python.exe" -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu
"%ROOT%\local\n2\nemo-py312\Scripts\python.exe" -m pip install -r "%ROOT%\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2\embeddings\reference-requirements.txt"
"%ROOT%\local\n2\nemo-py312\Scripts\python.exe" -m pip install --no-deps "%ROOT%\local\n2\source\Speech-cf724ac337d1ebc7d0dda1e23fb80916f52927a5"
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set CUDA_VISIBLE_DEVICES=
set WANDB_MODE=disabled
"%ROOT%\local\n2\nemo-py312\Scripts\python.exe" -c "from nemo.collections.asr.models import EncDecSpeakerLabelModel, SortformerEncLabelModel; import torch; print(torch.__version__)"
```

Purpose/input/output: these commands install a reproducible local CPU reference dependency environment from pinned packages and official source. They produce interpreter/site-packages files and pip cache, no model/audio outputs. Use `export_titanet.py` for model export. Reserve at least C: 50 GiB / G: 75 GiB before installation; observed free space after installation preparation was C:137 GiB / G:129 GiB. No existing environment is deleted or modified by this workflow.
