# External Stub Runner

This runner is a replaceable integration point for another ASR system.
Its persisted manifest records project-relative audio paths and ids.
For augmented runs, predict_one() receives record['inference_audio_path'],
which points at a temporary augmented WAV valid during that call.
The current runner calls the modular inference pipeline and writes
diagnostics.jsonl beside utterances.jsonl for debugging. The evaluator
contract remains predictions/utterances.jsonl.
