// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


// This file contains the i2s task and the associated callbacks which handle building
// buffers for SHF, taking samples fom mic_array, sample rate conversion and muxing

#include <stddef.h>
#define DEBUG_UNIT AUDIO_TASK
#ifndef DEBUG_PRINT_ENABLE_AUDIO_TASK
    #define DEBUG_PRINT_ENABLE_AUDIO_TASK 0
#endif
#include "debug_print.h"

#include <print.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <platform.h>
#include <string.h>
#include <math.h>

/* lib_xcore */
#include <xcore/select.h>
#include <xcore/assert.h>
#include <xcore/hwtimer.h>
#include <xcore/port.h>
#include <xcore/clock.h>
#include <xcore/chanend.h>
#include <xscope.h>

/* Library headers */
#include "fifo_chan/rx_fsm.h"
#include "fifo_chan/tx.h"
#include "i2s.h"
#include "mic_array.h"
#include "shf_bypass/shf_bypass.h"

/* App headers */
#include "device_enums.h"
#include "audio_task.h"
#include "data_plane_defaults.h"
#include "i2s_task.h"
#include "shf_wrapper.h"
#include "app_conf.h"
#include "tile_common.h"
#include "audio_cmds.h"
#include "control_interface.h"
#include "mux.h"
#include "timing_debug_defs.h" // STATIC_INLINE def
#include "src_poly.h"
#include "src_ff3_fir_coefs.h"
#include "src_rat_fir_coefs.h"
#include "audio_rates.h"
#include "packing.h"
#include "user_dsp.h"

#ifdef MAX
#undef MAX  // some header file in xmath leaks this convenient name
#endif
#define MAX(a, b) ( ((a) > (b)) ? (a) : (b) )

#ifdef MIN
#undef MIN  // some header file in xmath leaks this convenient name as well
#endif
#define MIN(a, b) ( ((a) < (b)) ? (a) : (b) )

#define TOTAL_CHANNELS_OUT MAX(AUDIO_TO_I2S_NUM_CHANNELS, appconfUSB_CHANNELS_OUT)
#define TOTAL_CHANNELS_IN  MAX(I2S_TO_AUDIO_NUM_CHANNELS, appconfUSB_CHANNELS_IN)

// SRC configuration
#if (appconfLRCLK_NOMINAL_HZ == 48000)
    #define DOWNSAMPLE_FAREND_TO_AM     true
    #define UPSAMPLE_AM_TO_I2S          true
#else
    #define DOWNSAMPLE_FAREND_TO_AM     false
    #define UPSAMPLE_AM_TO_I2S          false
#endif

static unsigned shf_in_buf_num = 0;
static unsigned shf_sample_index = 0;
static shf_input_t shf_input_buf[NUM_SHF_INPUT_BUFFERS] = {{{{0}}}};

static shf_output_t *shf_output_buf = NULL;
static unsigned shf_output_valid = 0;


// Macro to see if port time occurs after now. Returns non zero if so.
#define port_timeafter(NOW, EVENT_TIME) ((int16_t)((EVENT_TIME) - (NOW)) < 0)

// Definition of I2S mux out control type
typedef struct __attribute__((packed)) i2s_out_mux_index_t{
    uint8_t packed[AUDIO_TO_I2S_NUM_CHANNELS];
    mux_index_t indices[AUDIO_TO_I2S_NUM_CHANNELS][SAMPLE_COLLECTION_SIZE];
    uint8_t upsample[AUDIO_TO_I2S_NUM_CHANNELS];
}i2s_out_mux_index_t;


typedef enum audio_rx_state_t {NEED_DATA, GOT_DATA, I2S_STOPPED} audio_rx_state_t;

/// largest buf in the mux
#define LARGEST_MUX_BUF_SIZE 12

/// returns most recent azimuth values
STATIC_INLINE float* current_azimuths() {
    return (shf_output_valid) ? shf_output_buf->azimuths : NULL;
}

/// returns most recent azimuth values
STATIC_INLINE float* current_spenergy() {
    return (shf_output_valid) ? shf_output_buf->spenergy : NULL;
}

/// returns most recent azimuth values
STATIC_INLINE float current_smoothed_doa() {
    return (shf_output_valid) ? shf_output_buf->smoothed_azimuth : NAN;
}

/// @brief Get the next value out of the most recently acquired buffer of processed data.
/// AEC residuals and mics share the same buffer, call this function immediately after
/// push_samps_to_shf to get the latest aec_residuals
STATIC_INLINE void pull_samps_from_shf(int32_t processed_mics[BECLEAR_NUMBER_OF_OUTPUTS],
                                       int32_t aec_residuals[BECLEAR_NUMBER_OF_MICS])
{
    if(shf_output_valid) {
        for(int i = 0; i < BECLEAR_NUMBER_OF_OUTPUTS; i++){
            processed_mics[i] = shf_float32_to_int32_scaled((*shf_output_buf).commsout[i][shf_sample_index]);
        }
        for(int i = 0; i < BECLEAR_NUMBER_OF_MICS; ++i) {
            aec_residuals[i] = shf_float32_to_int32_scaled(shf_input_buf[shf_in_buf_num].mics[i][shf_sample_index]);
        }
    }
    else {
        memset(processed_mics, 0, sizeof(int32_t) * BECLEAR_NUMBER_OF_OUTPUTS);
        memset(aec_residuals, 0, sizeof(int32_t) * BECLEAR_NUMBER_OF_MICS);
    }
    // No buffer increment or flip. Done in AEC task (if needed)
}

/// Zero the microphone and far end signals for a set number of samples.
/// @param[in,out] count Initialise to the number of iterations that the inputs
///                      should be muted. This function will decrement the count
///                      to 0 and mute the signals until it gets there
/// @param[in,out] mics microphone samples, array of size MIC_ARRAY_CONFIG_MIC_COUNT
/// @param n_mics number of elements in the mics array
/// @param[in,out] far_end reference signal of size BECLEAR_NUMBER_OF_FAR
/// @param n_far_end number of elements in the far_end array
STATIC_INLINE void mute_at_boot(uint32_t* count, int32_t* mics, int n_mics, int32_t* far_end, int n_far_end) {
    if(0 != *count) {
        *count -= 1;
        memset(mics, 0, sizeof(*mics) * n_mics);
        memset(far_end, 0, sizeof(*far_end) * n_far_end);
    }
}

