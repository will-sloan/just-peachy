#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import argparse
import pathlib
import jinja2
import yaml_autogen.parsers as yp

"""
Use this script to generate the print_enum_functions.h and super_print_arg.h files
"""


def parse_cmd_super_print_parameters(cmd, device_enum_dict, super_print_cmds_list):
    """Parse the super printing requirements for a command
    Args:
        cmd: command to get the super print info for
        device_enum_dict: dictionary of all enums in device_enums.yaml
        super_print_cmds_list: list all super printing requiring commands and their corresponding super printing information
    """
    enum_param_list = (
        []
    )  # List of parameter indexes, along with other info needed for enum str printing, that will be printed using the enum string lookup function
    default_param_list = (
        []
    )  # List of parameter indexes that can be printed using the default print_arg functions
    assert (
        len(cmd["super_print_parameters"]) == cmd["num_values"]
    ), "ERROR: When specifying super_print_parameters, all parameters, even if default, need to be specified"

    for i in range(len(cmd["super_print_parameters"])):
        p = cmd["super_print_parameters"][i]
        if p == cmd["value_type"]:
            default_param_list.append(i)
        else:  # If not default printing, only other case supported is enum string printing
            # We should find p in the enums list.
            assert (
                p in device_enum_dict
            ), f"For command {cmd['user_cmd']}, paramter {p}, not a default value type and also not present in the device enum list"
            enum_param_list.append({"param_index": i, "str_map": p})
    super_print_cmds_list.append(
        {
            "cmd": cmd["user_cmd"],
            "enum_param_list": enum_param_list,
            "default_param_list": default_param_list,
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, type=pathlib.Path, nargs="+")
    parser.add_argument("-e", "--enums", required=True, type=pathlib.Path)
    parser.add_argument("-t", "--template", required=True, type=pathlib.Path)
    parser.add_argument("-o", "--output", required=True, type=pathlib.Path)
    parser.add_argument("--remove-hidden", action="store_true")
    parser.add_argument("--remove-internal", action="store_true")

    args = parser.parse_args()

    render_data = list()

    command_yaml_parser = yp.CommandYAMLParser(args.input)
    command_data_list = command_yaml_parser.parse()

    command_data = dict()
    for elem in command_data_list:
        command_data.update({k: (command_data.get(k, []) + v) for k, v in elem.items()})

    for resid, commands in command_data.items():
        command_data[resid] = [
            command
            for command in commands
            if not (
                (args.remove_hidden and command["hidden"] == True)
                or (
                    args.remove_internal and command["user_cmd"].startswith("INTERNAL_")
                )
            )
        ]

    enums_yaml_parser = yp.EnumYAMLParser(args.enums)
    enums_list = enums_yaml_parser.parse()[0]

    for resid, commands in command_data.items():
        for command in commands:
            if command.get("super_print_parameters") is not None:
                parse_cmd_super_print_parameters(command, enums_list, render_data)

    with open(args.template, "r") as fd:
        template_env = jinja2.Template(fd.read(), trim_blocks=True, lstrip_blocks=True)
    # If output directory doesn't yet exist, create it
    args.output.parent.mkdir(exist_ok=True, parents=True)
    with open(args.output, "w") as fd:
        fd.write(
            template_env.render(
                render_list=render_data, template_file=args.template.name
            )
        )
