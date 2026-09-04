"""Deployment-policy replay for qualified speaker embedding backends."""

from .replay import calibrate_open_set_policy, run_backend

__all__ = ["calibrate_open_set_policy", "run_backend"]
