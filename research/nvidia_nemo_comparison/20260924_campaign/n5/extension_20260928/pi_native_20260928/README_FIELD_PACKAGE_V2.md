# Fresh package test-wrapper derivative

Purpose: resolve V1's specific installed-entrypoint harness failure. The V1 Python `runpy` wrapper omitted the installed release directory from sys.path, so health stopped with `No module named native` before controller checks. V1 output, code, admission and verified1014file/one-link private backup remain unchanged. V2 adds exactly one wrapper line inserting the installed main.py directory before runpy. Packaged field_entry_v1 and all application/isolated-source code are byte-identical; no capture, model, GUI or user-facing runtime behavior change is inferred.

Inputs/outputs, command meaning,64MiB combined allowance and resource limits are those in README_FIELD_PACKAGE_V1.md. Fresh field-package-v2 roots permit the failed installed health/controller boundary to execute; the archive/staging steps are its necessary setup. Prior independent failure review/backup is bound into this new admission. The isolated two-version pointer rollback is not original baseline activation. Prepared GUI remains unqualified and is not invoked.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_package_v2.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V117.json
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_package_v2.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V117.json
```

Then run review_field_package_v1.py --run field-package-v2 using the same Python prefix (README_REVIEW_FIELD_PACKAGE_V1.md). Fixed roots refuse overwrites. No old ledger/policy mutation, source-only/model rerun, download or reset. A fresh census is required if V117 has aged past15minutes.
