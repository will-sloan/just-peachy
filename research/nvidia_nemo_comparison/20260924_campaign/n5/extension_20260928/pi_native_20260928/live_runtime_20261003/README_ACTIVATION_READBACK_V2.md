# Activation01 host readback repair

`readback_desktop_activation_v2.py` reads the already completed activation01. It never sends SSH, runs activation, starts models or changes Desktop. The executed action captured its baseline with `native_writes:false`; the exact command-bound dispatcher changed the outer result to `true` after the action returned. The original host reader rejected that field. Failed readback01 and the executed action remain unchanged.

This narrow reader pins the actual command and action hashes, proves their AST initialization/execution/update order and reconstructs only the captured boolean. The resulting canonical baseline must reproduce exactly99,894 bytes and SHA8872bc2ee78e94c5e3449f7bc2379b383f1bcd23e91f0b1a9862c0e3262646eb. All original inspector closure, baseline hash, root/path/member, artifact byte/hash and aggregate-size checks remain. Exact natural SSH/reader closure and the command source admission pin are also required. This is not a generic missing-field exemption.

Inputs: private `operation-desktop-activation-01` with exact executed sources, admission, natural closure and result. Output: fresh `desktop-activation-01-readback-02`, full small-file metadata copies, independent source/restores and VERIFY. Existing C50GiB/G75GiB plus16MiB reserves stay in force. Python pins CPU14 and writes its actual numeric owner before project reads.

PowerShell (set `$N` and `$Q` to the canonical runtime-source/private-evidence directories):

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/readback_desktop_activation_v2.py" --operation "$Q/operation-desktop-activation-01" --output "$Q/desktop-activation-01-readback-02"
```

Command Prompt / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\readback_desktop_activation_v2.py" --operation "%Q%\operation-desktop-activation-01" --output "%Q%\desktop-activation-01-readback-02"
```

This reader deliberately refuses another operation or reused output. A source/closure/baseline mismatch stops verification; it never retries native activation. Its changed-boundary checks use the actual retained sources and verify that tampering with another baseline field, the baseline flag state, or command source is refused.
