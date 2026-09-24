# Prototype focused tests

Task12 finite transcript review, source/epoch fencing and explicit adoption:
[README_TRANSCRIPT_REVIEW.md](README_TRANSCRIPT_REVIEW.md).

Task11 reversible-reference, contamination, storage and touch controls:
[README_ADAPTATION.md](README_ADAPTATION.md).

Roster matching, explicit closed assumptions, bounded parameter and touch-picker
checks are documented in [README_ROSTER.md](README_ROSTER.md).

Linked session, exact audio, interruption/storage failure and explicit-output
isolation checks are documented in [README_SESSIONS.md](README_SESSIONS.md).

The Windows live clock and beam diagnostic regression checks are included in
the normal suite. From PowerShell in `prototype` run
`& '..\.edge-speech-env\python.exe' -B -m unittest discover -s tests -p 'test_live*.py' -v`
and the same command with `-p 'test_beam*.py'`. From CMD/Anaconda Prompt, omit the
leading `&` and replace single quotes with double quotes. Inputs are synthetic
buffered callback timestamps and mocked command replies; outputs are unittest
pass/fail results. They do not open a microphone or USB control connection.
See `../tools/README.md` for the separate explicitly consented physical check.

Tests use synthetic fixtures or the explicitly named existing source files in their own scripts. They do not silently record a microphone. Follow each test's description; native replay and live checks have separate consent/source evidence.

## Enrollment shutdown and temporary-data cleanup

Purpose: `test_enrollment_cleanup.py` verifies ordinary Save/Discard cleanup,
visible restoration failure, retention of still-active owners/workers, safe
startup failure after capture admission, and retention of a reference after a
failed store commit. `test_live_stop_ownership.py` injects stream stop/close
failure to verify that an active source retains its hardware lease until retry
actually closes it. These are model-free regression tests, not hardware proof.

Inputs are synthetic arrays, fake worker/stream/lease objects and mocked store
calls. Outputs are unittest results. No actual microphone, USB command, neural
inference, personal data file or output endpoint is opened or changed.

Run from `prototype` in PowerShell:

```powershell
& '..\.edge-speech-env\python.exe' -B -m unittest discover -s tests -p test_enrollment_cleanup.py -v
& '..\.edge-speech-env\python.exe' -B -m unittest discover -s tests -p test_live_stop_ownership.py -v
```

CMD / Anaconda Prompt:

```bat
"..\.edge-speech-env\python.exe" -B -m unittest discover -s tests -p test_enrollment_cleanup.py -v
"..\.edge-speech-env\python.exe" -B -m unittest discover -s tests -p test_live_stop_ownership.py -v
```

For a portable installation, substitute the release environment's Python for
`..\.edge-speech-env\python.exe`; install dependencies using the main README.

## Prepared-file tap identity

`test_file_tap.py` checks that changing a running file's O0/O1 selection cannot
relabel unchanged WAV bytes. The user must Stop and load the actual other-tap
prepared WAV. Known `O0.wav`, `O1.wav`, `O0_continuous.wav` and
`O1_continuous.wav` names must match the selected tap before an engine starts.
Arbitrary filenames use the user's explicit prepared-tap declaration; filenames
are not acoustic verification. Live tap switches retain Stop/drain/restart.

Inputs are synthetic controller state and path names, with no files read,
microphone, neural models or endpoint calls. Outputs are eight unittest results.
Run from `prototype` in PowerShell:

```powershell
& '..\.edge-speech-env\python.exe' -B -m unittest discover -s tests -p test_file_tap.py -v
```

CMD / Anaconda Prompt:

```bat
"..\.edge-speech-env\python.exe" -B -m unittest discover -s tests -p test_file_tap.py -v
```

## Personal-store unit tests

Purpose: verify UUID persistence, duplicate display names, actual gallery scoring, changed metadata/vector bindings after rename/add-reference, deletion, input-domain isolation, quality support/finite-value validation, safe NPY shape preflight, explicit import/export consent, atomic import rollback, and mutation/read locking. These are **model-free software contract tests**, not speech-recognition or live-enrollment evidence.

