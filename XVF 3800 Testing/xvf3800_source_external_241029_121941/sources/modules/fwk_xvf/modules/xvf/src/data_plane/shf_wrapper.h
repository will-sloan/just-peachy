// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef _SHF_H_
#define _SHF_H_

// This module contains the framework for SHF including plumbing in and out of i2s/audio,
// the cross tile link for forwarding samples to and from PP and the fork and join
// constructs for parallelising the execution of the algorithm.
#include <stdbool.h>
#include "app_conf.h"

#include "BeClearCommon.h"

#include "mux.h"
#include "xcore/chanend.h"
#include "xcore/parallel.h"
#include <xcore/interrupt_wrappers.h>
#include <xcore/interrupt.h>
#include <xcore/triggerable.h>

#include "xmath/xmath.h"
#include "packet_queue.h"
#include "aec_cmds.h"  // auto generated
#include "timing_debug_defs.h" // STATIC_INLINE def


#define BECLEAR_NUMBER_OF_MICS      4
#define BECLEAR_NUMBER_OF_FAR       1

#define BECLEAR_OUTPUT_BEAM_0       0
#define BECLEAR_OUTPUT_BEAM_1       1
#define BECLEAR_OUTPUT_FREE_RUNNING 2
#define BECLEAR_OUTPUT_AUTO_SELECT  3

#define BECLEAR_FP_EXPONENT         ((int)(-1.0 - log(BECLEAR_MAX_SAMPLE+1)/log(2))) // Used for normalising and denormalising fns below

#define NUM_SHF_INPUT_BUFFERS       2       // Double or single buffer. May be set to 1 or 2 only.
#define NUM_SHF_OUTPUT_BUFFERS      2       // Double or single buffer. May be set to 1 or 2 only.

#define SHF_FRAME_TIME_TICKS        (uint32_t)((float)XS1_TIMER_HZ * (float)BECLEAR_SAMPLES_PER_FRAME / (float)BECLEAR_SAMPLE_FREQUENCY)

// Typedefs for the buffers used for SHF

/// @brief Struct to hold data going from audio to shf
typedef struct shf_input_t {
    // Mic input. Also holds AEC residuals on output
    float mics[BECLEAR_NUMBER_OF_MICS][BECLEAR_SAMPLES_PER_FRAME];

    // Far-end/reference input
    float far[BECLEAR_NUMBER_OF_FAR][BECLEAR_SAMPLES_PER_FRAME];
} shf_input_t;

typedef struct shf_output_t {
    // Processed output
    float commsout[BECLEAR_NUMBER_OF_OUTPUTS][BECLEAR_SAMPLES_PER_FRAME];

    // per beam DOA info, documented in shf under get azimuth
    aec_resid_aec_azimuth_values_t azimuths[AEC_RESID_AEC_AZIMUTH_VALUES_NUM_VALUES];

    // per beam speach energy level
    float spenergy[BECLEAR_NUMBER_OF_OUTPUTS];

    // smoothed azimuth which is NAN with no speech
    float smoothed_azimuth;
} shf_output_t;

typedef struct aec_state_t {
    // Microphone positions, one array of 3 values for each microphone
    const float * micpos[BECLEAR_NUMBER_OF_MICS];

    // bypass select
    uint8_t bypass;
    uint32_t idle_time_ticks;
    uint32_t min_idle_time_ticks;
    // whether to apply gating to the fixed beams or not
    uint8_t fixed_beams_gated;
} aec_state_t;

typedef struct pp_state_t {
    uint32_t idle_time_ticks;
    uint32_t min_idle_time_ticks;
} pp_state_t;

// This scales an int32_t to a float accoring to the range set by BECLEAR_MAX_SAMPLE
STATIC_INLINE void shf_int32_to_float32_scaled(float* out, mux_source_t* in)
{
    for(int i = 0; i < in->n_elems; ++i) {
        out[i] = s32_to_f32(in->buf[i], BECLEAR_FP_EXPONENT);
    }
}

// This produces an int32_t of full range from a float of range set by BECLEAR_MAX_SAMPLE
STATIC_INLINE int32_t shf_float32_to_int32_scaled(float f)
{
    int32_t mantissa;
    exponent_t exp;
    f32_unpack(&mantissa, &exp, f);
    mantissa >>= (BECLEAR_FP_EXPONENT - exp);
    return mantissa;
}

// Job declarations for SHF

/// @brief intialises and runs the PP functions
/// @param chanend_t chanends as required by shf
/// @param control_pkt_queue_t pkt_queue Pointer to the control packet queue
DECLARE_JOB(INTERRUPT_PERMITTED(pp_task), (chanend_t*, control_pkt_queue_t*));

/// @brief intialises and runs the AEC functions
/// @param chanend_t chanends as required by shf
/// @param chanend_t audio <-> AEC chanend
/// @param control_pkt_queue_t pkt_queue Pointer to the control packet queue
DECLARE_JOB(aec_task, (chanend_t*, chanend_t, control_pkt_queue_t*));


#endif
