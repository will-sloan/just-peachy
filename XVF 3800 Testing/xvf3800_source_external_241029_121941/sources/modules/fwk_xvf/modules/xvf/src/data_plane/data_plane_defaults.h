// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// API that must be fulfilled for the data plane to know what values to set.
#ifndef DATA_PLANE_DEFAULTS_H
#define DATA_PLANE_DEFAULTS_H

#include <stdint.h>
#include <user_dsp.h>
#include <stddef.h>
#include "i2s_task.h"

/// @brief Struct which will hold the defaults
typedef struct {
    /// Gain applied to the raw microphone values before passing to the SHF
    /// algorithm. The gain is applied with floating point multiplication
    ///
    /// Units: Absolute multiplier
    float mic_gain;

    /// Gain applied to the reference signal values post SRC but before passing to the SHF
    /// algorithm. The gain is applied with floating point multiplication
    ///
    /// Units: Absolute multiplier
    float ref_gain;


    /// Number of 16kHz microphone samples to mute after initialisation. 
    /// If set to zero then all microphone samples will be used. This time
    /// should include the time taken for the DC offset elimination (DCOE)
    /// filter to settle. Note that this is ignored for the packed input case
    ///
    /// Units: samples
    uint32_t mic_init_time_samples;


    /// Default channels selection for the left and right output. This array
    /// will contain 2 indices where:
    /// 0 - Focused beam 1
    /// 1 - Focused beam 2
    /// 2 - Free running beam
    /// 3 - Auto select
    uint8_t selected_channels[USER_DSP_NUM_OUTPUT_CHANNELS];


    /// Delay applied to input signals, if positive it is the number of samples
    /// the reference is delayed, if negative then it is the number of samples
    /// that the microphones will be delayed.
    int32_t sys_delay;

    /// Flags to indicate if output audio streams are in packed format
    uint8_t op_packed[AUDIO_TO_I2S_NUM_CHANNELS];

    /// Category and source of audio channel of the left output.
    /// If packed audio is enabled, this configures only the first of the three streams
    mux_index_t op_l;

    /// Category and source of second packed audio stream of the left output
    mux_index_t op_l_pk1;

    /// Category and source of third packed audio stream of the left output
    mux_index_t op_l_pk2;

    /// Category and source of audio channel of the right output.
    /// If packed audio is enabled, this configures only the first of the three streams
    mux_index_t op_r;

    /// Category and source of second packed audio stream of the right output
    mux_index_t op_r_pk1;

    /// Category and source of second packed audio stream of the right output
    mux_index_t op_r_pk2;

    /// Flag to indicate if the far-end DSP is enabled
    uint8_t far_end_dsp_enable;

    /// Flag to indicate if the I2S inputs are in packed audio format
    uint8_t i2s_input_packed;

    /// Flag to indicate if the pipeline is configured to receive a processed far-end reference signal from the DAC
    /// 0 means the reference signal given to the audio pipeline is the same as the one sent to the DAC
    /// 1 means the reference signal given to the audio pipeline is received over I2S from the DAC, even in UA builds
    uint8_t i2s_dac_dsp_enable;

} data_plane_defaults_t;


/// @brief function which the data plane will call to get a reference
/// to the defaults
const data_plane_defaults_t* data_plane_defaults_get();

#endif // DATA_PLANE_DEFAULTS_H