/// multiply in array by gain to make out array
STATIC_INLINE void apply_gain(float* out, float* in, const size_t n_elems, float gain) {
    for(int i = 0; i < n_elems; ++i) {
        out[i] = in[i] * gain;
    }
}

/// float to int conversion on an array of floats, out->n_elems
/// used to determine array size
STATIC_INLINE void float_to_mux_buf(mux_source_t* out, float* in) {
    for(int i = 0; i < out->n_elems; ++i) {
        out->buf[i] = shf_float32_to_int32_scaled(in[i]);
    }
}

/// @brief Prepare and accumulate audio samples into a buffer
/// and exchange with aec when a whole block has been accumulated.
///
/// Preparation includes converting to a float, scaled to within range
/// accepted and then applying gain to the microphones.
///
/// @param[in] raw_mics input microphone signal
/// @param[in] far_end input reference signal
/// @param c_audio_to_i2s channel to communicate with shf_wrapper
/// @param mic_gain gain applied to each mic signal after converting to float
///
/// @note this will need rework for issue #178 to allow post gain mics to be output.
/// This has not been considered here as the output mux strategy is not yet known.
STATIC_INLINE void push_samps_to_shf( const float* raw_mics,
                                      const float* far_end,
                                      chanend_t c_audio_to_aec )
{
    for(int i = 0; i < BECLEAR_NUMBER_OF_MICS; i++){
        shf_input_buf[shf_in_buf_num].mics[i][shf_sample_index] = raw_mics[i];
    }
    for(int i = 0; i < BECLEAR_NUMBER_OF_FAR; i++){
        shf_input_buf[shf_in_buf_num].far[i][shf_sample_index] = far_end[i];
    }

    if(++shf_sample_index >= BECLEAR_SAMPLES_PER_FRAME){
        shf_sample_index = 0;

        uint32_t addr_of_shf_input = (uintptr_t)(&shf_input_buf[shf_in_buf_num]);

        // Exchange buffer pointers with AEC
        chan_out_word(c_audio_to_aec, addr_of_shf_input);
        shf_output_buf = (shf_output_t*)(uintptr_t) chan_in_word(c_audio_to_aec);
        xassert(NULL != shf_output_buf);
        shf_output_valid = (NULL == shf_output_buf) ? 0 : 1;

        shf_in_buf_num ^= (NUM_SHF_INPUT_BUFFERS - 1); // Flip input buffer if double, else do nothing if single buffer
    }
}

/// In place multiply by 3, with saturation
static int32_t saturate_x3(int32_t sample)
{
    sample = MIN(sample, 715827882);  // INT_MAX/3
    sample = MAX(sample, -715827882);  // INT_MIN/3
    return sample * 3;
}

/// in place upsampling, `state` must be an array of size `SRC_FF3_FIR_TAPS_PER_PHASE`
STATIC_INLINE void upsample_3x(sample_collection_t* collection, int page)
{
    static int32_t state_us[AUDIO_TO_I2S_NUM_CHANNELS][SRC_FF3_FIR_TAPS_PER_PHASE] ALIGNMENT(8);

    // Do the upsampling. The original sample is overwritten in the first step.
    // Multiplying by 3 cause it's a three-phase upsampling, and avoiding overflow
    collection->samples[0] = saturate_x3(fir_s32_32t(state_us[page], src_ff3_fir_coefs[2], collection->sample));
    collection->samples[1] = saturate_x3(conv_s32_32t(state_us[page], src_ff3_fir_coefs[1]));
    collection->samples[2] = saturate_x3(conv_s32_32t(state_us[page], src_ff3_fir_coefs[0]));
}

STATIC_INLINE void downsample_3x(sample_collection_t * collection, int page)
{
    // We only downsample inputs, so the delay line has TOTAL_CHANNELS_IN pages.
    static int32_t state_ds[TOTAL_CHANNELS_IN][SRC_FF3_FIR_NUM_PHASES][SRC_FF3_FIR_TAPS_PER_PHASE] ALIGNMENT(8);
    int64_t partial_sum = 0;

    // Do the downsampling
    partial_sum += fir_s32_32t(state_ds[page][0], src_ff3_fir_coefs[0], collection->samples[0]);
    partial_sum += fir_s32_32t(state_ds[page][1], src_ff3_fir_coefs[1], collection->samples[1]);
    partial_sum += fir_s32_32t(state_ds[page][2], src_ff3_fir_coefs[2], collection->samples[2]);

    collection->sample = (int32_t)partial_sum;
}

/// @brief Takes an array of sample collections and unpacks their sample members into the provided array; downsampling is performed first if required.
/// @param sample_count Length of the two arrays - both arrays must be the same length
/// @param do_downsample If true, downsamples all sample collections from 48kHz to 16kHz, else just copies a single sample
/// @param collections Array of sample collections
/// @param data_src Array of samples that have been sample rate converted
/// @param data_native The raw far end samples with no SRC
STATIC_INLINE void unmake_collection_array_and_downsample(int32_t sample_count,
                                                          bool do_downsample,
                                                          sample_collection_t* collections,
                                                          int32_t* data_src,
                                                          int32_t* data_native)
{
    for (int collection_idx = 0; collection_idx < sample_count; collection_idx++)
    {
        if (do_downsample)
        {
            // Make copy of native sample rate (fixed factor of 3 copy)
            for(int sample_num = 0; sample_num < SAMPLE_COLLECTION_SIZE; sample_num++){
                // Make sure we index into the flat storage properly
                unsigned native_idx = sample_count * sample_num + collection_idx;
                data_native[native_idx] = collections[collection_idx].samples[sample_num];

                // reduce by 6dB for headroom before downsampling
                // this could be reduced to 3.5 dB
                collections[collection_idx].samples[sample_num] /= 2;
            }
            // Produce downsampled version (fixed factor of 3 downsample)
            downsample_3x(&collections[collection_idx], collection_idx);
        } else {
            // Just copy a single sample across since the rates match
            data_native[collection_idx] = collections[collection_idx].sample;
            // half reference to match 48kHz behaviour.
            collections[collection_idx].sample /= 2;
            
        }
        data_src[collection_idx] = collections[collection_idx].sample;
    }
}


