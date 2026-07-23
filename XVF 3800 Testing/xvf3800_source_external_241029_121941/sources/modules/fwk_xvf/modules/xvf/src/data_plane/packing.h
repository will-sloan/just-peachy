// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
///
/// A set of helper functions for detecting and manipulating packed samples.
/// Supports 16kHz 6ch <-> 48kHz 2ch and 32kHz 6ch 16b <-> 48kHz 2ch 32b.
///

#ifndef PACKING_H
#define PACKING_H

#include "i2s_task.h"
#include <stdint.h>
#include <stdbool.h>

// Union for re-interpreting a buffer of 6 x 32b signals as 12 x 16b signals
typedef union packed_samps_32_16_t{
    int32_t samps_32[2][3];
    int16_t samps_16[2][3][2]; // 2 channels, 3 slots, 2 short word positions
}packed_samps_32_16_t;


STATIC_INLINE int32_t mask_and_set_LSB(int32_t input, uint8_t bitres)
{
    xassert(bitres <= 32);
    const uint32_t bitshift = 32 - bitres;

    input &= (0xFFFFFFFF << bitshift);
    input |= (0x00000001 << bitshift);

    return input;
}

STATIC_INLINE int32_t mask_and_unset_LSB(int32_t input, uint8_t bitres)
{
    xassert(bitres <= 32);
    const uint32_t bitshift = 32 - bitres;

    input &= (0xFFFFFFFE << bitshift);

    return input;
}

/// apply packing algorithm to a sample collection
STATIC_INLINE void pack(sample_collection_t * packable_structure, uint8_t in_bitres)
{
    packable_structure->samples[0] = mask_and_unset_LSB(packable_structure->samples[0], in_bitres);
    packable_structure->samples[1] = mask_and_set_LSB(packable_structure->samples[1], in_bitres);
    packable_structure->samples[2] = mask_and_set_LSB(packable_structure->samples[2], in_bitres);
}

/// apply double packing algorithm to a sample collection which packs 2 timeframes of 6 x 16b samples @ 32kHz
/// into a stereo 32b signal at 48kHz.

STATIC_INLINE void pack_double(sample_collection_t * packable_structure, sample_collection_t two_unpacked_frames[2][AUDIO_TO_I2S_NUM_CHANNELS])
{
    // Reinterpret output as 16b
    packed_samps_32_16_t *samps = (packed_samps_32_16_t *) packable_structure;

    // Left out, slot 0
    samps->samps_16[0][0][1] = (two_unpacked_frames[0][0].samples[0] >> 16) & 0xfffe;
    samps->samps_16[0][0][0] = (two_unpacked_frames[1][0].samples[0] >> 16) & 0xfffe;

    // Right out, slot 0
    samps->samps_16[1][0][1] = (two_unpacked_frames[0][1].samples[0] >> 16) & 0xfffe;
    samps->samps_16[1][0][0] = (two_unpacked_frames[1][1].samples[0] >> 16) & 0xfffe;

    // Left out, slot 1
    samps->samps_16[0][1][1] = (two_unpacked_frames[0][0].samples[1] >> 16) | 0x0001;
    samps->samps_16[0][1][0] = (two_unpacked_frames[1][0].samples[1] >> 16) | 0x0001;

    // Right out, slot 1
    samps->samps_16[1][1][1] = (two_unpacked_frames[0][1].samples[1] >> 16) | 0x0001;
    samps->samps_16[1][1][0] = (two_unpacked_frames[1][1].samples[1] >> 16) | 0x0001;

    // Left out, slot 2
    samps->samps_16[0][2][1] = (two_unpacked_frames[0][0].samples[2] >> 16) | 0x0001;
    samps->samps_16[0][2][0] = (two_unpacked_frames[1][0].samples[2] >> 16) | 0x0001;

    // Right out, slot 2
    samps->samps_16[1][2][1] = (two_unpacked_frames[0][1].samples[2] >> 16) | 0x0001;
    samps->samps_16[1][2][0] = (two_unpacked_frames[1][1].samples[2] >> 16) | 0x0001;
}

STATIC_INLINE void unpack(sample_collection_t * packed_samples, int32_t num_mics, int32_t num_far, int32_t* raw_mics, int32_t* far_end)
{
    // We assume that packed_samples is a pointer to a 2-wide array of sample_collection_t.
    // We assume that packed_samples[0] contains {reference, mic0, mic2}, and that packed_samples[1] contains {unused, mic1, mic3}

    far_end[0] =  packed_samples[0].samples[0];
    raw_mics[0] = packed_samples[0].samples[1];
    raw_mics[1] = packed_samples[1].samples[1];
    raw_mics[2] = packed_samples[0].samples[2];
    raw_mics[3] = packed_samples[1].samples[2];
}

