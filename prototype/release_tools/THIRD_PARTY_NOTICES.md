# Third-party release notices

Task12 adds project-authored finite review code using existing Python difflib,
Sherpa and the unchanged pinned models. No external model, dictionary, tokenizer,
conversion or runtime was installed. Qwen3-0.6B and llama.cpp are reference-only
conditional candidates, not packaged artifacts. Their upstream licence families
do not qualify an unspecified checkpoint or quantized derivative. Exact retained
asset hashes, runtime versions and inherited notices are bound in
`../docs/UIITER2_12_DEPENDENCIES.json`. Local corpus audio remains private.

Task10 adds one optional **DPDFNet baseline** ONNX artifact from the official
Sherpa speech-enhancement release, using the already installed Sherpa1.13.4
streaming runtime. No package upgrade or extra transitive dependency.
Its exact publisher SHA, author/code revision, model-card revision, distinct
export provenance and obligations are in `../docs/UIITER2_10_DEPENDENCIES.json`.
DPDFNet author code and model card declare Apache-2.0; the original author
licence is retained as `licenses/DPDFNet-Apache-2.0.txt`. Preserve applicable
copyright/NOTICE, licence and modification notices when redistributing.
The official Sherpa export differs from the Hugging Face export; no local
conversion, binary equivalence or reproducible-build attestation is asserted.
Weights, runtime code and training/source data remain distinct artefacts.
This is a permissive candidate, not blanket legal clearance for all project
models or data. Optional model binaries remain in the external hash store;
task08's immutable archive is unchanged. Test corpus WAVs/vectors stay private.

Task09 adds project-authored script-evidence selection/review code using the
existing runtime and frozen assets. No third-party library, model, tokenizer,
dictionary, conversion or driver was installed or copied. Its source/provenance
and reference-only licence review are in `../docs/UIITER2_09_DEPENDENCIES.json`.
The CMU ARCTIC test audio stays in the existing private/local dataset; it is not
bundled into the release. No new redistribution clearance for existing models
or datasets is asserted. The task08 immutable archive retains its own historical
notices and does not include this local optional extension.

Task08 introduces only project-authored Python contracts, tests and documentation.
No dependency, model, wheel, dictionary, driver binary or vendor source was newly
downloaded or added to the application. The 13 existing ARM64 wheels were
rehashed; `../docs/UIITER2_08_DEPENDENCIES.json` retains their provenance ledger
and the local matching-vendor guide hashes. Prior licence obligations below and
the separate model/data notices remain unchanged. Reference-only hardware
documentation is linked, not bundled as a new licensed driver implementation.

Task 07 adds no third-party package, model, dictionary, tokenizer or conversion.
Its 24-word vocabulary is original project-authored text; no word-frequency
corpus was imported. The spelling heuristic uses Python's existing standard
library and original bounded character-comparison code. Project rights remain
unchanged; no new public distribution licence is asserted.

Reviewed reference-only upstream sources: [Sherpa hotword documentation](https://k2-fsa.github.io/sherpa/onnx/hotwords/index.html),
[SymSpellPy MIT licence](https://raw.githubusercontent.com/mammothb/symspellpy/master/LICENSE)
and [RapidFuzz MIT licence](https://raw.githubusercontent.com/rapidfuzz/RapidFuzz/main/LICENSE).
Neither optional library nor its transitives/dictionaries was installed or
copied. Their code licences would not independently clear a dictionary corpus.
`../docs/UIITER2_07_DEPENDENCIES.json` binds the existing runtime/model assets,
installed Sherpa API and original vocabulary. Actual inference remains greedy;
no qualified matching ASR BPE vocabulary was introduced. Existing notices below
and distinct model/data obligations remain in force.

`licenses/` contains original licence/notice files copied from the exact publisher wheels selected in `requirements-arm64.lock`. The external wheelhouse retains each wheel's complete metadata and embedded libraries. `evidence/ARM64_WHEELS.json` records publisher URLs, hashes, versions and licence declarations. A hash is an integrity check, not a new licence grant or publisher signature.

Application and vendored project source retain their original rights. No new public distribution licence for project source is invented here. Neural weights are separate existing local assets; the application archive includes their hashes and expected filenames, not model binaries or a transfer of model rights. Review each upstream model's actual licence before distributing models outside the user's existing private project.

The matched XMOS host executable, USB library and firmware command map are not distributed by this release. A separately built and verified ARM64 host bundle is required for Linux hardware use; follow the vendor sources in PI_DEPLOYMENT_WORKFLOW.md. No XVF firmware is flashed by these tools.
