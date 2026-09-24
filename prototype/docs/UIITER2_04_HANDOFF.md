# UIITER2 task 04 — Explicit rosters, Unknown and scores

Implemented locally on 20 September 2026. **209 software checks PASS**, six
bounded native file cases PASS, and a final native display-isolation check PASS.
Completed task 01–03 changes are retained. No new model/library, threshold
fitting, training, corpus sweep, automatic commit/push or master Word edit.
Task 05 has not been started.

## Launch and controls

From `C:\Users\amiri\Documents\GitHub\just-peachy` in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD or Anaconda Prompt from the same directory:

```bat
prototype\Start-Prototype.cmd
```

The app opens idle. Mode now offers **Just Transcription**, **ALL enrolled +
constant Unknown**, **SELECTED + constant Unknown**, and **SELECTED + Closed
group (Always assign)**. Spatial-assisted/C079 and Strongly Spatial-assisted/
C060 each have explicit ALL and SELECTED variants with constant Unknown.
Advanced retains **Numbered Unknowns** (no gallery) and **ALL enrolled + Numbered
Unknowns**, plus live scores and developer sensitivity/weight controls.

Short titles have the requested full meanings in subtitles/help. Ordinary
named/spatial views always use one Unknown without removing internal tracks,
segmentation, UUID matching or diagnostics. Experimental modes stay selectable;
actual missing/incompatible references are reported as capability issues.

Selected-mode entry opens a draft UUID roster; compatible current-tap references
are selectable, duplicate names retain separate UUIDs, and missing references
are visibly unavailable. Cancel/Back sends no mutation. Empty selection cannot
start identification. Apply validates before stopping/draining and switching at
a fresh epoch, reusing models. Roster UUIDs persist privately. Historical captions
retain their original epoch's evidence; this is not retroactive relabeling.

Closed group chooses the most compatible selected profile for eligible current
voice, including below the normal open-set threshold. Rejected open-policy names
are visibly **· assumed**, with raw scores and `assignment=forced` recorded.
A sole selected person is explicitly a user-assumed label. Missing/stale voice,
silence, overlap, absent track or audio-gate failure never invents a name/score.
This can misname a waiter and does not establish word-by-word overlap identity.
Forced identities do not update personal references.

**Separate display features** use independent `display_roster_ids`; matching
uses `roster_ids`. Highlighting, hiding and Show all neither change the matching
gallery nor restart capture. Hiding requires an already selected named mode and
an explicit warning. The full transcript remains in the archive. Show all keeps
the identity mode while restoring visibility.

## Actual implementation and exported configuration

- `app/mode_policy.py`: ten mode definitions, separate roster/Unknown policy and
  bounds on three existing parameters. `app/people.py`: real selected UUID matrix
  loading, compatibility summaries and gallery provenance.
- `app/identity_policy.py`: native C088 resolver remains the open-set calculation;
  the explicit closed override queries the current vector only after clean/fresh
  voice gates. Existing anonymous tracker decisions remain independent. An adapter
  preserves actual spatial contribution/age without querying the device again.
- `app/pipeline.py`: installs that adapter in the same measured S7 dispatcher;
  links native evidence IDs to assumed caption provenance. No new capture/model
  lane. Vendor algorithms, all frozen configs/assets and actual live source,
  timing, gain and spatial provider files are unchanged from the checkpoint.
- Controller/UI: safe roster/parameter epochs, independent display membership,
  actual decision-recipe provenance, touch roster transaction and Advanced pages.
  Task 03's linked session archive preserves configurations and display-change
  events; its storage/playback implementation is unchanged.
- Dedicated module/test/tool READMEs provide purpose, inputs/outputs and
  PowerShell/CMD/Anaconda commands. `MODE_GUIDE.md` and `MODE_SEMANTICS.md` explain
  evidence, Unknown, visibility, status, failure and field-test limits.

**Effective configuration export:** `prototype/docs/MODE_MATRIX.json` contains
all **46** supported default mode/recipe/O0/O1 configurations, mode semantics,
parameter bounds and source/config hashes. Regenerate using
`tools/export_mode_matrix.py`; commands are in `tools/README_ROSTER.md`.
Actual epochs additionally record selected UUIDs, loaded gallery/reference
hashes, full effective profile and overrides in `prototype_mode_configuration`
and linked `epoch.json`. Raw private evidence remains under the paths below.

Advanced scores show up to three actual candidates/UUID suffixes, raw cosine,
next-candidate margin, accepted/forced/rejected/pending state, threshold,
clean/unique/disjoint support, overlap/freshness, spatial term/age and the
decision's actual recipe. A one-person gallery has no next-candidate margin;
missing fields show `—`. Last-decision freshness/configuration is distinguished
from current selection. The page reads bounded existing events at most 1Hz.
Raw scores are not probabilities and the panel performs no extra inference.

