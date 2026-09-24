# XVF start failure recovered — 20 September 2026 (Toronto)

The GUI failure was reproduced in the saved device receipt: Windows input
callbacks were arriving (26,400 priming frames) and VERSION/USB_BIT_DEPTH/build
reads succeeded, but AEC_MIC_ARRAY_TYPE returned “Check the audio loop is active.”
No live route settings had been changed and no samples had entered recognition.
This establishes an unresponsive device audio processor; it does not prove the
underlying reason. The evaluation board's eight-hour limit is a possible cause.

After closing the failed GUI, one existing S3 `TEST_CORE_BURN 0` soft-restart
operation recovered the device. The shared hardware lease was held; no stream
was open. Firmware remained3.2.1 ua-io48-lin, USB16/16, four linear microphones,
packed input off and ASR gain1. No firmware flash, driver change, packed playback
or Windows default-output change occurred. A restart resets volatile DSP state;
unreadable prior settings cannot be claimed restored. Normal Start subsequently
verified and applied its documented microphone route.

The existing real `check_live_desktop.py` then passed Fast/Captions/O0 with
5.06 seconds delivered, native state COMPLETED, no capture fault or dropped
frames, successful route restoration, and clean microphone/application closure.
Maximum reported source queue lag was16ms. Ten queued raw tail blocks were
explicitly excluded at the intentional Stop boundary; no gap was repaired.
This verifies transport/inference/Stop, not speech-recognition accuracy.

No application code, models, recipes or personal enrollments were changed for
this recovery. The source GUI was reopened afterwards, ready for an explicit
Start. Mic test text/metadata remain in the private isolated check directory;
no microphone WAV or personal enrollment was created.

If the same failure returns after prolonged power-on, stop/close the prototype,
power-cycle the XVF board, reconnect it, then reopen the GUI and press Start.
Fully restart the board if it has a separate power source; restarting only the
GUI does not reset its processor. PC speakers and other microphones can stay
connected. If the error persists after a board restart, retain the next device
receipt for investigation rather than repeatedly retrying or changing drivers.

XMOS documents the evaluation board's
[eight-hour processing limit and power-cycle recovery](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/02_setting_up_the_hardware.html)
and the existing
[TEST_CORE_BURN0 firmware restart](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/programming_guide/04_testing_the_software.html).
No measured board uptime was available, so expiry is not asserted as proven.

Private evidence and reproducible commands:

- `Resumes/.xvf_recovery_20260921/README.md` and RESET_RESULT.json: exact one-shot
  recovery, checks, command replies, dependencies and source hashes. The helper
  refuses a second invocation; it is not an automatic runtime recovery policy.
- `C:\Users\amiri\JustPeachy\checks\xvf-recovery-20260921\LIVE_CHECK.json`:
  actual live native result and full integrity details.
- Original failure remains at
  `C:\Users\amiri\JustPeachy\data\device_receipts\live_20260921T022622_328736Z.json`.

Launch from repository root, PowerShell: `& .\prototype\Start-Prototype.ps1`.
CMD/Anaconda Prompt: `prototype\Start-Prototype.cmd` after
`cd /d "C:\Users\amiri\Documents\GitHub\just-peachy"`.
