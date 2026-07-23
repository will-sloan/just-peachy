// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include "unity.h"

#include "pan_pot.h"

#include <math.h>
#include <stdint.h>
#include <stdbool.h>
#include <xcore/hwtimer.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

void setUp(void) {
    // time() seems to work on xsim.
    srand(time(NULL));
}

void tearDown(void) {
}

static float randf() {
    static const float max = RAND_MAX;
    return rand() / max;
}

static bool isclose(float a, float b, float max_abs_diff) {
    bool res = fabs(a - b) <= max_abs_diff;
    if(!res) printf("%f is not close to %f\n", a, b);
    return res;
}

/// check pan_pot and pan_pot_fast at some precomputed values
void test_pan_pot( void ) {
    struct {
        float angle;
        float expected_ratio[2];
    } tv[] = {
        {M_PI/2, {0.5946035575013605, 0.594603557501360}},
        {M_PI, {0, 1}},
        {0, {1, 0}},
    };
    int n_tv = sizeof(tv) / sizeof(*tv);
    for(int i = 0; i < n_tv; ++i) {
        uint32_t start = get_reference_time();
        pan_pot_ratio_t out = pan_pot(tv[i].angle, 0);
        printf("Took ticks: %lu\n", get_reference_time() - start);

        start = get_reference_time();
        pan_pot_ratio_t out_fast = pan_pot_fast(tv[i].angle, 0);
        printf("Fast took ticks: %lu\n", get_reference_time() - start);

        // float is cast to int without rounding so rasult can be wrong by up to 1
        TEST_ASSERT_TRUE(isclose(tv[i].expected_ratio[0], out.l, 0.00001));
        TEST_ASSERT_TRUE(isclose(tv[i].expected_ratio[1], out.r, 0.00001));

        // fast can be up to 0.3% wrong
        TEST_ASSERT_TRUE(isclose(tv[i].expected_ratio[0], out_fast.l, 0.01));
        TEST_ASSERT_TRUE(isclose(tv[i].expected_ratio[1], out_fast.r, 0.01));
    }
}

/// check pan_pot and pat_pot_fast are always the same
void test_pan_pot_fuzz( void ) {

    for(int i = 0; i < 200; ++i) {
        // generate sunny day in range inputs.
        float angle = randf() * 2 * M_PI;
        float left = randf() * 2 * M_PI;

        pan_pot_ratio_t a = pan_pot(angle, left);
        pan_pot_ratio_t b = pan_pot_fast(angle, left);

        if(!isclose(a.l, b.l, 0.01) 
           || !isclose(a.r, b.r, 0.01)
        ) {
            printf("angle %f\n", angle);
            printf("left %f\n", left);
            printf("a %f %f\n", a.l, a.r);
            printf("b %f %f\n", b.l, b.r);
            TEST_FAIL_MESSAGE("pan_pot and pan_pot_fast gave different results for the above inputs");
        }
    }
}

// run some linear tests with known values. Also checks that l offset is calculated properly
void test_pan_pot_linear( void ) {
    
    struct {
        float angle;
        pan_pot_ratio_t expected;
    } tv[] = {
        {M_PI/2, {0.5, 0.5}},
        {M_PI, {0, 1}},
        {0, {1, 0}},
    };
    int n_tv = sizeof(tv) / sizeof(*tv);

    float l_offset[] = {0, M_PI/4, M_PI/2, M_PI, 3*M_PI/4};
    int n_l_offset = sizeof(l_offset) / sizeof(*l_offset);

    // test some input angles and l offsets
    for(int i = 0; i < n_tv; ++i) {
        for(int j = 0; j < n_l_offset; ++j) {
            float angle = tv[i].angle;
            float offset_angle = fmodf(angle + l_offset[j], 2*M_PI);
            float this_l = l_offset[j];

            uint32_t start = get_reference_time();
            pan_pot_ratio_t out = pan_pot_linear(offset_angle, this_l);
            printf("linear took ticks: %lu\n", get_reference_time() - start);

            // result is cast to an int so could be 1 away from true result 
            TEST_ASSERT_TRUE(isclose(tv[i].expected.l, out.l, 0.00001));
            TEST_ASSERT_TRUE(isclose(tv[i].expected.r, out.r, 0.00001));
        }
    }
}

void test_pan_pot_apply( void ) {
    pan_pot_ratio_t p = {0.25, 0.5};
    int32_t out[2];
    pan_pot_apply(out, &p, 100);
    TEST_ASSERT_EQUAL(25, out[0]);
    TEST_ASSERT_EQUAL(50, out[1]);
}
