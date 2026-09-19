# Native personal-enrollment fixture check

`check_native_people.py` executes the real segmentation and ReDimNet2 representation, a fresh private personal store, and two paced native C065/C088 query sessions. It uses existing CMU ARCTIC recordings, never a physical microphone or precomputed research gallery. Reference and query files have disjoint hashes. The intentionally dry/unity fixture domain is explicitly separate from live XVF enrollment.

Checks: unique usable speech quality, save, a new Python process loading the same UUID, duplicate display names with different UUIDs, rename, a distinct additional reference when its fixed quality gate passes, duplicate reference rejection, actual native personal-gallery queries on fresh same-person/other-person speech, and deletion. Weak recognition or rejected quality is reported; thresholds are not relaxed to obtain a pass.

Run in PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype'
& '..\.edge-speech-env\python.exe' tests/check_native_people.py
```

CMD/Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
"..\.edge-speech-env\python.exe" tests\check_native_people.py
```

Inputs default to existing `G:\Just_Peachy_S6C\20260910T123540Z\source_inventory\v2\decoded_16k` and the configured content-addressed model store. Optional `--sources`, `--models` and `--private-root` select explicit existing locations. Private generated query WAVs, test voice vectors and complete native session evidence stay beneath `G:\Just_Peachy_PROTO1\tests\personal_fixture\<run_id>`. The compact review result is `tests/evidence/native_people_summary.json`; it contains hashes, quality metrics, policy/scoring summaries and UUIDs, never voice vectors or audio. This is file-based test evidence and cannot qualify personal live enrollment.

The run is normally about one minute, with each native query bounded at90 seconds. Re-running creates a separate external fixture run and does not touch user people or historical research. Do not run repeatedly without a code change or a specific unresolved failure.

Exit status is0 for PASS,2 for LIMITED (for example a fixed quality/recognition gate did not pass), and1 for execution failure. The first completed native run on September18,2026 passed all11 checks in40.1seconds: one enrolled CMU actor was recognized on different files, and one other actor remained Unknown. This is a narrow function check, not a live or population accuracy estimate. The later source-binding/exit-code additions do not change its inference or thresholds; the preserved first-run receipt predates those reporting additions.
