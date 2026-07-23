// Copyright 2022-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include <string.h>
#include "aec_cmds.h"
#include "shf_wrapper.h"
#include "user_dsp.h"
#include "doa_smoothing.h"
#include "app_conf.h"

#if appconfSPATIAL
#include <math.h>
#include <float.h>
#include "pan_pot.h"

// The angle which is considered "left". The azimuth output from SHF
// is in radians and depends on the mic geometry. The panning algorithm
// needs to know where from 0 to 2π is left. Center is left + π/2 and right
// is left + π.
#define LEFT_ANGLE_RADIANS 0

static float spatial_doa = FLT_MAX;  // out of range so that it always gets updated on first iteration.
static pan_pot_ratio_t pot;

// use auto select
#define SPATIAL_BEAM 3
#endif

// See note in user_dsp.h about timing constraints for these functions

/// store of all the recent azimuths.
static float current_azimuths[AEC_RESID_AEC_AZIMUTH_VALUES_NUM_VALUES];

static float smoothed_azimuth = 0.0;

void post_shf_dsp(int32_t out[BECLEAR_NUMBER_OF_OUTPUTS],
                  user_dsp_post_shf_input_t* input)
{
#if appconfSPATIAL
    // pan the auto select beam onto the left and right channels
    if(input->post_shf_processed_mic_samples && input->azimuths) {
        // Only update DoA if the change is significant, this avoids
        // warbly output that comes with a continually changing DoA
        static const float pi_by_5 = M_PI / 5;
        if(fabs(spatial_doa - input->azimuths[SPATIAL_BEAM]) > pi_by_5) {
            spatial_doa = input->azimuths[SPATIAL_BEAM];
            // only need to update the pan pot when the angle changes.
            pot = pan_pot_fast(spatial_doa, LEFT_ANGLE_RADIANS);
        }
        pan_pot_apply(out, &pot, input->post_shf_processed_mic_samples[3]);
    }
#else
    memcpy(out, input->post_shf_processed_mic_samples, BECLEAR_NUMBER_OF_OUTPUTS * sizeof(int32_t));
#endif
    if(NULL != input->azimuths)
    {
        memcpy(current_azimuths, input->azimuths, sizeof(current_azimuths));
        smoothed_azimuth = input->direction_of_voice;
    }
}

void beam_selection(uint8_t out_idx[USER_DSP_NUM_OUTPUT_CHANNELS],
                    float out_azimuths[USER_DSP_NUM_OUTPUT_CHANNELS])
{
#if 0
    // Enable this section of code if you want the selected azimuths to report
    // the raw azimuths calculated for the currently selected beams.
    out_azimuths[0] = current_azimuths[out_idx[0]];
    out_azimuths[1] = current_azimuths[out_idx[1]];
#else
    // This sets the currently selected azimuths to have the following values:
    //
    //     [0] = smoothed azimuth value that attempts to point to a speaker
    //     [1] = raw azimuth of the auto select beam
    out_azimuths[0] = smoothed_azimuth;
    out_azimuths[1] = current_azimuths[3];
#endif

#if appconfSPATIAL
    // override the selected channels so that spatial is output
    out_idx[0] = 0;
    out_idx[1] = 1;
#endif
}
