# Task10 — Optional noise routing and model coordination

Implemented in the existing Windows prototype,20 September2026. **Default
remains Bypass; enhancement remains experimental.** One DPDFNet baseline uses
the installed stateful streaming API. Native results are mixed, so this is a
field-testing option, not an accuracy upgrade or CM5 qualification.

## Results that matter

Twelve fixed cases ran through real Sherpa, Pyannote and ReDimNet. Full
S/D/I, matching scores, quality admission, resources and timing are in
[UIITER2_10_RESULTS.json](UIITER2_10_RESULTS.json). S/D/I below are word errors;
references are complete canonical clips, not inferred transcripts.

| Case | Original S/D/I | Enhanced S/D/I | Interpretation |
|---|---|---|---|
| Clean |1/0/0|1/0/0|Same word-error count. |
| Quiet,−20dB |1/3/0|0/2/0|Improved this example. |
| Stationary noise,0dB SNR |2/0/1|4/0/1|Worse: WER30%→50%. |
| Transient click |1/0/0|1/0/0|Same count. |
| Short “Will we ever forget it.” |0/0/0|0/0/0|All five words retained,1.585s. |
| Negation |1/0/0|1/0/0|Negation retained; no phone-level claim. |
| Pronouns |0/0/0|0/0/0|Five words retained. |
| Fresh outsider |0/0/0|0/0/0|Speaker matching assessed separately. |
| Existing post-XVF O0 excerpt |3/0/0|2/1/0|Same WER, different mistakes. |
| Digital silence / synthetic instrumental |0 false words|0 false words|Narrow empty controls, not general music validation. |
| Two-speaker overlap |WER unavailable|WER unavailable|No unique ordered single-output reference. |

**Important failure case:** the unchanged quality gate admitted0s of original
overlap and2s after enhancement; enhanced audio could therefore pass an
enrollment quality check despite being mixed speech. Do not enroll while others
speak. No thresholds were loosened or tuned. No sound-quality metric packages
were installed. Across the81 referenced words, both branches made13 errors;
this tiny constructed set is not a population estimate.

The genuine whole-clip cosine was0.700→0.786 for clean speech, but0.564→0.562
under stationary noise. The outsider's cosine to that person rose0.225→0.299.
These use separately extracted matching-domain references; they are not
probabilities. All four actual application routes confirmed the fresh known
fixture and left the outsider unnamed. Final caption ownership was0% Unknown
for that known query and100% for the outsider, across each route. This measures
coarse final caption spans, not word-aligned DER or provisional naming latency.

## Controls and behavior

Launch from `C:\Users\amiri\Documents\GitHub\just-peachy`:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

**Settings → Advanced → Noise / model routing**:

| Choice | ASR | Identity / quality |
|---|---|---|
| Bypass (default) |Original|Original|
| Enhance for ASR |Enhanced|Original|
| Enhance for identity |Original|Enhanced|
| Enhance for both |Enhanced|Enhanced|

Selection drains the current epoch; a new explicit Start is required. Original
references remain intact. Enhanced identity needs a newly consented reference
with the same helper SHA, tap and waveform domain. Paragraph ASR follows its
own selected branch; source/gain/reference rules remain unchanged. Existing
Captions/naming/anonymous/spatial/seat modes, recipes, O0/O1, text assistance and
task09 advisory evidence remain available.

The lightweight coordinator reuses five timestamped evidence categories:
waveform, Pyannote speech/overlap, Sherpa progress, voice quality and valid beam
evidence. It retains source intervals, observed availability, provenance and
unknown/fresh/stale status. No new USB poller, identity algorithm or embedding
schedule. Clipping/overlap can mark uncertainty; optional work yields under
backlog. Quiet speech, accent or missing words never imply noise or suppress
captions. Correlated scores are not combined as independent probabilities.

One shared helper, one additional bounded ring, persistent recurrent/STFT
state. Hop160/window320 at16k; initial output after320input samples, steady
buffering160samples/10ms. Native flush preserves exact length, including short
tails. No wrapper padding/trimming/normalization. At failure/backlog>0.5s,
ASR receives raw audio at the exact next unpublished sample; late helper output
is discarded. Enhanced identity stops at that boundary and later names clear.
An EOF flush deadline releases captions even if the native call stalls; worker
ownership remains held until it exits. Source gaps remain explicit failures.

