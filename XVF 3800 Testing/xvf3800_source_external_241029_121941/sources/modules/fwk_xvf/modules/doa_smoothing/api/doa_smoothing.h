// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// Interface for doa smoothing module. This uses the azimuths 
/// and spenergy data from the BeClear algorithm to provide a 
/// likely DoA of a speaker in a room as well as voice presence.
///
#pragma once

#include <stddef.h>

#define DS_NUM_FIXED_BEAMS 2

/// private struct which is used internally
typedef struct {
    int count;
    float last_az;
    float smoothed_az;
    ptrdiff_t last_slow;
} doa_smoothing_doa_t;

// private struct which is used internally
typedef struct {
    float smooth_spenergy;
    float peak_spenergy;
    int hold_timer;
} doa_smoothing_vad_t;

// Holds doa smoothing state, use DOA_SMOOTHING_INITIALISER to initialise with 
// correct default values.
typedef struct {
    // state
    doa_smoothing_doa_t doa;
    doa_smoothing_vad_t vad;
} doa_smoothing_t;

// macro to use when initialising a doa_smoothing_t, example:
//
//     doa_smoothing_t var = DOA_SMOOTHING_INITIALISER;
#define DOA_SMOOTHING_INITIALISER {.doa={0}}

/// Perform DoA smoothing on azimuth and spenergy data from BeClear algorithm.
///
/// @param[in,out] state holds persistent state, should pass in same instance of doa_smoothing_t for each call.
/// @param[in] in_azimuths latest azimuth data.
/// @param[in] in_spenergy latest spenergy data. 
/// @return NAN if no speech is preset or a valid angle in radians indicating the direction of the speaker.
float doa_smoothing(doa_smoothing_t* state, const float* in_azimuths, const float* in_spenergy);
