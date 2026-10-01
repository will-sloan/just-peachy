# Finite runtime preservation and export
Purpose: preserve the whole manager tree, including every independently reserved local recording backup, without enlarging the original per-producer or 256 KiB frame limits. Used by finish items F04, F09, F16 and F25.

Files: field_runtime_preservation_v2.py selects the ten-profile policy; field_runtime_preservation_io_v1.py handles partition census, binary frames, guarded 16 KiB streaming and full independent readback. field_runtime_export_v1.py is a read-only native entry. field_runtime_auxiliary_v1.py pins its complete source graph. field_runtime_transport_v1.py preserves early-owner-before-payload, matching HELLO, bounded I/O/watchdog and natural exit with an independent closure callback.

Inputs: exact Policy3 and manager manifest, complete source tree, actual independently registered native owners, fresh lifecycle/configuration pins and bounded read-only admission. Native commands must use the original bootstrap with this pinned loader and complete modules, a fresh unique systemd unit and the current strict SSH identity. No bare native command or old dispatcher authorizes activation.

Outputs: independently bounded metadata/recording partition manifests, exact per-file hashes and preserved complete PC tree. Pending bytes remain ordinary bytes. Completed malformed/unknown owners fail. Typed ownership closures stay separate from process identities. A receiver succeeds only after natural source exit and exact independent closure, followed by complete PC readback. It does not publish recording success or fabricate a journal BACKUP.

## Host check
Requires the existing edge-speech Python environment and psutil. This changed fixture uses synthetic policy/owners/closure with actual small Windows file copies and the actual transitive source graph. It does not run the native exporter or any model. Choose a never-used output path inside a fresh bounded host scope; source backup and independent restore are required before use. Failed output remains preserved.

PowerShell:
~~~powershell
$python = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $python -B ./check_field_runtime_preservation_v1.py --output 'G:/approved-scope/new-check'
~~~
Command Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_field_runtime_preservation_v1.py --output "G:\approved-scope\new-check"
~~~
Anaconda Prompt: activate the existing environment containing psutil, change to this source directory, then:
~~~bat
python -B check_field_runtime_preservation_v1.py --output "G:\approved-scope\new-check"
~~~
API: census(root, policy, manifest, guard), send_census(stream, value, guard), read_census(stream, policy, manifest, guard), export_files(stream, root, value, policy, guard), receive_files(stream, destination, expected, policy, manifest, guard, verify_closed). Transport run additionally requires the policy and all actual persistence/closure/stop/guard callbacks. Native exporter run(request, modules) is called only by the backed hash-bound bootstrap.

Source preparation is not deployment or offline qualification. Native wrapper integration, actual runtime closure, installation and acceptance remain open until their receipts exist.