Controls expose existing cosine threshold 0.35–0.75, margin 0–0.15 and spatial
joint weight 0–1.2. Inactive controls are disabled. Defaults remain C088
0.5128856897354127 / 0.03 and C079/C060 weights 0.60/0.90. Changes apply at a safe
epoch, persist privately and are logged; Reset restores exact defaults. These
are independent of 200ms GUI label stability. No threshold was lowered to make
a name appear. Closed mode adds only selected-gallery dot products, not extra
embedding model calls or personal-reference adaptation.

## Executed verification

| Check | Actual result |
|---|---|
| Full software suite | 209 PASS; zero failures/errors/skips; 19.24s |
| Deterministic contracts | Real matrix exclusion, duplicate names/rename/delete/unsupported tap, empty/cancelled roster, open rejection/closed forcing, silence/overlap/stale/invalid voice, no reference changes, parameter bounds/reset, retained spatial parents, independent display membership |
| Selected open, enrolled A | Native confirmed A; 42 actual gallery score calls |
| Selected open, other B | B remained unnamed/Unknown; 40 score calls; loaded only A |
| ALL enrolled, same B file | Native confirmed B with both enrolled UUIDs loaded; 40 score calls |
| Selected closed, same B file | 43 forced decisions, 3 unavailable decisions, 62 explicitly linked assumed caption updates; no reference adaptation |
| Spatial selected / strong spatial selected | Both ran actual C079/C060 configurations and confirmed A; 42 score calls each; file inputs correctly used voice-only fallback |
| Six native cases combined | Six 12s prepared files; 80.69s wall including setup/UI; one ASR load, one speaker-model load, six streams; reference files unchanged and reference/query hashes disjoint |
| Final native running-display check | Changing display UUIDs/hiding did not change gallery ID, engine or the single capture stream; Show all retained the mode. Actual assumed captions and score provenance passed; 17.50s wall |
| Resources | Six-case maximum sampled process RSS 502.96 MiB; last process CPU counter 43.344s. Final short check 465.91 MiB / 6.625s CPU. These are Windows observations, not CM5 qualification or a measured overhead improvement |
| UI/output/cleanup | Actual 480×800 client screenshots visually checked; native workers/owners closed, default Windows output observations unchanged; no audible playback |

The native data is two existing CMU ARCTIC speakers in explicitly isolated dry
test-fixture stores, with unchanged real ASR/segmentation/ReDimNet inference.
It is not the user's personal gallery or a new microphone enrollment. The first
helper attempt correctly failed the existing PCM16 admission rule; the helper
was corrected and decoded-byte equality checked, without changing runtime gain
or weakening admission. Earlier receipts remain local and are not overwritten.

The final native check predates only two UI-only refinements: limiting the
historical assumed suffix to named views and clarifying the Settings Advanced
button text. Exact reverse-patch hashes bind those edits to native evidence;
the final 209-check suite covers them. The six-case proof's core inference/
gallery files and effective configurations still match the delivered source.

**NOT_TESTED:** fresh live/XVF acoustic naming, real group/outsider usability,
physical touchscreen, robust overlapping-person accuracy, broad recognition
generalization and CM5 total-RAM/performance. Spatial cue conflict/freshness/
decay has retained deterministic coverage; file fallback is not proof of current
hardware direction accuracy. No speech/identity accuracy gain is claimed.

## Local evidence and rollback

Private evidence root:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Resumes\.uiiter2_04
```

Six-case receipt: `native_v2\ROSTER_NATIVE_CHECK.json`. Final display/score
receipt: `final_smoke_v2\FINAL_NATIVE_CHECK.json`. The final native epoch is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Resumes\.uiiter2_04\final_smoke_v2\conversations\ebf01b9e710543a5aedaa6884872be2c\epochs\019fd80f91fe4925817ae58ad8077d48
```

Compact hashes/results: `prototype/docs/UIITER2_04_CHECKS.json`. Six actual
corpus-fixture screenshots are under `prototype/docs/evidence/uiiter2_04`;
full private recordings/vectors/logs stay outside publication. Normal personal
data remains `C:\Users\amiri\JustPeachy\data` or its configured override.
Existing release ZIPs are unchanged; this update is in the exportable source
checkout. Rebuild through the existing release process when packaging it.

The rollback ZIP preserves completed **local tasks 01–03**, not just git HEAD.
Close the app/tests. From the repository in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_04\restore_before_04.py
# Review the dry-run before applying:
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_04\restore_before_04.py --apply
```

In CMD/Anaconda Prompt, use the same commands without `&` and the comment line.
The script verifies hashes, refuses later edits, restores task 04's pre-existing
files and moves new Python modules to a private backup. It does not touch
people/conversations/models. New docs/evidence remain historical. An older UI
lacks the closed-group assumed markers; preserve and interpret task 04 archives
using their explicit assignment fields or this updated UI. Only the dry run
was performed. No commit/push or release build was performed.
