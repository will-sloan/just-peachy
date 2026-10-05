# Full application restoration

Request: restore the mature application over the current runtime; no redesign or broad revert. Build17, all galleries and recordings remain rollback/reference inputs. This list tracks implementation separately from actual CM5 validation.

| ID | Concrete work and exit evidence | State |
|---|---|---|
| R01 | Locate original UI, twelve Mode definitions, roster, drag/drop seats, enrollment prompts/quality/CRUD and History; identify bypass in build17. | Located; source map below |
| R02 | Reconnect original Modes/People/Settings/seat/roster pages to a lightweight controller, with backend and application Mode independent. | Implemented; see limits below |
| R03 | Pass selected Mode, UUID roster, seating and exact settings into the current isolated pipeline; preserve model-specific matching gates and motion trust. | Implemented; compatibility limits below |
| R04 | Restore explicit-consent paragraph enrollment and persistent ReDimNet/TitaNet-specific CRUD through an owned bounded process. | Implemented; real encoder/quality helper preparation passed; human enrollment pending |
| R05 | Replace normal 300-second expiry with manual Stop plus measured storage/resource limits; retain finite load/drain/backlog/cleanup and bounded rolling state. | Implemented; normal desktop policy and310.2s manual Stop passed |
| R06 | Post-drain Save session / Discard; retain full synchronized processed/raw/caption/beam/motion/configuration package; History reopen/rename/delete/export and explicit paths. | Implemented; rich Save/whole-session Discard/30member PC export passed |
| R07 | Build a new immutable runtime from build17, with source backups and independent restores; retain all backend/profile assets and one shortcut. | Build21 installed/activated; rollback preserved; Backup08 verified |
| R08 | Focused native source/model/Stop/closure regression spanning both diarizers, both encoders, anonymous and a newer geometry; one manual-stop live run beyond five minutes plus save/discard/export checks. | Passed representative checks03/04/06/07/10/11/12; quality/hour claims excluded |
| R09 | Activate reviewed candidate, update mode/pipeline/recovery/operator guides, create verified handoff and publish reviewed source. | Activation/guides complete; final archive and publication certified by adjacent receipts |

## Recovered source map

Repository source `prototype/app` was retained by commit `509195b8` (accepted rc5 preservation), with shared backend separation in `2a8a2183` and N2 model/gallery integration in `d22ec204`. Relevant current source history ends at `f709f1fd` for these files; BMI270 work did not delete them.

| Feature | Actual existing implementation | Build17 regression |
|---|---|---|
| Navigation/captions/settings | `prototype/app/ui.py`, `config/ui.json` | Original class loaded, but several pages overridden by facade |
| Twelve Modes | `app/mode_policy.py`, Controller switch/effective_profile | Facade allows only transcription and one identity display mode; worker hardcodes mode |
| Selected participants / display roster | `app/roster_ui.py`, Controller switch/display_roster | Facade returns empty people/roster and rejects strict display |
| Draggable seats / session anchor | `app/seat_ui.py`, `seats.py`, `seat_controller.py`, `seat_identity.py` | Page/controller/provider disconnected |
| Paragraph enrollment / quality / CRUD | `app/ui.py`, `controller.py`, `enrollment_quality.py`, `enrollment_progress.py`, `people.py`, `n2_people.py` | People override and read-only runtime gallery adapter bypass creation |
| History management | `app/session_ui.py`, `session_controller.py`; v29 `storage.py` | New store exists; facade omits rename and richer metadata; discard retains transcript |
| Manual-stop operation | v29 profiles/launcher/worker/source/authorization/storage | Fixed 300-second policy is enforced at multiple layers |
| Beam/motion provenance | Current source/provider/mounted motion | GUI uses latest-only snapshots; full common session recording must be connected |

Historical simulation/component results are not proof that restored native integration works. No hour-long whole-application qualification is claimed.

## Scope of completion

R02/R03 restore all twelve Mode definitions with explicit compatibility checks.
Assigned seats are Pyannote/ReDimNet only; saved spatial replay is not connected.
R04 reuses real paragraph/consent/quality/Save/CRUD and prepares both actual
encoders/quality models in closed helpers; human enrollment quality is untested.
R05 normal desktop manual lifetime is verified;310.2s manual Stop passed in a
finite qualification envelope, not an hour/sustained-real-time proof.
R06 rich Save, whole-session Discard and30member export/PC readback passed.
Optional DPDFNet, adaptive promotion, Windows transcript review and RAM audio
excerpts remain unavailable with precise explanations. These limits remain
listed; the checklist does not silently count them as implemented.
Noisy accuracy, physical touch/offline coldboot and battery/hour validation are
future physical tests. The matched replay/screen/offload automation is deferred.
