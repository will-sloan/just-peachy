"""State-file sharing-lock regressions; commands and rationale are in README.md."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
import common


def test_transient_lock_retries_without_overwriting_original(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    target.write_bytes(b"old complete state")
    original = common.os.replace
    attempts = []
    delays = []

    def locked(source, destination):
        attempts.append(source)
        assert target.read_bytes() == b"old complete state"
        if len(attempts) < 3:
            raise PermissionError("sharing violation")
        original(source, destination)

    monkeypatch.setattr(common.os, "replace", locked)
    monkeypatch.setattr(common.time, "sleep", delays.append)
    common.atomic_bytes(target, b"new complete state")
    assert len(attempts) == 3 and len(delays) == 2
    assert target.read_bytes() == b"new complete state"
    assert not list(tmp_path.glob("*.tmp"))


def test_persistent_lock_preserves_checkpoint_and_raises(tmp_path, monkeypatch):
    target = tmp_path / "checkpoint.msgpack"
    target.write_bytes(b"last valid checkpoint")
    ticks = iter([0., 6.])
    monkeypatch.setattr(common.time, "monotonic", lambda: next(ticks))

    def locked(*_):
        raise PermissionError("persistent sharing violation")

    monkeypatch.setattr(common.os, "replace", locked)
    with pytest.raises(PermissionError):
        common.atomic_bytes(target, b"new checkpoint")
    assert target.read_bytes() == b"last valid checkpoint"
    assert not list(tmp_path.glob("*.tmp"))


def test_concurrent_writers_have_private_temporary_files(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    original = common.os.replace
    barrier = threading.Barrier(2)
    local = threading.local()
    sources = set()

    def synchronized(source, destination):
        if not getattr(local, "seen", False):
            local.seen = True
            sources.add(str(source))
            barrier.wait(timeout=5)
        original(source, destination)

    monkeypatch.setattr(common.os, "replace", synchronized)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(common.atomic_bytes, target, value) for value in (b"a" * 8192, b"b" * 8192)]
        for job in jobs:
            job.result()
    assert len(sources) == 2
    assert target.read_bytes() in (b"a" * 8192, b"b" * 8192)
    assert not list(tmp_path.glob("*.tmp"))


def test_progress_file_lock_does_not_abort_training(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(common, "RUN", tmp_path)

    def locked(*_):
        raise PermissionError("progress reader holds file")

    monkeypatch.setattr(common, "atomic_json", locked)
    common.status("training", step=69040)
    assert "Progress update deferred" in capsys.readouterr().out
