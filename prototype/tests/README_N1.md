# N1 event and safe-start tests

Purpose: check current N1 speaker-span ownership using synthetic source EVENTs.
No audio scenes, microphone enumeration, neural models, profiles, playback or
visible GUI are used. Inputs are embedded A/B/A, interruption, overlap, correction,
rewrite and large-paragraph events. Output is an ordinary unittest report.

PowerShell from the campaign worktree:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m unittest prototype.tests.test_n1_spans -v
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest prototype.tests.test_n1_spans -v
```

No environment activation/install is required. See the vendor
`README_N1_SPANS.md` for the timing limitation and correction contract.

Use `prototype.tests.test_n1_safe_start` in the same commands to test the real
controller's isolated idle startup, blocked microphone/enrollment and backend
switching. Its temporary data contains no personal profiles. The model path is
deliberately empty; any attempt to load a model or enumerate audio fails.