/// @brief Takes an array of sample collections and packs into two frames. Downsampling is performed first always.
///        This is called every iteration of the audio loop and receives a frame from I2S every other time.
///        If the packed flag is detected then this returns and allows the caller to handle packed data
/// @param sample_count Length of the two arrays - both arrays must be the same length
/// @param do_downsample Assumed to always be true, downsamples all sample collections from 48kHz to 32kHz
/// @param audio_frame_48 Array of sample collections
/// @param new_data_state whether or not fresh 48k data has been received
/// @param data_src Array of samples that have been sample rate converted
/// @param data_native The raw far end samples with no SRC
STATIC_INLINE bool unmake_collection_array_and_downsample_swb(int32_t sample_count,
                                                              bool do_downsample,
                                                              i2s_to_audio_data_t *i2s_to_audio_data,
                                                              audio_rx_state_t new_data_state,
                                                              int32_t* data_src,
                                                              int32_t* data_native)
{
    static bool got_packed = false; // initial value. This state is held when receiving frames

    // Only update this flag when we receive a valid packet
    if (i2s_to_audio_data != NULL){
        got_packed = i2s_to_audio_data->was_packed;
    }

    // If packed we return immediately with no SRC
    if (got_packed){
        return true;
    }
    else if (do_downsample)
    {
        sample_collection_t *audio_frame_48 = i2s_to_audio_data->far_end_samples_i2s;

        // Because we downsample to two samples every other input packet of 3 inout samples, we need to store the second sample
        static int32_t second_sample_src[TOTAL_CHANNELS_IN] = {0};

        for (int collection_idx = 0; collection_idx < sample_count; collection_idx++)
        {
            if (new_data_state == GOT_DATA){
                // Make copy of native sample rate (fixed factor of 3 copy)
                for(int sample_num = 0; sample_num < SAMPLE_COLLECTION_SIZE; sample_num++){
                    // Make sure we index into the flat storage properly
                    unsigned native_idx = sample_count * sample_num + collection_idx;
                    data_native[native_idx] = audio_frame_48[collection_idx].samples[sample_num];
            
                    // reduce by 6dB for headroom before downsampling
                    // this could be reduced to 3.5 dB
                    audio_frame_48[collection_idx].samples[sample_num] /= 2;
                }

                static int32_t ALIGNMENT(8) state_ds[TOTAL_CHANNELS_IN][SRC_RAT_FIR_TAPS_PER_PHASE_DS] = {{0}};

                // Produce downsampled version (fixed factor of 3/2 downsample);
                push_s32_48t(state_ds[collection_idx], audio_frame_48[collection_idx].samples[0]);
                data_src[collection_idx] = fir_s32_48t(state_ds[collection_idx], src_rat_fir_ds_coefs[0], audio_frame_48[collection_idx].samples[1]) * 2;
                second_sample_src[collection_idx] = fir_s32_48t(state_ds[collection_idx], src_rat_fir_ds_coefs[1], audio_frame_48[collection_idx].samples[2]) * 2;

            } else if (new_data_state == NEED_DATA){
                data_src[collection_idx] = second_sample_src[collection_idx];
            } else { // must be in I2S_STOPPED state
                data_src[collection_idx] = 0;
            }
        }
    } else {
        xassert(0); // This should never happen since we only ever call this if we are in 3/2 ratio
    }
    return false;
}


/// process the sample collection in the required way given the options selected for
/// this channel, this will upsample, pack, or for 16khz do nothing based on the
/// parameters. upsample must be true to enable packing.
/// @param[in,out] collection data that is processed in place
/// @param[in]     chan number of channel to upsample
/// @param packing if true, the collection will be packed, ignored if output
///        is not 48k
/// @param output_48k set to true if this channel expects a 48k output
STATIC_INLINE void prepare_output_channel_wb(sample_collection_t* collection,
                                            int chan,
                                            bool do_packing,
                                            bool do_upsample)
{
    // Packing takes precidence as an output option over upsample
    if(do_packing)
    {
        uint8_t bitres = 0;

    if(appconfUSB_ENABLED) {
        get_usb_bit_depth(&bitres, NULL); // We only care here about the IN endpoint bit depth (device-to-host)
    } else {
        bitres = appconfINT_PACKED_BIT_DEPTH;
    }
    
        pack(collection, bitres);
    }
    else if (do_upsample)
    {
        upsample_3x(collection, chan);
    }
    else {
        // nothing to do, the desired sample is in the correct place
    }
}

/// process the sample collection in the required way given the options selected for
/// this channel, this will upsample, pack, or for 32khz do nothing based on the
/// parameters. upsample must be true to enable packing.
/// @param[out] collection data that is to be written to
/// @param[in] two_audio_frames Two complete frames of 2/6 (packing) samples to be packed
/// @param[in]     chan number of channel to upsample
/// @param packing if true, the collection will be packed, ignored if output
///        is not 48k
/// @param output_48k set to true if this channel expects a 48k output
STATIC_INLINE void prepare_output_channel_swb(sample_collection_t collection[AUDIO_TO_I2S_NUM_CHANNELS],
                                              sample_collection_t two_audio_frames[2][AUDIO_TO_I2S_NUM_CHANNELS],
                                              int chan,
                                              bool do_packing,
                                              bool do_upsample)
{
    static int32_t ALIGNMENT(8) state_us[AUDIO_TO_I2S_NUM_CHANNELS][SRC_RAT_FIR_TAPS_PER_PHASE_US] = {{0}};

    // Packing takes precidence as an output option over upsample
    if(do_packing)
    {
        pack_double(collection, two_audio_frames);
    }
    else if (do_upsample)
    {
        // We do not use src_rat_3_2_96t_us because we need to pick samples from consecutive frames and the samples are not contiguous in memory
        collection[chan].samples[0] = saturate_x3(fir_s32_32t(state_us[chan], src_rat_fir_us_coefs[0], two_audio_frames[0][chan].samples[0]));
        collection[chan].samples[1] = saturate_x3(conv_s32_32t(state_us[chan], src_rat_fir_us_coefs[2]));
        collection[chan].samples[2] = saturate_x3(fir_s32_32t(state_us[chan], src_rat_fir_us_coefs[1], two_audio_frames[1][chan].samples[0]));
    }
    else {
        xassert(0); // We should never get here for SWB because this helper only handles 3/2 output to SHF rate
    }
}

