# License and access scope

The local offline bundle reuses already present authorized baseline assets for
this user's offline installation. It is not permission to redistribute weights
publicly. Baseline hashes are in the immutable application's config/assets.json;
wheel licenses remain inside their publisher wheels and the existing application
release_tools/licenses directory. Each wheel's publisher URL and SHA-256 is in
ARM64_WHEEL_PUBLISHER.json. Audit each separate model's terms before any public
binary/weight release; code license and model license are different.

| Component | Pinned terms / recency | Access and N5 scope |
|---|---|---|
| NeMo-Speech.cpp 97a15afa… | Apache-2.0; ggml c03b4e2b… MIT; SentencePiece 17d7580d… Apache-2.0 with bundled notices | Official pinned sources; one-thread change recorded; 12 notices in native package |
| D1 Nemotron-3-Diarization | OpenMDW 1.1; September 2026 | Already downloaded; no new model access gate |
| A1 parakeet_realtime_eou_120m-v1 | NVIDIA Open Model License; 2025 history | Already downloaded; portability still unproved |
| A2 nemotron-speech-streaming-en-0.6b | NVIDIA Open Model License; March 2026 | Already downloaded; Q8 bytes have their own pin/parity obligations |
| A3 nemotron-3.5-asr-streaming-0.6b | OpenMDW 1.1; June 2026 | Already downloaded; English-only campaign supports no multilingual claim |
| E1 TitaNet-Large | CC BY 4.0; older 2022/2023 exception | Attribution retained; exact export/frontend and reference pins separate |
| Arm GNU 12.3.rel1 build tools | GPL toolchain components and runtime exceptions, bundled notices | Build-only; compiler/sysroot are not shipped in native runtime |
| CMake 3.30.5 / Ninja 1.11.1.1 | BSD-style / Apache-2.0, publisher wheel notices | Build-only verified PyPI wheels |
| QEMU Ubuntu 10.2.1 | GPL-2.0 family; Ubuntu package copyright retained privately | Unpacked isolated emulator; not installed or shipped to CM5 |

Authoritative candidate revision/hash/term snapshots are in ../assets,
../n2/embeddings and ../n3/MODEL_REGISTRY.json. No paid endpoint, NIM, cloud-first
model fetch, noncommercial-only component or account/credential workaround is
introduced. New candidate weights and the private offline baseline bundle stay
outside GitHub. Hardware-vendor source/license and firmware ABI matching remain
a separate pending XMOS build audit; ARM32 helpers are not packaged as ARM64.
