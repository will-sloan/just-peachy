# Bounded terminal configuration

Purpose: F09/F15 preserve the complete last_application metadata when speech makes pretty JSON exceed its32KiB slot. Compact JSON retains every field; when needed, a zlib/base64 envelope retains the complete canonical document with its decoded length/SHA256. Decoded maximum256KiB; original32KiB primary plus32KiB pending physical reservation unchanged. No truncation, field removal or audio change. Oversized incompressible metadata explicitly fails. Configuration failure now blocks the overall worker success receipt.

Inputs: exact TitaNet-memory capsule and this source pinned by the installer. Outputs: derived64-module capsule/review; actual last_application.json plus its independently verified decoded metadata. Existing publication function code retains short-write, fsync, pending and replacement-failure handling; only its encoder binding differs for this one path. All other configuration writers are unchanged.

API: derive(bundle_bytes, pinned_helper_source); terminal_encode(document,32768); decode_terminal(file_bytes). Use the new versioned installer after exact backup and independent restoration. This source does not launch a model or change the Pi by itself.

To decode a private stopped-run snapshot on the PC, replace INPUT and OUTPUT with private paths. OUTPUT must not exist. PowerShell, from the native source directory:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); import json,pathlib; from field_runtime_terminal_config_v2 import decode_terminal; v=decode_terminal(pathlib.Path('INPUT').read_bytes()); pathlib.Path('OUTPUT').open('x',encoding='utf-8').write(json.dumps(v,ensure_ascii=False,indent=2))"
~~~
CMD / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); import json,pathlib; from field_runtime_terminal_config_v2 import decode_terminal; v=decode_terminal(pathlib.Path('INPUT').read_bytes()); pathlib.Path('OUTPUT').open('x',encoding='utf-8').write(json.dumps(v,ensure_ascii=False,indent=2))"
~~~
Keep decoded metadata private. This addresses terminal metadata integrity; it does not qualify accuracy, physical touch or offline operation.

Version2 verifies exact canonical JSON bytes, preserving ordinary JSON tuple-to-list conversion. Version1 incorrectly compared decoded JSON directly with the original Python object and rejected a complete speech run at terminal publication. The failed candidate remains preserved. No payload, file cap or failure guard changed.
