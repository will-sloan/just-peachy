# C12 source-origin field proposal

Purpose: add the missing `pipeline_sample_rate` to the captured-source origin event. `CaptureAdmission` already checks every requested stream's actual lossless mono header at16000Hz. The proposal retains that validated common rate and publishes it. Source playback, gain, frames, pacing, model state, selectors, journals and clocks are unchanged. The bb1b validator remains exact. This is an additive proposal; no existing source epoch or failed event is edited.

Inputs: exact original C12 manifest139dc8f8,48 frozen application source files, N6f helper6f716290, original protocol874d, native loop29ccc and guardbb1b. Preparation reads these small sources/metadata only. It does not read audio, PCM journals, model assets or live process state.

Outputs: fresh source copy with one changed file; N6g copied wrapper with only the new beam-source pin/docstring; tight diffs; twelve-job MANIFEST_PROPOSAL with unchanged scientific fields and fresh G outputs; PROPOSAL with literal child arguments and remaining gates. No G payload directories, queues or approvals are created. The old first attempt remains failed and uncredited; modified old event files are never published.

PowerShell metadata preparation:
```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_C12_source_origin_prepare_v1.py" --output "$sim\reports\S6D\20260913T195357Z\application\beam_C_source_origin_proposal_v2"
```

Anaconda Prompt or CMD:
```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_C12_source_origin_prepare_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\application\beam_C_source_origin_proposal_v2"
```

Use a fresh output suffix. The wrapper's prospective CLI is `s6d_beam_native_run_n6g.py --manifest MANIFEST_PROPOSAL.json --manifest-sha256 EXACT_SHA --job-id EXACT_ID`; it is not a standalone launch instruction. Root must separately review, construct/admit a fresh one-supervisor V4/40GiB queue and supply all owned protocol environment fields. Core96, diagnostics, old C12 pins,80GiB policies and model recipes are outside this change.

The first unlaunched proposal_v1 preparation stopped at the AST check because Windows' default text encoding changed a docstring. It remains an incomplete draft; explicit UTF-8 is used by the corrected preparation. Only proposal_v2 is the candidate for source review.

Focused model-free fixtures use fake header/stream objects with the real AST-loaded admission/producer methods and unchanged bb1b guard. Their README and receipt are frozen with the source. They include strict wrong header, missing/wrong event-rate negatives and source/function equivalence. No actual source audio/model test is authorized by this preparation.
