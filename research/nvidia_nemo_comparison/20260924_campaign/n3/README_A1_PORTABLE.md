# A1 portable CPU service and strict parity

The initial a1servicev1 attempt is preserved. It exposed two concrete API
issues: `ASRModel.set_export_config(cache_support=True)` resets service
geometry to the model default, and exported decoder targets/lengths are INT32.
The fresh `_v2.py` derivatives restore the exact service override after export
setup, assert every streaming field remains equal, and require the observed
decoder dtypes. `a1_export_contract.py` implements that bounded correction;
`test_a1_export_contract.py` checks reset/reapply and unexpected geometry.
Use the v2 commands below for current work. No model tuning or weight change
is involved. The actual v1 receipt confirmed feature-processor training=True;
the deterministic A1 comparison will therefore require new inference.

Purpose: implement the actual recurrent EOU model with ONNX Runtime, NumPy and
SciPy, without Torch/NeMo or a server in the deployed service. Strict saved-audio component parity and an independent application-runtime
smoke now pass; Controller/target acceptance remains pending. Existing model
weights, frozen applications and earlier failed/default exports stay unchanged.

The official service sets an 80-ms advance (one encoder output, one dropped
cache frame), whereas the model's default export advances two outputs. These
states cannot share an export blindly. It also constructs a separate feature
processor whose training flag must be inspected. The new export/check sets that
processor to eval explicitly, preventing training-mode random dither. If the
old reference actually used dither, its A1 predictions require a fresh nominal
comparison before N4. This is an inference setting change, not neural training.

`a1_onnx_v2.py` implements the pinned 16-kHz mono PCM16 frontend, exact exported
window/filterbank, 25-frame feature history, encoder channel/time/length caches,
greedy RNNT with ten symbols per frame, blank-state handling, token-piece deltas
and predicted EOU/EOB resets. Vocabulary pieces come from the exact model; no
sentencepiece installation or expected transcript is needed at runtime.
`OnnxRecognizer` uses the reviewed ReferenceStream accounting and tail policy:
hold the final 80-ms chunk, pad it once, then deliver 16 explicit zero steps.
Raw words and control tokens retain the same event splitting. Names never gate
text. The component now has a packaged Controller/P0 adapter; its actual GUI checks
remain queued. See README_A1_CONTROLLER.md and README_A1_SCREEN.md.

`export_a1_service_v2.py` takes `--model`, `--source`, and fresh `--output`. It loads
the pinned reference service, records its original feature-processor training
flag, exports the actual service geometry, validates both graphs and writes
frontend buffers, vocabulary/config, BUNDLE.json hashes and RESULT.json.
`EXPORTED_SERVICE_BUNDLE_NOT_QUALIFIED` is deliberately not runtime acceptance.
Model weights and exported vocabulary/buffers remain private licensed assets.
Code scheduling is derived from the attributed Apache-2.0 helpers described in
README_A1_SERVICE.md; preserve LICENSE_NVIDIA_NEMO.txt and the weight license.

`check_a1_service_v2.py` adds `--bundle` and the predeclared four-cell
`--audio-manifest` (strict audio-only fields). It restores a fresh reference,
tests dynamic batch/window/cache shapes, then compares the independent portable
frontend, every encoder/cache output, recurrent decoder state, text/control
tokens and EOU probabilities on all four saved cells plus an exact replay.
Float tolerance remains rtol/atol 2e-4; integer lengths must match exactly.
Reference truth never enters either recognizer. Outputs are private RESULT.json
with hashes/errors and exception evidence on failure. No source is modified.
The reference/portable pair is a numerical conformance diagnostic; its memory
and duration do not count as a fair resource or target performance measurement.

`test_a1_onnx_v2.py` has six model-free tests for zero-feature history/log guard,
reset/storage independence, invalid chunks, blank prediction-state rollback,
EOU reset, and the exact symbol cap. It opens no audio device or GUI.

`prepare_a1_service_v2.py` creates a two-job CPU4 plan that reuses the original
source/model bindings and fixed four-cell audio panel. It accepts a parent N3
plan and fresh alphanumeric version, and outputs a private plan/worker spec.
It does not launch inference. The existing supervisor starts it only after
the currently healthy owner releases resources, with the original disk and
campaign limits. No new download, microphone, playback or Pi access occurs.

PowerShell, from the worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_onnx_v2.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_export_contract.py
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_service_v2.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --version a1servicev2
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1servicev2.json
```

CMD/Anaconda Prompt (explicit interpreter, no activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_onnx_v2.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/test_a1_export_contract.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/prepare_a1_service_v2.py --parent-plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-v4.json --version a1servicev2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/supervise_n3.py check --plan G:/Just_Peachy_N1/20260924_campaign/local/n3/plan-a1servicev2.json
```

Follow README_QUEUE.md's hidden `wait --plan` launch procedure once, after
verifying current PID/creation identities and excluding duplicate waiters.
Do not invoke the model export/check directly during another candidate's run.
Use new output versions after failure. Even a passing host service needs the
independent application-runtime smoke, deterministic paired comparisons,
Controller integration and separate ARM64 software checks before release.
