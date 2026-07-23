#!/usr/bin/env python
# Copyright 2023-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class CommandYAMLParser(GenericYAMLParser):
    """
    A command YAML file consists of one or multiple resource ID blocks, which
    are of the form:

    <RESID>:
      <CATEGORIES>

    where each <RESID> is a unique string (e.g. AEC_SERVICER_RESID,
      AEC_RESID etc.) followed by an optional " (<RESOURCE_INDEX>)" definition,
    and where each <CATEGORIES> block is one or multiple of the three command
      categories, which must be unique per RESID and are each of the form:

      dedicated_commands: | shared_commands: | external_commands:
        <COMMANDS>

      where each <COMMANDS> block is one or multiple commands, which each
        must contain the 6 obligatory fields, and are of the form:

        - cmd: str
        number_of_values: int
        type: CMD_READ_WRITE | CMD_READ_ONLY | CMD_WRITE_ONLY
        help: str
        value_type: <VALUE_TYPE>
        hidden: true | false

        where <VALUE_TYPE> must be one of:

              TYPE_INT32
              TYPE_UINT32
              TYPE_INT16
              TYPE_UINT16
              TYPE_INT8
              TYPE_UINT8
              TYPE_CHAR
              TYPE_FLOAT
              TYPE_RADIANS

      and may contain the optional fields:

        index: int
        define: str
        default_value: int OR float OR (int ...) OR (float ...) or str
        value_ranges:
          <VALUES>
        super_print_parameters:
          <PARAMETERS>

        where each <VALUES> block is exactly number_of_values entries of
          the form:

          value<N>: <ACCEPTABLE_VALUE>
           for <N> = 0 .. (number_of_values - 1)

          where each <ACCEPTABLE_VALUE> may be of one of the forms:

                any
                [<RANGES>]

            where each <RANGES> block may be one or a multiple of
              comma-separated intervals of the form:

                 A .. B

            where both A and B are integers, A is permitted to be equal
              to B, and all intervals are closed, meaning that they
              include all the limit points.

        and where each <PARAMETERS> block is exactly number_of_values
          entries of the form:

          - <PRINT_TYPE>

          where each <PRINT_TYPE> may be of one of the forms:

            <DEVICE_ENUM_ENTRY>
            <VALUE_TYPE>

          where <DEVICE_ENUM_ENTRY> is a device enum declared
            via device_enums.h

    An example valid file, assuming that an enum 'device_modes' is declared
      in device_enums.h would be:

    EXAMPLE_RESID_1:
      dedicated_commands:
      - cmd: EXAMPLE_CMD_1
        number_of_values: 1
        type: CMD_READ_WRITE
        help: An example command
        value_type: TYPE_FLOAT
        hidden: true
      - cmd: EXAMPLE_CMD_2
        number_of_values: 2
        type: CMD_READ_ONLY
        help: An example command
        value_type: TYPE_UINT8
        hidden: false
        value_ranges:
          value0: [0 .. 7]
          value1: [1 .. 1, 5 .. 5, 7 .. 10]
        super_print_parameters:
          - TYPE_UINT8
          - device_modes
      shared_commands:
      - cmd: EXAMPLE_CMD_3
        number_of_values: 2
        type: CMD_WRITE_ONLY
        help: A different example command
        value_type: TYPE_RADIANS
        hidden: false
      external_commands:
    EXAMPLE_RESID_2:
      dedicated_commands:
      - cmd: EXAMPLE_CMD_4
        index: 1
        define: EXTERNAL_LIBRARY_EXAMPLE_CMD_4
        default_value: "Example default value               " (34 chars omitted)
        number_of_values: 70
        type: CMD_READ_ONLY
        help: The final example command
        value_type: TYPE_CHAR
        hidden: true

    Having been parsed by yaml.safe_load, this would result in the following
      Python data structure:

    {
      'EXAMPLE_RESID_1':
      {
        'dedicated_commands':
        [
          {
            'cmd': 'EXAMPLE_CMD_1',
            'number_of_values': 1,
            'type': 'CMD_READ_WRITE',
            'help': 'An example command',
            'value_type': 'TYPE_FLOAT',
            'hidden': True
          },
          {
            'cmd': 'EXAMPLE_CMD_2',
            'number_of_values': 2,
            'type': 'CMD_READ_ONLY',
            'help': 'An example command',
            'value_type': 'TYPE_UINT8',
            'hidden': False
            'value_ranges': {
              'value0': ['0 .. 7'],
              'value1': ['1 .. 1', '5 .. 5', '7 .. 10']
            },
            'super_print_parameters': [
              'TYPE_UINT8',
              'device_modes'
            ]
          }
        ],
        'shared_commands':
        [
          {
            'cmd': 'EXAMPLE_CMD_3',
            'number_of_values': 2,
            'type': 'CMD_WRITE_ONLY',
            'help': 'A different example command',
            'value_type': 'TYPE_RADIANS',
            'hidden': False
          },
        ],
        'external_commands': None
      },
      'EXAMPLE_RESID_2':
      {
        'dedicated_commands':
        [
          {
            'cmd': 'EXAMPLE_CMD_4',
            'number_of_values': 70,
            'offset': 1
            'define': EXTERNAL_LIBRARY_EXAMPLE_CMD_4
            'default_value': "Example default value         " (36 chars omitted)
            'type': 'CMD_READ_ONLY',
            'help': 'The final example command',
            'value_type': 'TYPE_CHAR',
            'hidden': True
          }
        ]
      }
    }

    Meanwhile, the templates that use these files expect a
      dictionary as an input.
    The dictionary should have a number of entries, each of the form

      RESID: COMMANDS

    where RESID is a unique string, and COMMANDS is a list of dictionaries
      with the following fields:

      name:      String   All-caps. Has form f"{RESID}_{cmd}", except for
                   BECLEAR commands which use command ['define']
                   from YAML data structure
      offset:    Integer  Command ['index'] from YAML data structure if
                   present, uses a default value if not. For
                   dedicated commands, this starts at 0, unless it
                   is an AEC or a PP command where it starts at
                   70. For shared commands, this starts at 90.
                   For external commands, this starts at 110. This
                   value increments by 1 for each new command.
      num_values:  Integer  Command ['number_of_values'] from YAML
                   data structure.
      size:      String   f"sizeof(<C_TYPE>)", where <C_TYPE> is
                   as described for the ctype field below.
      type:      String   Command ['type'] from YAML data structure.
      help:      String   Command ['help'] from YAML data structure.
      user_cmd:    String   Command ['cmd'] from YAML data structure.
      res_id:    String   RESID
      value_type:  String   Command ['value_type'] from YAML data structure.
      value_ranges:  String   Command ['value_ranges'] from YAML data
                   structure if present, "" if not.
      hidden:    Bool   Command ['hidden'] from YAML data structure.
      ctype:     String   Underlying C type of the command ['value_type'],
                   converted with the following map:
                   {
                     "TYPE_INT32": "int32_t",
                     "TYPE_UINT32": "uint32_t",
                     "TYPE_INT16": "int16_t",
                     "TYPE_UINT16": "uint16_t",
                     "TYPE_INT8": "int8_t",
                     "TYPE_UINT8": "uint8_t",
                     "TYPE_CHAR": "char",
                     "TYPE_FLOAT": "float",
                     "TYPE_RADIANS": "float",
                   }
      default_value: String   Command ['default_value'] from YAML data
                   structure if present, None if not.
      super_print_parameters: String  Command ['super_print_parameters'] from
                      YAML data structure if present, None if
                      not.

    This function translates one input YAML file to the dictionary expected
      by the templates.
    """

    DEFAULT_CATEGORY_OFFSETS = {
        "dedicated_commands": 0,
        "shared_commands": 90,
        "external_commands": 110,
    }
    RESIDS_WITH_EDITED_OFFSETS = {
        "AEC_RESID": {"dedicated_commands": 70},
        "PP_RESID": {"dedicated_commands": 70},
    }
    C_TYPE = {
        "TYPE_INT32": "int32_t",
        "TYPE_UINT32": "uint32_t",
        "TYPE_INT16": "int16_t",
        "TYPE_UINT16": "uint16_t",
        "TYPE_INT8": "int8_t",
        "TYPE_UINT8": "uint8_t",
        "TYPE_CHAR": "char",
        "TYPE_FLOAT": "float",
        "TYPE_RADIANS": "float",
    }

    def parse(self) -> list:
        data_list = super().parse()
        output_list = list()
        for data in data_list:
            output_data = {}
            # Remove RESIDs with no categories present - means no commands present.
            #  Does not however guarantee commands are present - could be empty
            #  categories.
            data = {resid: cats for resid, cats in data.items() if cats}

            # Loop over remaining RESIDs. Could be none!
            for resid, categories in data.items():
                # Deal with category offset special cases
                resid = resid.split()[0] # Remove the optional resource ID spec.
                edited_offsets = self.RESIDS_WITH_EDITED_OFFSETS.get(resid, {})
                category_offsets = dict(self.DEFAULT_CATEGORY_OFFSETS)
                category_offsets.update(edited_offsets)

                # We know this resid has some categories defined now; add it to
                #  the output dictionary
                if resid not in output_data:
                    output_data.update({resid: []})

                # Remove categories with no commands.
                categories = {cat: cmds for cat, cmds in categories.items() if cmds}

                # Loop over remaining categories. Could be none!
                for category, commands in categories.items():
                    local_offset = category_offsets[category]

                    for cmd in commands:
                        # Detect SHF commands.
                        shf_command = "BECLEAR" in cmd.get("define", "")

                        if shf_command:
                            name = cmd["define"]
                        else:
                            name = f"{resid}_{cmd['cmd']}"

                        ctype = self.C_TYPE[cmd["value_type"]]

                        output_cmd = {
                            "name": name.upper(),
                            "offset": cmd.get("index", local_offset),
                            "num_values": cmd["number_of_values"],
                            "size": f"sizeof({ctype})",
                            "type": cmd["type"],
                            "help": cmd["help"],
                            "user_cmd": cmd["cmd"],
                            "res_id": resid,
                            "value_type": cmd["value_type"],
                            "value_ranges": cmd.get("value_ranges", ""),
                            "hidden": cmd["hidden"],
                            "ctype": ctype,
                            "default_value": cmd.get("default_value"),
                            "super_print_parameters": cmd.get("super_print_parameters"),
                        }

                        local_offset += 1

                        output_data[resid] += [output_cmd]
            output_list.append(output_data)

        self.data = output_list
        return output_list
