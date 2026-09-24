# N3 v4 recovery — running, not accepted

The first registered recurring follow-up ran on September 24, 2026. It found
numerical-v3 terminal at 32/32 attempted jobs: 15 complete, three failed and
14 dependency-skipped. The exact previous supervisor and coordinator had
exited. No active job was interrupted or edited. All v3 evidence is preserved.

The native A2/A3 failure occurred before model loading: ctypes supplied zero
CTC chunk geometry even though the RNNT recognizer validates those fields.
The adapter now uses the pinned C++ StreamingConfig defaults (0.16-second
chunk and 1.92-second left/right padding), retaining explicit RNNT context.
Both fresh native A2/A3 saved-audio smoke tests pass. A2's eight-case real-audio,
empty/tail, repeated-stream and forced-endpoint conformance panel also passes.

The A1 export checker initially omitted audio because the encoder advertised
an optional bypass_pre_encode port absent from its export forward signature.
An instance-only export metadata correction removes that unused port. Both
ONNX graphs now export, pass ONNX validation and pass NeMo's own trace check.
The stricter independent dynamic/cache test still fails on its first case
(maximum absolute difference about 10.18). This is retained as a parity failure,
not a qualified portable model. Do not relax tolerances or claim all three
failures resolved. The pinned model and vendor source have not been altered.

## Admission and evidence

- Fresh plan: local/n3/plan-v4.json, SHA-256
  8000480360bb6620ba266bb585bc9e10f229c52366f0570a4aae3ae63ee7836f.
- Frozen prototype: local/releases/n3-common-v4/prototype. The common UI is
  unchanged. Prior v2/v3 releases and failed outputs remain untouched.
- Current result: local/n3/numerical-v4/RESULT.json. Inspect fresh ownership and
  per-job results rather than relying on this dated progress checkpoint.
- Eleven unchanged A0/reference jobs are reused with original result/lock
  bytes, hashes, timing and event paths; REUSE_RECEIPT.json explicitly says
  new_inference=false. The native paths, export, suite and analysis rerun.
- Fresh isolated suite: 448 tests across 47 modules, zero failures/errors,
  two explicit skips. Seven recovery and nine queue tests also pass.
- Source and final N2 review were pushed and remotely verified at
  21b6e90a818108f9f203a7772b3ec38808b6d59e, branch
  codex/n1-foundation-20260924 and tag n3-native-recovery-20260924-v4.
- N2 is now accepted with final reviewed reports and a hash-verified 60-file
  analysis handoff. N4/N5 remain prerequisites-dependent work, not accepted stages.

README_REUSE.md gives purpose, inputs, outputs, refusal conditions and exact
PowerShell/CMD/Anaconda preparation commands. The usual supervisor owns one
numerical child and the sole GPU slot. No visible app, desktop focus/input,
microphone, playback, personal-store modification or Pi contact was used.

## Next continuation

Let the healthy native evaluations finish. Inspect exact v4 owners before any
new numerical work. Investigate why the independent A1 dynamic/cache check
disagrees despite NeMo's trace check succeeding, including input/cache/layout
and export-state semantics. Diagnose from the preserved graph and full error
record; do not assume the warnings caused it. Use a new bound derivative for
any repair, and reuse unchanged native/reference evidence only after matching
the relevant dependencies. The current narrow reuse helper deliberately only
permits the explicitly reviewed native/configuration repair; it is not a
general license to reuse inference after arbitrary source changes.

Review all native screens, source-paced and actual isolated GUI outputs,
lexical/PnC/ITN and route comparisons, then close N3 and its small handoff.
N4 must regenerate its composition catalog from the accepted N3 source and
complete full-bank, calibration/observability and resource checks. The campaign
deadline and final 12-hour packaging reserve have not changed.
