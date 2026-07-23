#!/usr/bin/env python
# Copyright 2023 XMOS LIMITED.
# This Software is subject to the terms of the XCORE VocalFusion Licence.

from . import GenericYAMLParser


class ControlDefaultYAMLParser(GenericYAMLParser):
    """
    A control defaults YAML file consists of one or multiple resource blocks,
        which are of the form:

    <RESID>:
      <CMDS>

    where each <RESID> is a unique string which corresponds to an existing
        command resource string defined by a call to parse_command_yaml (e.g.
        AEC_SERVICER_RESID, AEC_RESID etc.)
    and where each <CMDS> block is consists of one or multiple commands, which
        are of the form:

      - cmd: string
        default value: int OR float OR (int ...) OR (float ...) or str

    An example valid file would be:

    AEC_RESID:
      - cmd: AEC_HPFONOFF
        default_value: on125
      - cmd: AEC_AECSILENCELEVEL
        default_value: 1e-8f

    PP_RESID:
      - cmd: PP_AGCONOFF
        default_value: on
      - cmd: PP_AGCMAXGAIN
        default_value: 60.0

    AUDIO_MGR_RESID:
      - cmd: AUDIO_MGR_MIC_GAIN
        default_value: 80.0
      - cmd: AUDIO_MGR_REF_GAIN
        default_value: 0.33
      - cmd: AUDIO_MGR_SELECTED_CHANNELS
        default_value: (3, 3)
      - cmd: AUDIO_MGR_SYS_DELAY
        default_value: 0
      - cmd: AUDIO_MGR_OP_PACKED
        default_value: (0, 0)

    Having been parsed by yaml.safe_load, this would result in the following
        Python data structure:

    {
        'AEC_RESID':
        [
            {
                'cmd': 'AEC_HPFONOFF',
                'default_value': 'on125'
            },
            {
                'cmd': 'AEC_AECSILENCELEVEL',
                'default_value': '1e-8f'
            }
        ],
        'PP_RESID':
        [
            {
                'cmd': 'PP_AGCONOFF',
                'default_value': True
            },
            {
                'cmd': 'PP_AGCMAXGAIN',
                'default_value': 60.0
            }
        ],
        'AUDIO_MGR_RESID':
        [
            {
                'cmd': 'AUDIO_MGR_MIC_GAIN',
                'default_value': 80.0
            },
            {
                'cmd': 'AUDIO_MGR_REF_GAIN',
                'default_value': 0.33
            },
            {
                'cmd': 'AUDIO_MGR_SELECTED_CHANNELS',
                'default_value': '(3, 3)'
            },
            {
                'cmd': 'AUDIO_MGR_SYS_DELAY',
                'default_value': 0
            },
            {
                'cmd': 'AUDIO_MGR_OP_PACKED',
                'default_value': '(0, 0)'
            }
        ]
    }

    This data structure is not used directly by any template. This information
        is merged into the data structure produced by an invocation of
        parse_control_yaml.

    This class translates one input YAML file to the dictionary expected
        by the internal processes that consume it.

    Because the class simply loads a YAML file and returns the dictionary, there
        is no need for any function to be overridden by this definition.
    """
