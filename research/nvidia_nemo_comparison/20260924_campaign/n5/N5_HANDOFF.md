# N5 partial release checkpoint

## 2026-09-27 11:54 UTC - Both numerical comparison scopes reviewed

N4 now has accepted independent numerical reviews for 7,680 main and 1,536 modes
cases. Read `../n4/MODELED_COMPARISON_HANDOFF_V1.md` for the exact scope and
remaining application work. A repaired diagnostic is checking both actual review
chains; it does not establish an accepted release shortlist. N5 therefore still
has no N4-selected release. N2/N3 offline acceptance remains as recorded below.

The immutable baseline CM5 ZIP, tested storage preflight and reconnect/install/
rollback instructions remain available. Optional backend installation, actual
ARM64 model/WAV/GUI validation and per-build Windows checks remain required.
The user's request for an easy wired reconnect and accessible backend GUIs is
preserved in `PI_RECONNECTION_REQUIREMENTS.md`; actual Pi storage and live CM5
integration stay deferred until reconnection. Neither deadline is extended.

## 2026-09-27 08:43 UTC - Baseline storage preflight verified

N2 and N3 have since been accepted within their recorded offline scopes; use
`n2/FINAL_REVIEW.json` and `n3/N3_ACCEPTANCE.json`. The historical checkpoint
below predates those receipts. N4's 7,680-case main modeled score review is
accepted, and the guarded modes bank was healthy at 1,408/1,536 cases at 08:41
UTC. Application/GUI, resource, naming and continuity acceptance remains open.
No N4-selected N5 release exists yet.

`PI_STORAGE_PREFLIGHT_CHECK_V1.json` records 11 passing software tests and a
read-only inspection of the preserved baseline CM5 archive. All 31 declared
member hashes and all nested archive inventories passed. The first development
failure (Windows ZIP filename normalization) and its source are preserved; the
corrected reader checks the original header spelling, with a passing rerun.
`README_PI_STORAGE_PREFLIGHT_V1.md` documents purpose, inputs/outputs,
PowerShell, CMD/Anaconda and later on-device commands.

The 310,867,595-byte archive contains eight baseline model assets and 13 wheels.
Known installed logical payload is 505,290,986 bytes. The conservative additional
space estimate is 3,009,905,316 bytes (2.80 GiB), including transfer/extraction,
installation/staging, an explicitly unmeasured 512-MiB runtime/filesystem budget
and a 1-GiB reserve. Existing files receive no space credit and existing rollback
releases are retained. Actual Pi free space is unknown. This estimate covers
the preserved baseline only, not future optional backend models or measured RAM.

The companion preflight remains outside the immutable baseline ZIP. At the later
reconnection it can check Linux ARM64/Python/OS-library metadata and actual free
space before the existing install/stage/health/activate/rollback flow. It never
installs, starts a GUI, opens an audio device or connects to the Pi. A space result
is not functional ARM64 validation. Follow `PI_RECONNECTION_REQUIREMENTS.md` for
the user's shared GUI/backend availability and storage requirements. Live CM5
checks remain deferred until reconnection; N5 is not complete.

Packaging reserve: 2026-09-28 02:48:19 UTC. Deadline: 2026-09-28 14:48:19 UTC.
Neither limit is extended. Follow N4/REMAINING_EXECUTION.md for the current chain.

## Initial checkpoint retained for provenance

N5 is not complete. The requested N4 accepted shortlist does not yet exist.
The whole-bank comparison, final resource tiers and per-shortlist Windows and
ARM64 model/GUI checks cannot be inferred from build success. The dated
N5_STATUS.json records live upstream progress at checkpoint time; inspect the
live private files before resuming. No N4/N5 automatic inference queue is added.

## Actually delivered

N2 completed 422/422 cells and its final checks passed: 384 screen, 32
regression, six GUI cells; all matched ASR invariance checks passed. Its exact
coordinator and finalizer exited. N3 v2 then failed the initial source check
because its inventory included mutable `__pycache__` bytecode. No v2 neural
job ran. Fixed the freeze selector, added a real temporary-tree regression
(nine queue tests pass), and prepared/admitted fresh n3-common-v3/plan-v3
with 373 files and zero bytecode entries. The replacement uses numerical-v3;
v2 failures remain unchanged. The earlier N4 catalog-v2 derivative has the
superseded N3 parent and must be regenerated from the accepted N3 source before
numerical admission. It is not an accepted release.

- Preserved immutable N1 baseline and its idle Windows shortcut. A new private
  offline CM5 bundle contains exactly that app, all 13 target wheels and eight
  pinned baseline assets. Every ZIP member was read back and hash-checked.
