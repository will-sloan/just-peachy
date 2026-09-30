# Explicit artifact limits and joined failure receipts

Purpose: address V65's internal 8MiB native/conversation journal and 960000-frame PCM ceilings without removing guards. This fresh derivative uses one strict, hashed contract for both journal roles and paired float/PCM storage. Explicit maxima are 16MiB per journal and 2080000 mono16k frames (130 seconds). Legacy callers retain 8MiB/960000 defaults. Record1MiB, queue4MiB/512items and PCM32768-frame block limits remain. A contract is configuration, not authorization to record.

`field_artifact_limits_v1.py` validates exact fields, integer types, finite bounds and file SHA; exposes a canonical hash and a 46034476-byte maximum for the two journals plus paired audio. Source/trace/code/metadata require additional admission space. `ARTIFACT_LIMITS_V1.json` is the explicit test configuration. `prepare_field_artifact_limits_v1.py` creates new `artifact_limits_v1/app` modules from the privately backed-up immutable installed v10 source, with exact replacement assertions and `ARTIFACT_DERIVATION_V1.json` original/new hashes. It never changes an old release. Rebuilding requires a fresh version; the builder rejects existing output.

The archive passes the contract to its conversation journal and audio writer, stores the hash in epoch metadata, and checkpoints again after the worker joins. Write errors, partial status, source/written gaps and accepted/completed differences remain. The native asynchronous writer reports physical closure separately from logical success; repeated close still reports a failed write. The bounded reader accepts extended files only with an explicit validated contract; legacy reading and external import limits stay unchanged. The prepared `pipeline.py` derivative selects the archive contract and rejects a conflicting explicit native configuration, but its constructor/live wiring is not executed by this protocol. Installed entry health/manifest/GUI integration and long-archive interchange remain pending.

`field_artifact_protocol_v1.py` uses the real derived ArtifactAsyncText and EpochArchive with a package overlay falling back to exact v10 modules. It writes one native journal above8MiB and 130 seconds of deterministic synthetic float/PCM samples, then closes and checks them. Small fixtures exercise byte/frame rejection, repeated failed close, joined PARTIAL metadata and exact prefix accounting. These are generated numerical fixtures, not recorded or played audio, acoustic silence, model inference, endurance or quality evidence. Configuration rejection files are retained. No Tk, PortAudio, models, private conversation mutation or release activation occurs.

Inputs: fresh CPU14 census, retained V65 failure review/backup, exact baseline/boot/PID identities, v10 manifest and source hashes, current authority and contract. Outputs: fresh `field-artifact-limits-v1` admission/source overlay, synthetic artifacts, per-case receipts, live systemd properties, resource/owner results, independent review and full private backup. Target and host each reserve32MiB (64MiB combined), within unchanged WINDOW_V5. Pi768MiB AS/1MiB stack/CPU2,3/shared200%/Tasks64/300s/60sStop/per-file32MiB; initial850MiB available, sampled192MiB available/640MiB aggregate stops. Fixed32GB device retains5GiB free. A single extended synthetic archive plus journal fits this smaller test admission; a later capture needs its own measured admission.

PowerShell (fresh paths only; a completed run must not be rerun):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B prepare_field_artifact_limits_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_artifact_limits_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V156.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_artifact_limits_v1.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B backup_field_artifact_limits_v1.py
```

CMD / Anaconda Prompt (use the specified environment; no packages or assets downloaded):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_field_artifact_limits_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_artifact_limits_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V156.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_artifact_limits_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_artifact_limits_v1.py
```

The builder has already executed when its derivative directory exists. The dispatcher requires a census younger than15minutes and checks current target-inclusive usage, all known owners, both leases and baseline identities again. Readers do not import the tested writers or modify their artifacts. No synthetic artifact belongs in Git. Preserve failed fixtures and admissions; never amend bound code to make an old run pass.
