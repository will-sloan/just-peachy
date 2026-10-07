# Native ASR resource boundaries and spoken utterances

## Purpose and current status

`asr_segment_contract.py` supplies a pure, bounded metadata contract distinguishing native recognizer resource resets from a completed spoken utterance. `asr_segment_runtime.py` supplies the production facade and disk ledger. `installed_engine.py` imports `SegmentedAsrMixin` and defines `Engine(SegmentedAsrMixin, Parent)`; `InstalledSession._caption` calls `asr_segment_row` before canonical persistence and identity projection. `check_asr_segments.py` supplies 19 focused synthetic/host regressions; all19 passed alongside17 caption/history fixtures in the final registered CPU14 run, including literal-decimal guard cases. Native acoustic compatibility and physical latency are not measured by these host fixtures.

Final evidence is `audit-preparation/caption-host-20261006-registered-d4f512bf/RESULT.json` under the local live-runtime evidence root: PASS36, zero failures/errors, fixture closed, source unchanged during check, elapsed1.547seconds. PID67144/creation FILETIME134357791560555739 naturally returned0 and was independently absent. The registered owner/source-backup/independent-restore/exit receipts are in the same directory. This documentation-only evidence update follows that run; runtime/helper code is frozen.

The repair keeps bounded recognizer resource state while preventing a 20-second timer from creating a displayed terminal period or breaking a BPE word. Immediate partials remain available. Identity projection preserves actual `recognition_segment_final`, `utterance_final`, `utterance_group_id`, `endpoint_kind`, `utterance_boundary_kind`, `spoken_punctuation_ready` and `leading_text_joiner`. The native facade populates these fields.

## Exact source audit

The installed original release is `b01-offline-20260930-v12`, with `RELEASE_MANIFEST.json` SHA-256 `274e6de279264f89642e3857c64bf164c699b600cd99e922429020b548bf55f0`. Its `vendor/edge_speech_pipeline/models.py:135` constructs Sherpa rule 3 with a 20-second minimum utterance length. Its `runtime.py:547–558` immediately resets on any endpoint and publishes a final; `runtime.py:862–877` submits every such final to punctuation. Its `config.py:66–68` gives 2.4 seconds of silence, 1.2 seconds after speech, and the unconditional 20-second length rule. The Export10 source windows of approximately 20.3, 20.2 and 19.9 seconds are consistent with this path; they do not independently prove which reported word was cut.

The release's `release_tools/requirements-arm64.lock` pins Sherpa Python/core 1.13.4. The existing local ARM64 wheel exposes `get_result_all`, BPE token strings and token emission timestamps. It does not expose the decoded frame count, trailing-blank count or a specific endpoint rule. Native token emission times are not asserted to be phonetic word alignment.

The existing Giga vocabulary has SHA-256 `49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb`, 502 tokens, 339 word-start markers `▁`, and a maximum symbol length of 10 characters. For the pinned greedy decoder, official [Sherpa 1.13.4 decoder source](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/online-transducer-greedy-search-decoder.cc) emits at most one token per output frame. The [transducer implementation](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/online-recognizer-transducer-impl.h) converts frames at 40 ms and preserves encoder states plus the last decoder context when resetting. Approximately 20.3 seconds therefore corresponds to about 508 emitted subwords and at most approximately 5,080 raw symbol characters, excluding fixed context/model allocations. This is a source-derived estimate, not an RSS measurement.

The [feature extractor](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/features.cc) discards already consumed feature frames. The application's disk audio journal adds no session-sized audio RAM cache; the 100 ms ASR read is 1,600 float32 samples, or 6,400 bytes. Its pending audio remains below one read block after dispatch. These facts do not bound the entire decoded token/text history if resource resets are simply disabled: a no-pause utterance continues growing the decoder result and S7 parent text.

