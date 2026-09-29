# Raspberry Pi storage constraint

The user confirmed a **32 GB device** on September29. Every deployed component must fit this same device: OS, original app, shared models, new runtime, private data, recordings/logs and recoverable rollback. No larger storage is assumed. Host campaign allowances are separate and do not enlarge the Pi.

Read-only verification: main device31,268,536,320bytes; root filesystem30,166,274,048bytes. Root uses10,617,393,152bytes, with17,995,952,128bytes available (~18.00GB /16.76GiB). Native research staging occupies2,276,100,907logical bytes (~2.28GB), already included in filesystem use. Filesystem allocation, metadata and reserved blocks mean these measures are not interchangeable. See PI_STORAGE_CAPACITY_V1.json.

Deployment rule: measure actual unique/shared asset bytes before packaging, preserve at least5GiB available on the Pi, and bound recording/log retention against the remaining measured space. Prefer shared immutable model assets and one selected working runtime per mode; development graphs remain research evidence, not automatic field-package contents. Backups and preserved experimental evidence can reside on the host. No automatic deletion of existing evidence or personal data is authorized merely by this storage note.

The current52GiB total campaign payload and4GiB new-output accounting span host research plus counted target bytes; neither is a Pi deployment allowance. Existing CPU/RAM/time limits remain measured operating safeguards and can be revised with evidence under the user's prior authority. The32GB deployment ceiling is fixed. Recheck free space before every dispatch and provide a concrete installed/rollback/recording budget with the field release.
