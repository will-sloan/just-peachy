# Fresh classic-frontend repair package

`build_classic_package.py` prepares a new `field-runtime-v29-build-17` package on the Windows host. It does not contact the Pi, deploy, activate a shortcut, start microphone capture, or modify build16. The builder verifies every parent package member against the exact reviewed build16 manifest before it copies anything.

The purpose is to restore the familiar operator application behind one profile-selection launcher and carry explicitly reviewed startup repairs without overwriting the rollback release. Model weights, separate ReDimNet/TitaNet galleries, BMI270 calibration, XVF routing, finite session/resource/storage controls and the external recording-store location are preserved.

Inputs are the immutable build16 package, an explicit reviewer name, and `--replacement MODULE=PATH` arguments for reviewed `launcher.py`, `classic_frontend.py`, `xvf_readiness.py`, `xvf_readiness_helper.py`, optional `installed_engine.py`/`worker.py`, and paired README files. The launcher, classic frontend and both readiness helpers are required together. The additional allowed guides are `README_CLASSIC_FRONTEND.md`, `README_XVF_READINESS.md`, `README_RUNTIME_REPAIR.md` and this README. No other module can be changed by this builder.

The launcher must retain the entire parent module AST after removing precisely the classic-frontend wrapper and one live-only recovery hook after session admission, and renaming its preserved laboratory view. An `installed_engine.py` replacement must preserve its entire parent AST except one `asr_final=row.get('final') is True` caption-provenance keyword. This carries the existing ASR event flag and changes no models, thresholds, inference or physical source code.

Outputs are a unique private preparation directory containing the full package, a deterministic gzip tar archive, `BUILD_RESULT.json`, early `REGISTERED_OWNER.json`, finite `HOST_SCOPE.json`, and `SOURCE_CLOSED.json`. Package members include exact independent backup/restore copies of each replaced Python module and paired manifest-covered `REPAIR_PROVENANCE.json` files. Every archive member is independently decompressed and compared with its package bytes before completion.

The 246 ordinary backend/source selections are retained for guarded field validation. The previously measured optional parallel D1-refiner selection is disabled: its measured admission binds different runtime content and is not reused. Historical evidence stays unchanged. This repair is not a new native measurement, sustained real-time result, quality qualification, or physical-touch test.

## Run from PowerShell

Run only after reviewing the concrete replacement files. Replace the reviewer text with the actual reviewer. `--replacement` arguments are single strings, with the member name before `=` and its saved host path after it.

```powershell
$repair = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$repair/build_classic_package.py" --reviewer 'Actual reviewer' --replacement "launcher.py=$repair/launcher.py" --replacement "classic_frontend.py=$repair/classic_frontend.py" --replacement "xvf_readiness.py=$repair/xvf_readiness.py" --replacement "xvf_readiness_helper.py=$repair/xvf_readiness_helper.py" --replacement "installed_engine.py=$repair/installed_engine.py" --replacement "README_CLASSIC_FRONTEND.md=$repair/README_CLASSIC_FRONTEND.md" --replacement "README_XVF_READINESS.md=$repair/README_XVF_READINESS.md" --replacement "README_RUNTIME_REPAIR.md=$repair/README_RUNTIME_REPAIR.md" --replacement "README_PACKAGE_REPAIR.md=$repair/README_PACKAGE_REPAIR.md"
```

The current repair uses no `worker.py` replacement. Omit the `installed_engine.py` replacement if the reviewed change does not require the ASR-final provenance addition. Never substitute an unreviewed file just to complete the package.

## Run from Command Prompt or Anaconda Prompt

The explicitly pinned interpreter avoids depending on whichever Conda environment is active. The same command works in both prompts.

```bat
set "REPAIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\ui_restore_20261004"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%REPAIR%\build_classic_package.py" --reviewer "Actual reviewer" --replacement "launcher.py=%REPAIR%\launcher.py" --replacement "classic_frontend.py=%REPAIR%\classic_frontend.py" --replacement "xvf_readiness.py=%REPAIR%\xvf_readiness.py" --replacement "xvf_readiness_helper.py=%REPAIR%\xvf_readiness_helper.py" --replacement "installed_engine.py=%REPAIR%\installed_engine.py" --replacement "README_CLASSIC_FRONTEND.md=%REPAIR%\README_CLASSIC_FRONTEND.md" --replacement "README_XVF_READINESS.md=%REPAIR%\README_XVF_READINESS.md" --replacement "README_RUNTIME_REPAIR.md=%REPAIR%\README_RUNTIME_REPAIR.md" --replacement "README_PACKAGE_REPAIR.md=%REPAIR%\README_PACKAGE_REPAIR.md"
```

The optional `--base`, `--base-manifest-sha256`, and `--output-root` arguments are restricted to the exact reviewed parent and existing private preparation roots; they cannot grant a different source or destination. The default base manifest SHA is `a88217b7dcdf0360309b4bea28baa376e6a55d64090fe64e2ba3cfeaa2cb2a73`. The emitted `data_root` is the preserved external store `/home/peachyprototype/JustPeachy/data/runtime-v29`; `--data-root` may only name that same path. A separate Desktop activation must pass it unchanged. This builder neither migrates nor edits recordings.

## Boundaries and next action

CPU14 affinity and actual host identity are persisted before project inputs are read. A cumulative 16 MiB/600-second preparation bound, 16 MiB expanded package, 512-member package, 2 MiB per member/archive and the existing C:50 GiB/G:75 GiB free-space floors remain enforced. Failures preserve the fresh directory and never edit or delete the parent package.

Read `BUILD_RESULT.json` and independently review its exact output package/provenance before a separate guarded native stage and activation. Native startup, Stop/closure, profile selection and restored frontend behavior still require focused Pi evidence. Do not treat a successful host build as proof that the repaired application started on the Pi.
