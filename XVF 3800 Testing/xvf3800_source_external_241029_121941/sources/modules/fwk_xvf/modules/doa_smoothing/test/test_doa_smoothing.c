// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include "unity.h"

#include "doa_smoothing.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#include <xcore/hwtimer.h>

#define _STRINGIFY(f) #f
#define STRINGIFY(f) _STRINGIFY(f)

// file names set during build
#define INPUT_FILE_STR STRINGIFY(DOA_SMOOTHING_INPUT_FILE)
#define OUTPUT_FILE_STR STRINGIFY(DOA_SMOOTHING_EXPECTED_OUTPUT_FILE)

static FILE* f_input_vec;
static FILE* f_output_vec;

void setUp(void) {
    f_input_vec = fopen(INPUT_FILE_STR, "r");
    f_output_vec = fopen(OUTPUT_FILE_STR, "r");
}

void tearDown(void) {
    fclose(f_input_vec);
    fclose(f_output_vec);
}


/// Reads the next line of the inputs files and converts to floats.
static bool get_next_input(float* doa, float* spenergy, float* expected) {
    char read_buf[1000];
    char* line = fgets(read_buf, sizeof(read_buf), f_input_vec);
    if(!line) {
        return false;
    }
    char* vals[9];  // no. vals per row
    vals[0] = line;
    // split the line on spaces
    for(int i = 1; *line != '\0'; ++line) {
        if(*line == ' ') {
            *line = '\0';
            vals[i] = line + 1;
            ++i;
        }
    }
    // for each beam
    for(int i = 0; i < 4; ++i) {
        doa[i] = atof(vals[1 + (2*i)]);
        spenergy[i] = atof(vals[2 + (2*i)]);
    }

    line = fgets(read_buf, sizeof(read_buf), f_output_vec);
    *expected = atof(line);
    return true;
}

/// Compare C implementation against python. This is done by reading input and expected
/// output test vectors from files which were generated using ../python/generate_test_vectors.py
/// and running them through the C implementation.
void test_doa_smoothing( void ) {
    doa_smoothing_t state = DOA_SMOOTHING_INITIALISER;
    float in_az[4];
    float in_spenergy[4];
    float expected;

    uint32_t worst_time = 0;

    while(get_next_input(in_az, in_spenergy, &expected)) {
        uint32_t start = get_reference_time();
        float out = doa_smoothing(&state, in_az, in_spenergy);
        uint32_t took = get_reference_time() - start;
        if(took > worst_time) {
            worst_time = took;
        }

        TEST_ASSERT_EQUAL(expected, out);
    }
    
    printf("worst case ticks: %lu\n", worst_time);
}
