#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class IndexYAMLParser(GenericYAMLParser):
    """
    A resource indices YAML file consists of one or multiple resource index
        definitions, which are of the form:

    <RESID>: uint8

    where each <RESID> is a unique string which corresponds to an existing
        command resource string defined by a call to parse_command_yaml (e.g.
        AEC_SERVICER_RESID, AEC_RESID etc.)

    An example valid file would be:

    PP_SERVICER_RESID: 0x10
    PP_RESID: 0x11
    DFU_CONTROLLER_SERVICER_RESID: 0x12

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'PP_SERVICER_RESID': 16,
        'PP_RESID': 17,
        'DFU_CONTROLLER_SERVICER_RESID': 18
    }

    Meanwhile, the templates that use these files expect a
        dictionary as an input. This dictionary has the same form as that which
        is output by yaml.safe_load.

    This class translates one input YAML file to the dictionary expected
        by the templates.

    Because the class simply loads a YAML file and returns the dictionary, there
        is no need for any function to be overridden by this definition.
    """
