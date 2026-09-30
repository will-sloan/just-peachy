# Actual field controller composition

Purpose: prepare a production composition of the installed v12 field controller with the V103 required-archive Stop controller, V105 native writers and V106 actual source chain. `field_live_controller_v1.py` is a fresh adapter. It has **not run on the Pi** and is not a general field launcher or offline acceptance. It provides `create(config_path)`, returning the actual constructed controller plus native-owner, writer, source/admission and imported-origin information. It does not auto-start capture or alter an installation pointer.

The input is the genuinely admitted, pinned `config/CONFIG.json` described in README_FIELD_LIVE_SOURCE_V1. The run must already have real bounded directories, exact installed v12 bytes, code pins and source/config admission, CPU/AS/stack/deadline limits, and a complete target/host reservation. This first live composition requires empty people/session/conversation parents, prepared schema/settings/live/n2 files and no unsupported private inputs. This is an isolated integration restriction, not a migration of the user's gallery or proof of its final compatibility. No existing personal data is moved or deleted.

The installed `controller_type` is derived by changing only its Base, source module, archive-store wiring and `_live_config`. Its backend/mode/tap/enrollment restrictions, artifact-conflict check, 512MiB quota and free-space/session reservation gates remain exact. It admits B01/Open with names/Balanced/O0 through the original checks; this does not claim that all three saved diarizer modes are now live-ready. The actual field-store class body, including constructor contract validation, is executed unchanged with a bounded SessionStore base. A simple subclass that bypasses FieldController checks is not used.

The store admits one conversation attempt and one archive epoch, preserves the bounded archive publisher, prevents automatic draft deletion, and latches conversation-publication failure. `ended` can no longer swallow that failure as an OSError. The controller has one live recording attempt; mode/backend changes after it require a fresh process. Its actual command dispatcher accepts initial mode/backend selection, live Start, Stop, Close and Save/Open. Playback, enrollment, transfer, delete, annotations, arbitrary file input and other write-producing actions are explicitly unavailable in this bounded composition. These required product capabilities remain open in final acceptance, not removed from scope.

Three data configuration paths use fixed old-plus-pending partitions: `data/settings.json`, `data/DATA_SCHEMA.json`, `data/last_application.json`, each primary32KiB + deterministic pending32KiB within its existing64KiB allocation. Settings allows at most32 publication attempts; schema and final-close each allow one. Finite JSON, path/free-space/count checks precede publication; the first fault requests nonblocking Stop before diagnostics and prevents retry. Other private configuration writes reject. The physical path map must be included in the complete layout census: this adapter alone does not prove that the old abstract config-group location map covers every file.

The actual Close method preserves its physical Stop/worker checks and models/lease-release tail. Only final configuration publication is guarded: its failure remains latched while already-permitted physical closure proceeds. A later mandatory Stop on a closed controller preserves its closed state. Actual presentation metadata/metrics are retained; the append is redirected to the reserved presentation slot, with Stop before diagnostics on failure. These failure paths are **unexecuted**. The whole process still requires independent ownership and closure verification.

Before construction, the adapter checks exact installed and helper origins/hashes, substitutes only the admitted archive module, composes the required controller/store and binds native transcript/clock/control sinks. The selected actual source is `isolated_pipeline_source_v5`. App model/profile/asset restrictions remain in the installed code; the eventual run must additionally pin and review the exact live D1 geometry/runtime rather than infer it from saved-mode receipts. Native assets are shared and are not recopied.

Review inputs: this source directory, exact installed release mirror and fresh private review admission. Output: one immutable `COMPOSITION_SOURCE_REVIEW_V1.json`. The review derives/compiles actual methods and compares untouched field restrictions, presentation metrics and physical close regions. It does not execute constructors, a mock controller, source, model or GUI. Never replay a closed review.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B review_field_live_controller_v1.py --preparation 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-controller-v1-preparation' --installed-mirror 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12'
```

CMD or Anaconda Prompt (existing interpreter; no installation/activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_live_controller_v1.py --preparation "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-controller-v1-preparation" --installed-mirror "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12"
```

No standalone capture command is supplied: whole-path/cardinality enforcement, a bounded streamed host mirror, a fresh measured resource allowance/admission and actual integration passage remain necessary. No claim of live source closure, all-mode usability, physical touch, sustained fit, accuracy or offline readiness follows from this source review. Preserve all prior failures, display270 and the October1 17:42:44UTC hard deadline.