/// receive from i2s and process, returns true if mics were filled with unpacked data,
/// returns false if received data was not packed, or if i2s didn't send anything
STATIC_INLINE bool receive_from_i2s(fifo_chan_rx_fsm_t* rx_fsm,
                                    int32_t* mics,
                                    uint32_t n_mics,
                                    int32_t* far_end_dsp_rate,
                                    uint32_t n_far_end,
                                    int32_t* far_end_native_rate)
{
    bool got_packed = false;

    if(get_src_packing_mode() == SRC_PACK_3_TO_2)
    {
        // These two frames represent the input sample collection for two sample periods
        // which will either be packed or upsampled.
        static sample_collection_t two_audio_frames[2][TOTAL_CHANNELS_IN] = {{{0}}};

        static audio_rx_state_t new_data_state = I2S_STOPPED;
        i2s_to_audio_data_t* i2s_to_audio_data = NULL;

        // Move on the rx'd data state machine.
        switch(new_data_state){
            // Do this state first to optimise for heaviest processing case
            case GOT_DATA:              
                new_data_state = NEED_DATA;
                // printchar('n');
                break;

            case NEED_DATA:
                i2s_to_audio_data = fifo_chan_rx_fsm_receive(rx_fsm);
                if(NULL == i2s_to_audio_data){
                    new_data_state = I2S_STOPPED;
                    // printchar('s');
                } else {
                    new_data_state = GOT_DATA;
                    // printchar('g');
                }
                break;

            case I2S_STOPPED:
                i2s_to_audio_data = fifo_chan_rx_fsm_receive(rx_fsm);
                if(NULL != i2s_to_audio_data){
                    new_data_state = GOT_DATA;
                    // printchar('g');
                } else{
                    // printchar('s');
                }
                break;
        }

        // Always call this since it containts state for two 32k sample periods
        got_packed = unmake_collection_array_and_downsample_swb(n_far_end,
                                                                DOWNSAMPLE_FAREND_TO_AM,
                                                                i2s_to_audio_data,
                                                                new_data_state,
                                                                far_end_dsp_rate,
                                                                far_end_native_rate);

        if(got_packed){
            if(new_data_state == GOT_DATA){
                unpack_double(two_audio_frames, i2s_to_audio_data->far_end_samples_i2s);
                // Copy the first frame into the working buffer
                unpack(two_audio_frames[0], BECLEAR_NUMBER_OF_MICS, BECLEAR_NUMBER_OF_FAR, mics, far_end_dsp_rate);
            } else if (new_data_state == NEED_DATA) {
                // Copy the second frame into the working buffer
                unpack(two_audio_frames[1], BECLEAR_NUMBER_OF_MICS, BECLEAR_NUMBER_OF_FAR, mics, far_end_dsp_rate);
            } else {
                memset(far_end_dsp_rate, 0, sizeof(far_end_dsp_rate[0]) * BECLEAR_NUMBER_OF_FAR);
                memset(mics, 0, sizeof(mics[0]) * BECLEAR_NUMBER_OF_MICS);
            }
        }

        if(NULL != i2s_to_audio_data){
            // return fifo credit back to i2s after we have used the samples
            fifo_chan_rx_fsm_done(rx_fsm);
        }

        return got_packed;
    }
    else
    {
        xassert(n_mics >= I2S_TO_AUDIO_NUM_CHANNELS);
        i2s_to_audio_data_t* i2s_to_audio_data = fifo_chan_rx_fsm_receive(rx_fsm);
        if( NULL != i2s_to_audio_data ) {
            if(i2s_to_audio_data->was_packed)
            {
                got_packed = true;
                // If we're running a packed input, the required data will have been sent from the I2S task.
                // Unmake the collections into the correct arrays.
                unpack(i2s_to_audio_data->far_end_samples_i2s, BECLEAR_NUMBER_OF_MICS, BECLEAR_NUMBER_OF_FAR, mics, far_end_dsp_rate);
            } else {
                unmake_collection_array_and_downsample(n_far_end,
                                                       DOWNSAMPLE_FAREND_TO_AM,
                                                       i2s_to_audio_data->far_end_samples_i2s,
                                                       far_end_dsp_rate,
                                                       far_end_native_rate);
            }
            // return fifo credit back to i2s
            fifo_chan_rx_fsm_done(rx_fsm);
        }
        else {
            // I2S stopped, or rx_fsm synchronising
            memset(far_end_dsp_rate, 0, sizeof(*far_end_dsp_rate) * n_far_end);
            memset(mics, 0, sizeof(*mics) * n_mics);
        }

        return got_packed;
    }
}

