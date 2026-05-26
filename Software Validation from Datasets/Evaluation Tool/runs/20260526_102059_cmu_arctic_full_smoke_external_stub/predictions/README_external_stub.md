# External Stub Runner

This runner is a replaceable integration point for another ASR system.
It receives each selected recording_id, resolved audio_path, and run_config.
For augmented runs, predict_one() receives record['inference_audio_path'],
which points at a temporary augmented WAV valid during that call.
The current stub calls a dummy modular pipeline that returns deterministic
placeholder transcript predictions so scoring can exercise the external
runner integration path before real model adapters exist.
