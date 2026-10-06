# Stabilization operator guide

This describes the activated build26 repair of the existing mature Just Peachy
application. Actual build25 **CHECK21 passed Pyannote/ReDimNet speech, Stop,
cleanup and Save raw + processed for 60.4 s**. CHECK22/23 add scoped quiet live
checks. CHECK27 completed full saved-worker replay, but failed parent closure.
Fresh build26 CHECK28 passed full rich replay/processed Save/Exit and
independent closure; build26 activation passed with verified rollback copies.
All six normal rows now have
their own bounded native live functional/closure observations. Exact results are in the
current matrix. Earlier observations retain
their original build/job labels. A microphone route does not prove sustained real-time performance,
readable captions, speaker accuracy, or one-hour stability.

## Open and run

Use the single versioned **Just Peachy** desktop shortcut. Select one complete
backend name, choose **Live microphone / Saved WAV**, and press **Open
Application**. This opens the retained portrait application; capture starts only
when you press Start. **Exit to desktop** is available in the chooser.

| Normal choice | Diarizer | Encoder |
|---|---|---|
| Pyannote + ReDimNet | Retained online Pyannote | ReDimNet |
| Pyannote + TitaNet | Retained online Pyannote | NeMo TitaNet |
| Nemotron Delayed + ReDimNet | CurrentDelayed | ReDimNet |
| Nemotron Delayed + TitaNet | CurrentDelayed | NeMo TitaNet |
| Nemotron Chunk52 2T + ReDimNet | Chunk52, two native graph threads | ReDimNet |
| Nemotron Chunk52 2T + TitaNet | Chunk52, two native graph threads | NeMo TitaNet |

Sherpa ONNX ASR/punctuation remains shared. **balanced** is the retained default
recipe. The exact manager admission governs available selections; there is no
silent backend substitution. See [BACKEND_MATRIX.md](BACKEND_MATRIX.md).

The mature caption layout, Mode, People, Settings, recording and history pages
remain in place:

1. Choose a conversation **Mode**. Open with names permits verified known people
   and Unknown people. Selected-people modes require their corresponding roster.
2. In **People**, use the selected encoder's separate gallery. ReDimNet and
   TitaNet vectors/calibration are not interchangeable. Existing enrollment and
   consent rules remain.
3. Inspect **Settings** as needed. Saved `direction='off'` is legitimate
   presentation state; its startup validation/preservation is part of this repair.
4. Press **Start**, then inspect actual source status. A window or worker alone
   does not prove microphone capture began.
5. Press **Stop** and allow source, models, archive and presentation to drain.
   An incomplete-closure error must not be dismissed as a successful stop.
6. Choose supported post-Stop audio disposition: keep processed/model-input
   audio, keep raw plus processed only when physical raw capture is qualified,
   or discard temporary audio. XVF processed output and model-input float/WAV
   are not raw microphone channels.
7. Use **History** to reopen/replay kept recordings. The actual directory is
   `<store>/sessions/<UUID>`. Export/offload copies data; deletion is separate.

Manual Stop is the normal boundary. Storage capacity, source policy, bounded
backlog and cleanup still constrain a session. A component soak does not admit
an integrated one-hour session.

The normal chooser and Mode menu omit standalone Anonymous choices. Internal
Unknown/anonymous tracks and **Open with names** remain; removing a menu item
does not justify an unverified person name.

## Live and saved sources

**Live microphone** uses actual XVF routing and live BMI integration. Preserve
source/sample clocks and inspect motion health when spatial cues matter.

**Saved WAV** permits matched acoustic comparisons. Use identical audio/timing
across profiles. A plain WAV has no recorded beam/BMI clocks and cannot provide
spatial or assigned-seat evidence.

For spatial replay, choose a **kept rich session** through History. Completed
beam/pose logs, original epoch, sample/callback anchors, hashes and metadata must
agree. Replay consumes recorded pose/beam evidence, never the tablet's current
orientation. Stale/missing/reference-change cues remain gaps. A replay seat
layout refers to the recording's frame.

See [README_SAVED_REPLAY.md](README_SAVED_REPLAY.md) and
[README_SAVED_SPATIAL.md](README_SAVED_SPATIAL.md). Final source-readback errors
remain latched even when repeated cleanup closes the lease.

## Assigned direction versus hybrid identity

**Assigned direction** chooses a unique eligible seat from clean speech direction
and the applied table layout. This closed-table assumption is marked **seat
assumed**; it is not voice verification, distance or absolute room position.
The actual selected diarizer/encoder still executes normally.

**Assigned hybrid** needs calibrated voice acceptance as well as seat evidence.
The original Pyannote + ReDimNet C088 gate applies only to that original domain.
TitaNet/Nemotron routes require independently admitted
encoder/query-domain/roster calibration. Until present, they report
**Unknown/calibration blocker**, rather than reuse C088 scores or thresholds.
Strong voice conflict releases seat association; ambiguous direction cannot
invent identity.

