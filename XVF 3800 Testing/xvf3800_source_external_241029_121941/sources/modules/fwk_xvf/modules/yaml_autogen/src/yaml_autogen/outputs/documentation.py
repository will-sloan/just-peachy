#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import argparse
import pathlib
import jinja2
import yaml_autogen.parsers as yp
import yaml_autogen.outputs.default_values as default_values

"""
Use this script to generate the documentation .csvs
"""


def generate_render_data(data_input, remove_hidden, remove_internal, defaults) -> dict():
    # This returns us a {resid:cmds} structure with updated defaults
    render_data, _ = default_values.generate_commands_data(data_input, remove_hidden, remove_internal, defaults)

    for commands in render_data.values():
        for command in commands:
            command["user_cmd"] = (
                command["user_cmd"][:21] + " " + command["user_cmd"][21:]
            )
            command["type"] = (
                command["type"]
                .replace("CMD_", "")
                .replace("_O", " O")
                .replace("_W", " / W")
            )
            command["value_type"] = command["value_type"].replace("TYPE_", "").lower()
            # Add information about value ranges
            if command.get("value_ranges") and "Valid range" not in command["help"]:
                value_range_str = ""
                for value, ranges in command["value_ranges"].items():
                    if ranges != "any":
                        for r in ranges:
                            index = value.replace("value", "")
                            value_range_str += (
                                f" val{index}: [" + r.replace("'", "") + "]"
                            )

                if value_range_str:
                    command["help"] += ". Valid range:" + value_range_str
            # Add information about default values
            if (
                command.get("default_value") is not None
                and command["default_value"] != "NA"
            ):
                command["help"] += f". Default value(s): {command['default_value']}"
    return render_data


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
    parser.add_argument("--remove-hidden", action="store_true")
    parser.add_argument("--remove-internal", action="store_true")

    args = parser.parse_args()

    render_data = generate_render_data(
        args.input, args.remove_hidden, args.remove_internal, args.defaults
    )
    render(render_data, args.template, args.output)
