# Version activation and rollback

No production activation or user startup entry was changed. Stop the app before
updating the selected data root. A live or uncertain runtime owner blocks the
updater; do not delete its lock to force an update. Use the current release
helper with the matching feature/schema checks, retaining both versions.

PowerShell from the campaign worktree (use an explicitly chosen install/data
root; the values below refer only to the existing isolated baseline):

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py prototype/release_tools/release.py healthcheck --root 'G:\Just_Peachy_N1\20260924_campaign\local\Installed Baseline' --data-root 'G:\Just_Peachy_N1\20260924_campaign\local\Installed Baseline Data'
```

CMD/Anaconda Prompt uses the same absolute Python in double quotes, without `&`.
To activate an already verified version, invoke `release.py activate --root ROOT
--data-root DATA --version VERSION --require-assets`. To roll back, use
`release.py rollback --root ROOT --data-root DATA`; a previous compatible pointer
must exist. On Linux substitute the installed Python executable. These commands
change the chosen version pointer, never overwrite the version's code or erase
profiles. Model and import health checks run with that version's runtime.

Fixture tests on Windows and Linux cover atomic ownership, immutable staging,
traversal/hash corruption, personal-byte preservation, schema/feature refusal,
activation and rollback. Actual N5 per-shortlist GUI startup-failure/reopen/
rollback validation is pending. A simulated fixture is not physical testing.

No schema migration is introduced by N5. Incompatible rollback is refused rather
than destructively converting profile data. Existing bounded history/log policies
remain; retention and actual eMMC write rate need target measurement. Do not
carry research archive logs into a field install or log private transcripts as
unbounded diagnostics. No new write-rate guarantee has been measured.
