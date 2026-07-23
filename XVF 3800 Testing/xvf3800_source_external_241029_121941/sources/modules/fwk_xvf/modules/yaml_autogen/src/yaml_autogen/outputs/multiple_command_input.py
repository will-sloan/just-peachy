#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import argparse
import pathlib
import jinja2
import yaml_autogen.parsers as yp

"""
Use this script if multiple "command" type YAML inputs are to be accumulated
into a single output file
"""

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, type=pathlib.Path, nargs="+")
    parser.add_argument("-t", "--template", required=True, type=pathlib.Path)
    parser.add_argument("-o", "--output", required=True, type=pathlib.Path)
    parser.add_argument("--remove-hidden", action="store_true")
    parser.add_argument("--remove-internal", action="store_true")

    args = parser.parse_args()

    yaml_parser = yp.CommandYAMLParser(args.input)

    render_data_list = yaml_parser.parse()
    render_data = dict()
    for elem in render_data_list:
        render_data.update({k: (render_data.get(k, []) + v) for k, v in elem.items()})

    for resid, commands in render_data.items():
        render_data[resid] = [
            command
            for command in commands
            if not (
                (args.remove_hidden and command["hidden"] == True)
                or (
                    args.remove_internal and command["user_cmd"].startswith("INTERNAL_")
                )
            )
        ]

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
