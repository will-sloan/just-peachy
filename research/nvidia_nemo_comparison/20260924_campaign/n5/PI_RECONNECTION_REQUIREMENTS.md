# Pi reconnection and backend availability — N5 requirements addendum

The user's reminder on 2026-09-25 confirms the intended delivery: after the
offline campaign, connecting and powering the Pi should lead through a short,
repeatable install/verification process to usable GUI backend choices. The Pi
is currently unreachable; no deployment or device inspection occurred in this
campaign. This document records remaining acceptance requirements, not completed
installation or a promise that every candidate fits or runs on the device.

Use one shared frontend with the accepted backend picker and clearly named
launchers for the available compositions. Retain the baseline. Make additional
backends available locally when their Linux ARM64 runtime/model route is
validated and storage permits. Clearly explain desktop-only, unsupported and
not-yet-installed choices; never silently switch backends after a load failure.
Loading one backend at a time must not require loading every installed model
into RAM. Storage capacity and working RAM/CPU performance are separate checks.

N5 should deliver the following before claiming the reconnect workflow ready:

1. A final `START_HERE` entry identifying the exact archive, hash, supported OS,
   selected configurations and tested status, with a short PowerShell deployment
   path and a USB/offline alternative. Provide equivalent CMD/Anaconda steps.
   Required inputs are the user's current host/address, username and verified
   host key/identity file, or the USB mount path. Do not reuse an old IP address
   as device authority, invent credentials or change host-key security.
2. A read-only preflight for architecture, OS/ABI, Python/GUI/native dependencies,
   writable install/data roots and actual free storage. Report exact download,
   transfer, staged-install, installed and rollback space for the final selected
   set, counting identical hash-addressed assets once. Include extraction and
   temporary copies in peak-space checks. The target is 32-GB eMMC; do not assume
   all nominal capacity is free or choose an arbitrary number of backends.
3. A core baseline bundle plus optional validated backend assets when this
   reduces storage pressure. Prefetch pinned assets for offline startup; avoid
   cloud downloads at first GUI launch. Any missing OS packages remain a clearly
   described prerequisite. Do not reflash the OS/XVF, enable services, assign
   GPIO pins or perform unapproved administrator changes to hide prerequisites.
4. A deterministic verify, stage, health-check, activate and launch sequence.
   Verify transfer/extracted hashes and architecture before activation. Preserve
   a usable prior version and a short rollback command. Preserve personal data
   outside versioned code and research profiles outside production enrollment.
   Encoder-specific galleries must report incompatibility instead of reusing
   vectors from another model. Give exact input/output paths and failure steps.
5. For every retained Pi backend, offline ARM64 import/load and saved-WAV
   functional/state/flush checks where technically possible, labelled EMULATED
   when run under QEMU. Test the shared frontend integration and startup failure
   paths without pretending that a binary audit or CLI help constitutes model
   inference. Bind each package and configuration to reviewed source/remote refs.
6. A final on-device checklist for after reconnection: confirm device identity,
   OS/storage, installed hashes and health output; start each installed GUI
   backend idle; run saved-audio captions and modes; verify persistence, backend
   switching, model namespace and rollback; then measure actual CM5 memory and
   source-paced performance. Keep live microphone/XVF and other hardware tests
   separately labelled and gated by their later authorization/configuration.

Current reusable evidence: `INSTALL_CM5.md`, `README_ARM64.md`,
`UPDATE_ROLLBACK.md` and `ARTIFACT_INDEX.json` describe the preserved baseline
offline bundle, install/deploy helpers and ARM64 engineering artifacts. The
baseline bundle contains 13 target wheels and eight pinned assets. Those earlier
artifacts are preparation evidence; they are not final N4-selected multi-backend
releases, and QEMU loader checks are not a model/WAV smoke. Preserve them and
produce fresh versioned derivatives instead of overwriting their hashes.

As of this reminder, N2 and N3 have accepted offline component handoffs, N4 ASR
full-bank component review has passed and D1 component evaluation is active.
N4 integrated acceptance and final release selection remain outstanding. The
old N5 handoff predates these upstream changes; use current N4 stage receipts
and `../n4/REMAINING_EXECUTION.md` for execution ordering. The existing task's
30-minute recurring continuation is active. N5 remains incomplete.

Offline checks can establish package/build/software readiness. Only actual
later device evidence can establish that files are installed on the Pi, GUI
backends run there, and its storage/RAM/performance requirements are met. The
campaign deadline and packaging reserve remain unchanged.
