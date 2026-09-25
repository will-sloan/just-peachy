# Accepted N3 analysis handoff

`package_n3.py` packages 30–59 explicitly allowlisted analysis files plus a
content manifest. It requires N3_ACCEPTANCE.json, passing FINAL_CHECKS.json and
a private receipt verifying the accepted Git commit and release tag on the
existing remote. Every analysis member must still match its accepted SHA-256
and byte count. Only Markdown, small JSON and text notices are admitted; no
audio, raw transcripts, voice vectors, profiles, model weights or binaries.

Inputs are `--root` (defaults to this n3 directory), `--file-list`,
`--git-receipt` and fresh `--output`/`--receipt` paths. Output is a private ZIP
with PACKAGE_CONTENTS.json and a small result receipt. It reads every archived
member back and verifies its hash plus ZIP CRC. Target size is <=10 MiB; hard
limit is 20 MiB. Existing outputs and oversized/failed artifacts are preserved.
It does not upload, change acceptance, run models or declare CM5 qualification.

After the accepted source tag has actually been pushed and verified, PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B research/nvidia_nemo_comparison/20260924_campaign/n3/package_n3.py --file-list research/nvidia_nemo_comparison/20260924_campaign/n3/HANDOFF_FILES_FINAL.json --git-receipt G:/Just_Peachy_N1/20260924_campaign/local/n3/git-backup-accepted-20260925-v1.json --output G:/Just_Peachy_N1/20260924_campaign/local/n3/handoffs/N3_ACCEPTED_HANDOFF_20260925_v1.zip --receipt G:/Just_Peachy_N1/20260924_campaign/local/n3/handoffs/N3_ACCEPTED_HANDOFF_20260925_v1.json
```

CMD/Anaconda Prompt (no activation required):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n3/package_n3.py --file-list research/nvidia_nemo_comparison/20260924_campaign/n3/HANDOFF_FILES_FINAL.json --git-receipt G:/Just_Peachy_N1/20260924_campaign/local/n3/git-backup-accepted-20260925-v1.json --output G:/Just_Peachy_N1/20260924_campaign/local/n3/handoffs/N3_ACCEPTED_HANDOFF_20260925_v1.zip --receipt G:/Just_Peachy_N1/20260924_campaign/local/n3/handoffs/N3_ACCEPTED_HANDOFF_20260925_v1.json
```

These names identify the first final package. A repeat must use fresh versioned
paths. The immutable earlier ZIP_CHECKPOINT.json and preparation archives remain
historical. Source/code and model fetch/build manifests are backed up through
the accepted Git tag; the small ZIP is an analysis handoff, not a model release.