The [punctuation implementation](https://github.com/k2-fsa/sherpa-onnx/blob/v1.13.4/sherpa-onnx/csrc/online-punctuation-cnn-bilstm-impl.h) uses 200-BPE model windows but builds all windows into one batch. Passing an indefinitely accumulated utterance would still create growing memory and inference work. Very large single words also need preflight or a raw-text fallback because a word can exceed that native window's assertion. An unbounded utterance cache or one giant PnC call is not admitted by this candidate.

## Helper inputs and outputs

`NativeSegmentContract.observe` takes a stable native segment ID, unchanged raw text, the actual full token result, the existing source start/end window, and exact native-endpoint/Stop booleans. A revision of the same segment replaces its suffix conceptually; the caller persists the authoritative revised text. `begin_after_reset` accepts the next segment. The helper retains constant-count metadata and a digest, with no transcript, token history, audio, files or models.

Outputs contain the source window, native segment ID, logical `utterance_group_id`, recognition-segment finality, separate spoken-utterance finality, boundary category and explicit leading text joiner. A native endpoint at or after 20 seconds is conservatively marked `resource`, because the API cannot distinguish a simultaneous pause. A shorter native endpoint is `native_pause`; explicit Stop is `stop`. A later short-stream silence endpoint may therefore be needed after an ambiguous length boundary. This conservative rule can add a pause delay; it does not pretend to recover an unavailable native reason.

When the previous boundary is a resource reset, a first token starting with `▁` supplies a space. A first actual token without `▁` continues the preceding word, supplying an empty joiner. Empty results wait for the first actual token. `join_raw_parts` follows only these explicit joiners: `PARTICUL` plus `AR` becomes `PARTICULAR`, while `▁VERY` followed by `▁VERY` stays `VERY VERY`. No spelling heuristic, token prefix/suffix deduplication or globally repeated-word deletion is used. Token/text mismatches reject this contract rather than assuming a different tokenizer. Duplicate final delivery is idempotent; a conflicting final or partial-after-final is rejected.

## Production execution and bounded state

The mixin verifies runtime SHA-256 `64c8021099be59578f1408228bd4dda6b76821f9efd29b2f68172b3f0938f78c`, models SHA-256 `d15972b6968ea8a1d5a8c76bba2fe30d504df5f0b1e7963a1166c65d4fcd9056`, and the exact 20-second configuration. It delegates inherited `_asr_loop` unchanged through `_SherpaSegments`. There is no AST replacement. The unchanged source regions are dispatch/reset/drain at `runtime.py:493–598`, native accept/reset/finish at `models.py:156–193`; the mixin overrides final/PnC dispatch formerly at `runtime.py:862–878`. N2 inherits this same admitted loop. All admitted D0/D1 combinations use the shared path.

The facade reads `recognizer.tokens(stream)` before the actual reset and counts actual accepted source samples. Original gain, synthetic finish padding, timing probes, cost calls, scheduler advances, partial cadence, source stop, failure handling and worker drain remain. Padding is excluded from observed source time. Admission/SQLite errors call existing `_fail` rather than escaping the background thread as an apparent success.

`SegmentLedger` writes `work/<native-session>/asr_segments.sqlite3`. One current parent revises in place; sealed pieces remain on disk; duplicate final publication is idempotent. Before each writable connection, shared `ensure_sqlite_file_limit` admits this exact database/sidecar basename using the recording store's real policy, actual free-space reserve and finite physical file allowance. The 4-MiB transaction-growth input adds rollback/header headroom; it is not a transcript quota. SQLite uses a 1-MiB page-cache setting, short-lived connections, one-row keyset reads and per-native-parent result lookups. The ledger replaces the growing `_s6d_punctuated` dictionary using existing `.get(parent)` calls. On-disk growth has no duration/text quota. Filesystem/SQLite failure remains explicit. A host fixture injects inadequate free space and confirms refusal before ledger creation.

Each endpoint seals its recognition piece immediately. A native pause, existing advisory endpoint, or Stop closes the spoken group and submits one descriptor to the existing bounded PnC worker. A silent empty piece after resource reset closes the prior nonempty group without words or extending that piece's source interval. `asr_spoken_boundary` separately records the later actual boundary source. Original dispatch telemetry continues reporting resource resets.

PnC pages disk pieces and assembles words using native joiners. It holds at most two windows of 96 words and 4,096 UTF-8 bytes each. A lexical word above 180 bytes streams as exact raw chunks; speech is never refused or truncated. This avoids the native 200-BPE single-word assertion and growing whole-utterance batches. Internal lexical window ends lose terminal periods/questions introduced only at their formatting boundary. Window seams limit learned context; native validation must assess that bounded formatting tradeoff.

Case/punctuation maps by original character ranges to the original native parents. A guard compares the exact raw-length lexical prefix, permitting only added punctuation afterward. Literal decimal/abbreviation periods and apostrophes remain raw characters. Changed lexical characters/word counts fall back to unchanged raw text. PnC revisions retain raw text, native parent IDs and original source windows. No global deduplication, spelling completion or fabricated phonetic timestamps are used. A combined word with conflicting attribution displays Unknown with every original span retained. Existing casing runs once over assembled resource pieces until actual spoken PnC is ready.

The 17 caption/history checks are separate from 19 segment/runtime checks. Remaining acceptance work is packaging, actual token compatibility, first-text/pause-to-PnC measurements, continuous-speech soak, Stop/failure drain, and portrait/manual-scroll verification. No engine/model installation is required. This candidate is not a claimed native pass until those results exist.

## Requirements and commands

Use an existing Python 3.10+ environment. Only the standard library is required for checks; no packages, models, network or native services are used. Required input is none; tokens/text are synthetic. The binding fixture reads the existing two admitted local source files to check pins and uses a synthetic delegation method. It does not perform acoustic inference. Temporary SQLite fixtures are removed. Output is test status plus a JSON structural receipt on stdout. Exit code is 0 for success and 1 for failure. No private transcript or audio is read, printed, extracted or modified.

Production inputs are the already-admitted `SherpaStream`, processed audio journal and engine session directory. Outputs are immediate existing partial/final source-piece events, the SQLite ledger, boundary metadata and later bounded PnC revisions for original parents. Launch using the candidate's ordinary entry point in `README_MANUAL_START.md`; this module has no separate microphone/model command. Save/Discard owns the existing session work directory and its ledger with the rest of that recording.

PowerShell:

```powershell
Set-Location -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006'
python .\check_asr_segments.py
```

Windows Command Prompt:

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
python check_asr_segments.py
```

Anaconda Prompt, using an already installed Python 3.10+ environment:

```bat
conda activate base
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
python check_asr_segments.py
```

Use your existing environment name instead of `base` if needed. No installation step is required. Host execution was explicitly released for this task; native execution remains coordinated by the parent owner.

## Registered Windows CPU14 host run

`run_host_caption_checks.py` runs both suites (17 caption/history plus 19 contract/runtime tests) in one process, sets CPU14 affinity before project imports, registers typed PID/creation-time ownership, backs up every relevant source file and independently restores/read-verifies those bytes, and optionally audits Export10 structurally. Input `--output` must name a fresh nonexistent private output folder. Optional `--export-zip` names the existing local Export10 ZIP. Output contains ownership, source closure, bounded test log, structural result and natural-exit receipts; it contains no private transcript words. Fixtures are temporary and checked closed. No SSH/native models/GUI run occurs.

PowerShell, from this folder using an existing interpreter:

```powershell
python .\run_host_caption_checks.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\caption-host-FRESH-LABEL' --export-zip 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\recording-export-10-monitor-01\closed-output\selected-recording.zip'
```

Windows Command Prompt and Anaconda Prompt (activate an existing environment first):

```bat
python run_host_caption_checks.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\caption-host-FRESH-LABEL" --export-zip "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\recording-export-10-monitor-01\closed-output\selected-recording.zip"
```

Replace `FRESH-LABEL` with a unique name; receipts are never overwritten. This registered runner requires Windows with logical CPU14, C: free above 50 GiB and G: free above 75 GiB plus its fixture/receipt allowance. Those are host-check admission floors, independent of production speech/session duration.
