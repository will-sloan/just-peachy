// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include "user_dsp.h"

#ifndef USE_FAR_END_DSP
    #define USE_FAR_END_DSP 0
#endif

#if USE_FAR_END_DSP
#include "xmath/xmath.h"

// Simple example DSP that processes far end using an EQ. Note the coeffs are correct for 48kHz only
// Each filter_biquad_s32_t can store (up to) 8 biquad filter sections
#define SECTION_COUNT   3

filter_biquad_s32_t filter[BECLEAR_NUMBER_OF_FAR] = {{
    // Number of biquad sections in this filter block
    .biquad_count = SECTION_COUNT,

    // Filter state, initialized to 0
    .state = {{0}},

    // Filter coefficients
    // Section 0: Frequency = 100 Hz, Q Factor = +1.2,  Gain = +6.0dB
    // Section 1: Frequency = 1000 Hz, Q Factor = +0.2, Gain = -6.0dB
    // Section 2: Frequency = 8000 Hz, Q Factor = +1.3, Gain = +6.0dB
    .coef = {
        { Q30(+1.00286226693868),  Q30(+0.86561763867029),  Q30(+1.58124059575259)},
        { Q30(-1.98608850422494),  Q30(-1.44869047773446),  Q30(-1.32398889950623)},
        { Q30(+0.98346660965693),  Q30(+0.59557353208939),  Q30(+0.56062804987035)},
        { Q30(+1.98614845462853),  Q30(+1.44869047773446),  Q30(+0.45958190453639)},
        { Q30(-0.98626892619203),  Q30(-0.46119117075968),  Q30(-0.27746165065311)}
        }
}};


void far_end_dsp(int32_t far_end_samples[BECLEAR_NUMBER_OF_FAR], bool far_end_dsp_enable)
{
    // See note in user_dsp.h and user documentation about timing constraints
    if(far_end_dsp_enable)
    {
        for(int channel = 0; channel < BECLEAR_NUMBER_OF_FAR; channel++)
        {
            far_end_samples[channel] >>= 1; // Simple 6db pre-attenuate to account for gain in filter
            far_end_samples[channel] = filter_biquad_s32(&filter[channel], far_end_samples[channel]);
        }
    } else {
        for(int channel = 0; channel < BECLEAR_NUMBER_OF_FAR; channel++)
        {
            far_end_samples[channel] >>= 1; // Simple 6db attenuate to account for filter gains to give similar apparent volume
        }
    }
}

#else

void far_end_dsp(int32_t far_end_samples[BECLEAR_NUMBER_OF_FAR], bool far_end_dsp_enable)
{
    // Do nothing - samples unmodified
}

#endif

