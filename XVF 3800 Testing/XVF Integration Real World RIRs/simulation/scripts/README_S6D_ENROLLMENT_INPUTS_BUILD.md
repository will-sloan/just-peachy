# Exact existing S6D enrollment and continuous file inputs

Purpose: s6d_enrollment_inputs_build_v1.py builds only the60 E microphone inputs and two900s continuous microphone inputs already fixed in device_enrollment/DEVICE_ENROLLMENT_INPUT_PLAN_V1.json and CONTINUOUS_INPUT_PLAN_V1.json. Their SHA values are fixed in the helper. It does not change the original plans, create scenes/identities/gains, enroll profiles, infer with models, open hardware, execute a policy, or write a physical consumption ledger. This file-only preparation was explicitly assigned by root; physical admission remains separate.

Inputs: original actual A15/B15 thirty-person/tier15 receipts with190 unique whole E clips, original mono FLOAT16k source/original-file hashes and quality flags, exact existing LibraryR04/R12 FLOAT four-MIC RIRs, existing ECQ/material/Q authorities, and36 bound canonical four-MIC scene files. Selected E identity/source/decoded PCM/original bytes/prompt disjointness from C and Q is rechecked with the original source-bound plan audit helper. The13 unavailable tier15 identities remain excluded exactly as planned. Source files/templates/gallery metadata are rehashed; no C or Q replaces E.

Enrollment recipe: place each original whole E file once in template order at the predeclared offsets with exactly8000 zero samples between clips. Use unity gain and float64 full scipy.signal.fftconvolve independently with each existing MIC RIR, retaining the common11367-sample tail. Round only on FLOAT32 output write. Do not normalize, trim, align channels, regenerate RIRs or invent a propagation delay. Any nonfinite/full-scale/even-PCM24 rail failure blocks completion; it never chooses a gain. Original source/template REVIEW flags are retained.

Continuous recipe: stream-copy all18 complete canonical45s FLOAT four-MIC scenes in each exact listed order, inserting only the two declared45s all-zero blocks. Each output is14400000frames (900s). Every output block is rehashed and compared with exact canonical/zero float32 PCM after writing; no normalization, resampling, overlap, crossfade or internal reset. Continuous Q references/timing/room/roles stay in the hash-bound original plan. No Q inference or calibration occurs.

Outputs:62 fresh mono-source-simulated four-MIC FLOAT16k WAVs under a new G:\Just_Peachy_S6D\20260913T195357Z child; per-file hashes, interleaved/channel PCM fingerprints, frame/peak/RMS/nonzero/readback evidence and provenance in PREPARATION_RESULT.json; ROOT_ADOPTION_MAP.json for later explicit physical entry binding; small source snapshot and RESULT_BINDING.json under the report child. No transport guard is inserted into these input files. The unchanged capture owner must add1s pre/3s post guards and preserve the.3413125s callback allowance in the physical ledger. An input-level headroom PASS is not DSP stream/clock/tail acceptance.

Storage: all WAVs and substantial fixtures stay on G. The builder checks the entire S6D run payload tree against40GiB before and after construction and requires75GiB G headroom plus projected files. File-only small metadata requires at least1GiB C; this does not waive the separate C>=50GiB/G>=75GiB runner/capture admission floors. Original plans still contain null physical bindings; root must adopt the new exact files into later entries and satisfy every existing floor. Failure preserves partial artifacts with BUILD_FAILED.json and never overwrites them.

PowerShell (fresh v1 suffix; use a new suffix after any existing/failed build):
```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_enrollment_inputs_build_checks_v1.py"
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_enrollment_inputs_build_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\enrollment_continuous_inputs_v1' --report "$s6dSim\reports\S6D\20260913T195357Z\device_enrollment\preparation_v1"
```

Anaconda Prompt / CMD (explicit existing interpreter; no install/environment changes):
```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_enrollment_inputs_build_checks_v1.py"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_enrollment_inputs_build_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\enrollment_continuous_inputs_v1" --report "%S6D_SIM%\reports\S6D\20260913T195357Z\device_enrollment\preparation_v1"
```

Checks helper purpose/inputs/outputs: s6d_enrollment_inputs_build_checks_v1.py uses small temporary numeric/file fixtures under the run's G review_fixtures directory, comparing full convolution to direct numpy.convolve, packing headroom to the frozen quantizer including round-to-rail edge cases, exact FLOAT write/readback, overwrite refusal and malformed continuous schedules. It prints four unittest checks and deletes its own temporary fixture directory on exit. It does not create physical scenes or access models/devices. The actual62-file build additionally verifies every source binding/frame and every output sample/block, preserving full logs rather than replacing failures with success claims.
