// Copyright 2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include "pan_pot.h"
#include "pan_pot_lut.h"
#include "xmath/scalar/f32.h"

#include <math.h>
#include <stdint.h>


static float right_as_left(float right) {
    return M_PI - right;
}

static float center_angle(float angle, float left_angle) {
    // 0 is left
    float centered_angle = angle - left_angle;

    // reflect angle at 0 and pi.
    if(centered_angle < 0) {
        centered_angle = -1 * centered_angle;
    }
    if(centered_angle > M_PI) {
        centered_angle = M_PI - (centered_angle - M_PI);
    }
    return centered_angle;
}

static float linear_ratio(float angle) {
    static const float inverse_pi = 1/M_PI;
    return 1 - (inverse_pi * angle);
}

static float constant_power_ratio(float angle) {
    return f32_cos(0.5 * angle);
}

// correct version of pan_pot algorithm
static float minus_4_5_db_left(float angle) {
    const float prod = constant_power_ratio(angle) * linear_ratio(angle);
    // sqrtf beat s32_sqrt from xcore_math
    return sqrtf(prod);
}

pan_pot_ratio_t pan_pot_fast(float angle, float left_angle) {
    float centered_angle = center_angle(angle, left_angle);

    return (pan_pot_ratio_t) {
        .l = pan_pot_lut(centered_angle),
        .r = pan_pot_lut(right_as_left(centered_angle))
    };
}

pan_pot_ratio_t pan_pot(float angle, float left_angle) {
    float centered_angle = center_angle(angle, left_angle);

    return (pan_pot_ratio_t) {
        .l = minus_4_5_db_left(centered_angle),
        .r = minus_4_5_db_left(right_as_left(centered_angle)),
    };
}

pan_pot_ratio_t pan_pot_linear(float angle, float left_angle) {
    float centered_angle = center_angle(angle, left_angle);

    return (pan_pot_ratio_t) {
        .l = linear_ratio(centered_angle),
        .r = linear_ratio(right_as_left(centered_angle)),
    };
}

void pan_pot_apply(int32_t* out, const pan_pot_ratio_t* pot, int32_t sample) {
    out[0] = pot->l * sample;
    out[1] = pot->r * sample;
}
