# Explicit two-thread native selection

`installed_engine.native_documents` integrates the separately pinned
`chunk52_threads2` profile with the shared live/saved engine. Inputs are the
immutable deployment binding, explicit RuntimeSelection and the already
verified embedding-specific runtime descriptor. Outputs are the model document,
the untouched sealed native document and the verifier token.

Only this experimental profile requires `binding.native_variants.chunk52_threads2`
with exactly `path` and `sha256`. The existing verifier checks the native build,
model and libraries and the exact completed numerical component comparison.
This does not authorize a session: ordinary production/qualification admission,
ownership and resource checks remain required. The retained `chunk52` option is
unchanged. No missing binding silently falls back to another native library.

Only native model/library/geometry/device fields are merged into the selected
model configuration. TitaNet's manifest, namespace and gallery configuration
remain those of the selected TitaNet descriptor. ReDimNet and anonymous selection
remain separate. The binder receives the original sealed native document, not
the merged embedding configuration. Session event and result receipts record
the exact native-variant provenance; sustained-real-time and quality flags remain
false until separately established.

## Host checks

The three focused tests cover TitaNet/native separation, absence of an explicit
pin, and preservation of the original profile. No model, native library, device,
audio or GUI is loaded. Run the CPU14/early-owner test wrapper in
[README_PIPELINES.md](README_PIPELINES.md#run-the-focused-tests), substituting
`test_native_selection` for `test_pipelines`. That wrapper contains the full
PowerShell and Command Prompt/Anaconda commands; use the existing environment.
The input is the synthetic descriptor fixture and the output is the unittest
result and its private host receipt.

For a qualified installed runtime, choose Nemotron, the explicit
`chunk52_threads2` profile, the desired embedding and Live or Saved in the
unified launcher, and enable experimental configurations. Direct native CLI
launches still require the finite current unit and hash-backed release described
in [README_RELEASE_AUTHORIZATION.md](README_RELEASE_AUTHORIZATION.md). The
isolated benchmark commands and exact measured scope are in
[README_NATIVE_VARIANT.md](README_NATIVE_VARIANT.md).
