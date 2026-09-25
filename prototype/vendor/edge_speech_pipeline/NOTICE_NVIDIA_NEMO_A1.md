# NVIDIA NeMo A1 derivative attribution

The portable A1 feature scheduling, recurrent decoding and EOU service behavior
follow the NVIDIA NeMo service helpers at revision
`cf724ac337d1ebc7d0dda1e23fb80916f52927a5`, distributed under Apache License 2.0.
See LICENSE_NVIDIA_NEMO_A1.txt. The campaign preserves the exact extracted helper
sources and attribution in its N3 README_A1_SERVICE.md and source manifest.

Changes: use exported ONNX CPU encoder/decoder graphs, NumPy/SciPy frontend
operations, explicit independent recurrent states, package-relative imports,
exact asset validation, and the common saved-audio journal/tail event protocol.
Keep this notice and the license with redistributed source. No neural weights
are included here. Parakeet Realtime EOU 120M weights, exported graphs, vocabulary
and frontend buffers remain subject to the NVIDIA Open Model License.
