# When you return: 10–15-minute live check

This is a ready-to-use human checklist, **not a record of completed checks**.
No live consent or real personal enrollment was supplied while you were unavailable
for the spoken check.
Allow longer if the usable-speech target needs another recording. Keep ordinary
PC speakers, headphones and other microphones connected; the app selects the
configured XVF input and does not change default playback devices.

Launch from the repository directory in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD/Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

Inputs: you, your consent, the configured XVF, local model assets and optionally
another consenting speaker. Outputs: your private saved profile, observed
captions/identity behavior and any problem evidence you deliberately retain.
The private data location is `%USERPROFILE%\JustPeachy\data` unless overridden.
See `ENROLLMENT_GUIDE.md` for the exact recording and transfer behavior.

| Time | Action | What to record |
|---|---|---|
| 0–2 min | Confirm the app opens idle. Choose Captions, O0 and Start; read the consent and accept only when ready. Speak a few sentences, pause and speak again. | Actual XVF input; partial words becoming final; readable mixed case; no unexpected playback/default-device change. Stop must release listening. |
| 2–5 min | People → Add person; enter your name by touch, choose 30s usable speech, consent and record. Read the supplied paragraph, then continue naturally. Stop after enough usable speech, wait for quality and Save if enabled. | Usable versus elapsed seconds, clipping/quality, whether Save is permitted, and the saved name/short UUID. A failed gate is a finding, not a reason to fabricate success. |
| 5–7 min | Close and allow cleanup; reopen. Check People, choose Balanced identity → Enrolled names with the same tap, Start with consent and use different new sentences. | Profile persistence; raw words preserved; name/Unknown behavior and any label delay. This is a fresh-speech check, not reading the reference again. |
| 7–10 min | If a consenting visitor is present, let them speak without enrolling them. Include brief silence. Try Conversation + names, then Selected focus with your UUID selected. | Wrong-person matches, Unknown, anonymous splits/merges and silence behavior. No identity-accuracy guarantee is assumed. If no visitor is available, mark this step pending. |
| 10–12 min | Scroll up while speech continues, then Back to live. Exercise Mode/People/Settings using touch. Try larger text/high contrast. If trying strict focus, read its warning and immediately verify Show all captions restores the full retained view. | No duplicate caption rows, useful scroll retention, visible essential actions, and a working full-caption rescue. Physical-touch comfort still needs this real check. |
| 12–15 min | For a visible issue, mark it without audio, or explicitly consent to a recent-audio excerpt while the session buffer is still available. Inspect the reported private path. Stop and close. | Issue description, mode/recipe/tap, path, actual stop/cleanup outcome and whether audio was deliberately saved. |

Do not expect a saved O0 reference to name you on O1. If testing both taps,
finish this check on one tap first, then add a separate accepted reference on the
other tap under the same person. That additional recording can exceed 15 minutes.

If startup or capture reports a gap, disconnect or restoration error, preserve
the exact message and Stop. Do not silently choose a PC mic or add a playback
stream to make it run. The evaluation firmware has an eight-hour limit; follow
the documented device recovery procedure between sessions instead of resetting
mid-speech. This checklist does not require unplugging the device or other PC
peripherals, firmware flashing, or the experimental packed-input wiring setup.

Report pass/fail/pending for each step with observed evidence. If a name is wrong,
use Show all captions and retain the words. A correct name on one passage is not
proof of reliable identity in another room, with another tap or with visitors.

## UI evidence already completed versus pending

The automated desktop UI check measured a **480×800 physical client**, excluding
window borders, at **96 DPI** with per-monitor DPI awareness 2. The actual short
saved-file run displayed native captions and revisions and closed its worker.
The 14 focused UI/casing tests also passed; these include fake-controller consent
and touch interactions and therefore do not imply real human microphone use.

The 125% **application comfort zoom** was measured at 600×1000 in a Tk test.
This is different from changing the operating system's display scaling.
Windows 100/125/150% system-scale combinations were **not** swept or changed, and
application zoom does not prove their behavior. Other OS scaling, physical touch,
CM5 performance and live personal naming remain pending until actually tested.
The short native file result also predates later backend changes; the integration
owner records subsequent long-run results separately. No future soak success is
claimed by this checklist.

`SCREENSHOT_MANIFEST.json` selects exactly six images: two actual native-file
screens and four explicitly synthetic UI screens. Each records its source,
hash and evidence limitation; an enrollment progress screenshot is not a real
voice recording.
