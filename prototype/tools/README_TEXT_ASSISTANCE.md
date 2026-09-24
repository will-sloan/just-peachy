# Task 07 bounded native verification

`check_text_assistance.py` runs one existing 12s genuine task04 CMU clip through
the actual controller, greedy Sherpa decoder, learned punctuation and archive.
It enables conservative text assistance, verifies raw output preservation and
source links, checks separate manual correction/undo, and observes no unwanted
text edits. It also runs a small, explicitly synthetic text set for positive
contextual edits, misspelling review and protected/ambiguous false-correction cases.

PowerShell from repository root:

```powershell
& .\.edge-speech-env\python.exe -B prototype/tools/check_text_assistance.py --wav Resumes/.uiiter2_04/native_v2/A_12s.wav --output-dir Resumes/.uiiter2_07/native_new
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype/tools/check_text_assistance.py --wav Resumes/.uiiter2_04/native_v2/A_12s.wav --output-dir Resumes/.uiiter2_07/native_new
```

Inputs: existing mono16k PCM16 prepared file, pinned installed model/runtime,
fresh output directory. Production data is untouched. No microphone or audible
output stream is opened; endpoint defaults may be observed read-only. File
pacing waits inside ordinary Python with a bounded 60s completion deadline.

Outputs: NATIVE_TEXT_CHECK.json (latency/CPU/memory, hashes, actual decoder/API,
tokenizer limitation and synthetic text examples), PRIVATE_NATIVE_EXAMPLES.json
(real words; keep private), isolated session journals/preferences. No general
ASR improvement is asserted from this check. Enrolled-name acoustic bias is
unavailable because matching ASR BPE assets are unbound, so no hotword A/B or
silence/music false-insertion result is fabricated. No model/dependency upgrade.
