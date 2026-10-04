# Exact History Export lease repair

`prepare_export_derivative.py` creates disabled10 from the exact admitted09
manifest and the reviewed `owned_export.py` shared-lease repair plus its README.
It preserves09, checks every old manifest member, uses no mutable runtime
directory as a source, and refuses any other code/content change. Operational
fields remain exact except new content identity and package-local target paths.
No native job, install, activation or production acceptance is performed.

Inputs: exact admitted09 package, final replacement module/README and SHA256s,
the exact08→09 `DERIVATION.json`, reviewer and private output root. Outputs:
fresh source/package/archive, `BUILD_RESULT.json`, the09→10 `DERIVATION.json`,
unchanged `PREDECESSOR_DERIVATION.json` and independently read-back repair copies.
Actual08 primary/GUI evidence retains its original identity. Neither09 nor10
is represented as natively executed by this source review.

PowerShell (set absolute paths using `README_PACKAGE.md`):

```powershell
& $PY -B "$N/prepare_export_derivative.py" --source $S09 --replacement $MODULE --replacement-sha256 $MODULE_SHA --readme $README --readme-sha256 $README_SHA --prior-derivation $DERIVATION08_09 --reviewer 'Reviewed History Export shared lease repair' --output-root "$Q/audit-preparation"
```

CMD or Anaconda Prompt:

```bat
"%PY%" -B "%N%\prepare_export_derivative.py" --source "%S09%" --replacement "%MODULE%" --replacement-sha256 %MODULE_SHA% --readme "%README%" --readme-sha256 %README_SHA% --prior-derivation "%DERIVATION08_09%" --reviewer "Reviewed History Export shared lease repair" --output-root "%Q%\audit-preparation"
```

CPU14 and a durable actual numeric owner precede project reads. Review the
disabled10 content and complete derivative chain, then separately issue a
fresh finite native admission. Admit only the resulting exact snapshot:

```powershell
& $PY -B "$N/prepare_package.py" --source $S10 --profiles "$S10/profiles" --source-snapshot-manifest-sha256 $MANIFEST10 --release-id field-runtime-v29-build-10 --reviewed-native-admission $FRESH_ADMISSION --output-root "$Q/audit-preparation"
```

```bat
"%PY%" -B "%N%\prepare_package.py" --source "%S10%" --profiles "%S10%\profiles" --source-snapshot-manifest-sha256 %MANIFEST10% --release-id field-runtime-v29-build-10 --reviewed-native-admission "%FRESH_ADMISSION%" --output-root "%Q%\audit-preparation"
```

The known failed09 helper and external export02 receipts remain preserved.
Targeted actual export, optional qualification and the application hour remain
separate native checks. Production11 can later relocate measured10 bytes only
under the existing exact path-only review, acceptance and complete-backup gates.
