"""H2-only product-pipeline scientific program.

This package is additive.  It preserves the checksum-bound all-18 evidence and
creates a new protocol identity for the fixed H2 architecture.
"""

from .contracts import (
    H2Job,
    H2ProgramError,
    H2_PROGRAM_SCHEMA_VERSION,
)

__all__ = ["H2Job", "H2ProgramError", "H2_PROGRAM_SCHEMA_VERSION"]