// Call output mux and assemble samples to be transmitted. If required, do upsampling or packing and
// push to the FIFO to be rx'd by I2S
STATIC_INLINE void send_to_i2s( mux_source_t *buffers,
                                i2s_out_mux_index_t *i2s_out_mux_index,
                                audio_task_params_t *audio_task_params,
                                fifo_chan_tx_t *fifo_to_i2s){

    // We need to treat SWB differently when outputting 48kHz becuase we need to build consecutive frames
    // to support either the 3/2 upsampling or packing a frame of 12 samples which is 6 chan x 2 sample periods
    if(get_src_packing_mode() == SRC_PACK_3_TO_2)
    {
        static enum {GOT_BUF, NEED_BUF} state = NEED_BUF;
        static audio_to_i2s_data_t* buf_to_i2s = NULL;

        // These two frames represent the audio output mux collection for two sample periods
        // which will either be packed or upsampled.
        static sample_collection_t two_audio_frames[2][AUDIO_TO_I2S_NUM_CHANNELS] = {{{0}}};

        if(NEED_BUF == state) {
            buf_to_i2s = fifo_chan_tx_next_buf(fifo_to_i2s);
            if(NULL != buf_to_i2s) {
                state = GOT_BUF;

                // Prepare the first of the two 32k samples to I2S
                for(int chan = 0; chan < AUDIO_TO_I2S_NUM_CHANNELS; ++chan) {
                    mux(buffers,
                        two_audio_frames[0][chan].samples,
                        i2s_out_mux_index->indices[chan],
                        SAMPLE_COLLECTION_SIZE);
                }
            } else {
                // I2S stopped processing our send frames likely because I2S clocks stopped and so isn't sending credits. Do nothing.
                if(audio_task_params->audio_to_i2s_overflow == false){
                    debug_printf("Aud+\n");
                    audio_task_params->audio_to_i2s_overflow = true;
                }
            }
        } else {
            // Prepare the second of the two 32k samples to I2S and upsample or pack as needed
            for(int chan = 0; chan < AUDIO_TO_I2S_NUM_CHANNELS; ++chan) {
                mux(buffers,
                    two_audio_frames[1][chan].samples,
                    i2s_out_mux_index->indices[chan],
                    SAMPLE_COLLECTION_SIZE);

                // Only do this ever other sample period because of the 3/2 rate increase
                prepare_output_channel_swb(buf_to_i2s->i2s_tx_samps,
                                           two_audio_frames,
                                           chan,
                                           i2s_out_mux_index->packed[chan],
                                           i2s_out_mux_index->upsample[chan]);
            }                    

            fifo_chan_tx_send(fifo_to_i2s);
            buf_to_i2s = NULL;
            state = NEED_BUF;
        }
    }
    else // Either SRC_PACK_3_TO_1 or SRC_PACK_1_TO_1
    {
        audio_to_i2s_data_t* buf_to_i2s = fifo_chan_tx_next_buf(fifo_to_i2s);
        if(NULL != buf_to_i2s) {
            for(int chan = 0; chan < AUDIO_TO_I2S_NUM_CHANNELS; ++chan) {
                mux(buffers,
                    buf_to_i2s->i2s_tx_samps[chan].samples,
                    i2s_out_mux_index->indices[chan],
                    SAMPLE_COLLECTION_SIZE);

                prepare_output_channel_wb(&buf_to_i2s->i2s_tx_samps[chan],
                                          chan,
                                          i2s_out_mux_index->packed[chan],
                                          i2s_out_mux_index->upsample[chan]);
            }

            fifo_chan_tx_send(fifo_to_i2s);
            audio_task_params->audio_to_i2s_overflow = false;
        }
        else {
            // I2S stopped processing our send frames likely because I2S clocks stopped and so isn't sending credits. Do nothing.
            if(audio_task_params->audio_to_i2s_overflow == false){
                debug_printf("Aud+\n");
                audio_task_params->audio_to_i2s_overflow = true;
            }
        }
    }
}

/// Update the mic and sys delay states with new value
STATIC_INLINE void update_sysdelay(audio_task_params_t* audio_task_params,
                                   audio_mgr_resid_audio_mgr_sys_delay_t* delay) {
    if(*delay < 0) {
        sample_delay_change(&audio_task_params->mic_delay, -*delay);
        sample_delay_change(&audio_task_params->sys_delay, 0);
    }
    else {
        sample_delay_change(&audio_task_params->sys_delay, *delay);
        sample_delay_change(&audio_task_params->mic_delay, 0);
    }
}

/**
 * @brief Audio task control commands handler function.
 *
 * @param pkt_queue             Pointer to the packet queue on which control messages are received.
 * @param lut                   Lookup table pointer for lut based command handling
 * @param lut_size              Size of the control lookup table
 * @param audio_task_params     Pointer to audio task config params
 * @param i2s_params            Pointer to I2S task config params, since these are updated as part of audio task control commands handling.
 */
STATIC_INLINE void do_audio_control(control_pkt_queue_t *pkt_queue,
                                    const control_lut_t *lut,
                                    size_t lut_size,
                                    audio_task_params_t *audio_task_params,
                                    i2s_callback_args_t *i2s_params)
{
    // do_audio_control() max time increases from 87 to 247 ticks on the application_xvf3800_inthost-lr16-pnone-lin-i2c build
    // when using the lut based handler. The increase is more for commands where custom handling is required.
    int32_t num_pkts_processed = 0;

    do
    {
        control_pkt_t *pkt = queue_read_packet(pkt_queue);

        /* code */
        if (pkt != NULL)
        {
            debug_printf("Audio do_control: processing packet %lu\n", pkt->cmd_id);
            if(handle_through_lookup(lut, lut_size, pkt->cmd_id, pkt->payload, pkt->payload_len) != CMD_LOOKUP_SUCCESS)
            {
                // Custom handler
                if (IS_CONTROL_CMD_READ(pkt->cmd_id))
                {
                    control_cmd_t cmd = CONTROL_CMD_CLEAR_READ(pkt->cmd_id);
                    switch(cmd)
                    {
                        case AUDIO_MGR_RESID_AUDIO_MGR_SYS_DELAY:
                            *(audio_mgr_resid_audio_mgr_sys_delay_t*)pkt->payload = sample_delay_current_delay(&audio_task_params->sys_delay) -
                                                                                    sample_delay_current_delay(&audio_task_params->mic_delay);
                            break;
                        default:
                            debug_printf("Handler not found for Audio Mgr command %d\n",pkt->cmd_id);
                            xassert(0);
                    }
                }
                else
                {
                    switch(pkt->cmd_id)
                    {
                        case AUDIO_MGR_RESID_AUDIO_MGR_SYS_DELAY:
                            update_sysdelay(audio_task_params, pkt->payload);
                            break;
                        case AUDIO_MGR_RESID_AUDIO_MGR_RESET_MIN_IDLE_TIME:
                            audio_task_params->min_idle_time = (XS1_TIMER_HZ / appconfSHF_NOMINAL_HZ);
                            break;
                        case AUDIO_MGR_RESID_RESET_MAX_CONTROL_TIME:
                            audio_task_params->max_control_time = 0;
                            break;
                        case AUDIO_MGR_RESID_I2S_RESET_MIN_IDLE_TIME:
                            i2s_params->i2s_reset_min_idle_time = 1; // Actual reset happens in the I2S task
                            break;
                        default:
                            debug_printf("Handler not found for Audio Mgr command %d\n",pkt->cmd_id);
                            xassert(0);
                    }
                }
            }

            // Change status to done at the end
            queue_set_packet_done(pkt_queue);
            num_pkts_processed++;
        }
        else {
            break;
        }
    } while (num_pkts_processed != pkt_queue->depth); // We don't process more than the full queue depth
}