For listening: **Sessions → New transcript + audio**, consent, Start, Stop,
Save and reopen. Choose Original / ASR / Identity / Enhanced and an explicit
output. Epochs retain exact `model_input.f32le`, optional `enhanced.f32le`,
window maps and transforms. Text-only sessions write neither waveform. Audio
quotas include both streams. Exported model windows matched exact branch bytes.

## Verification, cost and limits

**283 software checks passed.** See [UIITER2_10_CHECKS.json](UIITER2_10_CHECKS.json) for final counts,
source hashes and private evidence paths. Native proof:12cases, nine application
epochs, four enrollment-worker routes, nine boundary lengths with exact reset/
chunk invariance, all routes/windows exact, actual480×800 controls. Injected
failure, late output, backlog, stalled EOF, no-consent, domain and stale-name
contracts are software tests, clearly distinct from real-model checks.

Final native comparison:95.08s wall,90.05s process CPU,518.43MiB peak sampled RSS
(50ms sampling). Helper load added11.31MiB and took87.41ms on this desktop.
Original two-query CPU10.20s; additional ASR-only1.08s, identity-only1.45s,
both2.70s. These are single sequential observations with model/thread/scheduling
variation, not certified savings. This desktop was in use; separate enrollment/contract
checks overlapped the end of the replay. CPU/RSS are process-local, not a controlled benchmark.
Actual enhanced publication lag relative to output-end source time: medians19.9–20.5ms, maxima28.0–33.3ms, including file
pacing/dispatch/compute; this is not ADC/acoustic latency. Flush compute time is
measured separately and checked positive. Full memory/thermals,
native ARM64, physical touch, live participants and XVF capture with this option
are **NOT_TESTED / AWAITING_USER**. No microphone was opened here.

New files: `app/enhancement.py`, `noise_coordination.py`, `noise_ui.py`, optional
manifest, focused tests/native tools and READMEs. Integration touches existing
pipeline/controller, profile compatibility, consented sessions/listening and
Advanced UI. Vendor runtime, existing model assets and frozen profiles are
unchanged. No firmware/default-device changes, study/training, automatic push,
Word edit or release rebuild. Task08 ZIP remains byte-identical; current source
contains tasks09–10. Future CM5 exports need this source and optional hash
directory, with the helper off until target qualification.

## Artifact and rollback

Exact optional artifact: `dpdfnet_baseline.onnx`,8,791,035bytes;
SHA256 `debaf0e8893479fca91b8b4c1eae8db195aa8980ccc9012f5809fde2b738151a`.
Sherpa1.13.4 streaming; official Sherpa pre-export; author code and model card
declare Apache-2.0. No new Python packages or local conversion. The chosen
export differs from Hugging Face's export; no build-equivalence claim.
[Dependency ledger](UIITER2_10_DEPENDENCIES.json) and
[notices](../release_tools/THIRD_PARTY_NOTICES.md) bind provenance and obligations.

Operational rollback: select **Bypass**, then Start a fresh epoch. For a full
source rollback, close the prototype; from repository root, dry-run first:

```powershell
& .\.edge-speech-env\python.exe .\Resumes\.uiiter2_10\restore_before_10.py
# Apply only after reviewing its plan:
& .\.edge-speech-env\python.exe .\Resumes\.uiiter2_10\restore_before_10.py --apply
```

CMD/Anaconda: same commands without the leading `&`. The hash-guarded script
restores only task10 changes from `prototype_before_10.zip`, preserves01–09,
refuses later edits, moves added code to a private backup, and leaves data/models
untouched. New enhanced references require `enhanced-reference-v1`; an older
reader is refused. Use Bypass in current source or a separate compatible data
root instead of downgrading personal data. Reproduction commands and
inputs/outputs: [runtime](../app/README_NOISE.md), [tests](../tests/README_NOISE.md),
[native tools](../tools/README_NOISE.md). Stop here; tasks11–12 remain unstarted.
