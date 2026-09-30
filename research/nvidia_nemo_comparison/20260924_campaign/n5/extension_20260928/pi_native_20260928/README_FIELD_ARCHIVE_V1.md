# Private archive import and consistent field storage

Purpose: fresh `b01-offline-20260930-v3` candidate adds bounded conversation transfer and makes the actual store, Start gate and Sessions display share the existing512MiB private-data limit. Device free-space reserve stays5GiB on the fixed32GB Pi; Start retains32MiB reservation. All private files, source receipts and rejected imports count. Automatic draft deletion is replaced with explicit quota/draft-limit errors. The original application and all earlier releases remain preserved. B05/sequential modes remain unavailable in this package.

`field_archive_v1.py` supplies the store. `field_entry_v3.py` binds it to the actual controller and adds an Import consent/path control, readable storage wording and Offline B01 header. Import rejects busy capture/archive/playback/enrollment owners. Full export produces a new manifest-bearing private ZIP; text-only export remains separate and cannot be imported. Imported labels preserve their original provenance and are not authenticated identity or quality evidence. No pickle, code execution, extraction of external paths or model loading occurs.

Inputs: completed pinned SAVED compact-patch-v1 conversation, closed mono16k epochs with exact float master and PCM copy; new transfer schema and per-file SHA256/byte manifest. Only the documented conversation/epoch files are supported. Text-only, legacy, partial, enhanced or unsupported archives are rejected explicitly. Limits: ZIP8MiB, totalunpacked32MiB, member8MiB, JSON1MiB,128datafiles/8epochs, paths240characters. Symlinks, traversal, duplicate names/JSON keys, encrypted/nonregular members, ID collisions, invalid schema, size/hash/source mismatches are rejected. Compression reads are bounded and every extracted member is rehashed. A fully validated hidden staging directory is published using Linux renameat2 RENAME_NOREPLACE, with no unsafe fallback. Rejected partial files and receipts remain private outside history and consume quota. Export refuses overwrite; interrupted output is retained and cannot pass import validation. No automatic deletion occurs.

Outputs: private manifest ZIP, exact imported conversation bytes, retained import/failure receipts, new code-only release ZIP/staged release, native protocol results, resource envelope and ownership closure, copied-source hash roundtrip,16negative controls and visible480x800 screenshot evidence. Diagnostic constructor scheduling invokes actual inherited UI actions; it does not replace the production store/controller. Quota/free-floor/busy negative cases are explicitly injected boundary checks, not actual disk exhaustion or model ownership. No capture, playback, model inference, new numerical/quality reference, touch, installed live or endurance acceptance follows.

Execution is admission-only. Dispatcher uses current WINDOW_V5, fresh (<15min) host census/current exact Pi identities and leases,96MiB combined output reservation split48MiBtarget/48MiBhost. Main768MiBAS,1MiBstack,CPU2/3/shared200%,Tasks64,300s runtime/60sStop,8MiBfile cap; sampled640MiBaggregateRSS/192MiBavailable stops. GUI expires180s and starts idle. No baseline pointer activation. Private fixtures, ZIPs, screenshots and transcripts stay out of Git.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_archive_v1.py --census '<fresh HOST_CENSUS JSON absolute path>'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_archive_v1.py
```
CMD / Anaconda Prompt (explicit installed interpreter; no environment activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_archive_v1.py --census "<fresh HOST_CENSUS JSON absolute path>"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_archive_v1.py
```
Never reuse a completed run directory. Independent reader verifies the actual release/source/archive hashes, manifest ZIPs, resource limits, natural closure, baseline/leases and exact private backup. Screenshot visual inspection is separate from automated widget evidence. This candidate still shares pinned retained research assets/runtime; it is not a self-contained field release.
