# Prototype iteration pack V2 — progress

**21 September field fix:** Selected closed-group now always displays a selected
name for new captions, marking missing evidence assumed and preserving separate
raw acoustic identity. See CLOSED_GROUP_DISPLAY_FIX.md and its CHECKS receipt.
Tasks01–12 below retain their historical completion/test counts.

| Task | State | Evidence / next human action |
|---|---|---|
| 01 — Live timing, finalization and Stop | IMPLEMENTED; bounded checks PASS | 156 software checks; actual O0/O1 transition, rapid stops, recovery and native speech tail passed. Read `UIITER2_01_HANDOFF.md`. Human scripted speech is AWAITING_USER; CM5 and long-session clock drift NOT_TESTED. |
| 02 — Calm captions and touch UI | IMPLEMENTED; bounded checks PASS | 166 software checks; short actual native-file GUI; exact 480×800 and 600×1000 comfort; measured 0/150/300ms presentation batching. Read `UIITER2_02_HANDOFF.md`. Real-room usability/touch and CM5 remain pending. |
| 03 — Linked sessions, exact audio and resources | IMPLEMENTED; bounded checks PASS | 185 software checks; exact native float archive; save/restart/reopen; isolated fake-output caption playback; interruption/storage checks. Read `UIITER2_03_HANDOFF.md`. Physical playback and CM5 NOT_TESTED. |
| 04 — Roster modes, Unknown and scores | IMPLEMENTED; bounded checks PASS | 209 software checks; six native 12s cases; selected gallery versus all-gallery recognition; explicit closed forcing; final native display-roster isolation. Read `UIITER2_04_HANDOFF.md`. Live group/outsider, touch and CM5 remain NOT_TESTED. |
| 05 — Assigned seats and spatial controls | IMPLEMENTED; bounded checks PASS | 229 software checks; three native 12s model cases with explicitly synthetic telemetry; actual assumed caption widget; no-restart motion invalidation. Read `UIITER2_05_HANDOFF.md`. Fresh live participant/XVF, physical touch and CM5 NOT_TESTED / awaiting participation. |
| 06 — Paragraph enrollment and progress | IMPLEMENTED; bounded checks PASS | 242 software checks; identical native before/after vectors, Done versus timed gates, ordinary-ASR estimate, restart/export/import, honest progress and 480×800 Tk. See `UIITER2_06_HANDOFF.md`. Fresh human/XVF enrollment, physical touch and CM5 NOT_TESTED / awaiting participation. |
| 07 — Names, vocabulary and text assistance | IMPLEMENTED; bounded checks PASS | 253 software checks; genuine native greedy-caption/archive check; contextual safeguards, separate manual undo, 480×800 UI. See `UIITER2_07_HANDOFF.md`. Acoustic name bias unavailable: no qualified matching ASR BPE vocabulary. Human/CM5 NOT_TESTED. |
| 08 — CM5 release and wiring | SOFTWARE_PREPARED; Windows checks PASS | 257 application checks; 22 packaging checks on Windows and x86-64 WSL; native portrait/archive proof; proto1-0.2.0 export. Native ARM64/CM5/hardware pending. See UIITER2_08_HANDOFF.md. |
| 09 — Script-aware enrollment | IMPLEMENTED; bounded checks PASS | 269 software checks; actual model/reference/fresh-query tests; coverage review and alternate diagnostics. Original naming unchanged. Matched-content/phonetic score unavailable; human/ARM64 pending. See UIITER2_09_HANDOFF.md. Task08 ZIP preserved. |
| 10 — Noise/model coordination | IMPLEMENTED; bounded native checks PASS, mixed accuracy | One DPDFNet helper; four experimental routes, Bypass default. 283 software checks; 12 fixed cases, 9 native epochs, 4 enrollment routes, exact archives and 480×800 UI. See UIITER2_10_HANDOFF.md and final CHECKS receipt; live/ARM64 pending. |
| 11 — Reversible session references | IMPLEMENTED; bounded checks PASS | 306 software checks, eight native epochs, actual 480×800 touch workflow. Default-off collection/matching, review/promotion/Undo; immutable originals and domain separation. See UIITER2_11_HANDOFF.md. Human field confirmation/CM5 pending; no accuracy-gain claim. |
| 12 — Optional audio transcript review | IMPLEMENTED; bounded Windows checks PASS | 321 software checks; seven native cases plus new-capture cancellation; actual 480×800 review/adopt/Undo workflow. Default Off, finite same-model alternatives, no automatic edits and no LLM. No demonstrated accuracy gain. See UIITER2_12_HANDOFF.md. Live people pending; CM5 disabled/unqualified. |

Updated 20 September 2026. Changes are local and rollbackable on baseline
`5b12f88430e619e37ce3397e005ca683b1fb9094`. No automatic commit/push, master Word
edit, training or dataset sweep. Task10 adds one explicitly authorized model; no new library. Existing 0.1.4 release
archives remain unchanged; task08 creates the cumulative proto1-0.2.0 export.

The original user failure logs and profiles remain intact. Runtime hashes,
precise test scopes and source backup are bound by `UIITER2_01_CHECKS.json`.
Task 02 separately binds its changes, screenshots and checks in
`UIITER2_02_CHECKS.json`; its rollback ZIP preserves the completed local task 01
baseline. Task 01's receipt remains historical and is not relabelled as a check
of task 02's later controller/UI source.

Task 03 separately binds source and checks in `UIITER2_03_CHECKS.json` and
preserves the completed local task 01/02 source in its rollback ZIP. Three actual
native-fixture screenshots were reviewed. Models, profile configuration, vendor
inference, task 01 live timing and task 02 caption rendering remain unchanged
from that task 03 baseline. No production personal data was modified.

Task 04 binds its own source/checks in `UIITER2_04_CHECKS.json`; rollback preserves
all completed local tasks 01–03. `MODE_MATRIX.json` exports ten non-seat modes and
46 default mode/recipe/tap configurations. The actual selected gallery is now
separate from display membership. Closed assumptions remain explicitly marked
and do not adapt personal references. Native fixture proof is not live/hardware
accuracy qualification. No new research sweep or model/dependency was added.

Task 05 binds its own source and checks in `UIITER2_05_CHECKS.json`; rollback
preserves completed local tasks 01–04. The current matrix has 12 modes, 54 default
profiles and four strong hybrid-seat variants; the former 46 profiles are unchanged.
Templates never auto-anchor. Direction-only uses explicit seat assumptions;
hybrid retains Unknown and separates voice memory from transient seat trust.
No native live/CM5 seat-recognition accuracy claim is made from software/file checks.

Task 06 preserves tasks 01–05 in its local checkpoint and binds final changes in
`UIITER2_06_CHECKS.json`. Timed enrollment and native embedding math are retained;
paragraph Done removes only the timed quota. Script estimates are optional
evidence metadata, never a voice-quality gate. No unattended person enrollment,
new dependencies, model upgrades, automatic release rebuild or push occurred.

Task07 preserves tasks01–06 in its local checkpoint. Default-off spelling review
and explicitly approved contextual edits remain separate from identity and the
original journal. Exact source, runtime and vocabulary provenance is in the
task07 receipts. No acoustic improvement or hotword A/B is claimed. No extra
package/model/dictionary was installed; greedy ASR and pinned assets remain.
