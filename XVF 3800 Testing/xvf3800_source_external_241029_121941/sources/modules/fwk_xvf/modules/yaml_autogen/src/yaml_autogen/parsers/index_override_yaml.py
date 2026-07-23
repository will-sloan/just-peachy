#!/usr/bin/env python
# Copyright 2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class IndexOverrideYAMLParser(GenericYAMLParser):
    """
    A resource override YAML file is a special control command YAML file. See
    ctrl_yaml.py for a complete description of these files.
    A resource override YAML file consists of one or multiple resource ID 
    blocks, which are of the form:

    <RESID>:
      <CATEGORIES>

    where each <RESID> is a unique string (e.g. AEC_SERVICER_RESID,
      AEC_RESID etc.) followed by an optional " (<RESOURCE_INDEX>)" definition,
    and where each <CATEGORIES> block is one or multiple of the three command
      categories. Further description of the <CATEGORIES> block here is
      unnecessary.

    An example valid file, assuming that an enum 'device_modes' is declared
      in device_enums.h would be:

    EXAMPLE_RESID_1 (0xD2):
      <CATEGORIES>
    EXAMPLE_RESID_2 (0x4A):
      <CATEGORIES>

    Having been parsed by yaml.safe_load, this would result in the following
      Python data structure:

    {
      'EXAMPLE_RESID_1 (0xD2)':
      {
        <PROCESSED_CATEGORIES>
      },
      'EXAMPLE_RESID_2 (0x4A)':
      {
        <PROCESSED_CATEGORIES>
      }
    }

    Meanwhile, the templates that use these files expect a
      dictionary as an input.
    The dictionary should have a number of entries, each of the form

      RESID: RESOURCE_INDEX

    This function translates one input YAML file to the dictionary expected
      by the templates.
    """

    def parse(self) -> list:
        data_list = super().parse()
        output_list = list()
        for data in data_list:
            output_data = {}
            for resid, _ in data.items():
                resid, override_raw = resid.split()
                if not override_raw:
                    continue
                override = int(override_raw.strip("()"), base=0)
                output_data[resid] = override
            output_list.append(output_data)
        self.data = output_list
        return output_list
