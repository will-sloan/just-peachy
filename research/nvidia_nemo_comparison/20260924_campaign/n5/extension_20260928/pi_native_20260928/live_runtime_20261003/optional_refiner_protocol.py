"""Bounded private IPC for the optional D1 child. See README_OPTIONAL_REFINER.md."""
from __future__ import annotations

import json
import socket
import struct

RATE = 16000
BLOCK_SAMPLES = 3200
MAX_FRAMES = 8192
MAX_PACKET = 65536


class Channel:
    """Length-framed JSON, never pickle; a partial read survives a timeout."""
    def __init__(self, sock):
        self.sock = sock
        self.sock.settimeout(.1)
        self.pending = bytearray()

    def send(self, value):
        raw = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
        if len(raw) > MAX_PACKET:
            raise ValueError("Optional refiner IPC capacity exceeded")
        self.sock.sendall(struct.pack("!I", len(raw)) + raw)

    def receive(self):
        while True:
            if len(self.pending) >= 4:
                count = struct.unpack("!I", self.pending[:4])[0]
                if not 0 < count <= MAX_PACKET:
                    raise ValueError("Invalid optional refiner packet length")
                if len(self.pending) >= count + 4:
                    raw = bytes(self.pending[4:count+4])
                    del self.pending[:count+4]
                    def pairs(items):
                        result = {}
                        for key, value in items:
                            if key in result:
                                raise ValueError("Duplicate IPC field")
                            result[key] = value
                        return result
                    value = json.loads(raw, object_pairs_hook=pairs,
                                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite IPC")))
                    if not isinstance(value, dict):
                        raise ValueError("IPC object required")
                    return value
            try:
                raw = self.sock.recv(MAX_PACKET + 4 - len(self.pending))
            except socket.timeout:
                return None
            if not raw:
                raise EOFError("Optional refiner channel closed")
            self.pending.extend(raw)

    def close(self):
        self.sock.close()
