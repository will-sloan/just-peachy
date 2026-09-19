# N6h closure JSON-wire proposal

Purpose: fix the C12v3 wrapper's consumer-closure comparison across Python and JSON serialization. The actual settings receipt contains `selected_profile_ids=()`, while its saved closure contains `[]`. N6g compares these directly and rejects the otherwise matching completed receipt. N6h compares the complete queue dictionaries as deterministic JSON with `allow_nan=False`. It does not round or cast numeric values, discard keys, change drain requirements, or change processing settings.

Inputs and outputs are unchanged from N6g: an exact root-approved manifest and its SHA, one literal job ID, supervisor-owned identity/heartbeat/STOP/completion environment, admitted full-source capture and the same models/profile/gallery/source graph. Outputs remain fresh native RESULT/events/journals, full multistream audit and outer completion only after every original predicate passes. No source waveform, capture route, ASR/identity inference, clock, thread, queue capacity, timeout, resource cap or decoder setting changes.

This is a source-only proposal. N6g and both failed C12 attempts remain immutable and uncredited. No production manifest, queue, approval or native output is created here. The existing producer remains `82a95a4b...`, bb1b evidence helper remains unchanged, and all three full-frame journal proofs remain mandatory. Future manifest/helper/source guards and fresh output paths must be rebound and independently reviewed before the root task launches a first-case rerun. Existing C12/core/diagnostic sources are not edited by this proposal.

The only code change is a deterministic `closure_wire` serializer and replacement of direct dictionary equality at the existing consumer-closure gate. JSON rejects nonfinite numbers and unsupported values; numeric text and all keys must match exactly. Tuple/list representation is the intended equivalence.

Model-free PowerShell check command, using a fresh G output:

```powershell
$s = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$s\s6d_N6h_closure_checks_v1.py" --source-root $s --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\N6h_closure_v1\checks_FRESH'
```

Anaconda Prompt or CMD:

```bat
set "S=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -B "%S%\s6d_N6h_closure_checks_v1.py" --source-root "%S%" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\N6h_closure_v1\checks_FRESH"
```

For a future approved supervisor job, the wrapper interface remains:

```text
<native-python> <exact-frozen-N6h-path> --manifest <new-approved-manifest> --manifest-sha256 <exact-new-SHA256> --job-id <literal-job-ID>
```

That template is not a standalone launch command: the existing supervisor must set its owned environment and pass source, allocation, output freshness, resource, deadline and approval checks. No old manifest is launchable with the new helper hash. Root alone constructs/adopts the concrete queue and launches.
