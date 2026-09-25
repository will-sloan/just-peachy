# A1 portable service in the common application

Purpose: run the qualified Parakeet Realtime EOU 120M service through the shared
Controller, continuous audio journal and final-only P0 punctuation. Inputs are
the exact private A1 ONNX bundle, nominal runtime binding, existing application
assets/configuration and saved mono 16-kHz PCM16 audio. Outputs are raw partial
and final events, separately formatted P0 text, ordinary captions and archives.
The original checkout, personal profiles and accepted releases are unchanged.

`n3_a1_service.py` packages the actual `a1_onnx_v2.py` implementation with only
its stream import made package-relative. `n3_a1_stream.py` carries the exact
reviewed ReferenceStream class; its unused non-A1 branch remains for source
parity and is never selected by the A1 owner. Normalized AST checks bind the
frontend, service and stream to the saved-audio parity implementation. Runtime
requirements are NumPy, SciPy and CPU ONNX Runtime; no Torch/NeMo import or
server is used on the A1 path. `LICENSE_NVIDIA_NEMO_A1.txt` carries the Apache-2.0
license. Preserve it and NOTICE_NVIDIA_NEMO_A1.md attribution when
redistributing this derivative. Model weights retain their separate terms.

`n3_a1_adapter.py` validates the selected model, export manifest, context,
precision, CPU provider, inference-only frontend and decoder settings before
loading. The service then validates every model/config asset hash. One resident
encoder/decoder pair and one P0 model serve independent scenes; each scene gets
fresh recurrent state. EOU resets only ASR state, never identity or the gallery.
The common tail policy holds one 80-ms chunk, pads the exact residual once and
delivers 16 explicit zero steps. Input sample accounting excludes synthetic
padding. P0 uses the unchanged Sherpa final formatter without loading Giga.

Closing the resident owner breaks its stream/model reference cycle and releases
ORT sessions even when an archived engine still references a closed stream.
The Controller drains its ASR/punctuation/archive owners before closing models.
Selecting the Baseline entry and starting a fresh session is the rollback.

The catalog identifies this implemented adapter with Controller validation
pending. Component parity and application-Python smoke passed; full-bank, GUI,
RAM/performance and ARM64/CM5 qualification are separate evidence requirements.
No physical device or microphone is needed for the checks below.

PowerShell, from the campaign worktree:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m unittest prototype.tests.test_n3_a1 prototype.tests.test_backend_catalog
```

CMD or Anaconda Prompt (no environment activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest prototype.tests.test_n3_a1 prototype.tests.test_backend_catalog
```

These six A1 tests check source parity, sample/tail/control replay, final-P0 raw
preservation, closed-owner model release, caption-only reuse and binding refusal.
They load no neural models. Actual private-desktop preparation and execution
are documented in the campaign's N3 README_A1_CONTROLLER.md. Its explicit
private runtime supplies the bundle directory; do not install research galleries
or model paths into the user's normal data root.