Inputs: code, NumPy from the existing interpreter and generated synthetic 192-dimensional vectors. Outputs: unittest PASS/FAIL on the console. Temporary profile/vector/archive files are created only under the OS temporary directory and removed after each test. No real person's profile or audio is used; no archive is added to the release/handoff.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m unittest discover -s .\tests -p test_people.py -v
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m unittest discover -s tests -p test_people.py -v
```

The same invocation can use a compatible Linux Python interpreter with NumPy and this source tree. There is no claim that these tests run native ARM64 inference. Release/install tests and their explicit Windows/Linux commands are documented separately in `../release_tools/README.md`.

The test route is explicitly `waveform_domain=dry_test_fixture` with `gain_policy=fixture_unity`. It cannot be queried as physical XVF audio. Live/processed XVF references require `waveform_domain=xvf_ua`, the verified O0 +3 dB-once or O1 unity policy, 16 kHz model samples and matching ReDimNet preprocessing. Unmatched existing profiles produce an actionable incompatibility error, rather than silently masquerading as an empty personal gallery.

The personal store caches validated metadata under its mutation lock. UI polling uses detached metadata or small summaries and does not rehash/load embeddings every refresh. Save/add-reference/rename/delete/import invalidate that cache. New process startup, explicit `list(refresh=True)`, export and gallery admission validate the underlying files again. Do not edit personal-store files outside the app while its `runtime.lock` is held; external changes are not an automatic learning mechanism. Tests prove repeated UI reads avoid vector I/O, returned objects cannot mutate the cache, gallery admission still catches changed vector bytes, and a failed add-reference write preserves the original profile/cache/files.

## Startup/Stop/close lifecycle regressions

Run the same command above with `-p test_lifecycle.py`. Purpose: prove corrupted settings release a failed constructor's ownership; missing WAVs and injected native-model construction failures close opened journals; completed terminal failures can close while preserving failure details; actual remaining workers or capture keep the owner lock; and a historical “started” flag does not block a fully stopped source. Inputs are temporary synthetic silence, stub liveness objects and an injected constructor failure. Outputs are unittest results and temporary closure receipts removed after each case. These checks deliberately load no neural weights, open no microphone and perform no USB or endpoint action.

## Controller caption views, retention and explicit problem saving

`test_controller_views.py` exercises the actual `Controller.snapshot`, settings,
person-mutation, mode-rescue, problem-save and retention methods. Eleven tests
use explicit synthetic S7-schema rows with stable token/segment IDs and a small
metadata-only stub personal store. No `Controller` constructor, background
controller worker, endpoint inventory, neural weights or capture is started.
The methods receive fixture state through `Controller.__new__`; only absent
session-stop/device-observation methods and read-only process/disk measurements
are stubbed. The real profile-selection metadata validation still runs during
the caption-only rescue check.

Inputs: this source, NumPy/soundfile/psutil from the existing interpreter,
synthetic mixed-speaker caption/identity revisions and generated RAM samples.
Outputs: unittest PASS/FAIL; disposable settings, problem metadata, pinned
markers and one 30-second synthetic PCM16 excerpt in the OS temporary directory.
The excerpt is never played, contains no person's voice and is removed with the
test's private temporary directory. No audio/profile is written into the repo,
release, real private people store or historical research directory.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\prototype'
& '..\.edge-speech-env\python.exe' -B -m unittest discover -s tests -p test_controller_views.py -v
```

CMD / Anaconda Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\prototype"
"..\.edge-speech-env\python.exe" -B -m unittest discover -s tests -p test_controller_views.py -v
```

The tests establish:

- Complete raw/provisional/final text across a mixed-speaker partition, unchanged
  raw inputs, retained S7-provided segment IDs, and late-label/name updates.
- Names-or-Unknown versus anonymous labels; selected-only visibility without
  deleting internal text; full-caption rescue; deletion clearing the last
  selected UUID and strict mode. Misaligned final text is not assigned to the
  wrong speaker partition.
- Detached view fields and visible retention defaults; valid settings persist,
  invalid/unsupported values leave settings and the existing file unchanged.
- Mark without audio saves only metadata and a pin. The public audio flag must
  be exactly `True`; enqueuing it performs no save by itself. An explicit audio
  mark copies exactly the last 30 seconds from the bounded, wrapped RAM journal.
- A low free-space floor rejects retention before deleting anything. Cleanup
  removes only completed unpinned session folders and preserves current,
  pinned, personal, problem and historical fixtures.

The bounded run passed all 11 tests. The compact source/evidence record is
`evidence/CONTROLLER_VIEWS_CHECK.json`. This is software-contract evidence only;
it adds no native-inference, live enrollment, physical microphone or future-soak
acceptance claim. Application/vendor/config sources were not changed.

## Task 05 assigned-seat checks

See [README_SEATS.md](README_SEATS.md) for synthetic logic/Tk checks, inputs/outputs, limitations and PowerShell/CMD/Anaconda commands. The native saved-model + synthetic-telemetry helper is documented in [../tools/README_SEATS.md](../tools/README_SEATS.md). No live seat accuracy is inferred from those checks.
# Task 06 enrollment checks

See [README_ENROLLMENT.md](README_ENROLLMENT.md) for paragraph/Done, source-support,
ASR-estimate, persistence, cleanup, progress animation and actual Tk fixture
checks, including exact PowerShell/CMD/Anaconda commands and input/output scopes.
The full unit runner now collects completed Tk test cycles on the main thread
before the next case, avoiding Tcl interpreter destruction on worker threads.
## Task 07 text assistance checks

See [README_TEXT_ASSISTANCE.md](README_TEXT_ASSISTANCE.md) for bounded spelling,
context/name ambiguity, protected text, separate reversible layers and touch UI
checks with exact commands, inputs and outputs.
# Task09 optional evidence checks

See [README_SCRIPT_EVIDENCE.md](README_SCRIPT_EVIDENCE.md) for synthetic contract,
actual 480×800 Tk, fixture-profile review and native evidence screenshot commands.
Run the full suite with `tools/run_unit_checks.py` for main-thread Tk cleanup.

Task10 optional noise checks and run commands: [README_NOISE.md](README_NOISE.md).
