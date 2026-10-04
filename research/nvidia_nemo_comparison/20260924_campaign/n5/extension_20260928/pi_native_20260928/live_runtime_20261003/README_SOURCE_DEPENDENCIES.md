# Public source and historical preparation dependencies

The public source is a reviewable code handoff, not an installed release or a
self-contained reproduction of the private campaign. Current selected runtime
module hashes are in [SOURCE_STATUS](SOURCE_STATUS.md). Production16 is staged, activated and the sole desktop release; actual idle/policy/normal Exit and independent readbacks passed. The public file list is explicit; do not add this directory recursively.
No profile, model, recording, gallery, transcript, owner registration, private
BASE.json or source-review/admission payload belongs in that list.

## What is included

| Source group | Included dependencies and intended use |
|---|---|
| Current runtime | Selected top-level modules, including admitted_identity.py and saved_source_metrics.py, with their current READMEs. Models, retained application/vendor code, profile descriptors and installed bindings remain separately pinned private installation inputs. |
| GUI-only15 source | gui_optional_policy_derivative_20261004/launcher.py, README_GUI_OPTIONAL_POLICY.md and test_gui_optional_policy.py preserve the exact changed GUI and host contract. The current top-level launcher/paired README match frozen15; other current guides can describe later outcomes. The separate UI-only comparison and production16 path certificate retain actual14 measurement provenance. |
| Identity repair preparation | prepare_identity_derivative.py, prepare_package.py and the five files in anonymous_identity_derivative_20261004: late_labels.py, admitted_identity.py, check_identity_correction.py, README_LATE_LABELS.md and README_IDENTITY_CORRECTION.md. The two nested READMEs preserve the exact reviewed build14 input bytes; top-level READMEs explain later actual results. |
| Saved-source build13 proof | Six historical files in saved_source_batch_derivative13: installed_engine.py, developer_replay.py, saved_replay.py, saved_source_metrics.py, test_saved_source_metrics.py and README_SAVED_SOURCE_METRICS.md. They preserve the source transformation and original proof. The current top-level test_saved_source_metrics.py is the parameterized proof entrypoint. |
| Optional build09/build11 source chain | The sibling optional_first_dispatch_20261003 runtime_derivative09, runtime_derivative09_bridge and runtime_derivative11_activity Python/Markdown files. These are explicit historical inputs to the selected preparers and tests, not current installation entrypoints. |
| Current optional dispatch | The sibling v09/launch_optional_action.py, receiver.py and README_CURRENT.md. The versioned directory name is historical; actual payload pins select the qualified package. |
| Current handoff builder | The sibling runtime_handoff_tools/build_handoff_v2.py and README_V2.md. The old builder and abandoned active-hour diagnostics are not required by current code and are excluded. |

Current external delivery tools include gui_policy_reuse, the GUI15 and
production16 preparers, and the production idle V2 action/controller/checker
with their paired READMEs. Their review/acceptance payloads remain private.

The sibling optional preparers create fresh derivative directories. Because the
historical outputs are included for review, rerunning those preparers in place
will correctly refuse an existing destination. Never remove those files merely
to make a historical command succeed.

## What cannot run from the handoff alone

All exact package preparers need the separately retained, hash-pinned predecessor
package, profile/reference capsule and review/admission inputs named in their
paired READMEs. For example, build14 preparation requires actual admitted13,
its prior builder and the private actual-row review; including the four repair
inputs does not replace those requirements. The original nested saved-source
test additionally expects private BASE.json. The current parameterized proof
still requires the exact frozen build12 predecessor through --base-package.
Historical optional checks similarly require their exact predecessor package.

These omissions are deliberate. Do not synthesize missing proof, relax a hash
check, or infer authorization from a source file being present. Older historical
helpers also preserve their original owner protocol and must not be substituted
for the current dispatcher during an active campaign. Private source-review
JSON, profile data and generated receipts stay outside both Git and the ZIP.

## Purpose, inputs and outputs

This document supports read-only source review and explicit publication planning.
Its inputs are the selected runtime source map and the final per-file Git/ZIP
whitelist. Its output is the distinction above between complete public source
dependencies and intentionally unavailable private execution inputs. It creates
no package, authority, native process or archive. Per-tool READMEs contain the
qualified interpreter, actual required inputs and bounded output locations.

## PowerShell

Read the current dependency/status documents before selecting a tool:

```powershell
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
Get-Content -LiteralPath "$N/README_SOURCE_DEPENDENCIES.md"
Get-Content -LiteralPath "$N/SOURCE_STATUS.md"
```

## Command Prompt and Anaconda Prompt

No environment activation or Python execution is needed to review the map:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
type "%N%\README_SOURCE_DEPENDENCIES.md"
type "%N%\SOURCE_STATUS.md"
```

Use the [final publication procedure](README_FINAL_PUBLICATION.md) only after
the final source and actual outcome review. One final ZIP is planned; no ZIP is
created by this dependency review.
