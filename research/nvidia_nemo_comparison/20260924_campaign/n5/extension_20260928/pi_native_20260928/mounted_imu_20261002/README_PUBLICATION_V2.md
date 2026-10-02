# Corrected motion handoff publication

Purpose, inputs, outputs and16MiB/600-second/host-floor bounds are those in
README_PUBLICATION.md. V1 stopped at a code-key lookup after backing up old guides
and copying some reviewed source; it made no Pi contact. Its files remain intact.

`publish_motion_delivery_v2.py` binds the actual `code/` capsule prefix, verifies
the previous host owner is absent, backs up all partial source independently,
and reuses identical source copies. It derives guides from the original restored
bytes, preserving v1 outputs, then completes a fresh private publication-v2 and
new immutable handoff. It never reruns native/model/capture work.

PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./publish_motion_delivery_v2.py
```

CMD/Anaconda Prompt in the existing project environment:

```bat
python -B publish_motion_delivery_v2.py
```

Run from this source directory. Inputs remain the existing reviewed v27 results,
restored capsule and original guide backups. Outputs are current guides/source,
MOTION_HANDOFF_RECEIPT and private publication-v2 backups/archive/readbacks.
The new label is one-use; do not rerun after success or failure.
