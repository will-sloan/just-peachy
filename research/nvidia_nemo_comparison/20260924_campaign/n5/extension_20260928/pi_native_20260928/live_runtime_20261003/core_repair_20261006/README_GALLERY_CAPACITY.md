# Personal gallery capacity

Purpose: remove the fixed 256-profile, 1024-member and 16 MiB aggregate gallery
refusals. Existing model validity, exact encoder namespaces and calibration
thresholds are unchanged. This module performs private byte copies and metadata
listing; it does not start a model or verify a speaker.

`gallery_snapshot_io.py` accepts real source and fresh target directories, a
membership receipt path, the actual session storage policy through `DiskBudget`,
the existing owner/RAM guard and a small receipt header. It copies one regular
file at a time in 16 KiB chunks and streams one membership record at a time into
the JSON `files` array. Output is the unchanged membership schema with file
paths, byte counts and SHA256 values, plus a small count/hash descriptor.
Reference vectors never enter receipts. File identities and source/copy hashes
are checked independently, and the published receipt receives independent hash
readback. Incomplete outputs are retained as evidence on failure.

`personal_gallery.py` uses the helper for used-gallery snapshots and the first
immutable-to-writable seed copy. Profile metadata is parsed one record at a time.
The small display roster is returned in UUID order; actual available RAM retains
the existing 192 MiB floor. Individual metadata records remain at most 128 KiB,
individual copied files at most 2 MiB, and receipt headers/members at most 256 KiB.
Regular-file, ownership, root-containment and no-symlink validation remain. Each
copy/write checks the actual filesystem free-space reserve, including the
session policy's byte and fractional reserve. Count and aggregate-byte estimates
are accounting, not availability quotas. Working copy and receipt buffers remain
bounded independently of the corpus size.

The runtime modules are imported by the candidate launcher. Include
`gallery_snapshot_io.py` alongside `personal_gallery.py`; use
`README_CORE_REPAIR.md` for package/run commands. Do not edit an installed release.

`test_gallery_capacity.py` has one focused standard-library fixture. Inputs are
257 declared UUID metadata profiles and 17 MiB of copy-only bytes in a fresh
temporary directory. Outputs are pass/fail assertions, exact membership/hash
readback, and automatic temporary-directory cleanup. It checks the actual test
filesystem against a 64 MiB reserve and skips only if that declared physical
floor is unavailable. The metadata RAM snapshot is declared; this test does not
claim model/gallery speaker quality or target-device memory qualification.

Run only after the current native owner preread releases Python, in a fresh
registered CPU14 process; do not overlap another test/native owner process.

PowerShell:

```powershell
$repairDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
Set-Location -LiteralPath $repairDir
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -m unittest -v test_gallery_capacity
```

CMD or Anaconda Prompt, using the existing environment without installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -m unittest -v test_gallery_capacity
```

Inputs/outputs are described above; keep this README updated with changes to
copy validation, resource reserves, membership schema or the focused fixture.

Validation on 2026-10-06 passed this case without a skip in the registered
24-test contracts process. All 257 metadata profiles were available; the used
gallery copy exceeded 16 MiB, preserved 274 member hashes and the streamed
receipt hash, retained the actual 64 MiB test filesystem reserve and removed its
temporary fixture directory. Source backup/readback and exact owner closure
receipts are in the private runtime root's
`audit-preparation/identity-host-contracts-20261006-a00bee7bd3784ea4981d549c13a1535d`.
