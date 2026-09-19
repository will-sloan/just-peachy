# Package the reviewed S6C handoff

`s6c_package_handoff.py` creates the final compact archive from an explicit,
hash-bound file list. It does not discover files, choose scientific results,
change metrics, run models, or decide whether the study is complete. The root
must first finish the required work and obtain the final independent acceptance.
The package receipt, when present, is the evidence that packaging actually ran.

Inputs: a JSON manifest with schema `jp_s6c_handoff_package.v1`, status
`APPROVED_FOR_PACKAGING`, study_status `COMPLETE_WITH_LIMITATIONS`, an exact
`acceptance` path/bytes/sha256 binding, `required_archive_names`, and `files`.
Each file supplies absolute `path`, exact `bytes`, lowercase `sha256`, relative
POSIX `archive_name`, and `role` (`analysis`, `table`, `plot`, `metadata`, or
`readme`). The acceptance receipt must also be included as a file. Its status is
`ACCEPTED_WITH_LIMITATIONS`; all six mandatory boolean fields checked by the
helper must be true. Missing optional hardware is documented in the acceptance
and hardware branch status, without asserting a physical run.

The source review supplies the material required filenames; the packer checks
that the explicit list is complete. Supported archive types are Markdown, CSV,
JSON, text and up to six PNG/SVG/PDF visuals. Raw audio, individual embeddings,
native JSONL logs and model binaries remain local. File limits are128MiB each
and512MiB combined before compression. The archive must fit20MiB, with10MiB as
the preferred target. Every selected file is verified from the same buffer that
is archived. Experiment/metric selection is outside this copying helper.

Archive names reject traversal, case-insensitive duplicates, file/directory
prefix collisions, Windows device basenames, trailing dots/spaces and invalid
Windows/control characters, so the selected member tree can be extracted on the
target Windows desktop.

Outputs: the requested ZIP directly in `simulation\handoffs`, with the exact
manifest and SHA256 member checksums inside; a sibling `.zip.receipt.json` binds
the archive, source manifest, acceptance, helper and README. The helper reopens
the archive, checks CRC, exact member coverage and every member's bytes before
renaming the temporary file. It checks both resolved paths remain in the named
handoff directory before the Windows rename. Existing packages/receipts are
never overwritten. A failed temporary file stays local for diagnosis; do not
delete source evidence or silently narrow result coverage to reduce size.

PowerShell, once the final reviewed manifest exists:

```powershell
$s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$s6cManifest = "$s6cSim\reports\S6C\20260910T123540Z\handoff_package\PACKAGE_MANIFEST.json"
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython "$s6cSim\scripts\s6c_package_handoff.py" --manifest $s6cManifest --check
& $s6cPython "$s6cSim\scripts\s6c_package_handoff.py" --manifest $s6cManifest
```

Anaconda Prompt / CMD:

```bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_MANIFEST=%S6C_SIM%\reports\S6C\20260910T123540Z\handoff_package\PACKAGE_MANIFEST.json"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_package_handoff.py" --manifest "%S6C_MANIFEST%" --check
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_package_handoff.py" --manifest "%S6C_MANIFEST%"
```

`--check` verifies packaging inputs without writing an archive. Neither command
is a substitute for the scientific/native/paced acceptance. No final manifest or
acceptance is fabricated while mandatory work remains unfinished.

For an independently reproduced copy after the default ZIP already exists, add
`--output` with a fresh `.zip` filename directly in the same handoffs directory,
for example `S6C_JOINT_CHATGPT_HANDOFF_20260910T123540Z_REVIEW_COPY.zip`.
The existing final archive and receipt remain preserved.
