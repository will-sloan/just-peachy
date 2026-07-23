// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// @brief This library contains the code which is used to bypass the SHF algorithm
/// when that is desired
#ifndef SHF_BYPASS_H
#define SHF_BYPASS_H

#include <stdint.h>
#include <xcore/chanend.h>
#include "BeClearCommon.h"

/// @brief wait until the reference timer has incremented by delay_ticks. Busy wait so burns MIPS whilst waiting.
/// @param delay_ticks number of ticks to wait
/// @return number of loops that iterated
uint32_t shf_bypass_wait(uint32_t delay_ticks);

/// @brief wait until the reference timer has incremented by delay_ticks. Event based wait so liberates MIPS to other cores
/// @param delay_ticks number of ticks to wait
void shf_bypass_event_wait(uint32_t delay_ticks);

/// @brief initialise AEC thread with chanend that is connected to PP thread.
void shf_bypass_init_aec(chanend_t);

/// @brief pass mics through to the qcom
void shf_bypass_main_aec(
    float* const* const mics,
    float* const* const spks,
    float* const* const qcom,
    float* const* const aecmics,
    unsigned burn
);

/// @brief Init bypass, does nothing except copy a reference to the chanend
void shf_bypass_init_pp(chanend_t);

/// @brief shf, but does nothing, returns the input with a single frame delay
/// @param burn if true then burn tasks are created for bypass
/// @param buf buffer of specified size which is used to store samples between calls
///            Buf must point to the same unmodified buffer on each consequtive call,
///            it should be 0 when first used
void shf_bypass_main_pp(unsigned burn, float buf[BECLEAR_MAX_NUMBER_OF_MICS][BECLEAR_SAMPLES_PER_FRAME]);

#endif
