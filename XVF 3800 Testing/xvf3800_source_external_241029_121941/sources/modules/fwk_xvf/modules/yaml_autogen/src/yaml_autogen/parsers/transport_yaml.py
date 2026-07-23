#!/usr/bin/env python
# Copyright 2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class TransportYAMLParser(GenericYAMLParser):
    """
    A transport YAML file consists of one or multiple string definitions, which 
        are of the form:

    <DEFINE_NAME>: <DEFINE_VALUE>

    where each <DEFINE_NAME> is an arbitrary string,
    and each <DEFINE_VALUE> is an arbitrary value. 

    An example valid file would be:

    I2C_ADDRESS: 0x2C
    SPI_MODE: 0

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'I2C_ADDRESS': 44,
        'SPI_MODE': 0,
    }

    Meanwhile, the templates that use these files expect a
        dictionary as an input. This dictionary has the same form as that which
        is output by yaml.safe_load.

    This class translates one input YAML file to the dictionary expected
        by the templates.

    Because the class simply loads a YAML file and returns the dictionary, there
        is no need for any function to be overridden by this definition.
    """
