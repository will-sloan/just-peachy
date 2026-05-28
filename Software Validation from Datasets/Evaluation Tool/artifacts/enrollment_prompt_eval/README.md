# Enrollment Prompt Evaluation Artifacts

This folder contains repeatable M12 experiment inputs. The tracked synthetic
JSONL fixture exercises the prompt comparison workflow without microphone
recordings, model downloads, or participant data.

Real evaluation rows should use the same schema as
`synthetic_prompt_samples.jsonl` and may replace inline `embedding` values with
an `embedding_path` that points to a JSON file containing `vector` or
`embedding`.
