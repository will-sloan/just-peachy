# Native B01 V5: retain the requested stack size

The V4 harness accidentally reset the stack setting by calling threading.stack_size() without an argument after setting it. Preserve V4's failure. Native model-free thread_stack_inspect_v1.py measured the actual glibc worker stack with pthread_getattr_np/pthread_attr_getstack: default8MiB; setter-only1MiB; setter followed by no-argument read8MiB. This behavior was measured on this Pi/Python, not inferred from documentation. V5 calls the setter once and records the requested value without a resetting getter. Other B01 source, model, allocator, memory and drain settings are unchanged.

Inputs/outputs and constraints are those of README_B01_STACK_V1.md, with fresh b01-short-v5 and b01_native_short_v5.py. Reuse shared-app-v2 and retain failed-start cleanup. Actual passage and closure must be independently reviewed; setting1MiB does not itself establish a safe production stack. No new ASR/WER accuracy scoring or live audio. Full-source/endurance, UI and populated personal gallery remain separate.

## PowerShell / Anaconda PowerShell

From this directory:

```powershell
& C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B dispatch_b01_stack_v3.py
```

Dispatcher V1's preparation failed on a wrong RESULT filename before staging/dispatch. V2 corrects that filename and completed the failed V4 attempt. V3 prepares V5. These fresh dispatchers reuse the comprehensive host census only within15minutes, with fresh complete output-window inventory, unchanged completed supervisor, exact closed PID/create identities, storage/headroom and original policy checks; they refuse stale census. They always recheck target boot, units, every retained owner and bound inputs. Inputs and rejected preparations remain preserved. Later runs need a fresh admission/derivative; never rerun these evidence paths.

The model-free stack inspector reads no models/audio and creates only sequential temporary test threads under128MiB address space, CPUs2/3. To reproduce on a separately admitted Pi command: `taskset -c 2,3 /usr/bin/python3 -B thread_stack_inspect_v1.py`; stdout is a private JSON measurement. Stage through the strict SSH identity in README.md. It is a diagnostic, not an application launcher.

## CMD / Anaconda Prompt / Linux

For CMD/Anaconda Prompt use `cd /d` to this directory and the same Python command without `&`. Native execution uses the exact systemd command saved by the dispatcher: MALLOC_ARENA_MAX2, CPUs2/3,CPU200%,Tasks64,180seconds,one native model thread,hard768MiB address space,>=850MiB available RAM,>=5GiB disk,16MiB reserved output. No activation/install/download/global OS change. Keep current rc5 app and all evidence. The dispatcher/harness is a test path, not yet a user-ready new Pi mode.
