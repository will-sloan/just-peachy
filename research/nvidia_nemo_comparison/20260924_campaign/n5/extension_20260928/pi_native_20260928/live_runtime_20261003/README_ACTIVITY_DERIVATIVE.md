# Exact optional activity repair derivative

`prepare_activity_derivative.py` copies the exact admitted10 manifest to a fresh disabled11 candidate, replacing only the SHA-pinned `optional_refiner.py` and `README_OPTIONAL_REFINER.md`. Empty activity acknowledgements continue through validation and source watermarks but consume no real-mask queue slot. Eight nonempty batches remain the limit. Every other content member and operational value is checked, apart from the new content hash and exact package-local path relocation. No native job, install or activation occurs.

Inputs: admitted10 package, reviewed replacement module and README with SHA256, exact09-to10 DERIVATION.json, reviewer, and private output root. Outputs: fresh package/archive, BUILD_RESULT.json, complete source-difference DERIVATION.json, preserved predecessor receipt, and independently read-back repair copies. The earlier disabled11 path-only preview is historical and must not be staged.

Set PY to `C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe`, N to this directory, Q to the private live-runtime evidence root, S10 to the exact admitted10 package, MODULE/README to the activity repair, and DERIVATION09_10 to its predecessor receipt.

PowerShell:

```powershell
& $PY -B "$N/prepare_activity_derivative.py" --source $S10 --replacement $MODULE --replacement-sha256 $MODULE_SHA --readme $README --readme-sha256 $README_SHA --prior-derivation $DERIVATION09_10 --reviewer 'Reviewed empty activity queue repair' --output-root "$Q/audit-preparation"
```

CMD or Anaconda Prompt (use the explicit qualified interpreter):

```bat
"%PY%" -B "%N%\prepare_activity_derivative.py" --source "%S10%" --replacement "%MODULE%" --replacement-sha256 %MODULE_SHA% --readme "%README%" --readme-sha256 %README_SHA% --prior-derivation "%DERIVATION09_10%" --reviewer "Reviewed empty activity queue repair" --output-root "%Q%\audit-preparation"
```

CPU14 and durable actual numeric owner registration precede project reads. A separate fresh finite native admission is required before preparing an enabled copy. Admit the resulting frozen package, never mutable N:

```powershell
& $PY -B "$N/prepare_package.py" --source $S11 --profiles "$S11/profiles" --source-snapshot-manifest-sha256 $MANIFEST11 --release-id field-runtime-v29-build-11 --reviewed-native-admission $FRESH_ADMISSION --output-root "$Q/audit-preparation"
```

```bat
"%PY%" -B "%N%\prepare_package.py" --source "%S11%" --profiles "%S11%\profiles" --source-snapshot-manifest-sha256 %MANIFEST11% --release-id field-runtime-v29-build-11 --reviewed-native-admission "%FRESH_ADMISSION%" --output-root "%Q%\audit-preparation"
```

The failed10 optional-first receipt remains unchanged. Source review does not assert an11 native pass or promote optional measurement to production. Separate native optional qualification and later production acceptance remain required.