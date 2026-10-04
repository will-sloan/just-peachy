# Provisional captions with bounded speaker correction

Purpose: emit ASR text immediately with a fast/unknown label, then revise recent
speaker labels when a slower pass supplies sufficient evidence. This component
does not delay text to wait for diarization. The legacy two-Nemotron selector remains unavailable. A separate Pyannote primary plus continuous anonymous CurrentDelayed child has actual saved and live300 compute/EOF evidence, plus an earlier bounded fallback result; production16 enables its exact reviewed experimental selection and policy. Synthetic tests cover the correction contract, not native quality.

Inputs are explicit fast and refinement profiles, source/session identity,
16 kHz sample intervals, a revision window and update period. For example:

```python
selection = RuntimeSelection(diarizer="nemotron", embedding="anonymous",
    input_source="live", nemotron_profile="official_very_low",
    allow_experimental=True, provisional_correction=True,
    refinement_profile="current_delayed", revision_window_seconds=30,
    refinement_period_seconds=5)
```

The fast profile's nominal input buffer is 0.64 seconds. CurrentDelayed's is
21.20 seconds. The latter is a larger-context choice, not a quality guarantee.
Nominal input times exclude computation. A 30-second revision window can accept
late evidence only if input buffering plus compute, queue and scheduling delay
fit inside it. Otherwise the existing fast/unknown label remains the fallback.
The period of five seconds is scheduling configuration, not measured throughput.

For each refinement-local label `r` and persistent fast label `f`, alignment
weight is the total sample intersection over exact matching source clocks:

```text
overlap([a,b),[c,d)) = max(0, min(b,d) - max(a,c))
W[r,f] = sum of overlap for spans carrying r and f
mapping = one-to-one assignment maximizing sum(W[r,mapping[r]])
```

The assignment must have at least 80 ms of overlap evidence per accepted label,
win more than half that refinement label's reference evidence, and remain unique
when the selected edge is forbidden. An equally scoring alternative means the
identity remains unresolved. Raw label numbers are never equated across models.
The algorithm has at most eight labels per producer and 512 intervals per batch.

Outputs include `caption_added` immediately, `speaker_alignment` with all exact
reference/refinement sample intervals and a digest, and `caption_revised` with
the same `caption_id`, an increasing revision and exact supporting intervals.
Consumers persist alignment evidence and upsert by ID; revisions are not new
caption lines. Expiration/capacity pressure freezes a fallback, and old sequence
retries cannot create duplicate captions after eviction. Default resident limits
are 256 captions and 512 fast spans; there is no complete in-memory transcript.

Only received audio may be cited. The source ID, session ID and sample rate must
match. In-flight jobs have bounded serialized bytes, queue count and deadlines.
Overflow, late work or backlog prevents refinement admission while ASR continues.
At the overall backlog limit, the controller explicitly stops with a failure
receipt and preserves the processed prefix instead of skipping input.

Use the PowerShell, Command Prompt or Anaconda configuration commands in
[command_matrix.md](command_matrix.md) with:

```text
--diarizer nemotron --profile official_very_low --experimental --provisional --refinement-profile current_delayed --revision-window 30 --refinement-period 5
```

