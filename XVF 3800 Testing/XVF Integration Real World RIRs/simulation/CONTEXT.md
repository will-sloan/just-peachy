# Active post-measurement context

Latest completed stage: S2 full 121-record RIR library, run `20260908T203309Z`. Current canonical set: `rir_library/v1/RIR_MANIFEST.json`; outcomes 95 EXTRACTED, 26 EXTRACTED_WITH_LIMITATIONS, zero FAILED. See `rir_library/v1/RESULTS.md` and `S2_README.md`. S0/S1 remain immutable historical parents. Physical replay and independent acoustic/scene validation are still unperformed; simulation-ready flags remain false.

Authority order: current user corrections; recorded audit facts; matching XMOS interface documentation; current V5 workbook for goals/plans. Workbook resolved to `C:\Users\amiri\Downloads\XVF_Measurement_V5.docx`, SHA256 c9a6badcd83065ae9f865de841c077f00668a480e1f0170c115c514e30a99db6.

Use only the current explicit 121-record formal REVIEW allowlist: historical 127 minus six exact Loeb Caf scope exclusions. Preserve the original 52 exclusions and forbid excluded noise windows. Upper Loeb stays active. Both original 100 m entries are bound by exact identity to effective 1.00 m. Never rescale the effective field twice.

Active angle context is carried from v2 into `config/scope_and_room_context.v3.json`: approximately ±4–5 degrees or less, conservative half-width 5 degrees, user_clarification, independently_calibrated=false. This replaces the percentage/denominator question. Preserve signed centers, native radians separately, circular wrap and linear front/rear ambiguity. No precise angle ground truth is established. ±10/20 are only possible future artificial robustness tests.

Preserve user-reported source-facing-tablet context, unresolved library alias, NAT tokens and unknown XYZ/height/yaw/photos. Do not fabricate geometry or enforce delays to match labels. Preserve Category 3 gain 10/delay −32 and separate Realtek acoustic clock. No qualified RIR exists in the audited/inspected project outputs.

Keep the current eight H2 assets exactly as bound. Active model ancestry and user-reported earlier tuning benefits are different kinds of evidence; do not swap to parent weights based on older prose. Current board read-only state is USB 16/16; no setters were sent. Physical format and HIL qualification belong to S3.

S1 used up to 4 workers, inner threads 1, CPU only, 16 GiB RAM budget, 5 GiB scratch cap, >=50 GiB free disk. Fresh SSD evidence supersedes S0: G: now has about 449 GiB free; C: about 82 GiB during work. Read exact time-stamped S1 resource snapshots before planning storage. No automatic later-phase execution.


## S1 active scope update — 2026-09-08

S1 is authorized only for the revised 12-record pilot. Historical 127 eligible and 52 excluded remain. Active set: 121; six exact `Loeb Caf` records additionally excluded, including all noise/stress/training uses. `Upper Loeb` remains active. Preserve the two bound 1.00 m corrections and ±5 degree user-estimated angle half-width. Qualitative context is not a numeric room model.

- Arise Kitchen Main Table: Resembles a breakfast countertop or high-seated dining position inside a kitchen. One end opens into space leading to a hallway.
- Arise 5th floor low table: A round, low-seating coffee spot or coffee-table setting. One end opens into space leading to a hallway.
- Upper Loeb: Resembles a slightly high-seated booth for about four people at the side of a large restaurant with very high ceilings. The booth is perpendicular to the wall, with a window on one side and the open restaurant on the other.
- Arise Floor 2 Kitchen: A rectangular dining table in a kitchen or enclosed room with one wall open. A hallway runs perpendicular to the room, with the hallway and wall arrangement described as T-shaped.
- Library Conference Room: A square table in a sealed/enclosed, conference-room-like setting, with concrete and glass on most surrounding surfaces.

Current overlay: `config/scope_and_room_context.v3.json`. S0 and both supplied reference packs stay immutable. No hardware/H2 changes or automatic S2.
