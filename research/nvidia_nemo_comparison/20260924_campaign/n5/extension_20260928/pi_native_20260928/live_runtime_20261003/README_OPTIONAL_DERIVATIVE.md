# Exact optional, History Export and publication-guard derivative preparation

`prepare_optional_derivative.py` makes a disabled build09 from the complete
SHA-pinned admitted build08 and exactly three reviewed code replacements:
`optional_refiner_qualification.py` and the History Export branch in `launcher.py`.
The third is the publication-aware output guard in `launch_raw_qualification_action.py`.
It adds only `owned_export.py` and its `README_OWNED_EXPORT.md`. It does not issue native authorization,
run a model, contact the Pi or alter build08. Its CPU14 owner is registered
before project reads. The replacement changes the explicit qualification
allocation guard; this is a new content identity, not path-only relocation.

Inputs are the immutable admitted08 package directory, each repair path and
SHA256, reviewer label and private output root. Outputs are a fresh source copy,
package/archive, `BUILD_RESULT.json`, `DERIVATION.json`, and two independently
read-back replacement copies. All candidate content is compared with08; any
change besides these files and the updated `README_QUALIFICATION_DISPATCH.md`
and `README_OPTIONAL_QUALIFICATION.md` refuses completion. Operational binding fields
must match except the new content digest and exact package-root path changes.
Existing08 primary and GUI evidence remains evidence of08, with its original
hashes. The derivative receipt explicitly states09 has not executed natively.

PowerShell, after setting actual absolute paths:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$N/prepare_optional_derivative.py" --source $S08 --replacement $REPLACEMENT --replacement-sha256 $REPLACEMENT_SHA --export-launcher $EXPORT_LAUNCHER --export-launcher-sha256 $EXPORT_LAUNCHER_SHA --export-module $EXPORT_MODULE --export-module-sha256 $EXPORT_MODULE_SHA --export-readme $EXPORT_README --export-readme-sha256 $EXPORT_README_SHA --shared-helper $SHARED_HELPER --shared-helper-sha256 $SHARED_HELPER_SHA --shared-readme $SHARED_README --shared-readme-sha256 $SHARED_README_SHA --optional-readme $OPTIONAL_README --optional-readme-sha256 $OPTIONAL_README_SHA --reviewer 'Reviewed optional, export and publication repairs' --output-root "$Q/audit-preparation"
```

CMD or Anaconda Prompt, using the same actual paths in environment variables:

```bat
"%PY%" -B "%N%\prepare_optional_derivative.py" --source "%S08%" --replacement "%REPLACEMENT%" --replacement-sha256 %REPLACEMENT_SHA% --export-launcher "%EXPORT_LAUNCHER%" --export-launcher-sha256 %EXPORT_LAUNCHER_SHA% --export-module "%EXPORT_MODULE%" --export-module-sha256 %EXPORT_MODULE_SHA% --export-readme "%EXPORT_README%" --export-readme-sha256 %EXPORT_README_SHA% --shared-helper "%SHARED_HELPER%" --shared-helper-sha256 %SHARED_HELPER_SHA% --shared-readme "%SHARED_README%" --shared-readme-sha256 %SHARED_README_SHA% --optional-readme "%OPTIONAL_README%" --optional-readme-sha256 %OPTIONAL_README_SHA% --reviewer "Reviewed optional, export and publication repairs" --output-root "%Q%\audit-preparation"
```

Review `DERIVATION.json` and the disabled package content SHA first. A separate
fresh boot/current-baseline admission must select that09 target/content. Build
the admitted09 from its exact disabled snapshot with the existing builder:

```powershell
& $PY -B "$N/prepare_package.py" --source $S09 --profiles "$S09/profiles" --source-snapshot-manifest-sha256 $MANIFEST09 --release-id field-runtime-v29-build-09 --reviewed-native-admission $FRESH_ADMISSION --output-root "$Q/audit-preparation"
```

```bat
"%PY%" -B "%N%\prepare_package.py" --source "%S09%" --profiles "%S09%\profiles" --source-snapshot-manifest-sha256 %MANIFEST09% --release-id field-runtime-v29-build-09 --reviewed-native-admission "%FRESH_ADMISSION%" --output-root "%Q%\audit-preparation"
```

No admission is inferred from elapsed time or from prior08 results. Later
production10 must retain the same09 content and pass the separate exact
path-only relocation/production acceptance/full-backup gates.
