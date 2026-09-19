# One bounded S6D device reset

Purpose: recover the connected XVF3.2.1 after the fresh read-only preflight could read VERSION but the audio core failed AEC_MIC_ARRAY_TYPE. The documented evaluation duration is a possible cause. This reuses the reviewed s3_hardware.reset function with TEST_CORE_BURN0, unchanged USB width and no packed-input switch. It does not flash firmware, alter drivers, open audio or play a carrier. It acquires/releases the existing hardware lock, refuses active recorder ports, preserves exact command replies, and requires a new complete preflight afterward. No prior DSP state restoration is claimed because those pre-reset fields were unreadable.

Inputs: fresh user confirmation, reviewed capture source freeze, exact current management VERSION/USB_BIT_DEPTH. Output: fresh reports/S6D/20260913T195357Z/reset_recovery_after_confirmation_v1/RESULT.json and command log. Only one invocation is allowed; an existing output directory causes refusal. Any failure requires diagnosis, not repeated resets. No packed-playback attempt is charged because no stream opens; this reset is separately retained in device history.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' -B 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_reset_recovery_v1.py'
```

Anaconda Prompt / CMD (explicit existing hardware interpreter; no install):

```bat
"C:\Users\amiri\anaconda3\python.exe" -B "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_reset_recovery_v1.py"
```

After PASS, run s6d_preflight_v2.py with a fresh --report folder below reports/S6D. Playback still requires the exact first-QA plan/queue authorization and reviewed capture owner. Never substitute PC audio devices.
