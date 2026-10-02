# Deferred broker Close

Purpose: fix F08/F09's actual broker Close race after a successful recording Return. Tk can invoke Close inside the returned-window display update; destroying that window immediately leaves the surrounding callback using invalid widgets. The exact capsule derivation now records the close request and destroys the window only after the event update returns. The broker still refuses Close while its recording process is alive, and still closes its ledger before destroying the UI.

Input: exact source-failure-corrected common capsule SHA4f3bef04b7f3a289a0d431ac3944dc2ed5c493c1df1484e1e5ff3d4b44b69670. Output: new capsule bytes and a derivation review; no files or Pi action from the API. Only Chooser.__init__, tick and close differ; all other source/methods, storage/resource limits, failure handling and model paths stay pinned.

PowerShell, Command Prompt or Anaconda Prompt, from this directory:
~~~text
python -B check_runtime_broker_close_v1.py --bundle PATH_TO_COMMON_BUNDLE --output NEW_PRIVATE_RESULT_DIRECTORY
~~~
Use the configured environment's Python (C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe), which provides psutil. The check registers its CPU14 host owner before project reads. It exercises the actual changed methods with explicitly synthetic Tk/broker objects, including a Close event during the returned-window update and rejection while the child remains alive. It creates no Tk window, native process, audio or model.

API: field_runtime_broker_close_v1.derive(raw_bytes) returns (new_bytes, review). Compile and independently back up source before native installation. A host fixture is not proof of native Close or complete recording success.