The writable TitaNet domain is currently `UNCALIBRATED_PERSONAL_DOMAIN`; new
Nemotron/ReDimNet queries likewise do not inherit the old calibration.
`calibration_receipt()` exposes the blocker. Direction assumptions can still
be inspected without claiming verified identity.

Motion/reference changes invalidate a seat anchor. The BMI270 provides relative
attitude, not absolute heading or reliable integrated room translation. Delayed
audio uses historical source-window pose/beam, not current cues.

See [README_SEAT_BACKENDS.md](README_SEAT_BACKENDS.md) and
[the retained Modes/math](../full_application_20261004/APPLICATION_MODES_AND_MATH.md).

## Advanced Nemotron attribution

One collapsed **Advanced attribution** control is available for named Nemotron
choices; Pyannote keeps its default.

| Preset | Embedding | Speaker attribution |
|---|---|---|
| Standard | Continuous | Retained standard policy |
| Sparse clean turns | Eligible clean-turn embedding | Retained standard policy |
| Late labels | Continuous | Single-D1 late labels |
| Sparse + late | Eligible clean-turn embedding | Single-D1 late labels |

These are existing policies, not new backend rows. Single-D1 late labels use the
one selected diarizer, existing 2 s refresh and bounded 30 s recent revision
window, with original caption/source evidence links. The optional parallel
refinement worker remains disabled. Sparse embedding does not discard live
microphone audio. Exact variants must be admitted; unavailable variants explain
their restriction instead of silently reverting.

See [sparse embedding](../README_SPARSE_EMBEDDING.md) and
[single-D1 late labels](../README_LATE_LABELS.md).

## Concrete differences and troubleshooting

| Previous issue | Prepared repair |
|---|---|
| Investigation interface replaced the preferred app | Small chooser opens retained mature portrait pages |
| Normal menu included poor-RTF/historical presets | Six named choices; history retained internally |
| Anonymous backend/conversation entries | Omitted from normal menus; Unknown remains |
| Chooser returned to desktop without explanation | Visible primary startup failure plus compact phase receipts |
| `direction='off'` rejected on construction | Correct settings validation/preservation; build25 CHECK21 constructed and started the mature app successfully |
| History showed wrong folder | Actual `sessions/<UUID>` folder |
| Seat routing restricted to old identity domain | Generic direction route; explicit hybrid calibration blockers |
| Saved spatial cues missing/current | Recorded rich-source clocks only; WAV remains acoustic |
| Sparse/late policies hard to select | Collapsed Advanced control; parallel refiner disabled |
| Actual speech exhausted SQLite metadata and closing diagnostics | Fresh measured text/SQLite allocation, independent terminal pool and cleanup that attempts all releases; CHECK21 completed 60.4 s speech/Stop/Save without failure or cleanup error |

## Speech metadata, cleanup and disk admission

The actual build24 speech session in job19 stored 19 nonempty captions and
808,000 processed samples (50.5 s) before ordinary SQLite metadata exhausted.
Its later diagnostic failure and logical cleanup failure remain preserved;
exact OS process closure does not pass that session's Save or logical cleanup.
This separates recognized speech from a complete successful recording.

Build25 prepares fresh session metadata as
`2 × (16 MiB + source_seconds × 256 KiB)`, equally split between text and SQLite,
plus the retained 1 MiB SQLite allowance and an additional independent 256 KiB
terminal pool. A 70 s check therefore reserves 35,127,296 B text and
36,175,872 B SQLite; ordinary writes cannot spend the terminal pool. Old
specifications and failed-session meters are unchanged. Cleanup attempts each
source/model/archive/lease release while retaining the original fault.

The external finite check reserves **256 MiB independently on Pi and PC**;
these disk allowances include conservative file limits and the freshly
measured shared history database. They are not allocated RAM, a normal GUI
session timer or a guarantee that any speech workload fits. Insufficient disk,
history growth or metadata exhaustion rejects safely; no ledger reset creates
credit. The actual 70 s raw/processed plan is 129,903,412 B including the
unchanged 32 MiB helper margin. Focused host checks support the changed writers
and failure paths. Actual CHECK21 then completed 60.4 s speech/Stop/Save; longer
speech remains unqualified. See the current result matrix for later route and
saved-worker evidence. Fresh build26 CHECK28 passed the repaired launcher closure
and full recorded spatial replay; the original CHECK27 remains failed.

Read [SPEECH_STORAGE_REPAIR_FINDINGS.md](SPEECH_STORAGE_REPAIR_FINDINGS.md),
[storage contract](README_STORAGE.md), [cleanup](README_METADATA_CLEANUP.md)
and [saved full-source check](README_NATIVE_SAVED_STABILIZATION_CHECK_V4.md).

**Desktop after Open:** inspect
`manager/launches/gui-<UUID>`: CREATED, SELECTED, VISIBLE and EXIT, or FAILED.
VISIBLE proves initial viewability only. FAILED retains the primary exception;
cleanup/receipt faults are secondary. Diagnostics reserve 64 KiB metadata plus
one 64 KiB directory, at most four 8 KiB phase files plus owner.

