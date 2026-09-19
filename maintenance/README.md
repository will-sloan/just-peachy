# GitHub snapshot maintenance

`github_snapshot.py` preserves compact S0–S7/PROTO1 handoffs and the model-free
PROTO1 source release for the repository. It reads existing completed
artifacts; it runs no experiments, models, microphone or device commands.

Inputs: the local simulation handoff folder, final source-release ZIP and a new
output directory. Outputs: copied original archives, explicitly labeled text-only
archives where audio/binary members were omitted, and a SHA-256/size/source index.
Original files are unchanged. Text-only archives retain historical manifests for
context and add `GITHUB_SNAPSHOT.json` explaining omissions and binding every
included member. They are not substitutes for the complete local data archives.

From the repository root in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B .\maintenance\github_snapshot.py --handoffs '.\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\handoffs' --output '.\project_handoffs' --release 'G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.1.2.zip'
```

CMD / Anaconda Prompt:

```bat
.edge-speech-env\python.exe -B maintenance\github_snapshot.py --handoffs "XVF 3800 Testing\XVF Integration Real World RIRs\simulation\handoffs" --output "project_handoffs" --release "G:\Just_Peachy_PROTO1\releases\just-peachy-proto1-0.1.2.zip"
```

Use a fresh output directory for a later snapshot, review changes and hashes,
then deliberately replace the published snapshot if appropriate. The script
refuses to overwrite a differing archive. It needs only Python's standard library.
Machine-local paths, raw measurements/RIR WAVs, voice embeddings, weights,
environments, firmware/vendor bundles and complete execution journals stay local.
Restore those from their separate data backups before rerunning experiments.

`GITHUB_SYNC_AUDIT.json` records the pre-staging source/archive inventory, ZIP CRCs,
high-confidence credential-pattern scan and comparison of all 110 PROTO1 release
payloads with the working source. Inventory counts exclude the generated audit
itself and later navigation/Git-attribute edits. It records preparation, not proof
of a push or repository visibility. Check GitHub privacy and the remote commit
before describing the snapshot as uploaded.