STATIC_INLINE void unpack_double(sample_collection_t two_unpacked_frames[2][AUDIO_TO_I2S_NUM_CHANNELS], sample_collection_t * packable_structure)
{
    // Reinterpret input as 16b
    packed_samps_32_16_t *samps = (packed_samps_32_16_t *) packable_structure;

    // Left out, slot 0
    two_unpacked_frames[0][0].samples[0] = ((int32_t)samps->samps_16[0][0][1] << 16) & 0xfffe0000;
    two_unpacked_frames[1][0].samples[0] = ((int32_t)samps->samps_16[0][0][0] << 16) & 0xfffe0000;

    // Right out, slot 0
    two_unpacked_frames[0][1].samples[0] = ((int32_t)samps->samps_16[1][0][1] << 16) & 0xfffe0000;
    two_unpacked_frames[1][1].samples[0] = ((int32_t)samps->samps_16[1][0][0] << 16) & 0xfffe0000;

    // Left out, slot 1
    two_unpacked_frames[0][0].samples[1] = ((int32_t)samps->samps_16[0][1][1] << 16) & 0xfffe0000;
    two_unpacked_frames[1][0].samples[1] = ((int32_t)samps->samps_16[0][1][0] << 16) & 0xfffe0000;

    // Right out, slot 1
    two_unpacked_frames[0][1].samples[1] = ((int32_t)samps->samps_16[1][1][1] << 16) & 0xfffe0000;
    two_unpacked_frames[1][1].samples[1] = ((int32_t)samps->samps_16[1][1][0] << 16) & 0xfffe0000;

    // Left out, slot 2
    two_unpacked_frames[0][0].samples[2] = ((int32_t)samps->samps_16[0][2][1] << 16) & 0xfffe0000;
    two_unpacked_frames[1][0].samples[2] = ((int32_t)samps->samps_16[0][2][0] << 16) & 0xfffe0000;

    // Right out, slot 2
    two_unpacked_frames[0][1].samples[2] = ((int32_t)samps->samps_16[1][2][1] << 16) & 0xfffe0000;
    two_unpacked_frames[1][1].samples[2] = ((int32_t)samps->samps_16[1][2][0] << 16) & 0xfffe0000;

}


static inline uint32_t is_packed_frame_marked(const int32_t * sample_buffer, size_t num_in, uint8_t bitres)
{
    // Only return true if all samples in this frame have 1 as LSB.
    xassert(bitres <= 32);

    const uint32_t bitmask = (0x00000001 << (32 - bitres));
    uint32_t marked = bitmask;

    for (int channel = 0; channel < num_in; channel++)
    {
        marked &= (sample_buffer[channel] & bitmask);
    }
    return marked;
}

static inline int32_t remove_marker(int32_t input, uint8_t bitres)
{
    xassert(bitres <= 32);
    const uint32_t bitshift = 32 - bitres;

    input &= (0xFFFFFFFE << bitshift);

    return input;
}

static inline void store_valid_packed_samples(i2s_callback_args_t* cb_args, size_t position, uint8_t out_bitres, size_t num_in, const int32_t* sample_buf)
{
    for (int channel = 0; channel < num_in; channel++)
    {
        cb_args->packed_input_buffer[cb_args->packed_input_buffer_number][channel][position] = remove_marker(sample_buf[channel], out_bitres);
    }
}

static inline void assemble_valid_packed_packet(i2s_callback_args_t *cb_args, size_t num_in, const int32_t *sample_buf, uint8_t out_bitres)
{
    uint32_t *packed_input_stage = &cb_args->packed_input_stage;
    uint32_t *packed_input_buffer_number = &cb_args->packed_input_buffer_number;
    bool *packed_input_valid = &cb_args->packed_input_valid;
    uint32_t *packed_input_buffer_ready = &cb_args->packed_input_buffer_ready;

    enum {
        Ref_Unused,
        Mic0_Mic1,
        Mic2_Mic3
    };

    // The format we expect is {ref, mic 0, mic 2} on the first input, {unused, mic 1, mic 3} on the second input.
    switch (*packed_input_stage)
    {
    case Ref_Unused:
        // We need this to be unmarked - if it is marked, we are not synched and should discard.
        if (!is_packed_frame_marked(sample_buf, num_in, out_bitres))
        {
            // If it's unmarked, we have sync - start packing buffers.
            store_valid_packed_samples(cb_args, 0, out_bitres, num_in, sample_buf);
            *packed_input_stage = Mic0_Mic1;
            *packed_input_valid = true;
        }
        else
        {
            // If it's marked, discard it.
            *packed_input_valid = false;
        }
        break;
    case Mic0_Mic1:
        // If we've been synched, check to make sure we're still synched - this packet should be marked
        if (is_packed_frame_marked(sample_buf, num_in, out_bitres))
        {
            // If it's marked, we remain synched - continue packing buffers
            store_valid_packed_samples(cb_args, 1, out_bitres, num_in, sample_buf);
            *packed_input_stage = Mic2_Mic3;
        }
        else
        {
            // This is an unmarked sample, so could be the start of the next valid frame
            store_valid_packed_samples(cb_args, 0, out_bitres, num_in, sample_buf);
            // don't change state as the next sample could be Mic0_Mic1
            // don't change buffer number as the current one was never ready
        }
        break;
    case Mic2_Mic3:
        // If we've been synched, check to make sure we're still synched - this packet should be marked
        if (is_packed_frame_marked(sample_buf, num_in, out_bitres))
        {
            // If it's marked, we remain synched - finish packing buffers
            store_valid_packed_samples(cb_args, 2, out_bitres, num_in, sample_buf);
            // At this point the buffer is complete - mark as such and switch buffers
            *packed_input_buffer_ready = *packed_input_buffer_number + 1; // Sets to 1 or 2 - both are truthy.
                                                                          // but the actual value is used in i2s_task
                                                                          // to as an index as well.
            *packed_input_buffer_number ^= 1;
            *packed_input_valid = false;
            *packed_input_stage = Ref_Unused;
        }
        else {
            // This is an unmarked sample, so could be the start of the next valid frame
            store_valid_packed_samples(cb_args, 0, out_bitres, num_in, sample_buf);
            *packed_input_stage = Mic0_Mic1;

        }
        break;
    default:
        // Unreachable code
        break;
    }
}

#endif // PACKING_H
