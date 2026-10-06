# Original kept-source metadata inspection V2

Actual inspect03 passed under V5, with the wrapper and read-only utility closed.
The original2581-byte session JSON SHA is
`7da45b76193d3ddd1e2aa29bbc6792b019643c8a945edd3959d9458db4fc6c69`.
The unchanged selected source has51files/42382804B and966400samples. Recorded
pose/beam/audio anchors share the original source epoch; no current sensors or
models were used. Evidence is private
`operation-kept-source21-inspect-03/dispatch/RESULT.json`. This establishes the
original source pins and clock structure; spatial replay attribution remains a
separate check. The prepared commands below are provenance and must not rerun
consumed inspect03.

Purpose: obtain the original raw-byte `session.json` hash needed by SavedV4
for the actual complete CHECK21 recording. Export ZIP metadata is reserialized
and cannot supply that original byte hash. No digest is guessed or substituted.

Inputs are fixed to build25 manifest
`6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8`,
boot `0561d730-3cad-48e0-940a-fe3930c89665`, actual kept UUID
`c24b685b2bd34d6bb04172965d712c0f`, and the closed CHECK21 proof. Its authoritative
processed source is966400 samples/60.4s at16kHz. A fresh590s payload lifetime
and full operation preread are required. Reuse of a failed label is forbidden.

The native action checks the complete pinned package, recorded PASS/Save proof,
exact main owner/cgroup absence, and existing read-only SessionStore. It acquires
only the existing shared source lock opened `rb`; it creates no lock or SQLite
file. Its 768-entry/512-file/32MiB-member/256MiB-total snapshot method is AST
identical to SavedV4. The whole source is hashed before and after inspection.
The pinned pure spatial `_Timeline` parser validates original pose/beam indexes,
causal sample anchors, ordered clocks, source epoch and966400-sample final bound.
No current BMI/XVF read, model construction, GUI, audio playback or source edit
occurs. Parsing all recorded pose rows is not an accuracy or DSP synchrony test.

V2 corrects only two comparisons between the published JSON and the database
view. Pinned build25 `SessionStore._publish` adds the exact audio descriptor
`processed_encoding=FLOAT32_LE`, `processed_channels=1`,
`replay_encoding=PCM_S16LE`, `segment_index=segments.jsonl` to its published JSON;
the read-only database view omits that block. The initial comparison now adds
exactly those four fields to the database view and compares complete canonical
JSON encodings, so bool/float channel-count aliases also reject. The final database reread must
equal its original database view, while the original published bytes and whole
source snapshot must also remain unchanged. Different or extra published fields
still reject. No original source field is removed or ignored.

Inspect02 passed the V5 host guard, then this original V1 metadata comparison
failed in a read-only native utility. Its natural1 result, raw failure and exact
utility absence remain preserved; no payload writes occurred. V2 preparation
backs up the original V1, exact package25 storage source/manifest and the new
source before checking AST. Every inspector definition except `inspect` is
unchanged. A static AST transformation proves that only those two comparisons
changed and binds the descriptor to the actual pinned `_publish` assignment.
No unchanged healthy native or host suite is rerun.

Output returns only original `session.json` SHA/size/stable identity, canonical
metadata SHA, kept state, exact sample count, whole-source digest/count/bytes,
finite recorded pose/beam/anchor counts and shared-lease closure. Captions,
names, vectors, coordinates and media are not returned. Independent native
process closure remains the wrapper's job; this action never declares its own
physical death.

Host preparation sets CPU14 and writes a typed actual PID/kernel-FILETIME owner
before reading project inputs. Within30s/2MiB it makes exact backups and separate
restore copies before compile/AST review, checks actual closed proof, and writes
fresh ACTION/PAYLOAD/RESULT. EXIT_INTENT is not exact host death; confirm that
owner separately before a native operation.

PowerShell preparation:

```powershell
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$s/prepare_kept_source21_inspection_v2.py"
```

Command Prompt or Anaconda Prompt (same existing interpreter):

```cmd
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/prepare_kept_source21_inspection_v2.py"
```

An optional `--output` must name a fresh directory directly below the existing
private `audit-preparation` root. After exact host-owner closure and the parent's
full preread, the selected read-only dispatch is V5 below. Frozen preparation
RESULTs record V2; those commands remain historical. V5 retains the complete
preread and backup09 binding, and compares the dispatcher's own kernel FILETIME
exactly. The V4 inspect01 failed before SSH when rounded creation times differed;
it performed no native action. Use a fresh inspect03 label and this explicit
V5 command with the unchanged backed ACTION and a fresh PAYLOAD:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$s/host_stabilization_operations_v5.py" --label kept-source21-inspect-03 --action 'ACTUAL_PREPARATION/ACTION.py' --payload 'ACTUAL_PREPARATION/PAYLOAD.json'
```

```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/host_stabilization_operations_v5.py" --label kept-source21-inspect-03 --action "ACTUAL_PREPARATION/ACTION.py" --payload "ACTUAL_PREPARATION/PAYLOAD.json"
```

Do not add `--writes`, call bare SSH, rerun an old label or replace the returned
original byte SHA with the ZIP metadata/canonical/proof digest. Read-only action
status is PREPARED until native execution and independent closure are observed.
The resulting original raw SHA is then the explicit input to
[SavedV4 preparation](README_PREPARE_SAVED_STABILIZATION_V4.md).
