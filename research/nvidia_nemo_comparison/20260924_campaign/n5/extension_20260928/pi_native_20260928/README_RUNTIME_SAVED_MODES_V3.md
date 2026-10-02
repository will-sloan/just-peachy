# Full-pipeline saved Streaming and Chunk52 preparation

Purpose: extend the existing versioned frontend to process an explicitly chosen prepared WAV through Sherpa ONNX ASR/PnC, Nemotron-3 diarization and either ReDimNet or NeMo TitaNet. Reuse the actual installed paced FileSource and all three previously pinned endpoint source/object/link contracts. This is prepared code, not a native runtime pass.

Inputs: the exact optional-recording COMMON capsule (SHA53283ec24117bd22c028151786c694ba76de502c62b65a68886f2c35a3bb7373), plus the original three endpoint Python sources and JSON contracts. The derive API accepts bytes and maps keyed by streaming/chunk52/delayed. It verifies all source and contract hashes.

Outputs: updated capsule bytes and a compact changed-member/hash review. No Pi writes, model import or capture occurs in this API. The existing64 code members,2MiB total,128KiB member,1MiB packed capsule and full independent recording/backup allocations remain. Existing endpoint members contain the complete original contracts; no old contract is overwritten.

The native source requires a real mono16k PCM16 WAV under ~/JustPeachy, one explicit Start, an unchanged file identity/hash before and after processing, and normal Stop/join. Streaming is bounded to30s of input; Chunk52 to120s. These conservative input limits keep the existing300s child/600s operation budget. File processing does not open the microphone or create a source subprocess. A separate actual source-start flag keeps model/EOF/archive closure checks active without falsely claiming microphone capture.

The UI requests the prepared path on Start. Choose recording Off or Processed before Start. Saved-input provenance is retained in the existing SOURCE_START/SOURCE_STOP receipts and source event. The original file is read only. File Stop may intentionally process a prefix; the exact accepted sample count and full-input flag are recorded.

Integration still required: manager profile validation, mode-specific admission binding, saved profile descriptors/availability, focused native routes, final shortcut selection and final startup/offline proof. Do not invoke an old installer with this capsule or treat this prepared source as a deployable release.

PowerShell syntax check:

~~~powershell
$python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $python -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('field_runtime_saved_modes_v3.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

CMD or Anaconda Prompt, from this README directory:

~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; p=Path('field_runtime_saved_modes_v3.py'); compile(p.read_bytes(),str(p),'exec')"
~~~

Programmatic API (call only inside a registered CPU14 coordinator with a current bounded host scope and verified source backups):

~~~python
from field_runtime_saved_modes_v3 import derive
updated_bytes, review = derive(optional_recording_capsule_bytes,
    endpoint_sources={"streaming": source1, "chunk52": source2, "delayed": source3},
    endpoint_contracts={"streaming": contract1, "chunk52": contract2, "delayed": contract3})
~~~

The CLI syntax check creates no runtime artifact. Exact source backup and an independent restored copy must precede use. Native success, caption content, embedding behavior, optional recording and complete PC offload require actual receipts.


V3 also binds the parent capture flag to the exact selected input route and returns the path keyboard to the main controls after Start. V1 was compiled/prepared only, never dispatched. All old bytes remain.

V3 uses the existing allocated BRIDGE_STOP.json slot for the actual saved file/thread Stop receipt. The old invented SOURCE_STOP.json was rejected by the actual source producer and is never added to the allocation. BRIDGE_CLOSE.json now records file EOF/hash/complete-input before Stop; this is separate from joined-thread closure. The workflow waits for that actual EOF instead of timing from pre-model Start. Broker labels now derive from actual policy mode/encoder/input, including baseline choices. All unchanged caps and model/source guards remain. Candidate10 partial saved run/failure remains immutable.
