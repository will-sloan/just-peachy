"""Compare local loader concurrency on distinct randomized batches; no gradients."""
import time
import json
import numpy as np
import pandas as pd
from common import CONFIG, RUN, atomic_json
from data import BatchLoader, plan_batches


def main():
    frame = pd.read_parquet(RUN / "train.parquet")
    plan = [item for item in plan_batches(frame, 202) if item[1] == 5 and item[2] == 32 and len(item[0]) == item[3]]
    results = []
    for index, workers in enumerate((6, 12, 16)):
        loader = BatchLoader(frame, workers)
        loader.batch(plan[index * 24])
        timings = []
        for item in plan[index * 24 + 1:index * 24 + 21]:
            start = time.perf_counter()
            loader.batch(item)
            timings.append(time.perf_counter() - start)
        loader.close()
        result = {"workers": workers, "median_seconds": float(np.median(timings)), "mean_seconds": float(np.mean(timings)), "batches": len(timings)}
        results.append(result)
        print(json.dumps(result), flush=True)
    atomic_json(RUN / "loader_benchmark.json", results)


if __name__ == "__main__":
    main()
