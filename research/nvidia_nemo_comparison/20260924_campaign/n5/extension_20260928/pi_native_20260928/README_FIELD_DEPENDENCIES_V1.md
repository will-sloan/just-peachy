# Retained dependency lock and guarded candidate deployment

Purpose: qualify a new deployment boundary for the exact offline B01v7 candidate without copying assets or rewriting previous releases. Pin the installed shared models/runtime, Python standard library, retained D1 weights/native libraries, file and symlink targets, and transitive ELF loader resolution. Verify those dependencies again before a candidate pointer can change. Original rc5 continues running; its install pointer/config/data are never changed.

`field_dependencies_v1.py` implements dependency collection/verification, exact release descriptors, compare-before-update candidate activation and rollback. Files are pinned by path, resolved target, symlink text, bytes, hash and file identity; directory symlink targets and runtime tree membership are checked. The common total deduplicates device/inode; category subtotals deduplicate resolved paths and can overlap across categories. Existing disk free space already includes these assets. This is tested retained placement, not relocation, portability, a self-contained archive or permission to delete research dependencies. ELF coverage is DT_NEEDED resolution from pinned runtime/standard-library/native ELF roots plus explicit PortAudio/Tk/Tcl roots; future dynamically selected plugins/resources are not exhaustively enumerated.

`field_dependency_probe_v1.py` imports real NumPy, ONNX Runtime, Sherpa, sounddevice and Tkinter APIs, then links the retained Nemo C library and compares all mapped ELF files with the pins. It creates no InferenceSession/model, PortAudio stream, Tk root or recording. `field_dependency_protocol_v1.py` runs that child, then registers exact existing v5/v7 releases using two small descriptors. A new candidate-only pointer moves v5→v7→v5, revalidating dependencies and personal-data schema before publication. The descriptors bind the private candidate/data directories; the original installer does not consume these pointers yet. Rollback requires exact current and previous pointer hashes. Synthetic invalid locks and busy-data ownership exercise rejection without touching assets or original releases. Three private canary/schema/copied-config files must remain exact. This does not qualify arbitrary private galleries or original rc5 activation.

Inputs: fresh CPU14 WINDOW_V5 host census, strict SSH, current Pi owners/units/leases/resources, exact v7 and v5 manifests, prior reviewed/private-backed-up V60 result, current quiet authority (capture disabled here), original live config/install backups. Outputs: fresh `field-dependency-v1` target admission, original backups, dependency lock and ELF traces, exact deployment descriptors, isolated pointer history, import/link result, rejection fixtures, storage and native resource receipts. Independent review creates a verified private target backup and REVIEW/BACKUP receipts. No audio, weights, runtime or release tree is copied; only small manifests/code/config/evidence are new.

Envelope:32MiB combined new output (16MiB target plus16MiB host reserve),768MiB AS,1MiB stacks,CPU2/3 shared200%,Tasks64,300s service/60s Stop/8MiB per file. Initial850MiB RAM; sampled192MiB available floor/640MiB aggregate RSS stop; RSS is not hard-enforced. Collection is limited to16000 entries,12000 entries per runtime tree,256 ELF roots and150s; commands each have10s deadlines. The no-model child has60s plus bounded owned cleanup. No downloads/reset/playback/capture. Fixed32GBPi retains5GiB free plus prospective512MiB private quota. Immutable failures and malformed documents are retained; no automatic cleanup or overwrite.

PowerShell, only for a fresh unexecuted run:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_dependency_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V138.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_dependency_v1.py
```

CMD and Anaconda Prompt (use existing environment, no installation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_dependency_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V138.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_dependency_v1.py
```

Helpers are invoked through the bound protocol, not directly to bypass admission. The reader sets hostCPU14 and PiCPU3/256MiB, disables bytecode, independently checks receipts, current dependency hashes and owner/lease/baseline closure, and backs up every new target file with hashes. It creates no GUI/models/capture. Do not rerun a passed test or overwrite an existing run/backup. A failure needs a fresh derivative/admission. Original baseline rollback remains unnecessary here because it is untouched; the new candidate-pointer rollback is explicitly separate and preserves all history.
