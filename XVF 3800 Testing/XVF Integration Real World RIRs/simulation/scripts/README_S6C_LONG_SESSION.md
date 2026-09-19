# S6C long host sessions and chronological evidence

`s6c_long_session.py` prepares a 30–60 minute paired file from complete canonical
physical-XVF captures, replays genuine historical R0 observations through one
uninterrupted shared v3 policy, runs model-free long-state fixtures, and provides
a separately invoked continuous paced native runner. It never uses reference
people/text to reset or steer the predictor. No hardware playback or new RIRs.

The composition uses a prospective family round-robin (sorted family IDs, sorted case IDs within each family), whole inputs once, no trimming,
gain or repetition, and explicit two-second digital silence between cases. The
last whole source may exceed the minimum requested duration. Original within-
scene gaps remain in the PCM. Both taps retain common capture sample zero.
Sanitized cue availability/source times receive each composition offset; adding
an offset to sequence numbers preserves local duplicates/backwards relations.
This is host-continuous synthetic concatenation of independently reset captures,
**not continuous hidden XVF adaptive state** or a real-world recording.

Inputs: frozen S6C epoch manifest, exact prepared 480-tap input index and source
WAV/cue hashes. Historical chronological mode additionally uses the complete S6B
R0 native index and each bound actual evidence/vector receipt through the frozen
S6C replay loader. Only N00 same-tap/no-gallery profiles are compatible with that
historical recipe. The .5-second historical single lane is an explicit mature
API role, not new long-window inference. Cached neural states still reset at
source boundaries; the one shared host policy does not. Added silence has no
invented cached segmentation/embedding/ASR events.

Outputs: `reports/S6C/20260910T123540Z/long_session/<version>/COMPOSITION.json`,
shifted cue file and whole paired WAVs under the corresponding G: payload root;
chronological EVENTS/SNAPSHOT/RESULT files; separate fixture receipt; and native
per-candidate/route STARTED, PROCESS_SAMPLES, RESULT or preserved FAILURE. Native
artifacts include full journals, actual events, all transcript views, summary
and durable v3 finalization/lease/writer closure. A fresh namespace is required
after a failed attempt. Existing attempts are never deleted or overwritten.

PowerShell preparation and model-free checks (no neural model calls):

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
Set-Location -LiteralPath $s6cScripts
& $s6cPython s6c_long_session.py --mode fixtures --epoch epoch2 --version v1
& $s6cPython s6c_long_session.py --mode prepare --epoch epoch2 --version v1 --minutes 30 --gap-sec 2
& $s6cPython s6c_long_session.py --mode chronological --version v1 --candidate C001 --asr-tap O0 --identity-tap O0
```

Native execution is **deferred until root selects the retained candidate and
reserves the paced interval**. The command below shows syntax, not an instruction
to run a prolonged experiment during the broad campaign. One invocation runs
one candidate/route with one continuous session and one model bundle. Substitute
the exact registered survivor and route. A naming profile additionally requires
`--gallery 'C:\admitted\fixed_long_session_gallery.json'`; this must be a fixed,
isolated explicitly admitted roster for the whole session, never an implicit
per-scene gallery switch. A no-naming profile rejects any gallery.

```powershell
& $s6cPython s6c_long_session.py --mode native --version v1 --candidate C001 --asr-tap O0 --identity-tap O0
```

Equivalent Anaconda Prompt/CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_long_session.py --mode fixtures --epoch epoch2 --version v1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_long_session.py --mode prepare --epoch epoch2 --version v1 --minutes 30 --gap-sec 2
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_long_session.py --mode chronological --version v1 --candidate C001 --asr-tap O0 --identity-tap O0
REM Only after selected-profile and paced-worker admission:
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_long_session.py --mode native --version v1 --candidate C001 --asr-tap O0 --identity-tap O0
```

All four numeric inner-pool environment variables are one before imports. The
runner verifies frozen code, Python/package versions, explicit asset hashes and
once-gained input bytes. Native status comes directly from the in-process engine,
avoiding an optional concurrently read LIVE file. It drains the UI event queue,
records two-second process/telemetry samples and emits 20-second progress lines.
Resource sampling is distinct from source pacing. USS is private resident, RSS
sum is an upper bound, Windows private commit is separate, unavailable shared
resident/PSS values stay null, and inaccessible process samples are marked
partial. Backlog observations are sampled, not continuous maxima. Native event
log size and process write bytes are separately recorded. Worker PID/creation is
saved; the caller verifies process exit after the runner closes. Only owned
source/engine state is stopped on deadline or explicit STOP_REQUEST.

The worker accepts completion only after exact full paired PCM and ASR cursor,
no live lane/retained lease, and all writer-close outcomes are verified. One
bundle model-load duration is recorded separately from native elapsed. Source
producer block-before-sleep timing must not be interpreted as negative phonetic
latency. No CM5 throughput translation or device-state continuity claim follows.
Long-state fixtures use constructed orthogonal vectors at spaced times across
capacities16/32/64/128/256; they measure guard activation rather than real people.

Historical replay additionally verifies the exact S6B epoch digest and full R0 profile for every source, and checks checkpoint SHA equality with S6C. Sequence offsets preserve negative, duplicated and backwards relations inside each source while keeping new source namespaces distinct.

The maintained runner now uses epoch2, whose APP bytes and model assets match epoch1. Naming endurance admits only the frozen registry global FIXED_ROTATION_A or FIXED_ROTATION_B roster at the original candidate enrollment tier. Each fixed roster has its own output namespace and stays constant throughout the session. Scene-conditional ALL_EXPECTED_SETUP or other per-scene rosters reject. The condition and enrollment tier must equal the requested registered candidate exactly. The alternative fixed roster requires its separately registered counterpart; no roster substitution under the original candidate ID is allowed.

The historical source index and epoch are admitted through the hash-pinned completed S6B LOCAL_ARTIFACT_INDEX authority, then their inner native/evidence/vector bindings are verified. An arbitrary self-consistent replacement historical index is not sufficient.

After finalization joins the native writers, the runner drains any remaining UI events and adds a terminal_after_finalization process/telemetry sample. Final event counts include the late closure/tail queue, and the terminal observation is distinguishable from periodic two-second samples.

Family order comes from the hash-bound canonical scene manifest and is only a preparation/scoring label, never a predictor input. The round-robin was registered before any composition/native execution to include all12families. A canonical-order alternative was previewed as metadata only and was never composed or executed.
