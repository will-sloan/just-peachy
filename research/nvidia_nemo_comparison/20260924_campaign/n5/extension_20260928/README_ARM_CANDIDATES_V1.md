# Cached ARM build and quantization candidate audit

Purpose: establish what the preserved build recipe and existing model files actually contain before proposing Pi acceleration. This is a read-only configuration/source/metadata audit. It does not build, execute, benchmark, disassemble or qualify the ARM64 runtime.

Inputs: N5 `NATIVE_BUILD_RECEIPT.json`, the hash-pinned local ggml source ZIP and the existing content-addressed D1/A2/A3 GGUF files. It verifies archive/model SHA256, reads the exact CMake and ARM feature-guard source, and parses bounded GGUF metadata/tensor descriptors without loading tensors. The source excerpts include the enum meanings needed to interpret the numeric GGUF types. It checks the extension window and pins itself to CPU14. Run after the numerical/preflight owner closes so it does not compete with a resource census or timing measurement.

Output: a fresh, small private JSON receipt with build/source/model bindings, recorded configure options, selected source lines, model precision metadata, tensor type counts and explicit scope limits. No audio/profile data is accessed; no WSL, target, GPU, download, training, conversion or model inference is launched. The report is an input to a later separately admitted, target-feature-verified build comparison. Preserve the generic baseline and retest state/EOF/accuracy before adopting an optimized artifact. Never equate a smaller quantized file with measured runtime RAM or speed.

PowerShell / Anaconda PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B audit_arm_candidates_v1.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\ARM_CANDIDATES_AUDIT_V1.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B audit_arm_candidates_v1.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\ARM_CANDIDATES_AUDIT_V1.json"
```

The existing environment is used directly; no package installation or activation is needed. The command refuses an existing receipt. A later justified audit uses a new output path and preserves the previous result. This does not clear the full-source ARM64 conformance or Python/Tk/E0/punctuation/GUI gates.
