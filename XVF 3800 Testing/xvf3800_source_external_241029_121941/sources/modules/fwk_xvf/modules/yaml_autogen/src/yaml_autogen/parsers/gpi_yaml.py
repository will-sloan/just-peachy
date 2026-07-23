#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class GpiYAMLParser(GenericYAMLParser):
    """
    A GPI YAML file consists of one or multiple Pin blocks, which are of the
        form:

    PIN<ID>:
      active_level: int
      event_config: <EVENT_CONFIG>

    where each <ID> is a unique integer,
    and where each <EVENT_CONFIG> is an entry in the "gpi_interrupt_edge" enum
        defined in device_enums.h

    An example valid file would be:

    PIN0:
      active_level: 1
      event_config: EdgeNone
    PIN1:
      active_level: 0
      event_config: EdgeBoth

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'PIN0':
        {
            'active_level': 1,
            'event_config': 'EdgeNone'
        },
        'PIN1':
        {
            'active_level': 0,
            'event_config': 'EdgeBoth'
        }
    }

    Meanwhile, the templates that use these files expect a
        dictionary as an input. This dictionary has the same form as that which
        is output by yaml.safe_load.

    This class translates one input YAML file to the dictionary expected
        by the templates.

    Because the class simply loads a YAML file and returns the dictionary, there
        is no need for any function to be overridden by this definition.
    """
