# N3 limitations at preparation checkpoint

- N3 is not complete. No N3 real-model accuracy/resource/GUI result is claimed
  before the supervised queue executes and its evidence is reviewed.
- N2's v7 run and final checks must finish successfully and release all owners.
  A failed prerequisite blocks N3; no overlapping model jobs are admitted.
- A1 actual EOU reference is implemented. Its dynamic ONNX encoder/export test
  still requires execution and complete frontend/predictor/EOU rollout parity.
  An exported graph alone will not qualify a portable streaming release.
- A2/A3 Q8 native CPU/CUDA adapters and FP32 references are implemented. The
  Windows x64 C ABI passed a compile-only header check; neural execution is
  separate. CPU DLLs do not prove ARM64 build, target RAM or latency.
- The Pi remains off. CM5 2-GB total-system qualification, ARM64 performance,
  physical microphones, scanout, camera, GPIO and all hardware work are untested.
- Resource probes use one numerical candidate. Sampled process RSS is not peak
  total-system RAM. Native WDDM per-process VRAM is not measured; null stays null.
- The paired screen is 48 scenes / 96 files, not whole-bank release acceptance.
  All 240 bank scenes reconcile to 156 complete nonoverlap, 47 overlap,
  26 incomplete ambient references and 11 empty controls per tap.
- Complete nonoverlap WER/CER are primary. Overlap cpWER uses one unassigned
  mono output versus speaker references and cannot certify diarized transcripts.
  Ambient scoring is target-only. Exact phonetic word-time truth is unavailable.
- Isolated source-clip punctuation supports a diagnostic only; there is no
  invented conversation-level punctuation/reconstruction gold standard.
- P2 has no exact licensed official standalone checkpoint verified. Optional
  CTC alignment and multitalker work are deferred, independently of ASR quality.
- ITN is a shared callable component and evaluator toggle, default off. A new
  on-screen ITN control has not been added to the frozen UI. The finite subset
  does not cover hundreds, decimals, fractions, dates, times or currency.
- Private GUI checks use the actual application on an isolated desktop, with
  captures of that application's own window only. They do not control the user
  desktop. Human visual review of those new captures remains pending.
- Naming retains N2's uncalibrated Unknown/explicit assumed-closed-roster rules.
  Read-along progress is unavailable in the new native ASR backend. No human
  enrollment or personal gallery conversion is performed in this stage.
- The numerical queue runs without an LLM. No authenticated atomic idle guard
  for an automatic Codex resume was verified. It writes an exact-task manual
  resume request; it does not promise automatic interpretation or final acceptance.
