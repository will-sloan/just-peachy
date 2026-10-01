# Manager PC copy after canonical frame correction

Purpose: F04/F25, copy the unchanged closed manager tree after the first receiver stopped before its first file on JSON key ordering. Original native manager reserve/record/finish/localbackup/reopen and the broker PC copy already ran; this path performs no recording or manager mutation. The original failed overall result and partial PC destination remain immutable.

Selected field_local_manager_ssh_mirror_v2.py changes only canonical JSON serialization used for exact header/terminal comparisons. Exporter2 emits sorted keys; V1 compared against insertion-ordered expected keys. Exact field names, values/types, file order, hash/readback, terminal, closure, limits and no-overwrite checks remain. field_local_manager_receiver_v2.py selects this host receiver. Native exporter/bootstrap/auxiliary bytes are unchanged; they are not repeated native recording tests.

Inputs: actual final-manager-joint-v2 evidence, fresh complete host owner/lifetime review and census, packed actual prior owners, new output. Four actual completed manager phase owners are bound. The actual failed exporter and all source-operation utilities are discovered from that evidence and must be dead before export. Each lifecycle comes from a new native read-only observation with the unchanged strict clock/freshness check and bounded clock barrier.

Fresh measured copy-only policy reserves155669036-byte full manager tree PLUS2097152-byte host metadata, with1MiB measured accounting margin. No Pi payload writes, no reused old admission, no credit for the earlier partial or small output. Host stores partition1703938 bytes; setup files are bounded262144 bytes/32files/64KiB each and one64KiB directory, totaling2031618<2097152. Copies retain all files/empty directories, exact SHA256/readback and natural exporter/helper closure before BACKUP.

Outputs: new RESOURCE_POLICY with independent backup/restore readback, raw observations, manager-copy-mirror, complete BACKUP receipt and separate RESULT. This does not retroactively pass the failed earlier dispatcher, production activation, raw support or offline field readiness.

PowerShell (native source directory):
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\copy_field_local_manager_v1.py --help
```
CMD / Anaconda Prompt:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B copy_field_local_manager_v1.py --help
```
Actual arguments:
```text
python -B copy_field_local_manager_v1.py --source-evidence ACTUAL_CLOSED_JOINT_EVIDENCE --output NEW_PRIVATE_COPY_DESTINATION --census FRESH_HOST_CENSUS --precheck FRESH_ALL_OWNER_REVIEW --prior PACKED_ACTUAL_OWNERS
```
Use the exact Python executable and existing native directory from README_FINAL_MANAGER_DISPATCH_V1.md. Existing destinations reject; never delete/reuse a failed one. All source files must first match their exact backups and independent restore copies. This is a read-only export within600seconds and before16:14:58Z.