**Session Failed / Source Never Started:** separate settings/controller failure
before acquisition from actual XVF/AEC/frame failure using source-start,
service-exit and cleanup receipts. Preserve failed context/evidence. A startup
repair alone cannot certify microphone acquisition; no firmware reset or repeated
Start of a failed context is a substitute.

**Hybrid Unknown:** inspect the exact calibration blocker; do not transplant
another encoder's threshold. **Spatial replay unavailable:** select a completed
rich recording; present sensors cannot fill absent sidecars. **Stop/readback
failure:** verify bounded cleanup and closure before calling audio safely saved.

## Current native evidence

Later per-combination observations are centralized in [STABILIZATION_RESULTS.md](STABILIZATION_RESULTS.md).

Results retain exact build/job scope; remaining rows need their own receipts:

| Observation | Result |
|---|---|
| Chooser / mature app / named Mode / Start + consent | **Observed in job13; worker failed before SESSION/capture. No ASR proof.** |
| Actual speech recognition before metadata exhaustion | **Observed in build24 job19: 19 nonempty captions / 50.5 s source; whole session FAILED. No accuracy claim.** |
| Build25 Pyannote/ReDimNet CHECK21 | **PASS: 60.4 s / 966,400 processed and raw samples; 48 indexed nonempty caption rows / 40 visible; ASR accept604 / finish1 / reset2; verified export120 segmentation calls/208 normalized192D embeddings; Stop/Save raw + processed true; no failure/cleanup_error.** |
| Each six-choice route opens mature app idle | **Observed in CHECK21/22/23/29/30/31; all six have bounded functional live workflow/closure evidence.** |
| Actual XVF start and source closure | **All six completed their scoped physical source/Stop and independent closure. CHECK22/23/29 were quiet; those do not prove speech/embedding accuracy.** |
| ASR / diarizer / encoder execution per combination | **CHECK21 proves Pyannote/ReDimNet inference; CHECK30/31 add actual Chunk52 and37/24 embedding calls. Quiet rows have their own limited call scope. No all-six speech/accuracy claim.** |
| Stop, closure and audio disposition | **CHECK21/22/23/29/30/31 passed scoped raw + processed Save/closure. Fresh build26 CHECK28 passed full Saved replay/processed Save/Exit/independent closure; CHECK27 failure preserved.** |
| Assigned direction and hybrid blocker behavior | **PENDING** |
| Recorded spatial replay/current sensor excluded | **Fresh build26 CHECK28 completed GUI replay of966400 samples/6040 anchors/906 beams/3156 original poses/898 historical queries; current motion excluded, original source unchanged, reference loss0, shared lease closed.** |
| Deployed shortcut, rollback and final package | **Build26 activated with native/PC before/restore readbacks, capture off/no app/autostart disabled. Final archive/hash verification comes from adjacent HANDOFF_RECEIPT.json.** |

Prepared package25 manifest pin: `6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8`.
Its Pyannote/ReDimNet CHECK21 speech/Stop/Save scope passed; later combination
statuses are centralized in STABILIZATION_RESULTS. Exact finalizer owner 20961/start1140246
returned naturally and was absent. The retained result is
`classic-ui-check-21-finalized-monitor-01/closed-output` (50 files / 174,233 B),
proof SHA `0c4844160ab39d53f140a8cd7a3e192ad6fe1f47308a10a4bc59213b91893423`.
The kept source UUID is `c24b685b2bd34d6bb04172965d712c0f`. The retained raw route
is four physical16kHz PCM32 channels; Export10 contains seven raw and seven
processed segments. CHECK21 did not test processed-only retention. The verified
export confirms120 Pyannote segmentation and208 normalized192D ReDimNet
embedding calls,208 speaker decisions and105 identity decisions. Summed API
times16.875635s/20.750158s cover overlapping windows and are not whole-pipeline
RTF. Actual ASR and model inference do not establish calibrated identity,
accuracy, noisy-world quality,300s speech or a successful whole-app hour.
Historical package23 pin:
`16bfa6fcddfac639c83e0c785b4292d98eac478873d5a4c3a2efb3ceb7740492`.
Build22 staging hit FSIZE0 and its partial failure is preserved; build23 was
staged without overwriting an existing runtime. Job13's exact closed/private
monitor records a worker failure before SESSION/capture despite chooser and
portrait Start/consent succeeding. This is preserved build23 history; later
CHECK21/22/23/29/30/31 results supply scoped live evidence for all six rows.

Quiet execution is not intelligible-transcript, accuracy or noisy-world proof.
Physical touch and integrated hour stability remain separate evidence.


Selected current handoff: `G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/final-handoff-v29-build26-20261006/JustPeachy-v29-ChatGPT-handoff.zip`. Its adjacent
`HANDOFF_RECEIPT.json` is the authority for completed construction, full
member readback and ZIP SHA. A path in this guide alone does not assert those
checks passed. No ZIP self-hash is embedded in archived documentation; older
archives remain immutable. Deployable/model assets and private recordings
remain separate.
