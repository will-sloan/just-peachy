// Copyright 2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define GATE_VAD_INITIALISER \
    {                        \
        {                    \
            {                \
                0            \
            }                \
        }                    \
    }

// private struct which is used internally
typedef struct
{
    float smooth_spenergy;
    float peak_spenergy;
    int hold_timer;
} single_beam_gate_vad_t;

typedef struct
{
    single_beam_gate_vad_t beams[2];
} gate_vad_state_t;

/**
 * @brief Mutes each beam if a) spenergy is low or b) it has the lowest energy
 * 
 * @param state State for both of the fixed beams
 * @param number_of_samples Number of samples in a BeClear frame
 * @param beams Array of pointers to frames of \p number_of_samples samples
 * @param spenergies Array of spenergies for each beam
 */
void fixed_beam_gating(gate_vad_state_t *state,
                       int number_of_samples,
                       float *beams[4],
                       float spenergies[4]);
