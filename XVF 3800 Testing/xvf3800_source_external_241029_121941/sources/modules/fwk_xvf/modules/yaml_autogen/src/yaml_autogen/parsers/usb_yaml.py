#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class UsbYAMLParser(GenericYAMLParser):
    """
    A USB YAML file consists of one or multiple string definitions, which are of
        the form:

    <DEFINE_NAME>: <DEFINE_VALUE>

    where each <DEFINE_NAME> is an arbitrary string, optionally ending in _STR,
    and each <DEFINE_VALUE> is an arbitrary value. If <DEFINE_NAME> ends in
        _STR, its corresponding <DEFINE_VALUE> should be (but is not required to
        be) a string. If <DEFINE_NAME> does not end in _STR, <DEFINE_VALUE> is
        not prohibited from being a string.

    An example valid file would be:

    VENDOR_ID: 0x20B1
    PRODUCT_ID_IO_16kHz: 0x4F01
    PRODUCT_ID_IO_48kHz: 0x4F00
    MANUFACTURER_STR: "XMOS"
    PRODUCT_STR: "XVF3800 Voice Processor"
    SERIAL_NUMBER_STR: "000000"
    CONTROL_INTERFACE_STR: "XMOS Control"
    HID_INTERFACE_STR: "XMOS HID"
    DFU_FACTORY_INTERFACE_STR: "XMOS DFU Factory"
    DFU_UPGRADE_INTERFACE_STR: "XMOS DFU Upgrade"
    DEFAULT_BIT_DEPTH_IN: "16"
    DEFAULT_BIT_DEPTH_OUT: "16"

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'VENDOR_ID': 8369,
        'PRODUCT_ID_IO_16kHz': 20225,
        'PRODUCT_ID_IO_48kHz': 20224,
        'MANUFACTURER_STR': 'XMOS',
        'PRODUCT_STR': 'XVF3800 Voice Processor',
        'SERIAL_NUMBER_STR': '000000',
        'CONTROL_INTERFACE_STR': 'XMOS Control',
        'HID_INTERFACE_STR': 'XMOS HID',
        'DFU_FACTORY_INTERFACE_STR': 'XMOS DFU Factory',
        'DFU_UPGRADE_INTERFACE_STR': 'XMOS DFU Upgrade',
        'DEFAULT_BIT_DEPTH_IN': '16',
        'DEFAULT_BIT_DEPTH_OUT': '16'
    }

    Meanwhile, the templates that use these files expect a
        dictionary as an input. This dictionary has the same form as that which
        is output by yaml.safe_load.

    This class translates one input YAML file to the dictionary expected
        by the templates.

    Because the class simply loads a YAML file and returns the dictionary, there
        is no need for any function to be overridden by this definition.
    """
