# Exact-byte B05 source reproduction

Purpose: correct the source-reproduction input path while preserving executed B05 source, run bindings and README. The earlier B05_PARENT_PIPELINE_V1.py.txt was a text-mode audit snapshot whose Windows newline conversion changed its byte hash. It is not the exact-byte parent that prepare_b05_anonymous_v1.py requires; using that old README command fails closed at its parent hash guard. No failed source was dispatched from that command. Actual source preparation and target admission independently used the correct parent/candidate hashes, and application evidence is unchanged.

Use the fresh private B05_PARENT_PIPELINE_EXACT_V1.py, fetched as bytes from the preserved remote shared-app-delayed-metadata2-v2/prototype/app/n2_pipeline.py and verified against SHA2566b6e797c418ed44babd9ced367ab8e05db940714e0918a925b4de5d5352625e7. The unchanged preparer verifies the preserved Windows anonymous reference, applies only its three hunks and requires candidate SHA2566312c12f80b67183faf93b6ca83502b47f0e7bca62d124a170a58a6a51000491. This is source reproduction only, no inference, assets, model or recording changes.

## PowerShell

From this directory, choose a fresh output path:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$private = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928'
& $py prepare_b05_anonymous_v1.py --parent "$private\B05_PARENT_PIPELINE_EXACT_V1.py" --reference 'G:\Just_Peachy_N1\20260924_campaign\local\releases\d1-stable-asr-chunks-v1\prototype\app\n2_pipeline.py' --out "$private\b05-source-reproduction-v1"
```

## CMD / Anaconda Prompt

Use `cd /d` here, invoke the same quoted Python executable without `&`, expand paths or use `set "JP_PRIVATE=..."` and `%JP_PRIVATE%`. No dependencies/downloads needed. Output is a single private reconstructed n2_pipeline.py; existing directories are refused. The executed derivative stays immutable. The complete B05 native run/review instructions remain in README_B05_ANONYMOUS_FULL_V1.md and README_B05_REVIEW_V1.md; this correction supersedes only the earlier parent snapshot path for reproduction.
