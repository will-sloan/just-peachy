# Finite local release lifecycle V2: execution index

Selected plan/check remain field_local_release_plan_v1.py and check_field_local_release_v1.py. Selected native journal is field_local_release_files_v2.py. V1 is an immutable unexecuted draft; V2 adds exact RELEASE/MANIFEST/code hash and membership checks on every inspection and explicit128MiB hardAS/1MiB stack/32MiB FSIZE checks before native construction. Native Journal remains UNEXECUTED and is not wired to a user launcher.

Purpose, inputs, outputs, proposed finite allocation and PowerShell/CMD/Anaconda commands for the unchanged host check are in [README_FIELD_LOCAL_RELEASE_V1.md](README_FIELD_LOCAL_RELEASE_V1.md). The host check passed three new positive groups and seventeen rejects once. Its policy hashes/census/recovery facts are fixtures; it did not construct Journal, create a native release, or verify physical recovery.

Native API (only inside a fresh registered bounded caller):
    from field_local_release_files_v2 import Journal
    journal = Journal(EXACT_EXISTING_ROOT, EXACT_RELEASE_SHA256, FRESH_QUALIFICATION_OPERATION, create=True)
    # Actual manager must validate operation-specific ownership/closure/backup receipts.
    journal.close()

PowerShell / Command Prompt / Anaconda Prompt use a separately reviewed strict-SSH caller for native execution:
    ssh -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local
A bare SSH session is not an admission. There is no standalone activation CLI. Required code/config/manifest backups and independent restore verification precede any native use.

Current limitations are explicit: production purpose is rejected, only bounded pre-deadline qualification operations are implemented, backup payload directory must stay empty until the real mirror consumer is wired, and supplied operation facts are not independently verified by this metadata primitive. Do not publish fake closure/backup/activation receipts. Pending and failed slots remain preserved. The proposed24-hour manual idle lifetime is NOT an applied allowance or automatic extension. Production manager, native filesystem/lock/fault tests, exact local backup, activation/rollback and offline proof remain open.
