# Retained release and evidence mapping

This mapping retains one baseline composition. There are zero newly accepted
N4 configurations; no optional candidate is a shipped Pi-ready alternative.
The later diagnostics do not alter the immutable baseline or its model hashes.
The authorized repository is https://github.com/will-sloan/just-peachy and the
campaign branch is codex/n1-foundation-20260924. Visibility and main are unchanged.

| Retained artifact | Source and packaging identity | Current readiness |
|---|---|---|
| Windows baseline; Start-N5-BASELINE.cmd | n1-common-ui-20260924-v1 at 2a8a2183c0050b6abf76ef27bbd803adad632a87; unchanged N1 installed code | N1 accepted offline scope plus N5 two-process Windows lifecycle smoke. Not complete N5 per-build/full-bank acceptance. |
| just-peachy-baseline-cm5-offline-v1.zip | Same N1 source; packaging n5-preparation-20260924-rc1 at 0817be1c0459d8e1f0bb4cd4c0df57b1960335f4 | Prepared local-only ARM64 wheel/model bundle. C-API ASR probe returned empty outputs under QEMU; full Python/GUI/model route is unverified. |
| nemo-speech-arm64-engineering-v1.tar.gz | n5-preparation-20260924-rc1; NATIVE_BUILD_RECEIPT.json pins native 97a15afa5caa9bce5baaa86c1184103877af4101 and toolchain | Six cross-built binaries and loader checks; A2 full first pass then repeat timeout, A3 unattempted. Not an accepted application composition. |
| Current analysis handoff | HANDOFF_SELECTION_V2.json plus the explicit status; HANDOFF_MANIFEST.json records the actual commit used | Partial checkpoint. Generated root GITHUB_BACKUP_RECEIPT.json verifies the remote branch and all selected bytes at packaging time. |

Both annotated source/preparation tags above were read again from the remote
on September 27. Their peeled commits still match this table. The historical
n5/GITHUB_BACKUP_RECEIPT.json records September 24 only; it is not the current
branch receipt. The compact packager creates a new receipt at the ZIP root,
without overwriting that historical file or inventing a self-referential commit.

## Exact baseline configuration and artifacts

Rechecked from the installed immutable release:

- Baseline composition ID: sha256:1a6be7490786a81d971c19ad35572b8c13c30993f7b8a7c1903f4b0617b6b1b5.
- config/backends.json: 22,102 bytes; SHA256 b94bbcd5a60deff6210dc5b2185f81e6e93638b8cb5439283eabecd9af718527.
- config/assets.json: 2,286 bytes; SHA256 2cd9bccf7d89bc4ee3c142c89167f3217325934ba48800ec3e7f1769c6b4cda7.
- ARM64_WHEEL_PUBLISHER.json: SHA256 f24f02434424f74ad6b845980cfaea3a42f9a82b1295ccd616f557b264721fb0.
- NATIVE_BUILD_RECEIPT.json: SHA256 ff864c110d00da373225506c1cb5bfc2a889a6e604d75c21c7aa3c04aac5faa8.

ARTIFACT_INDEX.json gives both private release archive paths, sizes and hashes.
The baseline ZIP is 310,867,595 bytes, SHA256
913e0a082e2de5f28e62f30503097cfb12f9008ed6d26fd1a803a7a2e8d32bbf.
The native engineering TAR is 1,874,637 bytes, SHA256
fabee1be06a4f833baf04b466ee8ff48b4947c71940a89771e125599f5927631.
These contain separate payloads and remain outside the analysis ZIP and GitHub.
The baseline's 31 declared bundle members were already read back and verified;
the later storage companion independently rechecked them. The immutable
archive's embedded historical documents are supplemented by current handoff
documents rather than rewritten in place.

## Reproduction and later installation

Use the source tag for the preserved baseline and its config/assets.json for
the eight model identities, filenames, byte sizes and deployment-relative paths.
The current offline package reuses the already-authorized shared model store;
this hash inventory does not itself provide fresh publisher download URLs.
Publisher reacquisition needs separately verified matching source/terms. Do not substitute
the current development catalog for the installed baseline catalog. The pinned
wheel source URLs/hashes are in ARM64_WHEEL_PUBLISHER.json, native source/tool
pins and build commands in NATIVE_BUILD_RECEIPT.json and README_ARM64.md.
The full Git branch contains the implementation and tests; the compact handoff
is an analysis selection, not a self-contained source checkout.

For an existing local archive, follow START_HERE.md, the separate read-only
storage preflight, INSTALL_CM5.md and UPDATE_ROLLBACK.md. Use actual device
identity and host keys after reconnection, stage and health-check before explicit
activation, preserve previous code, and keep personal data and model-specific
galleries outside releases. Do not run the Windows shortcut during an admitted
numerical worker. It opens idle on the user's desktop only when they invoke it.

No new candidate tag is warranted without N4 selection and per-build validation.
N2/N3 accepted component tags retain research lineage, not release readiness.
Any future derivative must preserve all failed attempts and execute matching
resource, state, timing, GUI and restart checks before receiving a release label.

## Additional stable-input Windows engineering previews

D1_ANONYMOUS_WINDOWS_CHECK_V1.json binds both fresh derivative receipts, all
source/model/runtime/audio hashes and paired normal process closure. E0 preview:
local/releases/n3-stable-asr-chunks-v1; encoder-free anonymous preview:
local/releases/d1-stable-asr-chunks-v1. Reproduce with
prepare_stable_asr_chunks_v1.py and the README of the same stem; the anonymous
parent is reproduced by prepare_d1_anonymous_v1.py. Both derive from accepted
N3 source with documented delivery/bypass changes; earlier immutable trees and
Git evidence are retained. No new N4 release profile is promoted.

Start-N5-NEMOTRON-REDIMNET.cmd and Start-N5-NEMOTRON-ANONYMOUS.cmd require the
verified pair and rehash its bound inputs. Both launch checks passed. They use
separate saved-file stores and share the existing front end. Full-bank,
automatic naming, ARM64 and CM5 remain unqualified. The public check and this
mapping are backed up at the next verified campaign commit; no new Pi-ready
package or tag is implied. Read README_D1_ANONYMOUS_PREVIEW_V1.md.
