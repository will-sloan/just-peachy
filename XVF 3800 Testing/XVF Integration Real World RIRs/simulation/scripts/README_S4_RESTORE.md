# S4 exact restoration regression tests

`test_s4_restore.py` checks the bounded decimal/float32 setter recovery in the production `s4_restore.restore_exposed` function. The physical S4 recovery found that asking for the saved `PP_AGCGAIN` getter value `84.72903` returned `84.72902`; submitting the next higher representable float32 value, `84.72903442382812`, restored the exact original getter `84.72903`. Production recovery preserves that exact equality requirement. It does not accept a nearby value merely because the difference is small.

These tests are entirely offline. They compile only the production restoration function and the actual getter-text parser from their Python syntax trees. They do not import the device modules, initialize PortAudio, create a real Control object, enumerate USB/audio endpoints, or call the recovery command. All replies come from `FakeControl` fixtures.

Inputs are `s4_restore.py`, the `values` parser in `s3_hardware.py`, and the existing recorder NumPy dependency. Output is nine verbose test results plus one JSON receipt on standard output, including the production module hash. Exit status is zero on success and nonzero on failure. No historical reports or hardware settings are modified.

Run in PowerShell:

```powershell
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\test_s4_restore.py'
```

Run in Anaconda Prompt or Command Prompt:

```bat
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\test_s4_restore.py"
```

Coverage includes exact success with the upward adjacent input, success only on the downward second input, rejection after both adjacent inputs remain unequal, no adjacent retry for a large mismatch or another command, propagation of unknown-command and nonfinite-getter errors, direct exact success, and no writes when an exposed setting already matches. There are at most two adjacent candidate attempts in addition to the original requested setter. These regressions validate the software rule, not unexposed firmware adaptive history or coefficient bits that were absent from the original snapshot.
