# Shared caption repair candidate — 2026-10-06

This candidate repairs storage projection and presentation across the existing speech engines. It introduces no backend, model, cloud service, semantic rewrite or word alignment. The activated build28 rollback remains separate. Registered CPU14 host checks passed 17 caption/history plus 19 contract/runtime fixtures; native model, latency and portrait verification remain separate.

## Purpose and files

- `caption_paragraphs.py`: pure display grouping of a bounded, authoritative, source-ordered partition. Inputs are retained UI span dictionaries and the current Mode. Outputs are paragraph dictionaries carrying every original dictionary in `_caption_parts`. Words, stutters, repeated names, source intervals and timing-kind provenance are preserved. No global text deduplication is used.
- `classic_frontend.py`: retains the verified portrait UI loader and current worker ownership. Caption reads are throttled at 100 ms instead of 250 ms. Compact captions use 19 px; Normal/Large/Extra large and saved accessibility preferences remain available. The immutable retained source/config files are not edited.
- `mature_frontend.py`: reuses the existing Tk mark renderer and touch/navigation layout. It renders the pure paragraph view, keeps pending dots at a steady muted colour, and connects existing scrolling and Return to live to paged storage.
- `check_caption_repair.py`: deterministic offline regression fixtures and an optional read-only export audit. It never starts capture, loads models, connects to the network, extracts audio or prints private transcript words.
- `storage.py` is maintained by the storage repair owner. `replace_caption_projection` atomically replaces one native parent's current parts, retires only its absent children, and retains historical events. `latest_captions`, `caption_page` and `caption_parents` use source/parent/span order. `installed_engine.py` is maintained by the identity owner and calls replacement once per display revision.

## Display contract and limits

Supported paragraphs continue on the same nonempty internal track, compatible profile/display assignment and label, with a source gap at most 2.5 seconds. Unknown/null-track text can also share an explicitly `unverified_unattributed` presentation paragraph; `paragraph_claims_shared_speaker=False` makes no biometric assertion. Distinct known tracks, actual source gaps and manual paragraph anchors remain boundaries. An equal displayed/assumed name alone cannot establish continuity. Every original ownership/identity span remains in `_caption_parts`. Caption-only uses the same source-gap rule without implying a speaker.

The bounded display first orders native parents by their original source anchor, then explicit token ranges. It never sorts overlapping coarse child windows as if they were phonetic timestamps. The store persists `projection_source_start` for new projections; legacy display rows use a bounded parent-anchor fallback without rewriting old recordings. A real Export10 span with later token range but fallback start0 must remain after earlier range starting1.1; a regression verifies this failure mode.

The 600-character paragraph bound is soft at existing span boundaries. An individual native span and a real BPE continuation remain intact; no invented word timestamp is used to split them. `asr_segment_runtime.py` supplies actual word-start/continuation joiners, separate resource/spoken finality and PnC readiness; see `README_ASR_SEGMENTS.md`. A continuation cases once after assembly, and conflicting attribution across one word displays Unknown while preserving all original spans. Source timing remains whatever the pinned runtime supplied, including `ASR_REVISION_WINDOW_NOT_PHONETIC_ALIGNMENT`. Paragraph IDs anchor to native parent and first token rather than changing child IDs/names. The retained renderer edits partial text at that anchor. Spoken finality remains separate from recognition-segment and identity finality.

The live tail reads 40 current spans. Manual scrolling takes a bounded latest 40 window; an upward scroll at its top prepends an older page and keeps at most 80 paging spans. A temporary paragraph break preserves the first existing paragraph's Tk anchor when older text is prepended. Delayed label/ownership changes refresh only those database parents, returning at most 120 current parts. If a parent repartition exceeds that bound, the existing reading window is retained. New live parents never rotate the manual window. Return to live immediately reloads the newest 40 and cancels an obsolete smoothing frame. This is paged database history, not a session-sized in-memory transcript. Legacy rows retain their exact database parent fallback so manual refresh does not erase an old recording. Atomic replacement fixes new revisions; no retrospective deletion of old caption evidence is claimed.

## Prerequisites and inputs

Use an existing Python 3.10+ interpreter; the checker requires only the standard library. Do not install packages or models. Run it from this candidate folder beside `caption_paragraphs.py`, `classic_frontend.py`, and `check_caption_repair.py`. The parent `live_runtime_20261003` directory supplies the unchanged pure `profiles.py` and `runtime_support.py` dependencies. In a packaged release those dependencies already reside in its code directory.

Required input: none for synthetic fixtures. Optional input: a local single-recording export ZIP containing exactly one `*/captions.jsonl`. Its caption index must be at most 8 MiB. Optional output: a writable JSON receipt path. The ZIP is read in memory and left unchanged. The receipt reports structural counts and test results only.

## PowerShell

```powershell
Set-Location -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006'
python .\check_caption_repair.py
python .\check_caption_repair.py --export-zip 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\recording-export-10-monitor-01\closed-output\selected-recording.zip' --output .\CAPTION_CHECK.json
```

