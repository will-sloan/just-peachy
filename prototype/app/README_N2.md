# N2 streaming speaker alternatives

N2 retains the selected Sherpa Giga recognizer and final-only punctuation. D1
uses the exact official Nemotron 3 Q8 standalone native diarizer. E1 uses the
official TitaNet-Large encoder exported to CPU ONNX with its verified frontend.
The backend menu selects D1/E0, D0/E1, or D1/E1. Baseline retains D0/E0.

Inputs are already prepared mono 16 kHz PCM16 WAVs; gain is one. This campaign
uses saved audio only. It does not enumerate/open microphones, operate the Pi,
or change the Windows playback endpoint. Private data belongs outside the
application/release tree. Research audio, vectors, and transcripts do not ship.

## Configure and run

Use the campaign setup script to write explicit model paths and hashes to a
new research data root. It neither downloads weights nor edits your usual data.
From PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research\nvidia_nemo_comparison\20260924_campaign\n2\configure.py --data 'G:\Just_Peachy_N1\20260924_campaign\local\n2\interactive-data'
& $py -B prototype\main.py --help
```

From Command Prompt or Anaconda Prompt (activation is unnecessary when using
the explicit interpreter):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B research\nvidia_nemo_comparison\20260924_campaign\n2\configure.py --data "G:\Just_Peachy_N1\20260924_campaign\local\n2\interactive-data"
"%PY%" -B prototype\main.py --help
```

The setup output prints the exact saved-audio launch command supported by this
checkout. Launch the visible frontend only when you want to use it. Backend
selection requires a new explicit Start/file action and a fresh session.

## Personal gallery integration

TitaNet uses `embedding_spaces/<namespace SHA256>/people` in the selected data
root. It reuses validated UUID save/load/rename/export/import operations while
binding every reference to the TitaNet model, preprocessing and route. Existing
ReDimNet vectors remain in their original folder and are never compared with
TitaNet queries. UUIDs may be explicitly retained when re-extracting permitted
reference audio; vectors must be extracted again. The runtime verifies the
configured namespace against the actual loaded encoder. A saved profile alone
does not prove recognition: the tests exercise reload and actual runtime scoring.

The separate `N2Gallery` adapter accepts explicit model-bound research galleries.
Operational acceptance requires calibration for the exact representation,
roster and query domain. The current processed-XVF domain lacks admitted C
negatives; its open-roster scores are diagnostic and the name map returns
Unknown. Closed selection reports an assumption, never a verified match.
Two contradictory observations reset confirmed name memory without recycling
the anonymous track. No online adaptation or synthetic personal profiles ship.

For N2, a closed selected-name display requires supported voice evidence;
unresolved, missing or mixed evidence stays Unknown. Its UUID and `assumed`
display metadata remain separate from a verified profile. The developer
identity-settings page explains the fixed model/domain/roster calibration
policy and does not expose baseline threshold controls for N2. Existing
baseline parameter controls retain their original behavior.

Backend selection remembers selected and highlighted UUIDs by compatible store
for the lifetime of the Controller. Visiting an empty TitaNet store clears
unavailable selections with a re-enrollment notice, preserves the logical mode,
and leaves full-caption modes selectable. Returning to the original store
restores its roster. A UUID may carry into another embedding space only when a
compatible profile with that UUID actually exists there.

N2 disables session reference collection, bank matching and promotion. Changing
backends discards pending session candidates and resets collection/matching to
Off. Original saved enrollments remain intact; returning to baseline permits
its existing opt-in workflow again. N2's session-reference page explains this
limit and provides no enabling controls.

## Timeline and limitations

Nemotron has eight persistent arrival-ordered slots per session. Slots do not
reset at ASR endpoints or known turn boundaries. More than eight physical people
are unsupported, and eight output channels cannot reliably signal overflow.
Raw overlapping channel activity is retained; this is not audio separation.
The three explicit profiles buffer 1.04/0.64/0.32 seconds plus frontend context
and measured computation. Raw frame timestamps and final endpoint overhang are
recorded. Waveform queries use only real received samples.

N2 embedding events include the exact encoder slice as `receptive_start_sec`
and `receptive_end_sec` on the 16 kHz sample grid, zero left padding, and the
native input cursor available before embedding. This supplies the common
archive window contract for both metadata-only and audio-saving sessions.
An exported embedding window reproduces the input waveform slice without
turn concatenation, added silence, normalization or gain.

The common frontend's word spans carry coarse ASR revision windows, not phonetic
word times. Single-channel windows receive the matching anonymous track;
mixed/overlap windows remain Unknown. Corrections name explicit current span
IDs and preserve all raw words and first labels. Naming and diarization are
independent of Sherpa text publication. Native/reference parity, export parity,
screen metrics, resource measurements and remaining gaps are in the N2 handoff.

## Tests and rollback

`tests/test_n2_archive.py` checks N2 embedding events against the real private
archive writer. Inputs are a synthetic activity timeline and a deterministic
test encoder; no model, GUI or hardware is launched. It tests metadata-only
archives and verifies that an audio archive exports exactly the half-open sample
slice passed to the encoder, with no padding, including a native endpoint frame
beyond real audio support. Outputs are console test results; temporary archives
are cleaned up. From PowerShell, run `& $py -B -m unittest discover -s prototype\tests -p test_n2_archive.py -v`.
From Command Prompt or Anaconda Prompt, run `"%PY%" -B -m unittest discover -s prototype\tests -p test_n2_archive.py -v`.

```powershell
& $py -B -m unittest discover -s prototype\tests -p test_n2_integration.py -v
& $py -B -m unittest discover -s prototype\tests -p test_n1_spans.py -v
```

```bat
"%PY%" -B -m unittest discover -s prototype\tests -p test_n2_integration.py -v
"%PY%" -B -m unittest discover -s prototype\tests -p test_n1_spans.py -v
```

Outputs: console test results and private runtime event journals under the
chosen data root. Select **Baseline** for runtime rollback. The immutable N1
release remains at `G:\Just_Peachy_N1\20260924_campaign\local\releases\n1-common-v1\prototype`.
Do not copy E1 data into baseline profiles. No changes are deployed to the Pi.
