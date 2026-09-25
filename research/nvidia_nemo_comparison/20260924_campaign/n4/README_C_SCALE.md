# Frozen C-only association scale proposal

`D0_C_SCALE_PROTOCOL_V1.json` freezes one proposed conversion of the inherited
D0/ReDimNet association score units into D0/TitaNet cosine units before reading
the newly collected C vectors. It is a declarative protocol, not executable
code, a fitted profile or permission to name speakers. Inputs will be the exact
two completed collections described in README_D0_CALIBRATION.md plus their
separate protected C labels. Outputs of a future implementation must include
every pair-admission count, fit/validation split, center and transformed field,
validation failures, the unchanged nominal comparators and source bindings.

The mapping aligns robust same/different-speaker C cosine centers and preserves
the frozen normalized-joint policy's numerical scale. It is a restricted
engineering proposal, not proof that two encoders have equivalent score
distributions. Identities are held together in a deterministic fit/validation
partition; weights prevent long clips or prolific identities dominating by
their number of windows. Full per-role diagnostics remain necessary. Short
clips and missing admission remain visible in denominators.

No grid search, Q feedback, clipping invalid parameters or refitting on the
validation partition is allowed. A failed or unsupported mapping remains
unqualified. A passed clean-C mapping still needs actual tracker regression and
does not certify processed-query recognition. E0 remains byte-for-byte nominal;
the inherited E1 settings remain available as a labelled nominal sensitivity.
Any runtime integration must use a fresh derivative and explicit profile hash.

There is no execution command for this JSON. Inspect and hash it in PowerShell:

```powershell
$jpProtocol='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4\D0_C_SCALE_PROTOCOL_V1.json'
Get-Content -LiteralPath $jpProtocol -Encoding UTF8
Get-FileHash -LiteralPath $jpProtocol -Algorithm SHA256
```

Command Prompt / Anaconda Prompt:

```bat
set "JP_PROTOCOL=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4\D0_C_SCALE_PROTOCOL_V1.json"
type "%JP_PROTOCOL%"
certutil -hashfile "%JP_PROTOCOL%" SHA256
```

Keep this version immutable once recorded. A later implementation must verify
its hash before fitting and write results to a fresh private directory. All
vectors, actor identities and detailed pair data remain outside GitHub.
