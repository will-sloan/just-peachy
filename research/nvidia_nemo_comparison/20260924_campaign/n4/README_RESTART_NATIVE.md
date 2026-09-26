# Native event review for a released source prefix

Purpose: independently count and validate native event history after a deliberate
mid-file stop, preserving the full planned saved-audio job. The existing full-file
reader remains unchanged and still rejects this partial execution. This explicit
derivative also accepts a separately labelled completed full-file release.

`restart_native_journal.py` keeps the qualified terminal/event/rotation checks,
using an explicit delivered-frame count for terminal counts and publication
cursors. It never changes the input job's frames, source path, gain or fingerprint.
Positive partial delivery must end on a 320-sample chunk boundary and remain
shorter than the full file. Completed release requires the entire planned length.
Source timestamps outside the delivered interval are reported without clamping.
Gaps, discarded prefixes, missing completion, wrong session/source, malformed
JSON, changed files, bad clocks, unfinished owners/queues and byte/record bounds
still fail or remain explicitly incomplete. Counts cannot be Boolean or float.

This reader is a reusable API, not a launcher. Inputs to `inspect` are the native
session directory, unchanged eight-field audio-only job, `delivered_frames`,
`intent` (`mid_file_stop` or `completed_release`) and optional guard checkpoint.
Its output is a small census with bindings, counts, source clocks, declared full
and delivered lengths, and unavailable-scope flags. It returns no transcript
text. `require_complete` rejects missing history and false acceptance claims.

The caller must independently join the delivered count to the released source
trace, complete engine/consumer/archive receipts, exact native session, same-
Controller pair and closed process lifetime. The caller must separately review
viewport session attribution, resource use and any timing or quality criteria.
A passing native census alone does not prove delivery, restart, model accuracy,
source-to-widget latency, resource suitability, N4 completion or CM5 integration.
No existing historical result is reclassified as an actual restart.

## Development checks and retained outputs

`test_restart_native.py` exercises the new API using the original adversarial
native-record fixtures with a genuinely longer planned synthetic job. It adds
partial/full scope, unchanged-job, intent/count, terminal cursor, type and false
acceptance checks. All nine saved historical native journals are re-read, and
their full-file classification must match the original reader exactly. Their
discarded prefixes remain unavailable. Positive prefix fixtures are synthetic
metadata only; they do not create audio, run inference or simulate acceptance.

`probe_restart_native.py` binds the original qualified code/evidence, checks exited
historical owners, snapshots these four files, and writes private PROBE_OWNER,
ADMISSION, tests.txt, synthetic and historical census JSON, and RESULT or FAILED.
It runs only model-free CPU14 work below normal priority, math threads=1/GPU off,
with healthy D1 identity checks before/after, writer lock, disk floors, shared
allowance, 720-second budget and 8-MiB output limit. It starts no Controller, GUI,
source, model or Pi. Existing evidence and failed attempts are retained.

No installation is needed; use the existing exact Python environment. Preserve
any existing output folder and increment the suffix for a rerun.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_restart_native.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-native-probe-v1'
```

CMD and Anaconda Prompt (explicit interpreter, same environment):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_native.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-native-probe-v1"
```

No production launch command exists in this module. Integrate it into the future
exclusive paired runner/reviewer only after its actual source delivery and
terminal receipt joins are independently enforced. The previous projected
128-binding runner union has no room for new readers; separate coordinator/
reviewer and child runtime dependency closures explicitly while preserving every
actual dependency, or otherwise reuse the fixed implementation within that bound.
Do not raise the child limit, omit dependencies or weaken its admission checks.
