# Task12 bounded native and UI checks

Purpose: exercise the existing ASR and actual controller with a small local CMU
Arctic set, then review exact archived ASR excerpts. Records before/after words,
reference edit counts (including harmful outputs), abstention, zero automatic
edits, actual model reuse, stream release, UI tick gaps and Windows resources.
No microphone, audible playback, private recording mining, LLM or download.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& .\.edge-speech-env\python.exe prototype/tools/check_transcript_review.py --output Resumes/.uiiter2_12/native_fresh
& .\.edge-speech-env\python.exe prototype/tools/check_transcript_review_ui.py --output Resumes/.uiiter2_12/ui_fresh
```

CMD / Anaconda Prompt: same commands without `&`; use
`cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"` first.

Inputs: pinned existing models and `CMU Arctic/cmu_us_awb_arctic`; `--corpus`
can select that speaker's corpus folder. Output must be a new folder. The native
tool uses a0001 (unusual proper name), a0234 (negation), a0099 (pronoun), b0365
(number), fixed-seed 0dB noise on a0234, and empty-speech silence/three-tone music
controls. Five source-paced application recordings plus one cancellation replay;
silence/music use native ASR with explicitly labelled full-clip control archives.
Nonwords, Amir/Emir and malicious-looking instructions are **text contract**
examples, not claims of acoustic recognition. Human spoken versions remain pending.

Native output: NATIVE_REVIEW_CHECK.json, fixture WAVs/archives and a real portrait
screenshot. Corpus words and voice/audio evidence stay local. The UI tool uses
an explicitly synthetic decoder with an actual Controller to show protected
changes, confirmation, adoption and Undo; outputs UI_CHECK.json and PNGs. Both
briefly raise their own 480×800 window, then close it. No test window stays open.

Fixed limits come from feature semantics. No parameter search, long soak, neural
training or automatic acceptance. Qwen is not installed; helper results are
NOT_TESTED/not applicable, never represented as an executed comparison.
