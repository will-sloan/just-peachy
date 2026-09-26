# Bounded publication and Controller history derivative

Purpose: preserve and diagnose the V2 main-bank failure at cell 1,382, then test
a fresh derivative with 64-MiB publication and Controller-history limits. The
100,000-event cap, full lossless outputs, clocks, prediction settings, application
methods remain unchanged. A 128-MiB expanded-artifact limit and 280-MiB cell reserve
retain the whole history. The first preserved probe measured a 73,245,202-byte
publication after the old trace cap failed at 25,166,187 bytes / 1,450 events.
The original V2 sources, plan, 1,382 successful cells and failed terminal remain
immutable. These scripts are development preparation until a matching passed
qualification exists; a queue finish or probe pass is not N4 acceptance.

Inputs: the stopped integrated-main-v2 terminal and exact source/plan/component
bindings. The probe reproduces the old failure and records its byte/event counts
without copying private text into reports. It then tests A1/D1 on both taps of the
failed scene with both encoders, plus the largest saved A1 input-event file with
both encoders. It runs the inherited 16 bank tests plus seven prefix-provenance tests, including the four earlier
native-clock boundaries. Selection reads source metadata, never evaluator truth.

Outputs: a fresh private probe directory with ADMISSION, source snapshots,
ORIGINAL_FAILURE, full boundary publication/Controller artifacts, tests, and
RESULT or FAILED. No failing output is overwritten. The qualified parent
sources remain intact. No models, GUI, playback, microphone, capture, enrollment
or Raspberry Pi are started. The helper uses CPU14 BelowNormal, one math thread,
GPU disabled, the existing writer lock, 20-minute between-operation budget,
256-MiB output allowance, C:50/G:75 GiB drive floors and the campaign 50-GiB
allowance including 6 GiB reserved. Temporary fixtures stay under its private
output and are removed only by their own TemporaryDirectory contexts.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpPrivate='G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $jpPython -B "$jpN4\probe_integrated_history_v3.py" --output "$jpPrivate\integrated-history-v3-probe-v1"
```

CMD and Anaconda Prompt (use the existing absolute interpreter; no installation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%JP_PY%" -B "%JP_N4%\probe_integrated_history_v3.py" --output "%JP_PRIVATE%\integrated-history-v3-probe-v1"
```

`application_publication_v3.py` and `controller_projection_v3.py` are internal
APIs called by `integrated_bank_v3.py`. `test_integrated_history_v3.py` requires
the probe's verified source paths and private fixture directory. Do not run it
against arbitrary source or assume its fixtures are production acceptance.

After qualification, `integrated_bank_plan_v3.py` takes `--asr-review`,
`--d0-review`, `--d1-review`, `--scope main|modes-panel`, optional
`--reuse-review PATH`, and a fresh `--output`.
It requires INTEGRATED_HISTORY_CHECK_V3.json matching all derivative code.
The bank uses `run --plan PATH --output NEW_DIRECTORY --allocation-gib VALUE`
and `review --run CLOSED_DIRECTORY --output NEW_JSON`. Full command recipes and
the actual allocation must be recorded with the eventual production dispatch.
No production plan or run is admitted merely by this README. The changed code
must appear in a fresh plan; no active/failed plan is edited. Scoring admission
must separately qualify the new derivative before full-bank scoring. Actual
GUI/resources, continuity/restart, N4/N5 acceptance and live CM5 checks remain.

For production reuse, first run the closed-prefix review described in
README_INTEGRATED_PREFIX_REUSE.md. Its exact passed receipt must be in the
derivative qualification and passed via --reuse-review. The new plan binds it;
reused cells retain original output/closure bindings and explicit producer
provenance. The whole 7,680-row denominator and new cache keys remain. The runner
permits allocations in 0.25-GiB steps, up to 8 GiB, subject to the 50-GiB shared
ceiling including 6 GiB pending reservations and 0.5 GiB separate contingency.
The 280-MiB per-cell reserve is inside the run allocation. Failed attempts, old
payloads and all snapshots count toward the ceiling; none are removed.