/// if start is set, update current and min based on the current value of the reference
/// clock. idle is calculated as theorecical max - time since start.
STATIC_INLINE void update_idle_time(uint32_t start, uint32_t* current, uint32_t* min) {
    if(0 != start) {
        uint32_t time_since_start = get_reference_time() - start;
        static const uint32_t audio_task_offset = 105; // determined time for ma_frame_rx if this thread
                                                       // does not get blocked by mic_array. Have to account
                                                       // for it here as it is work that this thread does which
                                                       // we are not timing
        static const uint32_t max_audio_time = (XS1_TIMER_HZ / appconfSHF_NOMINAL_HZ) - audio_task_offset;
        *current = max_audio_time - time_since_start;
        if(*current < *min) {
            *min = *current;
        }
    }
}

// Used for debug build. See timing_debug_defs.h
_AUDIO_DEBUG_GLOBAL_DEFS

/// @brief handles main audio loop and exchanges samples with i2s, mic_array, and SHF. Also handles post SHF DSP.
/// Note that this task receives two words over the channel initiall which contain
/// the addresses of the two i2s_exchange_data_t structs used for double buffering
/// the samples exchanged with i2s.
void audio_manager_task(chanend_t c_mic_to_audio,
                        chanend_t c_shf_aec,
                        chanend_t c_audio_to_i2s,
                        chanend_t c_i2s_to_audio,
                        control_pkt_queue_t *control_pkt_queue)
{
    if(get_core_burn_status() != 0){
        SET_FAST_MODE();
    }

    // to support more samples per frame, need to update main loop to
    // poll less often and then make sure the correct samples are referenced
    // in buffers[MUX_RAW_MICS]
    _Static_assert(MIC_ARRAY_CONFIG_SAMPLES_PER_FRAME == 1, "This file requires sample size to be 1");

    mux_source_t buffers[] = {
        [MUX_SILENCE] =              MUX_SOURCE_INIT(LARGEST_MUX_BUF_SIZE),
        [MUX_RAW_MICS] =             MUX_SOURCE_INIT(MIC_ARRAY_CONFIG_SAMPLES_PER_FRAME * MIC_ARRAY_CONFIG_MIC_COUNT),
        [MUX_UNPACKED_MICS] =        MUX_SOURCE_INIT(MIC_ARRAY_CONFIG_MIC_COUNT),
        [MUX_MICS_W_GAIN] =          MUX_SOURCE_INIT(MIC_ARRAY_CONFIG_SAMPLES_PER_FRAME * MIC_ARRAY_CONFIG_MIC_COUNT),
        // I2S received to here so needs to be big enough for both channels
        [MUX_FAR_END] =              MUX_SOURCE_INIT(TOTAL_CHANNELS_IN),
        [MUX_FAR_END_NATIVE] =       MUX_SOURCE_INIT(SAMPLE_COLLECTION_SIZE * TOTAL_CHANNELS_IN),
        [MUX_FAR_END_SYSDELAY] =     MUX_SOURCE_INIT(BECLEAR_NUMBER_OF_FAR),
        [MUX_FAR_END_W_GAIN] =       MUX_SOURCE_INIT(BECLEAR_NUMBER_OF_FAR),
        [MUX_PROCESSED_MICS] =       MUX_SOURCE_INIT(BECLEAR_NUMBER_OF_OUTPUTS),
        [MUX_AEC_RESIDUALS] =        MUX_SOURCE_INIT(BECLEAR_NUMBER_OF_MICS),
        [MUX_ALL_USER_CHANNELS] =    MUX_SOURCE_INIT(BECLEAR_NUMBER_OF_OUTPUTS),
        [MUX_USER_CHOSEN_CHANNELS] = MUX_SOURCE_INIT(USER_DSP_NUM_OUTPUT_CHANNELS),
        [MUX_DELAYED_MICS] =         MUX_SOURCE_INIT(MIC_ARRAY_CONFIG_SAMPLES_PER_FRAME * MIC_ARRAY_CONFIG_MIC_COUNT),
    };
    _Static_assert(MUX_N_SOURCES(buffers) == NUM_MUX_ENTRIES, "Not all mux entries initialised");


    const data_plane_defaults_t* const defaults = data_plane_defaults_get();

    // skip mute at boot for packed input as it is not using real microphone
    uint32_t mute_at_boot_counter = defaults->mic_init_time_samples;

    xassert(defaults->sys_delay <= appconfMAX_SYS_DELAY);
    xassert(defaults->sys_delay >= -appconfMAX_MIC_DELAY);

    // buffer is used by either mic delay or sys delay, we will not support delaying both
    int32_t sys_delay_buf[MAX(
            SAMPLE_DELAY_BUF_SIZE(BECLEAR_NUMBER_OF_FAR, appconfMAX_SYS_DELAY),
            SAMPLE_DELAY_BUF_SIZE(MIC_ARRAY_CONFIG_MIC_COUNT, appconfMAX_MIC_DELAY)
            )];

    audio_task_params_t audio_task_params =
    {
        .min_idle_time = (XS1_TIMER_HZ / appconfSHF_NOMINAL_HZ),
        .current_idle_time = (XS1_TIMER_HZ / appconfSHF_NOMINAL_HZ),
        .max_control_time = 0,
        .mic_gain = defaults->mic_gain,
        .ref_gain = defaults->ref_gain,
        .current_selected_channels = {
            defaults->selected_channels[0],
            defaults->selected_channels[1],
        },
        .audio_to_i2s_overflow = false,
        .sys_delay = SAMPLE_DELAY_INITIALISER(sys_delay_buf,
                                              BECLEAR_NUMBER_OF_FAR,
                                              appconfMAX_SYS_DELAY,
                                              MAX(defaults->sys_delay, 0)),
        .mic_delay = SAMPLE_DELAY_INITIALISER(sys_delay_buf,
                                              MIC_ARRAY_CONFIG_MIC_COUNT,
                                              appconfMAX_MIC_DELAY,
                                              ((defaults->sys_delay < 0) ? -defaults->sys_delay : 0)),
    };

    // We do not have room for control services in I2S (especially at 48k) so do it from audio_manager instead via shared memory
    i2s_callback_args_t *i2s_app_data = get_i2s_callback_ptr(c_audio_to_i2s);

    mux_source_t* chosen_mics = &buffers[MUX_RAW_MICS];

    // Structure storing the mux settings for the I2S outputs
    i2s_out_mux_index_t i2s_out_mux_index = {
        // In format {output0, output1}
        .packed = {defaults->op_packed[0], defaults->op_packed[1]},
        .indices = {
            // Output 0, nominally left channel
            {{defaults->op_l.buf, defaults->op_l.idx},
             {defaults->op_l_pk1.buf, defaults->op_l_pk1.idx},
             {defaults->op_l_pk2.buf, defaults->op_l_pk2.idx}},
            // Output 1, nominally right channel
            {{defaults->op_r.buf, defaults->op_r.idx},
             {defaults->op_r_pk1.buf, defaults->op_r_pk1.idx},
             {defaults->op_r_pk2.buf, defaults->op_r_pk2.idx}}
        },
        .upsample = {UPSAMPLE_AM_TO_I2S,  UPSAMPLE_AM_TO_I2S}
    };

    i2s_app_data->requested_input_is_packed = defaults->i2s_input_packed;
    i2s_app_data->far_end_dsp_enable = defaults->far_end_dsp_enable;
    i2s_app_data->far_end_dac_dsp_enable = defaults->i2s_dac_dsp_enable;

    // Lookup table for handling commands that can be handled through simple memcpy
    // Note currently this is a linear search so put liklely commands earlier
    const control_lut_t control_lut[] =
    {
        {AUDIO_MGR_RESID_AUDIO_MGR_SELECTED_AZIMUTHS, audio_task_params.current_azimuths},
        {AUDIO_MGR_RESID_I2S_MIN_IDLE_TIME, &i2s_app_data->i2s_min_idle_time},
        {AUDIO_MGR_RESID_AUDIO_MGR_MIN_IDLE_TIME, &audio_task_params.min_idle_time},
        {AUDIO_MGR_RESID_I2S_INACTIVE, &audio_task_params.audio_to_i2s_overflow},
        {AUDIO_MGR_RESID_AUDIO_MGR_CURRENT_IDLE_TIME, &audio_task_params.current_idle_time},
        {AUDIO_MGR_RESID_I2S_CURRENT_IDLE_TIME, &i2s_app_data->i2s_current_idle_time},
        {AUDIO_MGR_RESID_MAX_CONTROL_TIME, &audio_task_params.max_control_time},
        {AUDIO_MGR_RESID_I2S_INPUT_PACKED, &i2s_app_data->requested_input_is_packed},
        {AUDIO_MGR_RESID_AUDIO_MGR_SELECTED_CHANNELS, audio_task_params.current_selected_channels},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_PACKED, &i2s_out_mux_index.packed},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_UPSAMPLE, &i2s_out_mux_index.upsample},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_L, &i2s_out_mux_index.indices[0][0]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_R, &i2s_out_mux_index.indices[1][0]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_L_PK0, &i2s_out_mux_index.indices[0][0]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_L_PK1, &i2s_out_mux_index.indices[0][1]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_L_PK2, &i2s_out_mux_index.indices[0][2]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_R_PK0, &i2s_out_mux_index.indices[1][0]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_R_PK1, &i2s_out_mux_index.indices[1][1]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_R_PK2, &i2s_out_mux_index.indices[1][2]},
        {AUDIO_MGR_RESID_AUDIO_MGR_OP_ALL, &i2s_out_mux_index.indices},
        {AUDIO_MGR_RESID_AUDIO_MGR_FAR_END_DSP_ENABLE, &i2s_app_data->far_end_dsp_enable},
        {AUDIO_MGR_RESID_AUDIO_MGR_MIC_GAIN, &audio_task_params.mic_gain},
        {AUDIO_MGR_RESID_AUDIO_MGR_REF_GAIN, &audio_task_params.ref_gain},
        {AUDIO_MGR_RESID_I2S_DAC_DSP_ENABLE, &i2s_app_data->far_end_dac_dsp_enable},
    };

    // Setup fifo for sending samples to i2s
    audio_to_i2s_data_t audio_to_i2s_data[I2S_TASK_FIFO_DEPTH] = {{{{0}}}};
    fifo_chan_tx_t fifo_to_i2s;
    fifo_chan_tx_init(&fifo_to_i2s, c_audio_to_i2s, audio_to_i2s_data, sizeof audio_to_i2s_data[0], I2S_TASK_FIFO_DEPTH);

    // setup fifo for receiving samples from i2s
    fifo_chan_rx_fsm_t fifo_from_i2s;
    // returning NULL while syncing is okay because the thread behaviour is similar
    // with and without rx'd data
    fifo_chan_rx_fsm_init(&fifo_from_i2s, c_i2s_to_audio, NULL);
    fifo_chan_rx_fsm_reset(&fifo_from_i2s);

    // Used for debug build. See timing_debug_defs.h
    _AUDIO_DEBUG_INIT_DEFS

    // Halt mic array until we are ready to loop and consume frames. This is a barrier synch between the two tasks.
    // This will safely account for any time spent in init in this task.
    chan_in_word(c_mic_to_audio);

    uint32_t idle_start_time = 0;

    while(1){
        // Get samples from mic array.
        // Note that this is the timing barrier in the loop (driven by the output of mic_array) so can be used to check idle time.
        // It means we will always be ready to receive from mic_array.

        // Note, if SAMPLES_PER_FRAME is changed from 1, logic will be needed here to poll mic
        // array less often, the rest of the loop will still operate on single sample frames
        update_idle_time(idle_start_time,
                         &audio_task_params.current_idle_time,
                         &audio_task_params.min_idle_time);
        ma_frame_rx(buffers[MUX_RAW_MICS].buf, c_mic_to_audio, MIC_ARRAY_CONFIG_SAMPLES_PER_FRAME, MIC_ARRAY_CONFIG_MIC_COUNT);
        idle_start_time = get_reference_time();

        bool use_packed_mics = receive_from_i2s(&fifo_from_i2s,
                                buffers[MUX_UNPACKED_MICS].buf,
                                buffers[MUX_UNPACKED_MICS].n_elems,
                                buffers[MUX_FAR_END].buf,
                                buffers[MUX_FAR_END].n_elems,
                                buffers[MUX_FAR_END_NATIVE].buf
                                );

        // update chosen mics, proper mux will be add in the future
        if(use_packed_mics) {
            chosen_mics = &buffers[MUX_UNPACKED_MICS];
        }
        else {
            chosen_mics = &buffers[MUX_RAW_MICS];
        }

        // remove microphone turn on thump and corresponding
        // reference
        mute_at_boot(&mute_at_boot_counter,
                     buffers[MUX_RAW_MICS].buf,
                     buffers[MUX_RAW_MICS].n_elems,
                     buffers[MUX_FAR_END].buf,
                     buffers[MUX_FAR_END].n_elems);

        if(sample_delay_current_delay(&audio_task_params.sys_delay) > 0) {
            // delay reference
            sample_delay_apply(&audio_task_params.sys_delay, buffers[MUX_FAR_END_SYSDELAY].buf, buffers[MUX_FAR_END].buf);
            memcpy(buffers[MUX_DELAYED_MICS].buf, chosen_mics->buf, buffers[MUX_DELAYED_MICS].n_elems * sizeof(buffers[MUX_DELAYED_MICS].buf[0]));
        }
        else {
            // delay mics
            sample_delay_apply(&audio_task_params.mic_delay, buffers[MUX_DELAYED_MICS].buf, chosen_mics->buf);
            memcpy(buffers[MUX_FAR_END_SYSDELAY].buf, buffers[MUX_FAR_END].buf, buffers[MUX_FAR_END_SYSDELAY].n_elems * sizeof(buffers[MUX_FAR_END_SYSDELAY].buf[0]));
        }

        // convert to floats
        float f_far_end[BECLEAR_NUMBER_OF_FAR];
        float f_mics[MIC_ARRAY_CONFIG_MIC_COUNT];
        shf_int32_to_float32_scaled(f_far_end, &buffers[MUX_FAR_END_SYSDELAY]);
        shf_int32_to_float32_scaled(f_mics, &buffers[MUX_DELAYED_MICS]);


        // amplify mics and reference for SHF
        apply_gain(f_far_end, f_far_end, BECLEAR_NUMBER_OF_FAR, audio_task_params.ref_gain);
        apply_gain(f_mics, f_mics, MIC_ARRAY_CONFIG_MIC_COUNT, audio_task_params.mic_gain);


        // Convert amplified mics and reference back to int for output
        float_to_mux_buf(&buffers[MUX_FAR_END_W_GAIN], f_far_end);
        float_to_mux_buf(&buffers[MUX_MICS_W_GAIN], f_mics);


        // exchange with shf
        push_samps_to_shf(f_mics, f_far_end, c_shf_aec);
        pull_samps_from_shf(buffers[MUX_PROCESSED_MICS].buf, buffers[MUX_AEC_RESIDUALS].buf);


        // Call user DSP post SHF. Pass all processed mic channels.
        post_shf_dsp(buffers[MUX_ALL_USER_CHANNELS].buf,
                    &(user_dsp_post_shf_input_t){
                         buffers[MUX_PROCESSED_MICS].buf,
                         buffers[MUX_AEC_RESIDUALS].buf,
                         current_azimuths(),
                         current_spenergy(),
                         current_smoothed_doa()
                     });
        beam_selection(audio_task_params.current_selected_channels,
                       audio_task_params.current_azimuths);
        buffers[MUX_USER_CHOSEN_CHANNELS].buf[0] = buffers[MUX_ALL_USER_CHANNELS].buf[audio_task_params.current_selected_channels[0]];
        buffers[MUX_USER_CHOSEN_CHANNELS].buf[1] = buffers[MUX_ALL_USER_CHANNELS].buf[audio_task_params.current_selected_channels[1]];


        // processing all done, upsample/pack if necessary, and send data to I2S across the FIFO 
        send_to_i2s(buffers, &i2s_out_mux_index, &audio_task_params, &fifo_to_i2s);


        // Do control
        uint32_t control_start_time = get_reference_time();
        do_audio_control(control_pkt_queue, control_lut, sizeof(control_lut)/sizeof(control_lut_t), &audio_task_params, i2s_app_data);
        uint32_t control_end_time = get_reference_time();
        uint32_t current_control_time = control_end_time - control_start_time;
        if(current_control_time > audio_task_params.max_control_time)
        {
            audio_task_params.max_control_time = current_control_time;
        }

        // Used for debug build. See timing_debug_defs.h
        _AUDIO_DEBUG_LOOP_DEFS
    }
}
