# Native UI documentation clarification

This addendum corrects inherited prose in the immutable, admission-bound `README_B05_NATIVE_GUI_V1.md`; it does not change the harness, source, admission or results.

The paragraph headed “Native B05 process-local startup stack reservation” contains the inherited phrase “no ... GUI”. For this version, **actual Tk widgets and their event loop were exercised while the root remained withdrawn**. No visible window, physical layout/touch validation, microphone or playback was involved. The first section of that README and `NATIVE_UI_FINDINGS_V1.md` describe the executed scope correctly.

The immediate input parent is **b05-native-stack-v1**, as the dispatcher's prior-admission check and the README's final paragraph specify. The inherited earlier mention of b05-anonymous-full-v1 describes ancestry, not this dispatcher's direct input. The fresh derivative is shared-app-native-gui-v1.

Purpose, inputs, outputs and the PowerShell/CMD/Anaconda commands remain in `README_B05_NATIVE_GUI_V1.md`; independent review commands remain in `README_B05_NATIVE_GUI_REVIEW_V1.md`. These commands document a completed immutable attempt, not a repeatable launch over existing evidence. A future run requires fresh identifiers, resource admission and evidence paths. This addendum has no executable command or new output path.
