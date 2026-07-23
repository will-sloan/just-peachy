// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include "sample_delay.h"
#include <stdint.h>


size_t sample_delay_change(sample_delay_t* state, size_t new_delay) {
    size_t actual_new_delay = (new_delay > state->max_delay) 
                              ? state->max_delay
                              : new_delay;
    state->delay_countdown = actual_new_delay;
    state->read = state->write;

    // Update current delay so it can be read
    state->current_delay = actual_new_delay;
    return actual_new_delay;
}
