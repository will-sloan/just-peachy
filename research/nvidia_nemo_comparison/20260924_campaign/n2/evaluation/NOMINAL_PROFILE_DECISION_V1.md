# Frozen nominal D1 profile decision — v1

Select **low_latency (1.04 s input buffer; 0.32 s right context)** for D1/E0 and D1/E1 before the main four-way factorial. This retains the original protocol preference. The complete three-profile native panel is a sensitivity experiment; no profile was chosen by cpWER and no naming threshold changed.

| Profile | Buffer / right context | Approximate DER, O0 / O1 | Macro scene JER, O0 / O1 | Native processing wall versus low |
| --- | --- | ---: | ---: | ---: |
| Low |1.04 /0.32 s |23.798% /32.318% |21.243% /21.613% |1.00x |
| Very low |0.64 /0.16 s |23.834% /31.585% |20.911% /21.936% |1.31x |
| Ultra low |0.32 /0.08 s |24.404% /31.712% |21.401% /22.708% |2.01x |

All three profiles completed the same 96 cells. Each tap has 42 complete-reference cells, six incomplete ambient exclusions, 330.28 reference speaker-seconds and 1877.2084 evaluated wall-seconds; macro JER uses 41 nonempty scenes. All profiles resolve 161/161 known source turns and 28/28 short turns per tap. Consistent returns are 57/54, 57/55 and 55/55 out of 59 on O0/O1; none is unresolved.

The 0.32 s buffer offers earlier possible native chunks at roughly twice the measured processing wall time. Its activity differences are mixed and do not support replacing the predeclared 1.04 s nominal profile. These accelerated CUDA native-only timings omit ASR, embeddings, identity and GUI work and exclude model loading. Buffer size is not measured caption latency. Application screens are still required.

The mandatory 250 ms sensitivity retains only 71.08/71.10 speaker-seconds, about 21.52% of the primary denominator; it cannot replace zero-collar results. O1 noise-control false activity remains 19.16/16.86/16.42 seconds for low/very-low/ultra; O0 is zero. N1's inserted ASR word on each tap is a separate retained failure. These are estimated 20 ms activity references, not phonetic DER/JER or a published benchmark comparison. The JSON retains both collar variants and their denominators.

Selection applies to the desktop research factorial. CM5/Pi portability, total 2 GB suitability and isolated GPU-memory qualification remain unresolved. The preserved coordinator I/O incident did not remove any numerical cell; all 288 completed after unchanged-cache recovery.

This version is immutable. A later change requires a new version with an explicit reason and supersedes binding. Original protocol, amendment, complete native summary and model/library hashes are bound in the JSON. No source identities, transcripts, audio or vectors appear here.

JSON file SHA-256: `09b86b287ae76f64f13bddd26ae30a7aa26d3f6ab12f94c2093e176ebdf30eac`.
