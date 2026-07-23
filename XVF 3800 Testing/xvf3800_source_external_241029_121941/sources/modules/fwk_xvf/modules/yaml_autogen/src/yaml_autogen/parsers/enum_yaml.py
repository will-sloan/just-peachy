#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class EnumYAMLParser(GenericYAMLParser):
    """
    An enum YAML file consists of one or multiple enums, which are of form:

    <ENUM_NAME>
      <ENTRIES>

    where each <ENUM_NAME> is a unique string,
    and where each <ENTRIES> block is one or multiple enum values blocks, which
        are of the form:

      <VALUE_NAME>
        value: [int]
        description: [str]

      where each <VALUE_NAME> is a unique string,
      and where the fields "value" and "description" must be provided but may
          be left empty.

    An example valid file would be:

    audio_mux_category:
      MUX_SILENCE:
        value: 0
        description: 4 channels of silence
      MUX_RAW_MICS:
        value:
        description: Output of the actual microphones
      MUX_UNPACKED_MICS:
        value:
        description: microphone output from the packed input signal, This will
            be undefined when not using packed input
      MUX_MICS_W_GAIN:
        value:
        description: Chosen microphone signal (packed/raw) after having the
            configurable fixed gain applied to it. Note that the gain is applied
            as floating point and then converted back to int32 to create this
            signal. This is the signal which is passed to the SHF task for
            processing

    gpi_interrupt_edge:
      EdgeNone:
        value: 0
        description: Do not create an event on any edge
      EdgeFalling:
        value:
        description: Create an event on a falling edge (high to low)
      EdgeRising:
        value:
        description: Create an event on a rising edge (low to high)
      EdgeBoth:
        value:
        description: Create an event on any edge

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'audio_mux_category':
        {
            'MUX_SILENCE':
            {
                'value': 0,
                'description': '4 channels of silence'
            },
            'MUX_RAW_MICS':
            {
                'value': None,
                'description': 'Output of the actual microphones'
            },
            'MUX_UNPACKED_MICS':
            {
                'value': None,
                'description': 'microphone output from the packed input signal,
                    This will be undefined when not using packed input'
            },
            'MUX_MICS_W_GAIN':
            {
                'value': None,
                'description': 'Chosen microphone signal (packed/raw) after
                    having the configurable fixed gain applied to it. Note that
                    the gain is applied as floating point and then converted
                    back to int32 to create this signal. This is the signal
                    which is passed to the SHF task for processing'
            }
        },
        'gpi_interrupt_edge':
        {
            'EdgeNone':
            {
                'value': 0,
                'description': 'Do not create an event on any edge'
            },
            'EdgeFalling':
            {
                'value': None,
                'description': 'Create an event on a falling edge (high to low)'
            },
            'EdgeRising':
            {
                'value': None,
                'description': 'Create an event on a rising edge (low to high)'
            },
            'EdgeBoth':
            {
                'value': None,
                'description': 'Create an event on any edge'
            }
        }
    }

    Meanwhile, the templates that use these files expect a
        dictionary as an input.
    The dictionary should have a number of entries, each of the form:
        ENUM_NAME: ENTRIES
    where ENUM_NAME is a unique string, and ENTRIES is a dictionary with a
        number of fields, each of the form:
                   VALUE_NAME: int
        where VALUE_NAME is a unique string.

    This class translates one input YAML file to the dictionary expected
        by the templates.
    """

    def parse(self) -> list:
        data = super().parse()[0]
        output_data = dict()
        for enum_name, values in data.items():
            entries = dict()
            previous_idx = -1
            for value, fields in values.items():
                idx = (
                    fields["value"] if fields["value"] is not None else previous_idx + 1
                )
                entries.update({value: idx})
                previous_idx = idx
            output_data.update({enum_name: entries})
        self.data = [output_data]
        return [output_data]
