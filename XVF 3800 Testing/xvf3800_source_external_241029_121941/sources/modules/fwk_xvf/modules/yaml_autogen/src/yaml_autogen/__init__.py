#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import pathlib


def get_templates() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent / "templates"
