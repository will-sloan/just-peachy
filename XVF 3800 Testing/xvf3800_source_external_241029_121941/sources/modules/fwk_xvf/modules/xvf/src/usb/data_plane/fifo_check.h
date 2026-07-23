// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#pragma once

#include <stdbool.h>
#include "fifo_types.h"


// Enum for tracking FIFO state so we start streaming at half full
// Note the order of these is important so we can optimise using 
// >= AUDIO_FIFO_STABLE to gate emptying
typedef enum audio_fifo_state_t{
    AUDIO_FIFO_EMPTY = 0,
    AUDIO_FIFO_FILLING,
    AUDIO_FIFO_STABLE,
    AUDIO_FIFO_EMPTYING,
    AUDIO_FIFO_FULL
}audio_fifo_state_t;

// Handle the FIFO fill level state machine to track when we should start pusing/popping
// to acheive a close to half full fill level on startup
static inline __attribute__((always_inline)) void check_fifo_state_after_push(audio_fifo_state_t *fifo_state, const fifo_ret_t ret, const int fill_level, const int stable_trigger, const char *direction)
{
    if (ret != FIFO_SUCCESS)
    {
        if (*fifo_state != AUDIO_FIFO_FULL)
        {
            debug_printf("%s full\n", direction);
        }
        *fifo_state = AUDIO_FIFO_FULL;
    }
    else 
    {
        if (*fifo_state == AUDIO_FIFO_EMPTY)
        {
            *fifo_state = AUDIO_FIFO_FILLING;
            debug_printf("%s filling\n", direction);
        }
        // If the we are within half a nominal packet size we are good
        else if (*fifo_state == AUDIO_FIFO_FILLING && fill_level >= stable_trigger) 
        {
            *fifo_state = AUDIO_FIFO_STABLE;
            debug_printf("%s stable\n", direction);
        }
        else
        {
            // Do nothing we are all good
        }
    }
}

// Handle the FIFO fill level state machine to track when we should start pusing/popping
// to acheive a close to half full fill level on startup
// returns true if samples are valid or false if not
static inline __attribute__((always_inline)) bool check_fifo_state_after_pop(audio_fifo_state_t *fifo_state, const fifo_ret_t ret, const int fill_level, const int stable_trigger, const char *direction)
{
    if (ret != FIFO_SUCCESS) 
    {
        if (*fifo_state != AUDIO_FIFO_EMPTY)
        {
            debug_printf("%s empty\n", direction);
        }
        *fifo_state = AUDIO_FIFO_EMPTY;

        return false; // tell caller popped samples are invalid
    }
    else // FIFO pop OK
    {
        if (*fifo_state == AUDIO_FIFO_FULL)
        {
            *fifo_state = AUDIO_FIFO_EMPTYING;
            debug_printf("%s emptying\n", direction);
        }
        // If emptying and we are stable_trigger we can shift to the stable state for next time
        else if(*fifo_state == AUDIO_FIFO_EMPTYING)
        {
            if(fill_level <= stable_trigger)
            {
                *fifo_state = AUDIO_FIFO_STABLE;
                debug_printf("%s stable\n", direction);
            }
        }
        // We are stable or filling which means we can say samples are valid
        else
        {
           return true;
        }
    }

    return false; // tell caller popped samples are invalid
}

