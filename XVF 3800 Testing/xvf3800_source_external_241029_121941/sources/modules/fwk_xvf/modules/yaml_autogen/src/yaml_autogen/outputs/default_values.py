#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import argparse
import pathlib
import jinja2
import yaml_autogen.parsers as yp

"""
Use this script to generate the _defaults.h files, see tests directory for examples of 
valid and invalid formatted defaults
"""

def split_multi(default_str):
    """
    Separates parameters in defaults yaml file. Supports either single values 
    or multiple values surrounded by "(" ")" and separated by ",". Below are 
    some example inputs and outputs.

    >>> split_multi("1e-8f")
    ('1e-8f',)
    >>> split_multi("4")
    ('4',)
    >>> split_multi("(4, 4)")
    ('4', '4')
    """
    if default_str.strip().startswith("("):
        return tuple(s.strip() for s in default_str.strip()[1:-1].split(","))
    else:
        return default_str.strip(),

def format_float(float_str):
    """
    Turn default string from yaml into value that is suitable for
    initialising a float in C
    """
    float_str = float_str.strip()
    if float_str.endswith("f"):
        # strip the f
        float_str = float_str[:-1]
    return str(float(float_str))
    
def format_value(val_str, type_str):
    """
    Format an individual value into a string that can be pasted into a C
    file. accepted inputs depend on the value type, ranges are not checked.
    """
    if val_str.endswith("dB"):
        # strip dB suffix if present
        val_str = val_str[:-2]
    try:
        # Support strings which have meaning in certain contexts.
        val_str = {
            "off": "0",
            "on70": "1",
            "on125": "2",
            "on150": "3",
            "on180": "4",
            "disabled": "-1",
            "on": "1",
            "off": "0",
        }[val_str]
    except KeyError:
        pass

    if type_str in ("TYPE_FLOAT", "TYPE_RADIANS"):
        return format_float(val_str)
    else:
        if val_str == "False":
            return "0"
        elif val_str == "True":
            return "1"
        else:
            return str(int(val_str))

def format_default_value(cmd):
    """Format default value to C style
    Args:
          cmd: dictionary storing command information
    """
    default_value_str = str(cmd["default_value"])
    type_str = cmd["value_type"]

    vals = split_multi(default_value_str)
    if cmd["num_values"] > 1:
        formatted = "{" + ", ".join(format_value(v, type_str) for v in vals) + "}"
    else:
        formatted = format_value(vals[0], type_str)

    cmd["default_value"] = formatted


def generate_commands_data(input, remove_hidden, remove_internal, defaults):
    render_data = list()

    command_yaml_parser = yp.CommandYAMLParser(input)
    command_data_list = command_yaml_parser.parse()

    command_data = dict()
    for elem in command_data_list:
        command_data.update({k: (command_data.get(k, []) + v) for k, v in elem.items()})

    for resid, commands in command_data.items():
        command_data[resid] = [
            command
            for command in commands
            if not (
                (remove_hidden and command["hidden"] == True)
                or (remove_internal and command["user_cmd"].startswith("INTERNAL_"))
            )
        ]

    defaults_yaml_parser = yp.ControlDefaultYAMLParser(defaults)
    defaults_data = defaults_yaml_parser.parse()[0]

    for resid, commands in command_data.items():
        if resid in defaults_data:
            new_defaults = defaults_data[resid]
            for original_command in commands:
                for new_command in new_defaults:
                    if original_command["user_cmd"] == new_command["cmd"]:
                        original_command["default_value"] = new_command["default_value"]

                render_data.append(original_command)

    # command_data is a {resid:commands} structure with updated defaults
    # render_data is a flattened list of commands with defined defaults
    return command_data, render_data


def render(render_data, template, output):
    with open(template, "r") as fd:
        template_env = jinja2.Template(fd.read(), trim_blocks=True, lstrip_blocks=True)
    # If output directory doesn't yet exist, create it
    output.parent.mkdir(exist_ok=True, parents=True)
    with open(output, "w") as fd:
        fd.write(
            template_env.render(render_list=render_data, template_file=template.name)
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, type=pathlib.Path, nargs="+")
    parser.add_argument("-d", "--defaults", required=True, type=pathlib.Path)
    parser.add_argument("-t", "--template", required=True, type=pathlib.Path)
    parser.add_argument("-o", "--output", required=True, type=pathlib.Path)
    parser.add_argument("-p", "--product", required=True, choices=("3800", "3820"), 
                        help="ignored, project used to impact behaviour but no longer does.")
    parser.add_argument("--remove-hidden", action="store_true")
    parser.add_argument("--remove-internal", action="store_true")

    args = parser.parse_args()

    _, render_data = generate_commands_data(args.input, args.remove_hidden, args.remove_internal, args.defaults)
    for cmd in render_data:
        if cmd["default_value"] not in (None, "NA") and cmd["type"] != "CMD_READ_ONLY":
            format_default_value(cmd)
    render(render_data, args.template, args.output)
