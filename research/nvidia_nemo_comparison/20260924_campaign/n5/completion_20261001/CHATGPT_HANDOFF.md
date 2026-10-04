# ChatGPT handoff — v29 live-runtime expansion

Read START_HERE, CURRENT_RUNTIME_PROGRESS, MODE_GUIDE and BACKEND_COMBINATIONS
first. They distinguish the installed release from the new candidate. The
archive is for understanding and review; it excludes models, recordings,
transcripts, speaker vectors, galleries and credentials.

The objective is offline live ASR, speaker diarization and optional identity on
the prepared2GB CM5. Sherpa/PnC remain shared. Pyannote or explicit Nemotron
geometries provide activity; ReDimNet or TitaNet provide separate embedding
namespaces. Anonymous operation remains available. XVF3800 capture and BMI270
motion integration are retained.

The v29 design separates source from backend, makes normal duration300s, adds a
separate3600s developer replay path, bounded disk spooling and post-Stop audio
retention, and capacity-based persistent UUID sessions. It removes the four-slot
renewal requirement for the new runtime while preserving ownership, leases,
finite per-session allocation, cleanup and original data.

Read [the pipeline documentation](../extension_20260928/pi_native_20260928/live_runtime_20261003/README_PIPELINES.md)
for each architecture, mathematics, implementation hooks and evidence gaps.
[Research adaptations](../extension_20260928/pi_native_20260928/live_runtime_20261003/RESEARCH_ARCHITECTURES.md)
links primary papers and separates adaptations from exact reproductions.
[Native results](../extension_20260928/pi_native_20260928/live_runtime_20261003/NATIVE_RESULTS.md)
contains matched-input performance/failure scopes; the
[RAM guide](../extension_20260928/pi_native_20260928/live_runtime_20261003/RAM_RESOURCE_GUIDE.md)
distinguishes2GB capacity, virtual-address limits, CPU work, heat and4/8GB hypotheses.

For interpretation:

- A live microphone path does not establish sustained real-time behavior.
- Input-buffer latency excludes compute, association, queueing and stable labels.
- Component RTF does not equal whole-application throughput.
- Numerical equivalence is not ground-truth accuracy.
- Quiet functional recording does not establish speech or speaker accuracy.
- A one-hour component run does not qualify a one-hour complete application.
- Recorded motion can invalidate position priors; BMI270 alone cannot recover
  reliable absolute translation or drift-free heading.
- A complete verified backup is distinct from source presence or an unfinished
  copy. Private failure evidence remains preserved.

Useful reading questions are: Where do sample clocks originate? Which queues
are bounded? What owns each model/source? How are provisional labels revised
without replacing caption text? Which spatial cues are trusted after movement?
Which audio bytes are retained and replayed? What happens on each first fault?

After understanding those paths, plan a small consenting real-world trial with
FIELD_VALIDATION and FIELD_RUN_TEMPLATE. Compare modes on the same saved
processed timeline before attributing differences to models. Enroll separately
only when deliberately authorized; never reuse a ReDimNet gallery as TitaNet.

Earlier v23/v27/v28 and campaign documents remain provenance. FINAL_COVERAGE
retains N1–N5, the34-method catalogue and unfinished240-cell N4 denominator.
This iteration does not silently complete those historical experiments.
