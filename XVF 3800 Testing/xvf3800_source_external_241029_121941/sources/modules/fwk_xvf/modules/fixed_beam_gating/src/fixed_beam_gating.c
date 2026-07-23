// Copyright 2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include <stdbool.h>
#include <string.h>

#include "fixed_beam_gating.h"

#define FIXED_BEAM_0 0
#define FIXED_BEAM_1 1

static bool spenergy_vad_gating_ref(single_beam_gate_vad_t *state,
                                    const float in_spenergy)
{
    static const float peak_energy_alpha = 0.999;
    static const float spenergy_alpha = 0.9;
    static const float spenergy_threshold = 0.002;
    static const float spenergy_absolute_threshold = 50000;
    static const float spenergy_absolute_max = 1e6;
    static const float hold_threshold = 20;

    if (in_spenergy > state->smooth_spenergy)
    {
        state->smooth_spenergy = in_spenergy;
    }
    else
    {
        state->smooth_spenergy = state->smooth_spenergy * spenergy_alpha;
    }

    if (state->smooth_spenergy > state->peak_spenergy)
    {
        state->peak_spenergy = state->smooth_spenergy;
    }
    else
    {
        state->peak_spenergy = state->peak_spenergy * peak_energy_alpha;
    }

    if (state->peak_spenergy > spenergy_absolute_max)
    {
        state->peak_spenergy = spenergy_absolute_max;
    }

    const float threshold_spenergy = spenergy_threshold * state->peak_spenergy;

    if ((state->smooth_spenergy > threshold_spenergy) &&
        (state->smooth_spenergy > spenergy_absolute_threshold))
    {
        state->hold_timer = hold_threshold;
    }
    else
    {
        state->hold_timer -= 1;
    }

    bool retval;
    if (state->hold_timer <= 0)
    {
        retval = false;
        state->hold_timer = 1;
    }
    else
    {
        retval = true;
    }
    return retval;
}

static void beam_selection(bool beam_gates[2],
                           float beam_spenergies[2])
{
    // Set this such that the VAD does not return 1 in silence
    static const float spenergy_absolute_threshold = 50000;
    static int last_beam = 0;

    if (beam_gates[0] && beam_gates[1])
    {
        int other_beam = last_beam ^ 1; // 0 -> 1, 1 -> 0
        if (beam_spenergies[other_beam] > beam_spenergies[last_beam] &&
            beam_spenergies[other_beam] > spenergy_absolute_threshold)
        {
            beam_gates[last_beam] = false;
            last_beam = other_beam;
        }
        else
        {
            beam_gates[other_beam] = false;
        }
    }
}

void fixed_beam_gating(gate_vad_state_t *state,
                       int number_of_samples,
                       float *beams[4],
                       float spenergies[4])
{
    bool beam_gates[2];

    float beam_0_spenergy = spenergies[FIXED_BEAM_0];
    single_beam_gate_vad_t *beam_0_state = &(state->beams[0]);

    float beam_1_spenergy = spenergies[FIXED_BEAM_1];
    single_beam_gate_vad_t *beam_1_state = &(state->beams[1]);

    beam_gates[0] = spenergy_vad_gating_ref(beam_0_state, beam_0_spenergy);
    beam_gates[1] = spenergy_vad_gating_ref(beam_1_state, beam_1_spenergy);

    // Remove this function call if mutually exclusive beams are undesirable.
    beam_selection(beam_gates, (float[]){beam_0_spenergy, beam_1_spenergy});

    if (!beam_gates[0])
    {
        memset(beams[FIXED_BEAM_0], 0, sizeof(float) * number_of_samples);
    }
    if (!beam_gates[1])
    {
        memset(beams[FIXED_BEAM_1], 0, sizeof(float) * number_of_samples);
    }
}
