# Complete waveform candidate: preserved state mismatch

A bounded waveform/frontend/ordered-state/high-resolution/EOF candidate is implemented, but it has **not passed the complete runtime gate**. No native waveform test or new GUI mode is accepted. Earlier native feature, frontend and constructed-state passes keep their original limited scope.

The first host reference attempt (d1-onnx-waveform-v1) hit its sampled64MiB output guard during NeMo checkpoint extraction, before model results. Retained output197,611,454bytes exceeded that admission. Exact job owners closed after forced exit125; this is not clean application finalization or hard output-quota enforcement. The partial weights file197,591,040bytes is shorter than the archive member198,666,820bytes, so reuse was rejected. The incomplete files and failure receipts remain private and untouched.

Fresh waveformV2 admitted256MiB, completed original-model tail/full references and an exact original full repeat, and used the checkpoint's actual learned silence embedding. It naturally exited1 on the first candidate tail: probability max error8.568e-8 passes1e-5, but final cached embeddings differ1.6391e-4. The full waveform, irregular/repeat/negative-call branches were not reached. Its7,706,972bytes of output fit the fresh bound. A prepared reader's successful-pass branch does not mean that branch was executed.

A separate graph/state diagnostic then fed **original PyTorch frontend values** into the unchanged graph and state path. Tail and original full-file cases each ran twice. Independent stored-array review found exact candidate repeats, continuous feature intervals and natural exit0, but final-state differences still fail the same1e-5 gate:

| Case | Valid probability rows | Probability maximum error | Final embedding maximum error |
|---|---:|---:|---:|
|1281-sample tail|8|8.5682e-8|1.6391e-4|
|715127-sample full source|4469|9.0003e-6|2.3460e-4|

This shows the new frontend alone cannot explain the failure. It does not yet identify an individual operator, establish a repaired graph, or qualify the public waveform path. The diagnostic exit0 means observations were collected; both cases explicitly retain failed state-gate flags. No tolerance was relaxed. Timings from this host diagnostic are not Pi performance or speedup evidence.

Original NeMo forward crops padded features to the valid4469 frames before streaming and trims the final coarse rounding. The wrapper follows2112/2112/245 valid output rows, with eight-feature context where available. The last87 audio samples are a sub-hop remainder, not silently removed input. The old Q8 runtime's4470 probabilities are a separate mapping; those counts are not interchangeable. Hardware/acoustic and phonetic alignment remain outside this test.

WINDOW_V5 admits5GiB combined existing-plus-new output after preserved extraction failures, leaving the52GiB total payload,2.5GiB reservations and physical drive floors unchanged. Old4GiB/64MiB admissions remain immutable. The Pi is still a fixed32GB device with5GiB required free; no target model copy was added this turn. ClosureV57 records4,127,737,930combined bytes,147Pi and44isolated host identities closed, original app/config/install unchanged, captureclosed and both leasesfree. Target free17,995,952,128bytes,availableRAM1,593,507,840bytes,52.9C,throttle0x0; globalswap1095in/33286out is contextual only.

Next runtime work: isolate the pre-encoded graph outputs on these retained natural-feature chunks, before exporting another graph or dispatching a native waveform trial. Preserve the1e-5 gate and original references. In parallel task order, prioritize compact bounded live journaling/reopenable PCM and native A2 optimized/sequential mode so field readiness is not indefinitely blocked on this alternate-runtime discrepancy. No agents or simultaneous unadmitted jobs are needed.

Execution and independent readers: README_D1_WAVEFORM_V1/V2.md, README_D1_WAVEFORM_OUTPUT_FAILURE_V1.md, README_D1_FEATURE_ISOLATION_V1.md, README_REVIEW_D1_WAVEFORM_V2.md and README_REVIEW_D1_FEATURE_ISOLATION_V1.md. Private references and review hashes are bound in CHECK_SUMMARY_V36.json. No capture, playback, WER/DER, speaker-quality or release acceptance follows.
