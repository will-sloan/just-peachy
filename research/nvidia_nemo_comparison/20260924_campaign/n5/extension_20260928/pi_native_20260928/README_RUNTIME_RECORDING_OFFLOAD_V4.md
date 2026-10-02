# Complete recording offload, including optional four-channel raw audio

Purpose: independently copy one closed original broker tree or its verified Pi-local backup to the PC, with complete membership, hashes, readback and exact exporter closure. Copy only; never delete recording data.

Inputs: installed source candidate and current active candidate receipts; full prior owner binding and previous utility receipt; recording-01 through recording-04; original or local root; new private destination. The source must have actual CLOSED and BACKUP receipts. Outputs: early identities, resource census, source manifest, full private mirror, per-file SHA readback and BACKUP receipt. No capture/model/Pi payload writes.

The unchanged per-file32MiB,1162files/264dirs,16KiBchunks/256KiBframes and time/floor guards remain. Raw-capable full independent single-tree ceiling is189080108B=155669036B+33411072B, plus4MiB host metadata. The actual release allocation also bounds the selected source. This is a prospective independent copy reservation, not deleted/unused credit or a change to old policies. All historical owners are read; exact issued prior identities are merged before the existing16-new-owner continuation limit; total stays1024.

PowerShell (replace uppercase path placeholders with absolute paths):
    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B export_runtime_recording_v4.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection PREVIOUS --candidate-install SOURCE_INSTALL --active-install ACTIVE_INSTALL --slot recording-01 --root-kind original --output NEW_PRIVATE_ORIGINAL

Command Prompt / Anaconda Prompt:
    python -B export_runtime_recording_v4.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection PREVIOUS --candidate-install SOURCE_INSTALL --active-install ACTIVE_INSTALL --slot recording-01 --root-kind original --output NEW_PRIVATE_ORIGINAL

Then use the original-copy output as PREVIOUS, --root-kind local and a distinct NEW_PRIVATE_LOCAL destination to preserve the independent Pi-local backup. Run from the source directory with the existing environment and credentials. Private recordings and galleries must never enter Git.
