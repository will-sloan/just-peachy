// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef __USER_DSP_H_
#define __USER_DSP_H_

#include "aec_cmds.h"
#include "shf_wrapper.h"
#include <stdint.h>

/// There is a timing limit on the time spent in these functions. Please use the 
/// minimum idle time control commands in conjunction with the TEST_CORE_BURN command to
/// characterise the amount of cycles available.
/// The far_end_dsp function is called from I2S and so check min_idle time for that task
/// The far_end_dsp function is called from Audio so check min_idle time for that task


/// @brief callback to pre-process one sample of the far end before outputting to DAC/SHF DSP input
/// Note that this callback runs at the I2S sample rate.
/// @param far_end_sample      input and output (sample is processed in place)
/// @param far_end_dsp_enable  Set to 1 to enable, 0 to disable. This is handled by the user. 
void far_end_dsp(int32_t far_end_samples[BECLEAR_NUMBER_OF_FAR], bool far_end_dsp_enable);

/// Struct passed to post_shf_dsp which contains all the information that is available 
/// for additional post-processing.
typedef struct {
    /// Pointer to array containing the BECLEAR_NUMBER_OF_OUTPUTS processed microphone channels.
    int32_t* post_shf_processed_mic_samples;

    /// BECLEAR_NUMBER_OF_MICS channels containing the microphones after AEC before post-processing.
    int32_t* aec_residuals;

    /// Pointer to array of BECLEAR_NUMBER_OF_OUTPUTS azimuths, each element is the azimuth for the
    /// post_shf_processed_mic_samples of the same index. It can be NULL if azimuths have not been 
    /// calculated.
    float* azimuths;

    /// The spenergy (speech energy) for each beam in post_shf_processed_mic_samples. If the spenergy 
    /// is non-zero then it contains energy that is likely speech. The value will be higher for louder
    /// or closer voices, noise and distortion will cause the speech energy to decrease. This points
    /// to an array of size BECLEAR_NUMBER_OF_OUTPUTS where each value corresponds to the beam of the
    /// same index. It can be NULL if spenergy has not been calculated.
    float* spenergy;

    /// Output of xmos algorithm to determine the direction of voice, NAN if no voice detected
    float direction_of_voice;
} user_dsp_post_shf_input_t;

/// @brief callback to post-process one sample of audio after the SHF voice DSP stage
/// Note that this callback runs at the SHF sample rate.
/// @param out Array to fill with the output of this function.
/// @param input See user_dsp_post_shf_input_t comments for details.
void post_shf_dsp(int32_t out[BECLEAR_NUMBER_OF_OUTPUTS],
                  user_dsp_post_shf_input_t* input);

#define USER_DSP_NUM_OUTPUT_CHANNELS 2

/// @brief called immediately after post_shf_dsp and will be used to determine the
/// channels that MUX_USER_CHOSEN_CHANNELS will consist of. It also sets the azimuth
/// of each chosen channel so that it can be requested via control command.
///
/// @param[in,out] out_idx 2 chosen channels from `out` which were written by
///    the function `post_shf_dsp`. Before being passed to beam_selection, 
///    out_idx will be populated by the suggested indices.
/// @param[out] out_azimuths azimuths of the two channels that have been
///    selected. Most likely a copy of the correct input from above.
void beam_selection(uint8_t out_idx[USER_DSP_NUM_OUTPUT_CHANNELS],
                    float out_azimuths[USER_DSP_NUM_OUTPUT_CHANNELS]);

#endif
