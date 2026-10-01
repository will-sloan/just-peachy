# Manager PC copy V2

Selected CLI is copy_field_local_manager_v2.py. [V1 purpose, inputs, outputs and full PowerShell/CMD/Anaconda instructions](README_FINAL_MANAGER_COPY_V1.md) apply with that filename substitution. Source V1 had two indentation errors introduced in the setup-byte guard edit; compilation rejected it before module execution, owner registration or SSH. No native copy attempt or output root occurred. Raw source and incomplete backup5 remain preserved. V2 changes only those indentation spaces and this README reference. Native source, reservations, first-fault behavior, fresh destination and strict comparisons are unchanged.

PowerShell: `& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\copy_field_local_manager_v2.py --help`.

CMD / Anaconda Prompt: `C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B copy_field_local_manager_v2.py --help`.

Use the same five required arguments documented in V1. Exact source backup plus independent restore/readback must complete successfully before actual invocation; do not continue to dispatch after a failed backup command.

