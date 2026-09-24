# N1 foundation: shared UI, data and supervision

This campaign directory contains reviewed scripts, configuration, redacted
receipts and the stage handoff. The application source is the worktree's
`prototype/`. Large assets, saved audio bindings, full transcript audits and
event logs stay outside Git under `G:\Just_Peachy_N1\20260924_campaign\local`.
The original checkout and personal data are preserved. The Pi is off throughout
the campaign. N1 uses saved processed audio only and starts no microphone.

Read `N1_HANDOFF.md` for acceptance, remaining limitations and N2 prerequisites.
The N1 instructions and current user request override historical auto-listening
and hardware statements in inherited prototype deployment documents. This
version always opens idle and blocks hardware unless a later user deliberately
uses the separate future-live opt-in. No such live test occurred in N1.

## Run the baseline later

`Start-N1.ps1` / `Start-N1.cmd` start the installed baseline with a separate
research data root and the existing verified model cache. Inputs are
the source release, Python environment and model files; outputs are the normal
GUI plus local captions/session journals under `local\manual-baseline`.
The launchers are for later manual use, not automatically started by N1.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign'
.\Start-N1.ps1
```

CMD / Anaconda Prompt (no environment activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign
Start-N1.cmd
```

Paths can be overridden with `-Python`, `-SourceRoot`, `-DataRoot` and
`-ModelsRoot`. Keep each simultaneously open version in its own data root. Only
one model stack is allowed for later 2 GB qualification; two research workers
are not a target-memory measurement. Candidate backends appear honestly as
unavailable until their adapters are implemented and validated.

## Reproduce a source freeze

`freeze_release.py` copies allowlisted source/doc/config/license files into a
new directory, writes a ZIP and hashes the runtime/frontend content. It refuses
an existing destination. Inputs are reviewed source and two explicit output
paths. Outputs are the frozen source, adjacent ZIP and JSON receipt; it excludes
audio, models, personal data and test evidence. Do not edit a frozen version.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\freeze_release.py --prototype '..\..\..\prototype' --destination 'G:\Just_Peachy_N1\20260924_campaign\local\releases\NEW_VERSION' --receipt 'NEW_VERSION.json'
```

CMD/Anaconda uses the same arguments with the quoted executable and paths;
omit PowerShell's initial `&`. Pick a new version after a critical correction
and rerun affected paired checks. The standard application release builder is
documented in `prototype/release_tools/README.md`; N1 release receipts identify
the actual staged archive and successful health/asset checks.

## Component guides

- `data/README.md`: exact captured-pair and E/C/Q audits; source-paced baseline
  runner; private evidence; supplemental saved regressions.
- `assets/README.md`: pinned official downloads and isolated native CPU build.
- `supervision/README.md`: status, resume, scheduled tasks and final cleanup.
- `frontend/README.md`: actual frozen GUI replay on a private Windows desktop.
- `review/README.md`: software checks with hardware calls disabled.

No script modifies the master workbook. `WORKBOOK_UPDATE.md` is a proposed
insertion only. Keep original/normalized references and raw/edited captions
separate. Unavailable timing or punctuation truth stays explicitly unavailable.

## Build the analysis handoff

`package_handoff.py` consumes `HANDOFF_FILES.json` and completed `N1_METRICS.json`.
It writes a new analysis-only ZIP and SHA-256 receipt, verifies every archived
member, and enforces the 20 MiB hard ceiling. Its reviewed allowlist excludes
private speech, full transcripts, model files and large event logs.
The 59-file ZIP is an analysis handoff. Launch and reproduction commands use
the installed release or full campaign worktree; scripts omitted from the ZIP
are available in the verified campaign Git commit.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\package_handoff.py --output 'G:\Just_Peachy_N1\20260924_campaign\N1_HANDOFF.zip' --receipt .\HANDOFF_PACKAGE.json
```

CMD/Anaconda uses the same double-quoted executable and paths without `&`.
Use a new output filename for a revision; the script never overwrites a ZIP.

`assemble_receipts.py` is the final acceptance gate. It reads the complete
corpus, 96-cell screen, 8-cell regression, 96-cell GUI and test evidence from the
explicit campaign/external roots; rechecks frozen files and release archives;
then writes redacted recovery, release, test, supervisor and N1 metrics JSON.
It stops on any absent/incomplete prerequisite. It does not rerun inference or
change a personal data root. Run it before packaging:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\assemble_receipts.py
```

CMD/Anaconda uses the same quoted executable without `&`. Override `--root`
and `--external` only for a verified relocated campaign with the same receipts.

`finish_n1_checks.py` is a bounded, one-owner continuation of N1's numerical
acceptance, not an LLM or another scheduled dispatcher. It waits for the exact
96-cell run and its owner to finish, starts the eight-cell supplemental job via
the same supervisor, renders the main final snapshots on a private desktop,
then runs both redacted analyses. Inputs are the frozen paths and existing
checkpoint contracts above. Outputs are `local/FINISHER_STATUS.json`, dedicated
logs, GUI receipts and the final analysis files. It does not publish or start N2.
It fails closed on numerical failures and preserves evidence for review.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\finish_n1_checks.py
```

CMD/Anaconda uses the same quoted executable without `&`. Run at most one copy;
the OS lock rejects a second owner. The actual campaign invocation is hidden
and below-normal priority. Existing complete results are reused only after the
analysis revalidates their hashes. Do not start it again while its PID is alive.
