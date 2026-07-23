#!/usr/bin/env python
# Copyright 2023-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import os
import typing
import yaml

FilePath = typing.Union[str, bytes, os.PathLike]
SetOfFilePaths = typing.Sequence[FilePath]
OneOrMultiplePaths = typing.Union[FilePath, SetOfFilePaths]


class GenericYAMLParser:
    def __init__(self, path: OneOrMultiplePaths) -> None:
        self.paths: OneOrMultiplePaths = path
        self.data = list()

    def parse(self) -> list:
        try:
            for path in self.paths:
                with open(path, "r") as fd:
                    self.data.append(yaml.safe_load(fd))
        except TypeError:
            with open(self.paths, "r") as fd:
                self.data.append(yaml.safe_load(fd))

        return self.data


from .command_yaml import CommandYAMLParser
from .ctrl_yaml import ControlDefaultYAMLParser
from .enum_yaml import EnumYAMLParser
from .gpi_yaml import GpiYAMLParser
from .gpo_yaml import GpoYAMLParser
from .index_yaml import IndexYAMLParser
from .mic_yaml import MicYAMLParser
from .usb_yaml import UsbYAMLParser
from .index_override_yaml import IndexOverrideYAMLParser
from .transport_yaml import TransportYAMLParser