## Windows Command Prompt

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
python check_caption_repair.py
python check_caption_repair.py --export-zip "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\recording-export-10-monitor-01\closed-output\selected-recording.zip" --output CAPTION_CHECK.json
```

## Anaconda Prompt

Open Anaconda Prompt and use an already installed environment with Python 3.10+. The base environment is sufficient if it meets that requirement; no `conda install` or network step is needed.

```bat
conda activate base
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
python check_caption_repair.py
```

Optional `--export-zip` and `--output` arguments are identical to the Command Prompt example. Substitute the name of your existing environment for `base` if needed.

## Outputs and interpretation

The checker exits 0 when its fixtures pass, or 1 on a fixture failure. A malformed export raises an error and exits nonzero. It reports test totals and, when requested, indexed/current/obsolete span counts, word-instance counts, source-token coverage, projected paragraph count, short-span count and timing categories. No words or speaker names from the export are emitted. A JSON receipt is written only if `--output` is supplied.

The real Export10 baseline has 60.4 processed seconds, 48 indexed spans, 39 spans belonging to three latest text revisions, 9 obsolete spans, 177 indexed versus 168 current word instances, and 26 current spans containing one to three words. Executed structural projection gives five display paragraphs, including three explicitly unverified unattributed paragraphs. All 168 current word instances/token positions remain and native-parent token order is verified. All labels remain Unknown; only two of the 39 top-level projection rows supply nonnull supported tracks. The other 37 are grouped for presentation without a claim of speaker continuity. No historical caption evidence is erased.

The final registered receipt is `local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/caption-host-20261006-registered-d4f512bf/RESULT.json` under the campaign root. It reports PASS36, zero errors/failures, source readback unchanged and all temporary fixtures closed. Its PID67144/creation FILETIME134357791560555739 naturally returned0 and was independently absent. This final run includes the literal-decimal punctuation guard. Paragraph/word counts are structural evidence, not human readability, acoustic accuracy or physical latency measurements. Final code is frozen; this receipt text is the only documentation update after that run.

This establishes a concrete storage duplication/fragmentation baseline. It does not establish ASR accuracy, physical GUI latency, acoustic mid-word reset causation or human reading comfort. The first useful raw text in that recording covered source time 0.8 s and was available at approximately 0.8865 s. Changing the storage throttle from 250 ms to 100 ms reduces that configured interval by 150 ms. With ideal 80 ms UI ticks, the throttled reads actually occur about every four ticks (320 ms) before and two ticks (160 ms) after; scheduling and query work can add time. This is a scheduling calculation, not a screen measurement. Report native display measurements separately rather than treating worker publication timestamps as physical screen time.

## Native verification after parent coordination

Use the parent candidate installer/guarded launcher instructions. Do not launch this helper directly as an application, replace rollback files, SSH independently or change capture clocks. Required visual checks on the retained 480×800 layout: a revised `particul` partial becomes `particular` in place; an intentionally spoken repeated phrase stays repeated; Unknown track continuity groups coherently; a different Unknown track breaks; a later supported name changes the existing span; an upward history page retains the manual anchor; Return to live restores the tail; Compact, larger sizes and High contrast stay usable. Save screenshots and timing receipts without broadly printing private words. Storage failure injection, duplicate finals and monotonic projection revisions are covered by the separate storage repair regression suite.

## Primary research applied narrowly

- [Google CHI 2023 live-caption stability research](https://research.google/blog/modeling-and-improving-text-stability-in-live-captions/) motivates measuring visible token movement and luminance changes. Here the existing character edit renderer is retained, paragraph churn is reduced, and the pending pulse is removed. No semantic-model rewrite is added.
- [AWS streaming partial results](https://docs.aws.amazon.com/transcribe/latest/dg/streaming-partial-results.html) distinguishes an evolving partial result from a completed segment and describes bounded revisable tails. This candidate uses stable native parent IDs and current partitions, without claiming AWS stability flags for Sherpa.
- [Deepgram endpointing and interim results](https://developers.deepgram.com/docs/understand-endpointing-interim-results) separates final recognition segments from an utterance-ending pause. That distinction informs aggregation; its service defaults are not transplanted.
- [Official Sherpa streaming WebSocket documentation](https://k2-fsa.github.io/sherpa/onnx/websocket/online-websocket.html) and [endpoint rule source](https://github.com/k2-fsa/sherpa-onnx/blob/master/sherpa-onnx/csrc/endpoint.h) identify silence and maximum-length endpoint rules. The reported recording has native resets at approximately 20-second source boundaries; the exact acoustic reason requires the matched runtime/audio trace. Endpoint values are not changed by this candidate.
- [Whisper Streaming's LocalAgreement implementation](https://github.com/ufal/whisper_streaming) illustrates agreement of successive hypotheses before commitment. Its principle informs stable revision handling only. No Whisper backend, code, model or reported latency is imported.
