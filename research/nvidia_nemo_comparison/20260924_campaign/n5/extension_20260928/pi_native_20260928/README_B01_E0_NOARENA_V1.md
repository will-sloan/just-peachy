# Combined B01 with E0 CPU arena disabled

Purpose: test whether changing only ReDimNet's CPU allocator permits the complete Sherpa + delayed Nemotron + ReDimNet application diagnostic to fit the existing 768 MiB virtual cap. The prior combined failure and standalone arena/no-arena exact parity are retained. No inference graph, input-window, voice identity, punctuation, ASR, D1 cache or speaker-history change is intended.

Inputs: prior B01 V9 hash-bound source/assets; independently reviewed delayed D1 metadata2 and native E0 no-arena full prefix/repeat checks; exact first 12 seconds of saved PCM. Fresh derivative adds a default-true `cpu_mem_arena` argument to the shared ORT factory and passes false only for N2 ReDimNet. Other callers retain their prior arena behavior. Its composition manifest explicitly binds the allocator policy and qualified delayed D1 runtime. No silent E0 bypass or baseline fallback.

Outputs: private source/admission/owner bindings, memory samples, shared-controller progress/captions/journals, RESULT where possible, and independent REVIEW. V1 native aborts may lack RESULT/finalization and remain failures. Terminal exit zero alone never establishes success. Require all source/identity samples, actual probability and caption output, no errors or silent punctuation fallback, natural application/process shutdown and closed exact owners. Functional/resource checks only, not ASR/WER or identity accuracy; no profile enrollment.

## PowerShell

From this directory, with a fresh census under 15 minutes old and reviewed E0 no-arena evidence:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_b01_e0_noarena_v1.py --run-id b01-e0-noarena-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V12.json'
```

## CMD / Anaconda Prompt

Use `cd /d` to this directory. Invoke the same explicit quoted Python executable and arguments, without PowerShell's `&`. No install or download. Strict SSH stdin uses the retained host key and installed target Python. Dispatcher refuses existing output/source directories and verifies all parent/asset hashes before admission. New derivative files break hard links before edits, preserving all parents.

Retain CPU2/3,total200%,one native thread per model,Tasks64,180seconds,hard768MiB virtual space,>=850MiB available RAM,5GiB target free and16MiB fresh-output allowance. Process-local telemetry-off, glibc arena1,128KiB mmap/trim and1MiB Python thread stack match the prior combined trial. Original app/global environment/install remain unchanged. No capture/playback or higher cap. Full-file, Stop/restart, UI and release qualification require separate evidence.

The E0 comparison has exact vectors but a higher overall peak RSS; it shows some released allocations, not a proven combined fit or guaranteed memory reduction. Preserve this trial even if it fails. See README_ORT_E0_NOARENA_V1.md for allocator documentation and component gates.
