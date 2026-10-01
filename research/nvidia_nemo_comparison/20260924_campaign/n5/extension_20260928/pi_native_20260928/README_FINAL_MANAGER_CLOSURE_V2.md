# Final manager closure collector
Purpose: read-only F04/F25 closure/accounting of the current postboot baseline and all registered research owners, including the three exact completed manager launch records in field-local-release-v2. This does not issue a new resource or recording admission. It never repairs historical missing identities.

Inputs: fresh host census; complete packed prior owner list produced after reading all owners/lifetimes; immutable final-manager-joint-v2/admission/RELEASE.json with SHA f39a8b7dbedbebed1492687d42d5648ac033dbba0d02a4a46537175e1fa40d9c; a new receipt version and absent owner receipt path.
Outputs: private NATIVE_CLOSURE_V<number>.json and NATIVE_RESOURCES_V<number>.json; bounded raw native stdout/stderr/phase/early owner. Existing output is rejected. No Pi payload writes, audio acquisition, GUI or model work.

PowerShell (replace all uppercase placeholders with reviewed fresh actual paths; never rerun a consumed version):
    & 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B collect_native_closure_v19.py --version NEW_NUMBER --prior-pi 'PRIOR_PATH' --census 'CENSUS_PATH' --resource-policy 'RELEASE_PATH' --policy-sha256 f39a8b7dbedbebed1492687d42d5648ac033dbba0d02a4a46537175e1fa40d9c --owner-receipt 'NEW_OWNER_PATH'

Command Prompt and Anaconda Prompt: change to this README directory with cd /d, then use the same arguments after:
    "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B collect_native_closure_v19.py

The collector sets host CPU14 and records its owner before project reads. Native helper CPU3/128MiB AS/1MiB stack/FSIZE0/45s alarm and host60s bounded transport remain. Strict SSH settings are inherited unchanged. Current baseline is boot892ed9fa-e39c-48af-8653-eae5e123daad, launcher1008/476 and app1124/514. Changed boot/baseline needs a fresh reviewed derivative. Typed OWNERSHIP_CLOSURE is never a PID identity. Unknown nested records fail; pending bytes are preserved. This version accepts only the exact recorded policy/paths/hashes for three new completed launches, plus the retained historical v1 exceptions. Later manager roots require a reviewed decoder update.

The closed joint policy supplies read-only accounting ceilings only; it cannot authorize a new dispatch. Original WINDOW_V5 is unchanged. The prior list must exclude exactly the two current baseline owners, since those are separately required alive. Old-boot absence does not retroactively prove historical logical closure.

Selected v19 fixes a statically detected nonexistent unpack symbol to the actual decode API and moves project imports after the early host owner receipt. V18 is preserved, backed and unexecuted; this is not a native retry. Native source compiled independently before use.
