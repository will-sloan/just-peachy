# Reconstruct retained runtime preservation

Purpose: finish F25 PC reconstruction from the already completed native failure export. The first receiver failed on an order-dependent RESERVED lookup after all native bytes/closure had been retained. This host-only helper selects the explicitly named RESERVED record and reconstructs the exact two roots into a new destination. It does not contact the Pi, repeat Stop/export, overwrite old outputs or claim natural manager exit. The retained service status9 remains a failed forced closure.

Inputs: failed receiver directory with RESULT/NATIVE_CLOSURE/PHASE, original candidate installation copies, fresh scope and new private output. Output: complete tree preserving empty directories; every member SHA/size independently reread, BACKUP receipt. Original full runtime host allocation/free floors are retained. The neural model is not recopied.

PowerShell:
~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\restore_runtime_preservation_v1.py --source FAILED_RECEIVER_DIRECTORY --candidate-install ORIGINAL_INSTALL --scope FRESH_SCOPE --output NEW_PRIVATE_OUTPUT
~~~
Command Prompt / Anaconda Prompt:
~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B restore_runtime_preservation_v1.py --source FAILED_RECEIVER_DIRECTORY --candidate-install ORIGINAL_INSTALL --scope FRESH_SCOPE --output NEW_PRIVATE_OUTPUT
~~~
Back up and independently restore this source before use. No test rerun or native action is needed to complete the existing captured data.
