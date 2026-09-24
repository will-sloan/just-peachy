# GUI presentation timing fixture

Purpose: `check_caption_presentation.py` measures 0/150/300ms presentation choices
using the actual Tk timer and renderer. It feeds one short **synthetic** caption
at 60ms revision intervals. This is display latency, not audio/model latency or
WER/identity evaluation. Only the latest pending revision is kept. No microphone,
inference, gallery, USB or production settings are opened. Mock layout images
contain synthetic people/text and say MOCK in their filenames and status line.

Inputs: source/configuration, the embedded synthetic fixture, fresh output path.
Outputs: `PRESENTATION_CHECK.json` (per-batch first/latest-arrival delays, resources,
source hashes and raw-immutability result) and seven explicitly mock PNGs. It uses
already installed Tk/psutil and Windows System.Drawing; nothing is downloaded. A visible temporary
window is necessary for screenshot evidence; it closes at completion.

PowerShell from the repository root:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tools\check_caption_presentation.py --output-dir .\Resumes\caption-presentation-new
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B prototype\tools\check_caption_presentation.py --output-dir Resumes\caption-presentation-new
```

Use a new output directory per run. These GUI measurements deliberately exclude
the application's existing 80ms snapshot polling interval; phase and OS
scheduling can add delay. A short native file check is separate:

```powershell
& .\.edge-speech-env\python.exe -B .\prototype\tests\native_ui_check.py --wav 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_08_07\O0.wav' --data-root '.\Resumes\native-caption-new' --mode anonymous_conversation --recipe balanced --layout-screenshots
```

CMD / Anaconda Prompt uses the same arguments with double quotes and without
`&`. Inputs are the explicit prepared mono16k O0 file and existing external model
cache. Outputs are private native session metadata, `NATIVE_UI_RESULT.json` and
real application screenshots including idle/empty pages and measured 125% client.
No microphone, playback, enrollment or production profile changes occur.
