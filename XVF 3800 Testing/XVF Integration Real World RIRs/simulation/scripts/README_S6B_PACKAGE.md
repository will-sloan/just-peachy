# Reviewed compact S6B handoff packager

`s6b_package.py` builds the final compact archive from an explicit reviewed file
whitelist. It starts no models, discovers no extra files, changes no source
artifact and deletes no historical results. The real build is deferred until
the owner supplies `HANDOFF_BUILD_SPEC.json` with passed final-review,
challenge-completion and full-completion receipts.

## Input contract

The build spec uses this structure. Paths are absolute local paths; the example
hashes and counts must be replaced by the actual final reviewed evidence.

```json
{
  "schema": "s6b-handoff-build.v1",
  "metadata": {"stage": "S6B", "run_id": "20260909T230840Z"},
  "stage_status": {
    "final_review": "PASS",
    "challenge_completion": "COMPLETE",
    "full_completion": "COMPLETE"
  },
  "output_path": "C:/absolute/handoffs/S6B_CHATGPT_HANDOFF.zip",
  "artifact_index_archive_path": "LOCAL_ARTIFACT_INDEX.json",
  "members": [
    {"source": "C:/absolute/report/HANDOFF.md", "archive_path": "HANDOFF.md", "sha256": "actual SHA256"},
    {"source": "C:/absolute/report/LOCAL_ARTIFACT_INDEX.json", "archive_path": "LOCAL_ARTIFACT_INDEX.json"},
    {"source": "C:/absolute/report/figures/comparison.png", "archive_path": "figures/comparison.png", "figure_id": "comparison"},
    {"source": "C:/absolute/report/figures/comparison.svg", "archive_path": "figures/comparison.svg", "figure_id": "comparison"}
  ],
  "gates": [
    {"name": "final_review", "source": "C:/absolute/report/FINAL_REVIEW.json", "sha256": "actual SHA256", "status_pointer": "/status", "expected_status": "PASS"},
    {"name": "challenge_completion", "source": "C:/absolute/report/CHALLENGE_COMPLETE.json", "sha256": "actual SHA256", "status_pointer": "/status", "expected_status": "COMPLETE", "assertions": [{"pointer": "/completed", "equals": 1584}, {"pointer": "/requested", "equals": 1584}]},
    {"name": "full_completion", "source": "C:/absolute/report/FULL_COMPLETE.json", "sha256": "actual SHA256", "status_pointer": "/status", "expected_status": "COMPLETE", "assertions": [{"pointer": "/completed", "equals": 480}, {"pointer": "/requested", "equals": 480}]}
  ]
}
```

Counts above are schema examples, not assertions that a final campaign used
those denominators. The owner supplies the exact appropriate counts and JSON
pointers from completed receipts. A gate may require `PASS`, `COMPLETE` or
`COMPLETE_PASS`; final review must require `PASS`. `stage_status` must exactly
match the verified gate statuses. Each declared assertion is checked.

Member SHA256 values are optional; when supplied, changed source bytes reject
the build. Every copied member is hashed regardless, rechecked at copy time and
again before publication. Gate SHA256 values are required. Metadata is copied
as provided, never silently changed to claim completion.

The supplied local artifact index must be a whitelisted JSON file containing a
nonempty `artifacts` or `rows` list. Each row must include absolute `path` and
64-digit `sha256`. The packager validates that shape and includes the exact
index bytes; it does not reread all heavyweight files listed inside it. Their
validation belongs to the supplied final evidence/receipts.

## Compactness, figures and provenance

Allowed file types: Markdown, JSON, CSV/TSV, text, Python, PowerShell, BAT/CMD,
TOML/YAML, PNG and SVG. Audio, vector banks, model binaries, full native logs,
Word workbooks and nested archives are excluded, including renamed forbidden
source extensions. Raw artifact folder names and known full log names reject.
Only the explicit whitelist is copied; no recursive directory collection occurs.

Every PNG/SVG requires an explicit scientific `figure_id`. One PNG and one SVG
for the same figure count once. Up to6 distinct figures are accepted, so4
PNG/SVG pairs count as4 figures. At most512 supplied members,16MiB per member,
64MiB uncompressed and20MiB final ZIP are accepted. The normal target remains
2–10MiB; a smaller valid handoff is allowed. The final review is responsible for
the figures being meaningful scientific plots rather than redundant images.

Archive paths must be canonical relative forward-slash paths. Absolute paths,
traversal, duplicate paths including case-only differences, duplicate sources,
Windows device names and the reserved `PACKAGE_MANIFEST.json` reject.

`PACKAGE_MANIFEST.json` inside the ZIP records each copied member's original
absolute path, size and SHA256, metadata, verified gate bindings, source spec
binding and packager binding. It excludes its own bytes, creating a finite
provenance graph. The archive checksum and verification receipt are outside the
archive and never become self-referential members.

## Outputs and publication

For `S6B_CHATGPT_HANDOFF.zip`, the build also writes:

- `S6B_CHATGPT_HANDOFF.sha256`: final archive SHA256 and filename.
- `S6B_CHATGPT_HANDOFF.receipt.json`: passed gates, archive binding and independent
  unzip verification receipt binding.
- A uniquely named `.package_verification_*` directory beside the archive with
  independently extracted members and its verification receipt.

The complete ZIP is fsynced and closed before a separate Python process reopens
it, verifies CRCs, extracts its exact member inventory, and hashes extracted
files. Publication uses a same-directory atomic hard link that fails if a final
target already exists, including concurrent creation. The source filesystem
must support hard links (the study's local NTFS volumes do). Only this
invocation's temporary link is removed after successful publication. Failed
staged archives/extraction folders remain for diagnosis. No prior archive,
source, historical result or failed attempt is overwritten or cleaned up.

If publication partially succeeds but writing an external receipt fails, inspect
the retained archive and staging evidence; do not rerun with overwrite. Use an
explicit new final filename only after diagnosing the failure. No accuracy
rerun or source mutation is performed by this utility.

## PowerShell

Model-free fixtures use a new isolated directory. The21 checks include exact
copy/extraction hashes, no-overwrite, finite manifest, traversal/duplicates,
forbidden raw artifacts, completion/hash guards, paired-figure counting, size
refusal and archive corruption rejection. The checked fixture is synthetic and
cannot be mistaken for a real completed S6B handoff.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py "$sim\scripts\s6b_package.py" check --root "$sim\staging\s6b\20260909T230840Z\package_checks_v2"
```

After the owner has written and reviewed the real build spec:

```powershell
& $py "$sim\scripts\s6b_package.py" build --spec "$sim\reports\S6B\20260909T230840Z\HANDOFF_BUILD_SPEC.json"
```

## Anaconda Prompt / Command Prompt

No extra dependencies are needed; the script uses Python's standard library.
The explicit EDGE interpreter keeps the study's invocation path consistent.

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6B_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6B_PY%" "%SIM%\scripts\s6b_package.py" check --root "%SIM%\staging\s6b\20260909T230840Z\package_checks_v2"
"%S6B_PY%" "%SIM%\scripts\s6b_package.py" build --spec "%SIM%\reports\S6B\20260909T230840Z\HANDOFF_BUILD_SPEC.json"
```

Use another fresh `package_checks_vN` directory for repeated fixture runs;
existing check evidence is deliberately preserved. The `verify` subcommand is
an internal independent-reader entry point and also accepts an archive plus a
fresh `--verification-root` for an explicitly requested later integrity check.
