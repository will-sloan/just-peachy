// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// Apply delay to sample-wise data, intended for delaying the reference
/// signal on the input to AEC
///

#ifndef SAMPLE_DELAY_H
#define SAMPLE_DELAY_H

#include <stdint.h>
#include <stddef.h>
#include "timing_debug_defs.h" // STATIC_INLINE def


/// Holds state for the delay, fields should be considered private
typedef struct {
    int32_t* const start;
    int32_t* write;
    int32_t* read;
    int32_t* const end;
    size_t delay_countdown;
    const size_t n_channels;
    const size_t max_delay;   // = (end - start) / n_channels
    size_t current_delay;
} sample_delay_t;

/// Determine required buffer size for this circular buffer
#define SAMPLE_DELAY_BUF_SIZE(N_CHANNELS, MAX_DELAY) (N_CHANNELS * (MAX_DELAY + 1))

/// Initialise a sample_delay_t with a correctly sized buffer and a delay
/// @param BUFFER an int32_t array sized using SAMPLE_DELAY_BUF_SIZE
/// @param N_CHANNELS This represents the number of samples that need to be
///                   delayed each time
/// @param INITIAL_DELAY default delay value
#define SAMPLE_DELAY_INITIALISER(BUFFER, N_CHANNELS, MAX_DELAY, INITIAL_DELAY) { \
    .start = BUFFER, \
    .write = &BUFFER[0], \
    .read = &BUFFER[0], \
    .end = &BUFFER[N_CHANNELS * (MAX_DELAY + 1)], \
    .delay_countdown = INITIAL_DELAY, \
    .n_channels = N_CHANNELS, \
    .current_delay = INITIAL_DELAY, \
    .max_delay = MAX_DELAY }


/// Add samples (in) to the delay buffer and get samples (out). `out` will be
/// the samples that were passed to `in` X samples ago, where X is the current
/// delay configured by delay_state. Note that after initialisation or after 
/// changing the delay the output will be zero until the delay has elapsed.
/// Zero is chosen as it will appear that the audio has stopped.
///
/// @param delay_state An initialised sample_delay_t
/// @param[out] out delayed samples, must point to array of size N_CHANNELS
/// @param[in] in new samples for delay, must point to array of size N_CHANNELS
STATIC_INLINE  void sample_delay_apply(sample_delay_t* delay_state, int32_t* out, const int32_t* in) {
    int32_t* wr = delay_state->write;
    int32_t* re = delay_state->read;

    int i = 0;
    // output valid samples if delay has been reached
    if(0 == delay_state->delay_countdown) {
        do {
            wr[i] = in[i];
            out[i] = re[i];
        } while(++i < delay_state->n_channels);

        re += i;
    }
    // output 0 if not
    else {
        do {
            wr[i] = in[i];
            out[i] = 0;
        } while(++i < delay_state->n_channels);

        delay_state->delay_countdown -= 1;
    }
    wr += i;

    // wrap around indices
    if(re >= delay_state->end) {
        re = delay_state->start;
    }
    if(wr >= delay_state->end) {
        wr = delay_state->start;
    }

    delay_state->write = wr;
    delay_state->read = re;
}


/// Update the delay value to `new_delay` 
/// @return actual delay used, if new_delay is out of range then it will not accepted
size_t sample_delay_change(sample_delay_t* state, size_t new_delay);

/// Get the current delay value
STATIC_INLINE size_t sample_delay_current_delay(sample_delay_t* state) {
    return state->current_delay;
}

#endif // SAMPLE_DELAY_H
