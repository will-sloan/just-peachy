# Copy selected recordings to the PC and verify them

`verify_recording_offload.py` verifies a copied v29 recording export against the
complete ZIP size and SHA256 measured on the Pi. It streams every member through
ZIP CRC validation and hashes the whole archive again afterwards. It does not
extract files, play audio, change recordings or delete the Pi copy. A successful
receipt establishes exact copying, not recognition accuracy or raw qualification.

The input is an existing ZIP produced by **History → select kept recordings →
Export**, plus its Pi SHA256 and byte count. The output is a fresh private folder
with `REGISTERED_OWNER.json` and `VERIFY.json`, or an explicit `FAILURE.json`.
Keep the archive and these receipts outside Git and the public handoff.

## Pi export and source hash

1. Stop and drain the session. Choose **Save processed** or the qualified
   **Save raw + processed** option. Select the recording(s) in History and export
   to a new filename, for example `/home/peachyprototype/Desktop/field-test-001.zip`.
2. In the Pi terminal, measure the completed export:

```sh
sha256sum -- /home/peachyprototype/Desktop/field-test-001.zip
stat -c %s -- /home/peachyprototype/Desktop/field-test-001.zip
```

Retain both results. Close no other recording and do not overwrite an old export.
The export contains exact float model input, segmented PCM16 replay WAV, indexed
captions/events and registered provenance. Qualified raw channels, when selected,
retain their original format/timeline metadata. Segments form one continuous
session; use the saved-session replay selector to replay the complete timeline.

## PowerShell on this PC

Use a new destination directory. Replace `SOURCE_SHA256`, `SOURCE_BYTES` and
`UNCOMPRESSED_LIMIT_BYTES` with the actual values/finite allocation for this
export. The uncompressed limit can equal the source ZIP size for the runtime's
uncompressed ZIP_STORED exports.

```powershell
$dest='G:/Just_Peachy_N1/recording-offloads/field-test-001'
if (Test-Path -LiteralPath $dest) { throw 'Choose a fresh destination' }
New-Item -ItemType Directory -Path $dest | Out-Null
scp -i 'C:/Users/amiri/.ssh/just_peachy_cm5_ed25519' -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@192.168.2.57:/home/peachyprototype/Desktop/field-test-001.zip "$dest/recording.zip"
if ($LASTEXITCODE -ne 0) { throw 'Copy failed; preserve the partial file' }
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/verify_recording_offload.py" --zip "$dest/recording.zip" --source-sha256 SOURCE_SHA256 --source-bytes SOURCE_BYTES --maximum-uncompressed-bytes UNCOMPRESSED_LIMIT_BYTES --output "$dest/verification"
```

## Command Prompt and Anaconda Prompt

Use the existing pinned interpreter; no package/model download or environment
installation is needed. These same commands work in Anaconda Prompt.

```bat
set "DEST=G:\Just_Peachy_N1\recording-offloads\field-test-001"
rem Continue only when DEST does not already exist.
mkdir "%DEST%"
scp -i "C:\Users\amiri\.ssh\just_peachy_cm5_ed25519" -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@192.168.2.57:/home/peachyprototype/Desktop/field-test-001.zip "%DEST%\recording.zip"
rem Stop if scp failed. Preserve partial copies; choose a fresh folder to retry.
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\verify_recording_offload.py" --zip "%DEST%\recording.zip" --source-sha256 SOURCE_SHA256 --source-bytes SOURCE_BYTES --maximum-uncompressed-bytes UNCOMPRESSED_LIMIT_BYTES --output "%DEST%\verification"
```

Only `VERIFIED_COMPLETE_COPY` is a successful PC readback. A failed/truncated
copy never authorizes deletion. Copying is the default; any later deletion is a
separate deliberate action on an explicitly selected recording.

## Bounds and scope

The verifier pins this host's coordinator to CPU14 before reading the archive,
registers its real process identity, reads in64KiB blocks, and rejects a ZIP
directory above16MiB or16384 entries before loading that directory. Member names
are bounded to512 UTF8 bytes. Duplicate/case-aliased/traversal/encrypted/link or
compressed members reject; v29 exports stored regular files. ZIP64 is supported.
The caller supplies the exact source extent and finite total uncompressed bound.
No model or audio arrays are loaded. Receipts are at most16KiB each.

Focused host verification uses a small synthetic stored export, its ZIP64 end
record equivalent, and corrupt digest/duplicate name/traversal/allocation
rejects. These checks establish verifier behavior only. Actual selected native
recording exports require their own source hash and PC verification receipt.
