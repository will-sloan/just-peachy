# Fixed research galleries and actual naming modes

Purpose: prepare the predeclared N2 15-second clean-source research references
for N4, with encoder-specific vectors and the exact application resolver for
each catalog tuple. This is gallery and mode-method preparation. It does not
establish coupled audio execution, Controller/widget parity, accuracy, visible
name latency, resource fit or accepted N4 matrix cells.

Inputs: accepted E0/E1 component receipts and their bound extraction results;
the runtime-safe gallery indexes, original/published gallery bytes; the immutable
n4-catalog-v3 source receipt and catalog. `prepare_mode_galleries.py` derives all
input paths from existing receipts. It rehashes every source file, verifies the
safe-index condition whitelist, joins each roster to the accepted extraction,
checks unchanged vector/profile payloads, the E0 metadata-only preprocessing
alias, exact namespace and the original reject-all gate transformation. It
returns no evaluator Q scores or reference labels to the predictor. No C fitting
or Q selection occurs. The primary tier is fixed in SCORING_PLAN.md.

Four conditions are retained: none, open, selected-plus-Unknown, closed. The
application modes are anonymous_conversation, enrolled_names, open_with_names,
selected_focus and selected_closed. The two open display modes share the fixed
open roster but retain separate mode contracts. Missing references remain in
intended/available/unavailable counts. The selected roster is never expanded to
hide outsiders or missing enrollment evidence. Processed-enrollment and duration
diagnostics remain in their original N2 evidence and are not substituted here.

The runtime loads real `N2Gallery` for all 15 N2 catalog compositions, including
A1/A2/A3 with D0/E0. Baseline A0/D0/E0 uses the real `ResearchGallery` and
`ProfileStore.load`. Its bridge copies the existing E0 vectors to isolated
float32 .npy files and verifies exact normalized bytes and IDs after loading.
This is a storage bridge, with bound original provenance, not new enrollment or
adaptation. It never searches personal profiles. Every derived file is private.
The baseline loader's inherited preprocessing string describes its original
enrollment API; the bridge manifest/provenance records the actual accepted E
centroid source. Do not interpret that inherited string as a new extraction.

`configure_actual_mode` calls the unchanged PrototypeEngine/N2Engine/N3IdentityEngine
`begin()` methods at a supplied real scheduler seam. Only session/model startup
and the event sink are replaced by the documented method harness. Actual code
selects the resolver, tracker diagnostic wrapper and caption annotator. No audio
or models run. Separate name-map state is created for every mode/session. The
caller must separately annotate each actual published `s6d_display`, retaining
its timestamp and original state row. An annotated display is not an in-place
caption-state mutation. The full Controller output path remains to be qualified.

Two observed source behaviors matter for interpretation:

- Baseline keeps its original C088 nominal thresholds and
  PrototypeIdentityResolver. Those thresholds are not calibrated for these
  processed queries. Synthetic exact-vector checks demonstrate that this
  original resolver can publish names. Any such output remains an unqualified
  baseline observation, not verified recognition. This is an explicit exception
  to the plan's general operational reject-all expectation; no threshold was
  changed to suppress the finding or improve a result.
- The other 15 compositions use N2NameMap with the unchanged processed-query
  UNCALIBRATED_REJECT_ALL gates. Open modes reject names. Closed mode can select
  a cosine assumption after sufficient clean evidence, explicitly unverified.
  With no voice support, original baseline display annotation can use the first
  roster entry; N2 annotation does not implement that fallback. The product
  mode description therefore overstates N2's always-assign behavior. Preserve
  and report that implementation gap; this preparation does not repair it.

Outputs in a fresh private directory: `GALLERIES.json`, four isolated E0 baseline
manifests/profile folders, and `RESULT.json` binding code/source/input bytes and
160 actual mode-begin checks (16 catalog tuples x 5 modes x both taps). Failed
attempts retain `FAILED.json`; reruns require a fresh directory. Only a redacted
receipt belongs in Git. Reference names/vectors and detailed private evidence
must not be committed. The allocation is 16 MiB, beneath the shared campaign
allowance; no downloads or neural payloads. The helper runs CPU14 below normal
with C50/G75-GiB floors and ONNX construction forbidden, leaving the existing
CPU4 ASR worker untouched. No desktop, Pi, capture or playback access.

Tests use isolated synthetic profiles and the actual frozen application methods:
source/runtime corruption, vector/gate/namespace/roster changes, Q-field rejection,
unsafe path refusal, real ProfileStore round trip, original-versus-N2 routing,
closed assumptions, missing-voice display behavior and independent mode state.
The real preparation verifies the fixed galleries and all 160 begin/annotation
routes. Neither check supplies observed first-visible naming metrics.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpOutput='G:\Just_Peachy_N1\20260924_campaign\local\n4\mode-galleries-v1'
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_mode_galleries.py','-v']; runpy.run_module('unittest',run_name='__main__')" $jpCode
& $jpPython -B "$jpCode\prepare_mode_galleries.py" --output $jpOutput
```

Command Prompt / Anaconda Prompt (existing interpreter; no environment changes):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_OUTPUT=G:\Just_Peachy_N1\20260924_campaign\local\n4\mode-galleries-v1"
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS); sys.argv=['unittest','discover','-s',sys.argv[1],'-p','test_mode_galleries.py','-v']; runpy.run_module('unittest',run_name='__main__')" "%JP_CODE%"
"%JP_PY%" -B "%JP_CODE%\prepare_mode_galleries.py" --output "%JP_OUTPUT%"
```

Set `JP_N4_SOURCE` only for tests against a separately verified equivalent source.
Production preparation takes its source from the bound accepted replay receipt.
Use `load_prepared_gallery(binding, contract)` for an independent runtime gallery
and `configure_actual_mode(dispatcher, observed_clock, profile, gallery, contract)`
at the existing scheduler seam. A future coupled runner must verify the bound
preparation receipt, source and component evidence and preserve separate display
history, raw text, mode, resolver, roster and modeled/observed clock scopes.
