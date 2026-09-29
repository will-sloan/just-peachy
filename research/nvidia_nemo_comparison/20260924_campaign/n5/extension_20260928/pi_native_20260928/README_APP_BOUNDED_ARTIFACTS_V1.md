# Fresh native application artifact integration V1

Purpose: integrate the qualified compact JSON event sink and bounded PCM writer into a separate copy of `shared-app-b01-fir-v1/prototype`. This is a model-free test of actual `PrototypeEngine._open_journal_text`, archive worker, `SessionStore` reopening and text export. It does not open a microphone, load models, repair a callback, establish live timing, or activate the derivative.

Inputs: a fresh WINDOW_V5 census; source hashes pinned in `prepare_app_artifacts_v1.py`; existing private failed-live event journals and the admitted saved 715127-sample mono 16kHz PCM file. No new audio or dependency downloads. The original source, archives, installed app and user previews stay untouched.

Outputs: separate target `app-artifact-integration-v1/prototype`, exact derivative manifest, compact engine/archive event streams, unchanged float32 audio master plus explicit PCM16 WAV listening copy, source-backed reopened rows, text export, partial/quota diagnostics and lifecycle/resource receipts. Private outputs remain on the target and are hash-backed-up to the campaign private directory. No playback. PCM rounding/clipping is explicit; float32 master retains original values.

Bounds: two event streams each at most8MiB including terminal footer, full record1MiB, asynchronous queue512items/4MiB, two patch predecessor payloads. Listening WAV at most960000frames/60s; this test feeds44.6954375s. Reopen at most2048 retained caption/format keys and8MiB serialized payloads; excess fails visibly. Legacy byte-offset archives retain their reader path. Compact archives use a format marker and sequential decoder. CLOSED requires COMPLETE; PARTIAL can expose an explicitly failed prefix without converting it to success. Exact-float plus WAV bytes are both charged to archive audio quota; metadata accounting remains conservatively based on expanded bytes. No duration beyond this bounded derivative is admitted.

The native worker is CPU2/3,200%,one native thread,768MiB hard virtual,1MiB stack,64tasks,300seconds with10second stop,8MiB per-file cap. A fresh96MiB combined reservation covers48MiB target and48MiB host backup. These are test bounds, not general field/endurance qualification. Existing app stays active.

## PowerShell

From the worktree, first create an unused fresh CPU14 `window_guard_v5.snapshot` receipt using the existing campaign procedure. Then:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$p/app_artifact_integration_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V63.json'
```

## CMD / Anaconda Prompt

No environment installation is needed; the explicit interpreter is the same from either prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\app_artifact_integration_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V63.json
```

These immutable V1 run names refuse reuse. Do not rerun a closed case; use a justified fresh derivative/admission. `--worker` and `--gate` are target-only entry points invoked by the guarded dispatcher, never manually.

Review after exact owners close, with strict host-key checking:

```bat
ssh -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local "python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/app-artifact-integration-v1/review_app_artifacts_v1.py"
```

The independent reader compares every stored event with retained originals, checks PCM and exact-float bytes, row lineage and legacy-equivalent presentation, partial-state accounting, output sizes, actual unit envelope and natural owner closure. A worker exit0 alone is not acceptance. Physical GUI, inference, live capture and field release remain separate gates.
