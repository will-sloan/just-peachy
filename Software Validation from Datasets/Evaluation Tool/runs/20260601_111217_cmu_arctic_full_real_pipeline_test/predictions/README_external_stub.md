# External Stub Runner

This runner is a replaceable integration point for another ASR system.
Its persisted manifest records project-relative audio paths and ids.
For augmented runs, predict_one() receives record['inference_audio_path'],
which points at a temporary augmented WAV valid during that call.
The current bridge calls the configurable end-to-end inference pipeline
and writes pipeline_diagnostics.jsonl beside the evaluator-compatible
utterances.jsonl contract.
