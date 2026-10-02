# Motion source and handoff publication

`publish_motion_delivery.py` reconciles the completed v27 motion integration into
the existing operator guides, copies a reviewed source whitelist, and makes one
small ChatGPT ZIP with independent archive and expanded readback. It reads
existing evidence only; it does not connect to the Pi or rerun models or audio.

Inputs: the fixed prepared-PC paths in the script, `delivery-review-v1/RESULT.json`,
the restored common capsule, current host source and existing completion guides.
Outputs: updated current guides, `mounted_imu_20261002` repository source,
MOTION_RELEASE_INDEX/CHECKLIST/HANDOFF_RECEIPT and private `publication-v1` backups.
It pins CPU14 before project reads, records its owner, enforces a600-second/16MiB
aggregate publication budget and host free-space floors, and preserves old guides
with independent restores before changing them. Old final packs stay immutable.

PowerShell from this folder:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./publish_motion_delivery.py
```

CMD or Anaconda Prompt in the existing project environment:

```bat
python -B publish_motion_delivery.py
```

The output label is one-use. Do not rerun a closed or failed publication directory;
preserve its receipts and use a separately reviewed fresh derivative if needed.
G-drive repository/evidence writes require the normal workspace permission.
Git review/whitelist commit/remote verification are separate operations after
publication. This tool contains no credential, media or private gallery output.
