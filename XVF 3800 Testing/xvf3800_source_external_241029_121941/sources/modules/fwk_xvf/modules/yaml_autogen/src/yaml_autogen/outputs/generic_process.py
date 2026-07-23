#!/usr/bin/env python
# Copyright 2023-2024 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

import argparse
import pathlib
import jinja2
import yaml_autogen.parsers as yp

"""
Use this script if an input can be simply translated by a Parser and fed to a
template to achieve the desired output.
"""

ACCEPTABLE_INPUT_PARSERS = {
    "command": yp.CommandYAMLParser,
    "gpi": yp.GpiYAMLParser,
    "gpo": yp.GpoYAMLParser,
    "mic": yp.MicYAMLParser,
    "usb": yp.UsbYAMLParser,
    "indices": yp.IndexYAMLParser,
    "enums": yp.EnumYAMLParser,
    "indices_override": yp.IndexOverrideYAMLParser,
    "transport": yp.TransportYAMLParser,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, type=pathlib.Path)
    parser.add_argument("-t", "--template", required=True, type=pathlib.Path)
    parser.add_argument("-o", "--output", required=True, type=pathlib.Path)
    parser.add_argument(
        "-y", "--yaml-type", required=True, choices=ACCEPTABLE_INPUT_PARSERS.keys()
    )

    args = parser.parse_args()

    yaml_parser = ACCEPTABLE_INPUT_PARSERS[args.yaml_type](args.input)

    render_data = yaml_parser.parse()[0]

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
