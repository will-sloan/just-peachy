// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#pragma once

// These are used by the dbtomult and fixed point volume scaling calcs
#define USB_AUDIO_VOL_MUL_FRAC_BITS     29
#define USB_AUDIO_VOLUME_FRAC_BITS      8

// Volume feature unit range in decibels
// These are stored in 8.8 values in decibels. Max volume is 0dB which is 1.0 gain because we only attenuate.
#define USB_AUDIO_MIN_VOLUME_DB     ((int16_t)-60  << USB_AUDIO_VOLUME_FRAC_BITS)
#define USB_AUDIO_MAX_VOLUME_DB     ((int16_t)0  << USB_AUDIO_VOLUME_FRAC_BITS)
#define USB_AUDIO_VOLUME_STEP_DB    ((int16_t)1  << USB_AUDIO_VOLUME_FRAC_BITS)
