# Task09 — Script-aware enrollment and advisory reference comparison

Implemented locally, 20 September 2026. **269 software checks PASS**, actual
audio → frozen models → saved references → fresh-query naming PASS, and actual
480×800 portrait review checked. This completes the supported selection/
provenance part of task09. **Matched-content/phonetic identity scoring remains
unavailable**: installed transducer token emissions do not provide calibrated
query-content confidence or validated acoustic word/phone boundaries.

Task08's working archive is preserved byte-for-byte. No new model, library,
dictionary, tokenizer, training, sweep, microphone recording, playback, production
profile mutation, automatic commit/push or release rebuild. Human/XVF enrollment
is **AWAITING_USER**; physical touch and CM5 ARM64/2 GB qualification **NOT_TESTED**.
Tasks10–12 have not started.

## Launch and controls

From `C:\Users\amiri\Documents\GitHub\just-peachy`, PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"
prototype\Start-Prototype.cmd
```

Use the local source for task09. Settings → Advanced → **Text-aware reference
selection: On**; default Off. Enroll with **Read paragraph → Done**, participation
and consent. At READY, **Review paragraph coverage** compares intended/decoded
words and support; add a separate review note with the touch keyboard, return,
and Save. People → person → **Review latest paragraph evidence** reopens it.

For a compatible name mode, Advanced → **Compare base / alternate voice scores**
shows both cosines for the same latest query and the query's age. The original
score still decides names/Unknown. Toggle Off then Stop/Start for original-only
operation. Settings apply at next enrollment/Start; this never restarts capture
implicitly. Timed/free-speech/paragraph enrollment, profiles, modes, recipes,
spatial/seat controls and applicable O0/O1 choices remain.

## Implemented behavior

| Component | Change and limit |
|---|---|
| `app/enrollment_progress.py` | Optional unbiased Sherpa token snapshots captured before endpoint reset; default-off path unchanged. |
| `app/script_evidence.py` | Matches intended versus independently decoded words; uses source-offset BPE emissions as approximate hints. Unknown/out-of-source timing stays unknown. No timestamp clamping, forced transcript or phone boundary claim. |
| Alternate contexts | Quality-admitted, contiguous nonoverlapping 2–4s audio; at least two agreeing estimated words; lexical diversity; maximum six. No reference splicing or repeated-duration inflation. Normalized context mean, then compatible reference mean per person. |
| `app/controller.py` | Retains bounded source only when optional paragraph helper enabled; selects contexts after capture/quality Stop; releases source afterward. Helper failure falls back to original Save. Notes are separate; stored review and score snapshot added. |
| `app/people.py` | Original anchors/centroids retained. Sidecar binding/size/span/vector validation and exact export/import/rename/delete support. Extra matrix scores are advisory; original scorer return is unchanged. |
| `app/script_evidence_ui.py`, `app/ui.py` | Advanced toggle, post-recording/stored coverage review, touch note entry and latest base/alternate comparison. Actual portrait pages inspected. |
| `app/paths.py`, `config/release_capabilities.json` | `script-evidence-v1` compatibility guard; local extension metadata. Original release version/archive not overwritten. |

ScriptEvidence v1 records script/transcript versions and hashes, source float32
audio SHA, sample rate/count, tap/gain/domain/preprocessing/model bindings,
utterance/clip/span IDs, estimated word spans and confidence method, quality
support, unknown/rejected coverage, context vectors, unique duration, original
anchor hash and separate user notes. `phone_boundaries=null`; dictionary and
pronunciation variants are unavailable. The original paragraph remains editable
and its default text is unchanged. Notes/ASR difficulty never remove original
quality-admitted voice evidence.

No CTC worker was added. Sherpa1.13.4 `get_result_all` token timestamps plus
`start_time` are emission times, verified against the exact upstream implementation.
Some final tokens arise after the recorded source because the existing decoder
flush adds internal padding. Those tokens remain unknown; valid earlier tokens
remain usable. No padding enters reference duration or embeddings.

An alternate bank cannot be reconstructed from old whole-reference vectors.
Only newly recorded optional paragraph references acquire it. Old profiles stay
usable, with alternate scores unavailable until an appropriate reference exists.
Raw source audio is not retained by the helper. Sidecars themselves contain
private vectors/transcripts and belong only in the external personal store.

## Executed verification and actual observations

| Check | Result / scope |
|---|---|
| Complete application suite | 269 PASS, zero failures/errors/skips; 28.22s. Includes 12 new task09 contract/Tk checks. Synthetic audio/control tests are labelled as such. |
| Four native references | Two people (CMU awb/bdl), each original a0001 and a0003. Each keeps 3.0s original support and selects one 3.0s alternate context: 12s total original and 12s total alternate, no extra unique source duration. All are limited short references. |
| Fresh queries | awb/bdl a0016 and outsider clb a0001/a0016 have hashes disjoint from reference files. Ordinary gallery returns match exactly with advisory comparison On/Off. |
| Actual C088 identity | 4.085s known query stays tentative: voice score passes, disjoint support is insufficient. A 9.640s constructed query of **three complete distinct recordings** awb a0016–a0018 confirms the correct enrolled UUID. This is a labelled query construction, not an enrollment splice. |
| Impostor / same words | 3.685s clb a0001 uses the reference prompt but remains Unknown throughout native identity decisions; no enrolled UUID confirmed. clb a0016 is the different-person/different-text contrast. |
| Same person / same words | Reference-audio comparison explicitly in-sample, never described as fresh accuracy; same-person/different-text queries are independent. |
| Wrong/skipped/repeated intended script | Wrong script selects no alternate; skipped/repeated variants preserve original 3s and never create additional source support. Approximate agreement changes honestly. |
| Background / quiet / short | Derived two-voice overlap, 0.01× low-level source, and 0.4s reply fail the original quality gate and select no bank. No threshold softened. |
| Storage / recovery | Original NPY hash preserved; rename/delete/export/import, O0/O1 mismatch refusal and compatible O1 bank, tamper/duplicate-span rejection, default/base parity, optional-helper failure, actual JSON size bound, required-feature refusal and lock cleanup pass. |
| UI | Actual controller reads copied native profiles and handles settings/review. Four 480×800 PNGs inspected. Score screenshot is a frozen native receipt, explicitly not a live microphone run. |

Representative **raw whole-query cosines** below; these are not temporal pipeline
decisions, probabilities or matched-content scores:

| Fresh query / reference person | Original | Alternate |
|---|---:|---:|
| awb different text / awb | 0.702 | 0.651 |
| bdl different text / bdl | 0.752 | 0.714 |
| Outsider clb, same prompt / awb | 0.216 | 0.040 |
| Outsider clb, same prompt / bdl | 0.094 | −0.074 |

Both genuine and impostor scores decreased in this small sample. **No general
identity accuracy improvement is demonstrated**, and no threshold was calibrated
from these paragraphs. Selection/provenance is functional; alternate inference
stays advisory. Existing C088 threshold/margin/unique/disjoint rules are unchanged.

## Measured costs and bounded storage

Final complete native check: **24.25s wall**, **21.22s CPU**, maximum **sampled
RSS 518.25 MiB** (543,428,608 bytes, not OS peak/CM5 qualification). Each of the
four reference helpers made one extra 3s embedding, taking **36.6–42.9ms** for
selection/embedding before sidecar persistence. Installed models were shared;
one speaker-model load, two sequential ASR loads because the test transitions
from enrollment configuration to Balanced, 14 stream creations. This is not
14 models or an additional live ASR worker.

Two-person resident gallery timing, 100 calls after warmup: median ordinary score
**3.50µs**, advisory comparison **17.95µs** (~14.45µs extra); no inference within
this timing loop. It is a small desktop observation, not a scaling guarantee.

Temporary source bound is 180×16000 float32 = 11,520,000 bytes, plus up to another
11,520,000 bytes during concatenation, then released. Maximum six context
embeddings after Stop; per-sidecar 256 KiB measured with actual serialized JSON.
Up to 16 notes of 500 characters. No optional CTC stack or dictionary memory.
Existing profile/archive limits remain; export includes unencrypted sidecars.

## Evidence, provenance and rollback

Public source-bound receipt: `docs/UIITER2_09_CHECKS.json`. Exact installed runtime
versions, eight rehashed model assets and source/licence review:
`docs/UIITER2_09_DEPENDENCIES.json`. No new third-party artefact was installed;
existing model/data rights remain distinct from code licences. A **synthetic,
nonprivate, vector-free preview** is `docs/UIITER2_09_SCRIPT_EVIDENCE_SAMPLE.json`;
it is not a loadable person profile or claimed native measurement.

Private evidence under `Resumes/.uiiter2_09`:

- `unit_final/FINAL_UNIT_CHECKS.json` and text log: final app/tests/source hashes.
- `native_accepted/NATIVE_SCRIPT_CHECK.json`: final native model/query evidence,
  exact source hashes and per-stage resource observations; vectors/session data
  remain alongside it privately.
- `ui_final/UI_CHECK.json` and four PNGs: inspected controller/native-profile
  views, using the earlier passing `native_final_v2` fixture store.
- `prototype_before_09.zip` and `baseline.json`: 243-file checkpoint of local
  tasks01–08. Failed/intermediate checks stay labelled and preserved.

Exact recreation commands and inputs/outputs are in
`app/README_SCRIPT_EVIDENCE.md`, `tests/README_SCRIPT_EVIDENCE.md`,
`tools/README_SCRIPT_EVIDENCE.md` and the private workspace README.

Preferred rollback is the toggle Off and Stop/Start: same profiles, original
identity behavior. For **source** rollback, close the app and first dry-run
(from repository root, CMD/Anaconda omits the leading `&`):

```powershell
& .\.edge-speech-env\python.exe Resumes/.uiiter2_09/restore_before_09.py
# Only after reviewing that dry-run, apply the same hash-checked restore:
& .\.edge-speech-env\python.exe Resumes/.uiiter2_09/restore_before_09.py --apply
```

The restore refuses later edits and incompatible selected data, restores changed
files from the checkpoint and moves new code into a verified private backup.
It does not alter people/models, Git history or the older release. If new
sidecars have been saved, use the current source with the toggle Off; an old
reader cannot open `script-evidence-v1` data. An explicit separate compatible
data root can be selected using `--data-root PATH` for rollback validation and
`JUST_PEACHY_DATA=PATH` for subsequent launch. Do not delete feature markers or
overwrite current profiles to force a downgrade. Corrupt declared sidecars
are visibly rejected; the feature switch is not an integrity bypass.

Preserved export: `G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.2.0.zip`,
SHA256 `f29db30c1f05d4ba32cf44f77cdff790fc51d04dc588020401f4c8f912875af4`.
It contains tasks01–08, **not task09**. The same portable source architecture
is retained; new ARM64/live testing and a separately versioned future export
are required before describing this extension as CM5-qualified. No workbook
was edited; insertion notes are in `WORKBOOK_UPDATE.md`.
