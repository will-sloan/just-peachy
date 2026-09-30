# Guarded installed health and controller launcher

Purpose: connect the qualified single-state candidate metadata to actual installed entrypoint execution, with continuous private-data/update ownership. No old release, pointer, app configuration or personal data is overwritten. Fresh descriptors/state point to unchanged installed v5/v7 releases and retained shared dependencies. Only small configuration/receipt files are copied; no audio, weights, runtime or release tree is copied.

`field_guarded_launcher_v1.py` accepts one bound launch JSON. It verifies source/run admission, boot, expiry, exact candidate state/descriptor/dependencies/entrypoint and required DATA_SCHEMA/live_config/n2_runtime hashes. It checks CPU2,3/768MiB AS/1MiB stack and closed capture before entry. Only `health` and `controller-check` commands are allowed; there is no GUI/capture command here. The immutable entrypoint's actual `main()` runs in the same launcher process.

Code inspection corrected an incomplete earlier description: the installed Controller already takes ApplicationLock, which uses the shared RuntimeLock. The missing boundary is continuity from launcher preflight through controller shutdown. The new launcher holds one real RuntimeLock throughout. For controller-check only, a process-local factory temporarily replaces `app.paths.RuntimeLock` with one tightly bound borrowed handle: exact private root, purpose application, same token/PID and only one borrower. The unchanged ApplicationLock still runs its root/schema/feature checks, while its close acknowledges the borrow without releasing the outer owner. Installed main then joins queues/threads before the launcher releases ownership. The factory is restored in finally; installed files remain exact. Health uses the outer lease directly and makes no borrow. This is an explicitly tested adapter, not evidence that an unmodified direct entry invocation supplies launcher-wide ownership.

`field_launcher_protocol_v1.py` prepares a fresh data root from verified configuration backups and a synthetic canary. It first checks missing n2_runtime before copying that config; then tests stale state, changed config digest and actually busy data. Positive cases execute installed v7 health, v7 idle Controller and v5 health after an explicit candidate rollback. Bounded test barriers retain ownership just before actual entry and after entry/threads finish; the parent tries a real update at both points and must receive busy rejection with unchanged candidate state. These barriers are internal no-capture test coordination, not user readiness. Each child has a60s deadline/owned cleanup; forced closure fails acceptance. All exact child owners and current process resource samples are retained. Child inherited ru_maxrss is not used as a fresh peak.

Inputs: fresh CPU14 target-inclusive WINDOW_V5 census and current owners/leases/resources, reviewed/private-backed-up V62 transaction result, exact prior state SHA, v5/v7 release manifests, retained dependency lock, original baseline/config bindings and current authority. Outputs: field-launcher-v1 admission/backups, fresh descriptors/state/transactions/data metadata, seven per-launch admissions/results/owners, six actual update-contention receipts, aggregate result, limits/resource closure and independent hashed private backup. The actual app may initialize empty private store metadata; original config hashes and canary must stay exact. No populated private gallery compatibility follows.

Envelope:8MiB combined new output,4MiB target/4MiB host,768MiB AS per parent/child,1MiB stacks,sharedCPU2,3/200%,Tasks64,300s service/60s Stop/8MiB file, one active launcher child. Initial850MiB available RAM; sampled192MiB floor/640MiB owned aggregate RSS stop, not hard aggregate enforcement. Fixed32GBPi/5GiB free reserve and all existing output remain counted. No download, reset, playback, capture, model inference or GUI. Rehashing required dependencies is a new entry gate; catalogue collection/ldd/import-probe protocols are not repeated.

PowerShell, fresh unexecuted paths only:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_launcher_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V146.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_launcher_v1.py
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_launcher_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V146.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_launcher_v1.py
```

The protocol invokes each child using the existing native Python and `field_guarded_launcher_v1.py --launch <fresh-case-launch.json>`. Do not invoke that directly to bypass supervision/admission or reuse completed paths. The independent reader sets hostCPU14/PiCPU3/256MiB, disables bytecode, checks raw child outputs/owners/lock tokens, before/after update rejections, exact configs/state/releases and private backup. It does not invoke the tested launcher or models. Original rc5 activation, captured-input parity, GUI/microphone lifecycle, crash recovery, endurance and full field release remain separate boundaries.
