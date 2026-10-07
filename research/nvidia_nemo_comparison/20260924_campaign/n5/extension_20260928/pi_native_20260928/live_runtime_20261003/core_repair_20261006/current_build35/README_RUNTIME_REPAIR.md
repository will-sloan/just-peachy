# Classic interface and current microphone startup repair

This is a new versioned derivative of build16. It preserves build16, v27/v28,
recordings and gallery bytes. The normal frontend is one backend chooser, then
the original `app.ui.PrototypeUI` portrait caption layout with Mode, People and
Settings navigation. No models load and capture stays off until Start. The old
laboratory interface is retained as source, not the normal entry.

`launcher.py` changes only the frontend call and one fault-bound readiness hook
before a new live worker. Model/source parameters, session300s policy, current
ownership, capacity-driven storage and post-Stop retention remain in place.
`installed_engine.py` additionally records the existing ASR event's `final`
boolean in caption provenance, so the retained frontend can distinguish final
text from provisional speaker attribution. It does not infer new finality,
change a label threshold or alter ASR/model output.

Input: the fresh immutable package's BINDING/manifest and the existing owned
`data/runtime-v29` store. Output: the portrait GUI, unchanged source/model
recordings/receipts, and any separately closed one-fault microphone recovery
receipt. Original source failures remain preserved. See the paired classic
frontend, package repair, and XVF readiness READMEs for API and bounds.

On the Pi, the owned Desktop command is the normal entry. For an authorized
operator, copy the exact command from the current Desktop file rather than
launching a worker outside its systemd scope. It uses the pinned existing
Python with `native_scope.py --binding BINDING.json --manifest-sha256 ACTUAL_SHA
--data-root /home/peachyprototype/JustPeachy/data/runtime-v29`.

PowerShell, Command Prompt and Anaconda host preparation commands are in
`README_PACKAGE_REPAIR.md`. Add explicit replacement inputs for `launcher.py`,
`classic_frontend.py`, `installed_engine.py`, the paired readiness modules and
their READMEs. Preparation is host-only; reviewed guarded staging and activation
are separate. No downloads, enrollment or playback are part of this repair.