- Static audit of 151 ELF binaries across 13 wheels: little-endian ELF64
  AArch64, exact publisher hashes, dependency inventory and Bookworm-compatible
  GLIBC/GLIBCXX/CXXABI requirements. zlib1g is an explicit OS prerequisite.
- Real native Linux ARM64 cross-build of pinned NeMo-Speech.cpp/ggml/
  SentencePiece: six ELF binaries, armv8-a, CPU-one-thread patch, no CUDA, mic,
  OpenMP, server or training environment. Separate ~1.8MiB engineering package
  contains binaries/SONAME links, source pins and 12 notices, with no weights.
- QEMU CLI help/version and explicit C-ABI dlopen/version passed in the correct
  bin/lib package layout. The first flat-layout loader failure is preserved.
  This is an EMULATED loader check, not a model/WAV functional smoke or CM5 test.
- Corrected wired deploy helper now transfers runtime_lock.py. Regression
  reconstructs transferred helpers in isolation. Twenty-two stdlib release
  tests pass on Windows and 22 on Linux, plus helper-transfer/dry-run, shell and
  wrong-architecture guard checks. Four new package-corruption/architecture
  refusal tests pass. N3's existing 32-job binding check remains verified.
- Install/rollback, mode/backend, enrollment/license and hardware-arrival guides;
  disabled/null CM5 hardware profile; exact artifact and Git backup receipts.

No desktop focus/input control, visible app launch, microphone/USB enumeration,
capture, playback, training, new scene bank, personal enrollment or Pi operation
was performed. Existing production data and immutable releases remain untouched.

## Required work still open

1. Review/finalize N2 and N3 after their exact admitted workers finish. Preserve
   failed attempts; classify model reference/export/parity results honestly.
2. Complete N4's runner/evidence compaction, D0 activity observability and D0/E1
   C-only association calibration, A1 integrated route or documented blocker,
   full 240×2 coverage for retained combinations, cluster-aware metrics,
   candidate-alone resources, actual paced GUI and continuity checks. N4's
   catalog wiring and evaluator tests are not release acceptance.
3. Freeze exact retained compositions with runtime/precision/buffer/gain/text/
   gallery/score manifests. Package baseline plus only functioning alternatives.
   Give each actual Windows/Linux composition its immutable ref/config mapping.
4. Run ARM64 wheel imports and real model/WAV state/flush parity on the same
   small saved inputs (QEMU may be used with explicit emulation labels). Build
   matched XMOS host/control-map ARM64 helpers after resolving the exact local
   business-license scope recorded in XMOS_BUILD_BLOCKER.md.
   ARM32 vendor binaries remain excluded. No physical hardware is required to
   complete these software checks, but CM5 performance stays NOT_TESTED.
5. Repeat required actual Windows control, saved-input, save/reopen/delete,
   namespace/import-export, failure/rollback and simulated source-interface
   checks for every selected build. Do not claim N1/N2 fixtures as newly executed
   N5 per-build checks. No physical mic or new human enrollment is authorized.
6. Finalize coverage/model status, memory tiers, noisy-name causal analysis and
   campaign handoff. Stop owned workers/probes only at actual completion.

The final 12-hour packaging reserve begins 2026-09-28T02:48:19.949192Z; campaign
deadline is 2026-09-28T14:48:19.949192Z. Disk reserves remain C50GiB/G75GiB.
N5_STATUS has elapsed wall-clock since the shared start; GPU/CPU compute and
LLM/token totals are unknown unless measured receipts expose them. No invented
totals or production-readiness claim. The prior shared-ledger write was rejected
by approval policy; this stage uses separate receipts without retrying it.

## Resume this existing task

> Complete the already-authorized N2–N5 campaign in
> G:\Just_Peachy_N1\20260924_campaign\worktree. Inspect N2 numerical-v2
> RESULT/CHAIN_RESULT and N3 numerical-v3 QUEUE_RESULT/RESULT, including exact
> live PID creation identities, before starting anything. Respect admitted CPU
> and GPU ownership and frozen source hashes. Review completed upstream jobs,
> then finish N4's listed implementation and full-bank acceptance gaps before
> promoting N5 candidate releases. Reuse N5's verified offline baseline and ARM64
> build/loader artifacts; finish actual ARM64 model and shared-GUI checks and
> exact candidate release manifests. Keep desktop input/focus available and Pi
> off, preserve original profiles and failed evidence, enforce disk/deadline
> reserves, back up reviewed small code/reports to the existing campaign branch,
> and close schedules/workers only when the campaign is actually finished.

Automatic LLM continuation has not been registered or verified. Existing
numerical jobs continue/checkpoint independently and emit a manual resume request.
This handoff ZIP is explicitly a partial checkpoint even though it uses the
requested campaign filename. Deployable archives are separate and private.
