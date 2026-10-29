"""Audit actual file headers against every selected train/dev segment; see README."""
from concurrent.futures import ThreadPoolExecutor
import time
import pandas as pd
import soundfile as sf
from common import RUN, audio_path, atomic_json, sha256


def main():
    frames = []
    for split in ("train", "dev"):
        part = pd.read_parquet(RUN / f"{split}.parquet", columns=["dataset_id", "source_registry_row_id", "audio_root_id", "audio_relative_path", "start_sec", "end_sec"])
        part["split"] = split
        frames.append(part)
    frame = pd.concat(frames, ignore_index=True)
    paths = frame[["audio_root_id", "audio_relative_path"]].drop_duplicates()
    def header(row):
        path = audio_path(row["audio_root_id"], row["audio_relative_path"])
        result = dict(row)
        try:
            info = sf.info(str(path))
            result.update(sample_rate=info.samplerate, channels=info.channels, frames=info.frames, actual_seconds=info.duration, bytes=path.stat().st_size, error="")
        except Exception as error:
            result.update(sample_rate=0, channels=0, frames=0, actual_seconds=0., bytes=0, error=str(error))
        return result
    started = time.time()
    with ThreadPoolExecutor(max_workers=16) as pool:
        headers = pd.DataFrame(pool.map(header, paths.to_dict("records")))
    headers.to_parquet(RUN / "audio_header_audit.parquet", index=False)
    checked = frame.merge(headers, on=["audio_root_id", "audio_relative_path"], validate="many_to_one")
    checked["end_overrun_seconds"] = checked.end_sec - checked.actual_seconds
    invalid = checked[(checked.start_sec < 0) | (checked.end_sec <= checked.start_sec) | (checked.start_sec >= checked.actual_seconds) | (checked.end_overrun_seconds > .05) | checked.error.ne("")]
    invalid.to_parquet(RUN / "audio_bounds_issues.parquet", index=False)
    report = {"files_checked": len(headers), "segments_checked": len(frame), "invalid_segments": len(invalid), "invalid_files": len(invalid[["audio_root_id", "audio_relative_path"]].drop_duplicates()), "by_dataset": invalid.groupby("dataset_id").size().to_dict(), "seconds": time.time() - started, "manifest_sha256": {split: sha256(RUN / f"{split}.parquet") for split in ("train", "dev")}}
    atomic_json(RUN / "audio_header_audit.json", report)
    print(report, flush=True)
    if len(invalid):
        print(invalid.groupby(["dataset_id", "audio_relative_path"]).agg(rows=("source_registry_row_id", "size"), file_seconds=("actual_seconds", "first"), latest_end=("end_sec", "max")).to_string(), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
