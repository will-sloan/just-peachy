#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class GpoYAMLParser(GenericYAMLParser):
    """
    A GPO YAML file consists of one or multiple Port blocks, which are of the
        form:

    PORT0:
      <PINS>

    where each <PINS> block is one or multiple pins, which are of the form:
      - pin_number: int
        active_level: int
        output_duty_percent: int
        flash_serial_mask: int


    An example valid file would be:
    PORT0:
      - pin_number: 0
        active_level: 1
        output_duty_percent: 0
        flash_serial_mask: 0xFFFFFFFF
      - pin_number: 1
        active_level: 1
        output_duty_percent: 0
        flash_serial_mask: 0xFFFFFFFF
      - pin_number: 2
        active_level: 1
        output_duty_percent: 0
        flash_serial_mask: 0xFFFFFFFF
      - pin_number: 3
        active_level: 1
        output_duty_percent: 100
        flash_serial_mask: 0xFFFFFFFF
      - pin_number: 4
        active_level: 1
        output_duty_percent: 0
        flash_serial_mask: 0xFFFFFFFF
      - pin_number: 5
        active_level: 1
        output_duty_percent: 100
        flash_serial_mask: 0xFFFFFFFF
      - pin_number: 6
        active_level: 0
        output_duty_percent: 0
        flash_serial_mask: 0xFFFFFFFF
      - pin_number: 7
        active_level: 0
        output_duty_percent: 0
        flash_serial_mask: 0xFFFFFFFF

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'PORT0':
        [
            {
                'pin_number': 0,
                'active_level': 1,
                'output_duty_percent': 0,
                'flash_serial_mask': 4294967295
            },
            {
                'pin_number': 1,
                'active_level': 1,
                'output_duty_percent': 0,
                'flash_serial_mask': 4294967295
            },
            {
                'pin_number': 2,
                'active_level': 1,
                'output_duty_percent': 0,
                'flash_serial_mask': 4294967295
            },
            {
                'pin_number': 3,
                'active_level': 1,
                'output_duty_percent': 100,
                'flash_serial_mask': 4294967295
            },
            {
                'pin_number': 4,
                'active_level': 1,
                'output_duty_percent': 0,
                'flash_serial_mask': 4294967295
            },
            {
                'pin_number': 5,
                'active_level': 1,
                'output_duty_percent': 100,
                'flash_serial_mask': 4294967295
            },
            {
                'pin_number': 6,
                'active_level': 0,
                'output_duty_percent': 0,
                'flash_serial_mask': 4294967295
            },
            {
                'pin_number': 7,
                'active_level': 0,
                'output_duty_percent': 0,
                'flash_serial_mask': 4294967295
            }
        ]
    }

    Meanwhile, the templates that use these files expect a
        dictionary as an input. This dictionary has the same form as that which
        is output by yaml.safe_load.

    This class translates one input YAML file to the dictionary expected
        by the templates.

    Because the class simply loads a YAML file and returns the dictionary, there
        is no need for any function to be overridden by this definition.
    """
