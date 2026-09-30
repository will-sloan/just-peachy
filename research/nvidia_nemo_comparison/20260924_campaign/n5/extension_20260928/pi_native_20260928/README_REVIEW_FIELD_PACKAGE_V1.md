# Native package review and private backup

Purpose: independently verify the closed field-package-v1/v2 evidence using standard ZIP/JSON/hash readers, not the package's own pass flag. Check source/admission hashes, live envelope, exact closed owners, baseline/capture/leases, code-only archives and installed bytes. V1 explicitly retains the installed-entrypoint test-wrapper import-path failure; no health/controller acceptance follows. V2 success additionally requires health/controller outputs, preserved private canary/config, candidate rollback pointers, rejection receipts, retained damaged-code fixture and unique asset inode accounting. No model/capture/GUI rerun.

Inputs: existing closed target run and host launch receipts. Outputs: private REVIEW/BACKUP/SYMLINKS plus exact target file copies. Every tar path/size/hash is checked; the sole allowed symlink deployment/models must point exactly to the installed model store. It is preserved as metadata without following it or copying models. All other links/traversal/duplicates are rejected. Original target evidence is untouched. A future restoration must recreate only that verified link after inspecting its destination.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_package_v1.py --run field-package-v1
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_package_v1.py --run field-package-v1
```

For the fresh corrected test-wrapper derivative use `--run field-package-v2`. Existing review/backup directories refuse overwrite. Host coordinatorCPU14, native readerCPU3/256MiB,64MiB combined run/backup cap. The reader does not run installed application code. Pointer rollback is in the isolated candidate installation, not the original rc5 activation. Field/visible/endurance/asset-relocation acceptance remains separate.
