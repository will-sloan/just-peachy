# Reviewed relocation of unchanged runtime bytes

The external `prepare_package.py` can relocate an exact frozen candidate into a
new independent release directory only with a separately reviewed, SHA-pinned
`just-peachy.reviewed-runtime-relocation.v1` certificate. This does not modify
the source package or reclassify its measurements as native execution of another release.

Inputs are the complete source snapshot/manifest pin, certificate/path/SHA,
destination release ID, and the separate native or production authorization.
The certificate must bind the actual source manifest and raw binding hashes,
unchanged candidate content and installed-release pins, exact source/destination
operational hashes, and the sorted complete list of path transformations.
Only `target`, `reference_code`, every `profiles.<key>.path`, and
`raw_factory_path` may replace the exact old-root prefix with the new root.
All suffixes, model/source hashes, raw qualification, geometry and other behavior
remain byte-equivalent in canonical JSON. Only the four existing authorization
fields are excluded from operational comparison. Partial mappings and any other
operational change are refused.

Outputs are a new immutable package plus its usual source backups/archive. The
exact `RELOCATION_CERTIFICATE.json` is added alongside authorization metadata,
after candidate content hashing. The builder neither issues this review nor
rewrites a measured receipt. Reusing an optional measurement requires a separate
reviewed proof retaining actual qualified source-package/binding provenance and
the certificate pin. Native admission, production acceptance, full backup and
activation remain separate existing gates.

PowerShell, with the exact paths from `README_PACKAGE.md` and actual reviewed
`S`, `SOURCE_MANIFEST`, `CERT`, `CERT_SHA`, and authorization file:

```powershell
& $PY -B "$N/prepare_package.py" --source $S --profiles "$S/profiles" --source-snapshot-manifest-sha256 $SOURCE_MANIFEST --release-id field-runtime-v29-build-13 --reviewed-relocation-certificate $CERT --relocation-certificate-sha256 $CERT_SHA --production-acceptance 'ACTUAL_PRODUCTION_ACCEPTANCE.json' --output-root "$B/live-runtime-20261003/audit-preparation"
```

CMD or Anaconda Prompt:

```bat
"%PY%" -B "%N%\prepare_package.py" --source "%S%" --profiles "%S%\profiles" --source-snapshot-manifest-sha256 %SOURCE_MANIFEST% --release-id field-runtime-v29-build-13 --reviewed-relocation-certificate "%CERT%" --relocation-certificate-sha256 %CERT_SHA% --production-acceptance "ACTUAL_PRODUCTION_ACCEPTANCE.json" --output-root "%B%\live-runtime-20261003\audit-preparation"
```

Use `--reviewed-native-admission ACTUAL_ADMISSION.json` instead of production
acceptance only for the separately authorized qualification mode. Omit both for
a disabled relocation preview. No certificate means the prior exact operational
equality rule remains unchanged. Raw/batch/variant options are inherited from
the snapshot; do not override them.

The pure host test uses actual frozen manifest/binding bytes but constructs only
an in-memory synthetic review fixture; it builds nothing and grants no authority:

```powershell
& $PY -B "$N/test_raw_release.py" --output-root "$B/live-runtime-20261003/audit-preparation" --relocation-package $S --checks test_relocation_keeps_actual_source_identity_and_all_nonpath_behavior
```

```bat
"%PY%" -B "%N%\test_raw_release.py" --output-root "%B%\live-runtime-20261003\audit-preparation" --relocation-package "%S%" --checks test_relocation_keeps_actual_source_identity_and_all_nonpath_behavior
```

CPU14 and an actual numeric host owner are registered before project reads. The
test writes a fresh result receipt and rejects changed source/manifest/model
pins, incomplete mappings, geometry/raw policy changes and a native-qualified
claim. No SSH, native model, desktop action or production acceptance is executed.
