"""Read-only extended-window resource census; no dispatch. See README.md."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "n4"))
from common import bind, freeze, load, verify
from metric_process import identity, pin, exact_process
from paced_slot import process_census, competitors
from window_guard import snapshot


def main():
    import psutil
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested-mib", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.requested_mib <= 128:
        raise ValueError("Bounded census request must be 1..128 MiB")
    local = HERE.parent.parents[4] / "local"
    allowed = (local / "n5/research-extension-20260928").resolve()
    output = args.output.resolve()
    if not output.is_relative_to(allowed) or output.exists():
        raise ValueError("Fresh receipt under private extension output required")
    own = identity(pin())
    derivation = load(HERE / "GUARD_DERIVATION.json")
    for key in ("parent", "child"):
        import hashlib
        path = Path(derivation[key])
        if hashlib.sha256(path.read_bytes()).hexdigest() != derivation[key + "_sha256"]:
            raise ValueError("Guard derivation changed")
    result = snapshot(local, args.requested_mib * 1024 ** 2)
    census = process_census(local.parent)
    if competitors(census, [own, identity(psutil.Process().parent())]):
        raise RuntimeError("Competing numerical/helper process exists")
    worker = load(local / "supervision/worker.json")
    owners = [{k: worker[k] for k in ("pid", "create_time")}]
    if worker.get("child_pid"):
        owners.append(dict(pid=worker["child_pid"], create_time=worker["child_create_time"]))
    if any(exact_process(o) is not None for o in owners):
        raise RuntimeError("Prior supervisor/application owner remains alive")
    result.update(status="CENSUS_ONLY_NO_WORKER_DISPATCHED", exact_prior_owners_closed=owners,
                  process_census=census, code=[bind(HERE / p) for p in
                  ("check_admission.py", "window_guard.py", "WINDOW.json", "GUARD_DERIVATION.json")])
    for row in result["code"]:
        verify(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    freeze(output, result)
    print(dict(status=result["status"], output=str(output), free_bytes=result["free_bytes"],
               calculation=result["calculation"], checkpoint=result["new_window_checkpoint"]))


if __name__ == "__main__":
    main()
