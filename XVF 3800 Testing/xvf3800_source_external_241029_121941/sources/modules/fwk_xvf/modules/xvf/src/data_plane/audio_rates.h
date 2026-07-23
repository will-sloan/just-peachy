// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

// This file determines the packet sizes to exchange between usb, i2s and audio for both directions

#ifndef __AUDIO_RATES_H
#define __AUDIO_RATES_H

#include "app_conf.h"
#include <xcore/assert.h>

// Number of sample periods worth of data to collect before exchanging with
// I2S when in 48kHz mode
#define NUM_48K_SAMPS_PER_EXCHANGE      3

typedef enum src_packing_mode_t{
    SRC_PACK_1_TO_1,
    SRC_PACK_3_TO_2,
    SRC_PACK_3_TO_1
}src_packing_mode_t;

// Run static pplication checks
#if appconfUSB_ENABLED
    #if ((appconfUSB_OUT_NOMINAL_HZ != appconfLRCLK_NOMINAL_HZ) || (appconfUSB_IN_NOMINAL_HZ != appconfLRCLK_NOMINAL_HZ))
        #error USB rate and I2S rate must be equal
    #endif
#endif

// All of the following values are numbers of samples per channel. Double them for stereo etc.

static inline const size_t get_usb_to_i2s_packet_size(void)
{
    if(appconfUSB_OUT_NOMINAL_HZ == 48000)
    {
        return 3; // Always packets of 3 to support packing and SRC
    }
    else
    {
        return 1; // Single samples because we have the same native rate throughout
    }
}

static inline const size_t get_i2s_to_usb_packet_size(void)
{
    if(appconfUSB_IN_NOMINAL_HZ == 48000)
    {
        return 3; // Always packets of 3 to support packing and SRC
    }
    else
    {
        return 1; // Single samples because we have the same native rate throughout
    }
}


static inline const src_packing_mode_t get_src_packing_mode(void)
{
    if(appconfSHF_NOMINAL_HZ == 16000)
    {
        if(appconfLRCLK_NOMINAL_HZ == 16000)
        {
            return SRC_PACK_1_TO_1;
        }
        else if(appconfLRCLK_NOMINAL_HZ == 48000)
        {
            return SRC_PACK_3_TO_1;
        }
        else
        {
            xassert(0); // UNSUPPORTED appconfSHF_NOMINAL_HZ and appconfLRCLK_NOMINAL_HZ combination
        }
    }
    else if (appconfSHF_NOMINAL_HZ == 32000)
    {
        if(appconfLRCLK_NOMINAL_HZ == 32000)
        {
            return SRC_PACK_1_TO_1;
        }
        else if(appconfLRCLK_NOMINAL_HZ == 48000)
        {
            return SRC_PACK_3_TO_2;
        }
        else
        {
            xassert(0); // UNSUPPORTED appconfSHF_NOMINAL_HZ and appconfLRCLK_NOMINAL_HZ combination
        }
    }
    else
    {
        xassert(0); // UNSUPPORTED appconfSHF_NOMINAL_HZ
    }
}

#endif
