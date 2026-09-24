# Native conformance and CPU resources

The same script supports A1 reference conformance: replace `--binding` with
`--reference-model <pinned_A1.nemo> --reference-source <pinned_NeMo_source>` and
use the isolated NeMo Python given in README_REFERENCE.md, in either shell.
A1 runs empty, one-sample, short-tail, silence and repeated full saved audio.
The official A1 service has no manual force-endpoint API; this is recorded as
unavailable. Its predicted EOU and explicit tail flush remain active.

`probe_native.py` loads the exact admitted A2/A3 model and runs empty, one-sample,
short-tail, zero-silence, complete saved paragraph and repeated forced-endpoint
cases. The forced endpoint occurs at a fixed 12.34-second input position without
consulting reference words or speaker boundaries. Every sample and flush must be
accounted for. Fresh same-window repeats must produce identical final text.
Silence output is measured, not discarded. Ordinary and forced outputs are not
required to be identical because endpoint policy can affect decoding.

Inputs: frozen prototype, native binding and strict saved-audio manifest.
Outputs: private native events, per-case timing/RSS and RESULT.json. No training,
new speech generation or new acoustic bank is involved. CPU probe results must
run with one numerical candidate active; the result includes only process RSS,
not desktop/global GPU totals or Pi system memory.

PowerShell (`CMD/Anaconda` omit the leading `&`):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n3/probe_native.py --prototype G:/Just_Peachy_N1/20260924_campaign/local/releases/n3-common-v2/prototype --binding <NATIVE_CPU_BINDING.json> --audio-manifest G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation/REGRESSION_AUDIO_ONLY.json --output <FRESH_PRIVATE_PROBE_DIRECTORY> --cpu 4
```

Replace the two angle-bracket paths with the N3 plan's explicit binding/output.
Do not run before the numerical owner releases its slots. Use a fresh directory
after any change; failed evidence is retained.
