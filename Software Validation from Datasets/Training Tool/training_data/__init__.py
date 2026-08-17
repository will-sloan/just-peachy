"""Deterministic local training-data inventory and evaluation-leakage firewall."""

from .registry import build_freeze, verify_freeze

__all__ = ["build_freeze", "verify_freeze"]
