# Record and use your own voice reference

The app opens with the microphone off. A saved personal reference helps the
experimental naming system compare new speech with your voice. It does not
guarantee correct identity, and a name shown on screen is not authentication.
Live human enrollment on this desktop remains pending until you perform it.

## Launch and inputs/outputs

Double-click `prototype\Start-Prototype.cmd`. From the repository directory:

PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
# Direct entry point:
& .\.edge-speech-env\python.exe .\prototype\main.py gui
```

CMD or Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
.edge-speech-env\python.exe prototype\main.py gui
```

Inputs are the named person's explicit consent, live XVF speech, a display name,
the selected O0/O1 tap, and a 15/30/60-second usable-speech goal. The existing local
model assets and `live_config.json` must be available; see `LIVE_AUDIO.md`.
The live adapter opens the configured XVF input only. It never opens a playback
stream, changes default speakers or substitutes another PC microphone. Other PC
microphones, speakers and headphones can remain connected. Ordinary live use
does not require the physical experiment's packed-input/analog confirmation.

Outputs are a UUID personal profile with validated voice vectors, quality and
route metadata. Personal data defaults to `%USERPROFILE%\JustPeachy\data` on
Windows (`C:\Users\amiri\JustPeachy\data` here), or `~/JustPeachy/data` on Linux.
Explicit `--data-root`/environment overrides can change this location. Profiles
live under `people/<UUID>` outside application releases and research galleries.
Enrollment does not save a raw reference WAV by default. Temporary recording
buffers are discarded after save or cancellation; saved vectors remain private
voice data, not anonymized data or encrypted storage.

## Record, inspect, save

1. **Choose the tap first.** In Mode → Engine recipe & audio tap, select O0 or O1.
   Keep that tap for the later naming test. Balanced identity is a suitable
   implemented recipe for exercising the personal-name flow; it is not a claim
   of room-specific accuracy.
2. Open **People → Add person**. Enter your name with the on-screen keyboard and
   tap Done. Names accept 1–80 printable characters. The short profile ID will
   distinguish people who happen to share a name.
3. Choose **15s, 30s or 60s** of unique usable speech; the default is 30s.
   These are prototype interface goals, not proven optimal enrollment lengths.
   Read the privacy wording, give your own consent and tap **Start recording**.
4. Speak naturally at a comfortable level. Read the guide below or different
   natural sentences. Avoid another person talking over you. The guide is
   editable and is never supplied as an expected transcript or lexical answer.
5. Watch **Unique usable** separately from **elapsed** time. Usable speech is
   estimated from nonoverlapping accepted speech intervals; the same captured
   samples are not counted again on every update. Progress can advance in chunks
   while quality processing catches up. Silence, weak speech, clipping, overlap,
   inconsistent voice evidence or capture gaps can prevent a usable reference.
6. **Read more / continue naturally** gives guidance; it does not restart capture
   or add synthetic duration. The goal does not stop the recording automatically.
   Continue if necessary, then tap **Stop recording**. A 180-second maximum limits
   each recording. The final partial block is checked when recording stops.
7. Wait for analysis and inspect the result. **Save reference** is enabled only
   when the backend's quality and capture-integrity checks permit saving. Elapsed
   time alone cannot enable Save. If the result is insufficient, discard this
   unfinished recording and make a fresh attempt; it cannot be silently resumed
   after Stop. Existing saved references remain intact.
8. Tap **Save reference**, confirm the person appears in People, then close the
   application and let cleanup finish. Reopen it: the person should still appear.
   Start a new consented session in **Enrolled names** using the same tap and speak
   different sentences. Keep the full transcript visible while assessing results.

The provided guide is:

> Please sit with me by the window. The sun is out, and the sky is blue. Would you like some hot tea or fresh juice? I usually choose tea. We can watch the birds and enjoy a good book. Thank you for sharing this lovely day.

In Enrolled names, a successful match can show your name; other speech is shown
as Unknown. Provisional names can be delayed or wrong. Conversation + names also
permits anonymous labels. Selected focus emphasizes a chosen roster in the full
transcript; its separate strict option may hide intended words. **Show all
captions** always provides a way back to the retained full-caption view.

## References are specific to the audio path

O0 and O1 references are not interchangeable. The store checks tap, sample rate,
gain policy, preprocessing and waveform domain as well as model compatibility.
O0 uses the live host +3 dB path once; O1 uses unity. The application performs this
processing; do not amplify references manually to make them appear compatible.

To use the same person with both taps, record at least one accepted reference
on **each** tap. After saving/cancelling the current recording, change tap, open
the existing person and choose **Add a reference session**. This keeps the same
person UUID. Only references compatible with the current query path contribute
to naming. If personal profiles exist but none match the selected path, the
backend reports the incompatibility; switch back or add a compatible reference.
Dry automated test fixtures are deliberately a separate waveform domain and do
not qualify as live XVF personal enrollment.

## Manage and transfer profiles

- **Rename** changes the display name for that UUID; it does not create a second
  identity. Two different UUIDs can have the same visible name.
- **Add a reference session** records new consenting speech for the existing
  person. The store permits up to 20 references per person and rejects the same
  exact source reference enrolled twice. More references are not a guarantee of
  better naming.
- **Delete profile** asks for confirmation and removes that person's local
  profile and reference vectors. It does not delete other people, historical
  research data or previously exported copies.
- **Export profiles** asks for consent and writes an **unencrypted ZIP** of the
  personal metadata/vectors with integrity hashes. It exports the personal store,
  not only the currently highlighted person. Choose a new filename: an existing
  archive is not overwritten.
- **Import profiles** asks for consent and validates the archive's manifest,
  checksums, vector format, model/preprocessing and paths before publication.
  Existing UUIDs are refused; import does not overwrite or automatically merge
  people. Different UUIDs may share a name. An incompatible model archive is not
  automatically converted.

Stop or finish the current enrollment before changing people. Save or discard an
unfinished reference before starting another one. People edits start a fresh
identity state on the next listening session; changing a name cannot rewrite raw
words that were already recognized.

## Save an issue privately

Settings or Diagnostics → **Mark a problem / save excerpt** offers:

- **Mark without audio:** save a local diagnostic mark and recent caption rows.
- **I consent · Save recent 30s audio:** also copy up to 30 seconds already in the
  current session's RAM buffer. This needs an available session buffer and the
  consent of people whose voices it may contain. Save it before stopping the
  session if you need that buffer; it does not start a new microphone or play audio.
- **Cancel:** save nothing.

The resulting path appears in status/Diagnostics under the external private
`problems/<UUID>` folder. Problem evidence is pinned outside automatic rolling
session cleanup. Audio excerpts and caption diagnostics can identify people;
review them before sharing. The profile archive and problem files are separate.

Use `LIVE_USER_CHECKLIST.md` for the remaining 10–15-minute human check. File
inference tests, UI stubs and a research gallery do not replace this check.
