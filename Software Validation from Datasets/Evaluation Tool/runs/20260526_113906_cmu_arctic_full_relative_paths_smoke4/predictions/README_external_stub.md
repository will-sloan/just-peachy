# External Stub Runner

This runner is a replaceable integration point for another ASR system.
Its persisted manifest records project-relative audio paths and ids.
For augmented runs, predict_one() receives record['inference_audio_path'],
which points at a temporary augmented WAV valid during that call.
The current stub calls a dummy modular pipeline that returns deterministic
placeholder transcript predictions so scoring can exercise the external
runner integration path before real model adapters exist.
