# Explicit continuous saved-input developer replay

`developer_replay.py` adds an explicitly requested, paced, continuous saved-WAV source for full-application developer runs of at least 3,600 seconds. The normal saved source still reads its input once. This module does not start models, capture hardware, create a native unit, or authorize a run by itself.

The source reads mono PCM16 16 kHz WAV in blocks of at most 320 samples. At each EOF it verifies the original file SHA, records a repetition boundary, rewinds that file, and continues the **same logical sample clock, journal, scheduler and model instances**. It does not reset ASR, diarization or embedding models at file boundaries. The final block ends exactly at `policy.maximum_samples()`. Stop keeps the accepted prefix and closes the journal once. No sample is skipped to catch up with wall time; backlog remains subject to the ordinary runtime policy.

Inputs: one real WAV path, its admission SHA256, `SessionPolicy(developer_soak=True, maximum_session_seconds=N)`, and explicit `repeat_input_seconds=N >= 3600`. Container bytes must fit `2*maximum_samples+65536`. A kept-session replay, live source, absent developer flag, mismatched duration or changed SHA is refused. No GUI repeat control is enabled. The Manager records the input SHA in the immutable request; the worker and source verify it again. Every wrap and the final EOF also verify the file. A changed file causes an incomplete failed session, never a successful replay certificate.

Outputs: ordinary complete processed/audio, captions and event records; `source_started` states repeated-input provenance; every `source_repeat_boundary` records repetition number, exact logical sample offset, input offset zero, original frames/SHA and `models_reset=False`. Session metadata records developer replay and `quality_evaluated=False`. Source clock and PCM values are continuous; repetition does not imply an hour of independent speech or a quality result.

## Host checks (no Pi, models, SSH or real-time hour)

The following entrypoint sets CPU14 and writes an actual early owner before project imports. It creates a fresh private evidence directory and never reuses a prior result. Set `N`, `Q`, and `VENDOR` to the current source, private audit-preparation directory, and retained pinned `vendor/edge_speech_pipeline` directory.

PowerShell:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/test_hour_replay.py" --output-root "$Q" --retained-vendor "$VENDOR"
```

CMD or Anaconda Prompt (the exact interpreter is intentional; no environment installation):

```bat
set PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe
"%PY%" -B "%N%\test_hour_replay.py" --output-root "%Q%" --retained-vendor "%VENDOR%"
```

Output is `hour-replay-checks-<uuid>/REGISTERED_OWNER.json`, synthetic archives and `TEST_RESULT.json`. Tests compare the full 57,600,000-sample hour to repeated input using a synthetic clock and blocks <=320 samples. They also check source stop/hash/policy guards and the final scheduler archive against the actual retained Python snapshot methods. They perform no model inference and do not prove native hour performance.

## Native execution interface

Only an externally reviewed, fresh, owned native scope and package admission may launch this. Forward these **additional launcher arguments** through that scope; do not run the launcher directly or reuse a component-only soak reservation:

```text
--headless --input-source saved --saved-path <pinned.wav>
--diarizer nemotron --embedding redimnet --nemotron-profile current_delayed
--maximum-session-seconds 3600 --developer-soak --repeat-input-seconds 3600
--max-drain-seconds 600 --max-backlog-seconds 120
```

The external job must bind input SHA, exact package/selection, complete source+load+drain+cleanup lifetime, whole-unit CPU/RAM admission and independent native/PC output reservations. The default component 256 MiB/256-file mirror is insufficient: the full application's audio/session allocation is around1.3GB, and the conservative complete job allocation including duplicate metadata headroom is2,306,682,336 bytes with default StoragePolicy. A dedicated full-app-hour budget (3GiB hard ceiling,2048files) must be admitted; see `README_FULL_APP_SOAK.md`. Storage floors and all per-process AS limits remain enforced; this module does not increase them.

`README_FINAL_SNAPSHOT.md` describes the streamed terminal history representation. Upstream ASR endpoint20s, presentation512 rows, scheduler4096 utterances and 1MiB per logical row remain finite limits. A dense/pathological input can still fail those limits explicitly. No native continuous full-application result is claimed by these host checks.
