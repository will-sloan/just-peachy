// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include "doa_smoothing.h"
#include "stdbool.h"

#include <math.h>

#define FIRST_BEAM 0
#define SECOND_BEAM 1
#define AUTO_SELECT_BEAM 3
#define TWO_PI (2 * M_PI)

static float smooth_doa_real_time(doa_smoothing_doa_t* state, const float* in_azimuths, const bool vad_flag) {
    static const int count_thresh = 10;
    static const float alpha = 0.825;

    float this_az = in_azimuths[AUTO_SELECT_BEAM];

    // Restrict selection to slow beams
    if(this_az != in_azimuths[FIRST_BEAM] && this_az != in_azimuths[SECOND_BEAM]) {
        this_az = state->last_az;
    }

    // counter to remove jumps
    //
    // 5degs = 0.0872665
    if(fabsf(this_az - state->last_az) > 0.0872665) {
        state->count += 1;
        if(vad_flag && state->count > count_thresh) {
            state->last_az = this_az;
            state->count = 0;
        } else {
            this_az = state->last_az;
        }
    } else {
        state->last_az = this_az;
        state->count = 0;
    }

    // smooth over 0-360 degrees
    if(this_az < (M_PI / 2) && state->smoothed_az > (3 * M_PI / 2)) {
        this_az += TWO_PI;
    } else if(this_az > (3 * M_PI / 2) && state->smoothed_az < (M_PI / 2)) {
        state->smoothed_az += TWO_PI;
    }

    // do ewm
    state->smoothed_az = (alpha * state->smoothed_az) + ((1 - alpha) * this_az);

    // compute `smoothed_az % TWO_PI` without division
    while(state->smoothed_az > TWO_PI) {
        state->smoothed_az -= TWO_PI;
    }

    return state->smoothed_az;
}

static bool spenergy_vad_ref(doa_smoothing_vad_t* state, const float* in_spenergy) {
    static const float peak_energy_alpha = 0.999;
    static const float spenergy_alpha = 0.9;
    static const float spenergy_threshold = 0.02;
    static const float spenergy_absolute_threshold = 5000;
    static const float spenergy_absolute_max = 1000000;
    static const float hold_threshold = 10;

    if(in_spenergy[AUTO_SELECT_BEAM] > state->smooth_spenergy) {
        state->smooth_spenergy = in_spenergy[AUTO_SELECT_BEAM];
    } else {
        state->smooth_spenergy = state->smooth_spenergy * spenergy_alpha;
    }

    if(state->smooth_spenergy > state->peak_spenergy) {
        state->peak_spenergy = state->smooth_spenergy;
    } else {
        state->peak_spenergy = state->peak_spenergy * peak_energy_alpha;
    }

    if (state->peak_spenergy > spenergy_absolute_max) {
        state->peak_spenergy = spenergy_absolute_max;
    }

    if((state->smooth_spenergy > (spenergy_threshold * state->peak_spenergy))
       && (state->smooth_spenergy > spenergy_absolute_threshold)) {
        state->hold_timer = hold_threshold;
    } else {
        state->hold_timer -= 1;
    }

    bool retval;
    if(state->hold_timer <= 0) {
        retval = false;
        state->hold_timer = 1;
    } else {
        retval = true;
    }
    return retval;
}

float doa_smoothing(doa_smoothing_t* state, const float* in_azimuths, const float* in_spenergy) {
    float vad_flag = spenergy_vad_ref(&state->vad, in_spenergy);
    float smoothed_az = smooth_doa_real_time(&state->doa, in_azimuths, vad_flag);

    if(vad_flag) {
        return smoothed_az;
    } else {
        return NAN;
    }
}
