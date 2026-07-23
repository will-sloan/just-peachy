#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class MicYAMLParser(GenericYAMLParser):
    """
    A microphone geometry YAML file consists of one or a multiple of microphone
        geometry blocks, which are of the form:

    <LABEL>:
      <MICS>

    where each <LABEL> block is a string declaring the kind of geometry that the
        microphone geometry block defines; acceptable values for the XVF38*0 are
        LINEAR_GEOMETRY and SQUARECULAR_GEOMETRY
    and each <MICS> block is one or multiple microphones and their respective
        position (as a float in metres), which are each of the form:

      - MIC<ID>: (<X>f, <Y>f, <Z>f)

        where <ID> is a unique integer,
        and <X>, <Y>, and <Z> are numbers in floating point form.

    An example valid file would be:

    LINEAR_GEOMETRY:
      - MIC0: ( -0.04995f,    0.00f,      0.00f )
      - MIC1: ( -0.01665f,    0.00f,      0.00f )
      - MIC2: ( 0.01665f,     0.00f,      0.00f )
      - MIC3: ( 0.04995f,     0.00f,      0.00f )
    SQUARECULAR_GEOMETRY:
      - MIC0: ( 0.0333f,      -0.0333f,   0.00f )
      - MIC1: ( 0.0333f,      0.0333f,    0.00f )
      - MIC2: ( -0.0333f,     0.0333f,    0.00f )
      - MIC3: ( -0.0333f,     -0.0333f,   0.00f )

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'LINEAR_GEOMETRY':
        [
            {
                'MIC0': '( -0.04995f,    0.00f,      0.00f )'
            },
            {
                'MIC1': '( -0.01665f,    0.00f,      0.00f )'
            },
            {
                'MIC2': '( 0.01665f,     0.00f,      0.00f )'
            },
            {
                'MIC3': '( 0.04995f,     0.00f,      0.00f )'
            }
        ],
        'SQUARECULAR_GEOMETRY':
        [
            {
                'MIC0': '( 0.0333f,      -0.0333f,   0.00f )'
            },
            {
                'MIC1': '( 0.0333f,      0.0333f,    0.00f )'
            },
            {
                'MIC2': '( -0.0333f,     0.0333f,    0.00f )'
            },
            {
                'MIC3': '( -0.0333f,     -0.0333f,   0.00f )'
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
