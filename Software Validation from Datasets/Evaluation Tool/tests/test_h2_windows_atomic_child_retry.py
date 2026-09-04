from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


TOOL_ROOT = Path(__file__).resolve().parents[1]
CHILD_POLICY_DIRECTORY = TOOL_ROOT / "scripts" / "h2_atomic_retry_child"


def test_child_sitecustomize_recovers_transient_replace(tmp_path: Path) -> None:
    source = tmp_path / "source.tmp"
    destination = tmp_path / "destination.json"
    event_log = tmp_path / "events.jsonl"
    script = r'''
import json
import os
from pathlib import Path
import sitecustomize
import sys

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
source.write_text("replacement", encoding="utf-8")
destination.write_text("original", encoding="utf-8")
real_replace = sitecustomize._ORIGINAL_REPLACE
calls = {"count": 0}

def flaky_replace(src, dst, *args, **kwargs):
    calls["count"] += 1
    if calls["count"] == 1:
        error = PermissionError(13, "synthetic Windows sharing violation")
        error.winerror = 5
        raise error
    return real_replace(src, dst, *args, **kwargs)

sitecustomize._ORIGINAL_REPLACE = flaky_replace
sitecustomize.RETRY_DELAYS_SEC = (0.0,)
os.replace(source, destination)
print(json.dumps({"calls": calls["count"], "value": destination.read_text()}))
'''
    environment = dict(os.environ)
    inherited = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(CHILD_POLICY_DIRECTORY), *([inherited] if inherited else [])]
    )
    environment["H2_ATOMIC_RETRY_EVENT_LOG"] = str(event_log)
    completed = subprocess.run(
        [sys.executable, "-c", script, str(source), str(destination)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    observed = json.loads(completed.stdout)
    assert observed == {"calls": 2, "value": "replacement"}
    events = [json.loads(line) for line in event_log.read_text().splitlines()]
    assert [event["status"] for event in events] == ["RETRYING", "RECOVERED"]
    assert all(event["policy_scope"] == "child_process_sitecustomize" for event in events)
    assert all(isinstance(event["process_id"], int) for event in events)