Change `--profile`, `--refinement-profile`, `--revision-window`,
`--refinement-period`, `--embedding` and `--source` independently. The command
prints validated settings only. A native execution route needs its own resource
admission before creating a second model. Run the focused tests using
[README_PIPELINES](../README_PIPELINES.md#run-the-focused-tests); passing them
does not establish identity accuracy or native acceptance.

Shared clocks, powerset, embedding, cache and motion mathematics: [architecture and math](../ARCHITECTURE_AND_MATH.md).


## Distinct implemented presentation and continuous-child paths

The older `provisional_correction=True` example above describes the pure
`CaptionLedger`/`RefinementCoordinator` contract. It is not a runnable native
fast-Nemotron/slow-Nemotron pair; the three official short-buffer CM5 attempts
failed their bounded throughput limits. Do not label that selector as a usable
low-latency model merely because its nominal input buffer is small.

The separately selectable `single_d1_late_labels` path uses one D1 context:
`SingleD1LateLabels.project` consumes actual S7 span history with `n2-caption:`
events, preserves caption/span/text-revision IDs and source intervals, and
freezes the last supported label or Unknown at the revision deadline. ASR need
not wait for native speaker evidence; this is delayed attribution, not a fast
diarizer. See [its running/configuration contract](../README_LATE_LABELS.md).

The new `optional_d1_refiner` architecture uses Pyannote primary and one continuous
anonymous CurrentDelayed child. `JournalRPC.read` advances one committed sample
cursor; `RefinerLabelBridge` maps independent slot permutations to genuine
primary tracks using the overlap equation above. It never restarts the native
model over skipped audio. Late/failed work disables only the child and retains
primary captions. The child and guarded attachment are implemented. Actual First03 on build14 processed all 715,127 samples in both primary and child, returned all 4,470 child frames and closed naturally. It produced zero optional revisions: primary histories supplied no accepted track anchors, so abstention is not evidence of correction quality. The owned first qualification dispatcher uses the same frozen worker, a fresh unit, early owners, exact source/asset/receipt pins and complete output reservations. Initial saved feasibility and real live300 followup remain distinct gates. The followup preserves the actual saved-primary evidence and uses an explicitly reviewed qualified-live-source composition bridge, without claiming an unrun live-primary baseline.

Actual build13 Followup01 kept all 4,800,000 primary/raw samples and closed cleanly, but disabled its child at the 30-second label-lag limit: 676,800 child samples and 2,112 frames, with no child EOF. That is measured bounded fallback, not full combined success. Build14 Followup02 completed all4.8M primary/raw/child samples and30,001 child frames with the explicit60-second window, full closure and a separately reviewed experimental receipt. It still produced zero optional revisions; production16 uses the exact source300/load120/drain60/backlog30/cleanup60 policy. Its actual idle GUI verified the eligible option, checked60/30 and unchecked120/120 summaries,267 Start-disabled checks and normal Exit without capture/models. See the [operator sequence](../MODE_GUIDE.md); these GUI observations do not add correction or model-performance evidence. See [owned harness instructions](../README_OPTIONAL_QUALIFICATION.md) and [optional-refiner status](../README_OPTIONAL_REFINER.md).

The separate one-context Research07 used sparse clean-turn embeddings plus delayed single-D1 attribution. All 4,470 x 8 native values and the final three-utterance/38-word ASR sequence matched baseline04 exactly. It published 30 supported/partially supported late-label updates; six final spans remained pending. This proves actual consumption of existing anonymous evidence with stable IDs and source intervals, not DER, enrolled-name accuracy or improved recognition quality.

## RAM and execution scope

Single-D1 late attribution adds bounded caption/evidence state to one diarizer; the optional continuous child adds a separate model and process. Actual First03 sampled whole-unit RSS 636,502,016 bytes and PSS 614,537,216 bytes, with system available RAM at least 1,217,429,504 bytes. The earlier live30-window Followup01 sampled aggregate RSS 696,287,232 bytes and PSS 651,709,440 bytes; its child stopped for label lag, not observed physical-memory pressure. Samples can miss peaks and the runs must not be combined into one peak. Followup02/window60 sampled aggregate RSS760,020,992 bytes/PSS700,768,256 bytes, minimum available1,178,828,800 bytes and max68.3C; child lag peaked30.98s and primary backlog0.50s with zero drops. Research07's 550,502,400-byte RSS is worker scope, not aggregate. First qualification applies a 1,024 MiB aggregate RSS soft-stop, 192 MiB system-available floor and initial 1,216 MiB available guard. These supervised thresholds are not measured required RAM. Per-process address-space ceilings are not added together to estimate physical use; primary captions must survive optional disable/failure. The component hour and failed whole-application hour have separate scopes in the linked results; none establishes sustained whole-application operation for this mode.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
