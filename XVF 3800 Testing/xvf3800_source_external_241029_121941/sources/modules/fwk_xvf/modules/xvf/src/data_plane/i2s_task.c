// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


// This file contains the i2s task and the associated callbacks which handle building
// buffers for SHF, taking samples fom mic_array (and usb), sample rate conversion and muxing

#include "xcore/chanend.h"
#define DEBUG_UNIT I2S_TASK
#ifndef DEBUG_PRINT_ENABLE_I2S_TASK
    #define DEBUG_PRINT_ENABLE_I2S_TASK 0
#endif
#include "debug_print.h"

#include <print.h>
#include <platform.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <xcore/hwtimer.h>
#include <xcore/select.h>
#include <xcore/assert.h>
#include <xscope.h>

/* Library headers */
#include "i2s.h"
#include "mic_array.h"
#include "shf_bypass/shf_bypass.h"

/* App headers */
#include "i2s_task.h"
#include "shf_wrapper.h"
#include "app_conf.h"
#include "tile_common.h"
#include "fifo_chan/tx.h"
#include "fifo_chan/rx_fsm.h"
#include "user_dsp.h"
#include "sw_pll.h"
#include "audio_rates.h"
#include "packing.h"

/* Config headers for sw_pll */
#include "fractions_1000ppm.h"
#include "register_setup_1000ppm.h"
#include "pll_servicer.h" // For get_i2s_task_pll_lock_status()


// Note printing has habit of creating extra back pressure
#define I2S_CALLBACK_TOTAL_TICKS_LIMIT      ((XS1_TIMER_HZ / appconfLRCLK_NOMINAL_HZ) - 150)


port_t get_i2s_mclk_res_id(chanend_t c_audio_to_i2s){
    uint32_t mclk_res_id = s_chan_in_word(c_audio_to_i2s);
    return (port_t)mclk_res_id;
}

i2s_callback_args_t* get_i2s_callback_ptr(chanend_t c_audio_to_i2s){
    uint32_t cb_args = s_chan_in_word(c_audio_to_i2s);
    return (i2s_callback_args_t*)cb_args;
}


inline void clear_sample_collection(sample_collection_t * target)
{
    memset(target->samples, 0, sizeof target->samples);
}


// This sends a data token which is enough to pre-trigger the select in usb_buffer. This means that
// some of the select latency is hidden and usb_buffer is ready to service exchange_samples_with_usb immediately
// It keeps the switch path open until exchange_samples_with_usb has completed
STATIC_INLINE void start_exchange_samples_with_usb(chanend_t c_usb_to_i2s, const bool usb_ready){
    if(usb_ready){
        chanend_out_byte(c_usb_to_i2s, 0);
    }
}

STATIC_INLINE void exchange_samples_with_usb(chanend_t c_usb_to_i2s,
                                            sample_collection_t *samples_to_usb,
                                            sample_collection_t *samples_from_usb,
                                            bool *usb_ready){

    if(*usb_ready){
        // Host to Device
        for(int ch = 0; ch < appconfUSB_CHANNELS_IN; ch++){
            for(int smp = 0; smp < get_usb_to_i2s_packet_size(); smp++){
                samples_from_usb[ch].samples[smp] = chanend_in_word(c_usb_to_i2s);
            }
        }
        // Device to Host
        for(int ch = 0; ch < appconfUSB_CHANNELS_OUT; ch++){
            for(int smp = 0; smp < get_i2s_to_usb_packet_size(); smp++){
                chanend_out_word(c_usb_to_i2s, samples_to_usb[ch].samples[smp]);
            }
        }
    } else {
        // Non-blocking read to wait for usb_enumerated_event
        SELECT_RES(
            CASE_THEN(c_usb_to_i2s, usb_ready_event),
            DEFAULT_THEN(default_handler)
        )
        {
            usb_ready_event:
            {
                chan_in_word(c_usb_to_i2s);
                *usb_ready = true;
            }
            break;

            default_handler:
            {
                // Do nothing & fall-through
            }
            break;
        }
    }
}


// Note that the i2s callback order per frame is restart, send then receive.
// So we increment buffer indices on the receive callback at the end of each frame
I2S_CALLBACK_ATTR
static void i2s_init(void *app_data, i2s_config_t *i2s_config){
    debug_printf("I2S init\n");
    i2s_config->mode = I2S_MODE_I2S;
    i2s_config->mclk_bclk_ratio = (appconfMCLK_NOMINAL_HZ / appconfBCLK_NOMINAL_HZ);

    i2s_callback_args_t *cb_args = app_data;


    // when i2s stops and starts again it calls init -> send -> wait for clocks -> restart_check
    // restart check needs to know we restarted to reset the states
    cb_args->did_restart = true;
}

I2S_CALLBACK_ATTR
static i2s_restart_t i2s_restart_check(void *app_data){
    i2s_callback_args_t *cb_args = app_data;

    if(cb_args->i2s_callback_ticks > I2S_CALLBACK_TOTAL_TICKS_LIMIT){
        debug_printf(   "Error: I2S callback ticks [%u] exceeded limit[%u] on cycle [%u], restarting..\n",
                        cb_args->i2s_callback_ticks, I2S_CALLBACK_TOTAL_TICKS_LIMIT, cb_args->i2s_cycle_number);
        cb_args->i2s_callback_ticks = 0;
        cb_args->i2s_min_idle_time = (XS1_TIMER_HZ / appconfLRCLK_NOMINAL_HZ);

        return I2S_RESTART;
    }

  // Add any extra code here if needed so it will be counted in the timing check.
    uint32_t t0 = get_reference_time();

#if appconfRECOVER_MCLK_I2S_APP_PLL
    port_clear_buffer(cb_args->p_bclk_count);
    port_in(cb_args->p_bclk_count);                                  // Block until BCLK transition to synchronise. Will consume up to 1/64 of a LRCLK cycle
    uint16_t mclk_pt = port_get_trigger_time(cb_args->p_mclk_count); // Immediately sample mclk_count
    uint16_t bclk_pt = port_get_trigger_time(cb_args->p_bclk_count); // Now grab bclk_count (which won't have changed)

    sw_pll_lut_do_control(cb_args->sw_pll, mclk_pt, bclk_pt);
#endif

    if(cb_args->did_restart) {
        cb_args->did_restart = false;
        // drop any existing buffers and reset the rx fsm, time has passed
        // any any state we have is bad.
        if(NULL != cb_args->curr_rx_buf) {
            fifo_chan_rx_fsm_done(&cb_args->fifo_from_audio);
            cb_args->curr_rx_buf = NULL;
        }
        if(NULL != cb_args->curr_tx_buf) {
            fifo_chan_tx_send(&cb_args->fifo_to_audio);
            cb_args->curr_tx_buf = NULL;
        }
        fifo_chan_rx_fsm_reset(&cb_args->fifo_from_audio);
        if(appconfLRCLK_NOMINAL_HZ == 48000){
            cb_args->i2s_48kHz_sample_number_rx = 0;
            cb_args->i2s_48kHz_sample_number_tx = 0;
        }
    }

    cb_args->i2s_callback_ticks = get_reference_time() - t0;

    return I2S_NO_RESTART;
}

/// Returns the buffer that has been received from audio, tries to
/// get a new one if there isn't one already stored. Returns true
/// if a buffer was aquired.
static bool get_next_audio_rx_buf(i2s_callback_args_t* cb_args) {
    if(NULL == cb_args->curr_rx_buf) {
        cb_args->curr_rx_buf = fifo_chan_rx_fsm_receive(&cb_args->fifo_from_audio);
    }
    return NULL != cb_args->curr_rx_buf;
}

/// Loads i2s_out with the samples that are due for the DAC. i2s_out should
/// should have a size of 2, representing the left and right channel.
static void set_dac_output(i2s_callback_args_t *cb_args, int32_t* i2s_out) {
    i2s_out[0] = cb_args->far_end_samples_to_dac[0];
    i2s_out[1] = cb_args->far_end_samples_to_dac[1];
}

/// i2s_send callback for UA when audio and i2s are running at the same rate. Puts far end
/// out onto the DAC
static void i2s_send_ua_1to1(i2s_callback_args_t *cb_args, size_t num_out, int32_t* i2s_out) {
    if(get_next_audio_rx_buf(cb_args)) {
        cb_args->mux_output[0].sample = cb_args->curr_rx_buf->i2s_tx_samps[0].sample;
        cb_args->mux_output[1].sample = cb_args->curr_rx_buf->i2s_tx_samps[1].sample;
        fifo_chan_rx_fsm_done(&cb_args->fifo_from_audio);
        cb_args->curr_rx_buf = NULL;
    } else {
        memset(cb_args->mux_output, 0, sizeof(cb_args->mux_output));
    }
    set_dac_output(cb_args, i2s_out);
}

/// i2s_send callback for INT when audio an i2s are running at the same rate. Returns processed
/// mics to the host and sets the DAC output if present.
static void i2s_send_int_1to1(i2s_callback_args_t *cb_args, size_t num_out, int32_t* i2s_out) {
    if(get_next_audio_rx_buf(cb_args)) {
        i2s_out[0] = cb_args->curr_rx_buf->i2s_tx_samps[0].sample;
        i2s_out[1] = cb_args->curr_rx_buf->i2s_tx_samps[1].sample;
        fifo_chan_rx_fsm_done(&cb_args->fifo_from_audio);
        cb_args->curr_rx_buf = NULL;
    } else {
        i2s_out[0] = 0;
        i2s_out[1] = 0;
    }
    if(2 < num_out) {
        // copy dac output to the second I2S wire
        set_dac_output(cb_args, &i2s_out[2]);
    }
}

/// i2s_send callback for UA when audio is sending 3 samples per transaction. Stores mux output from
/// audio and outputs processed far end to DAC.
static void i2s_send_ua_3to1(i2s_callback_args_t *cb_args, size_t num_out, int32_t* i2s_out) {
    if(get_next_audio_rx_buf(cb_args)) {
        if(0 == cb_args->i2s_48kHz_sample_number_tx) {
            cb_args->mux_output[0] = cb_args->curr_rx_buf->i2s_tx_samps[0];
            cb_args->mux_output[1] = cb_args->curr_rx_buf->i2s_tx_samps[1];
        }
        if(++(cb_args->i2s_48kHz_sample_number_tx) >= NUM_48K_SAMPS_PER_EXCHANGE){
            cb_args->i2s_48kHz_sample_number_tx = 0;
            fifo_chan_rx_fsm_done(&cb_args->fifo_from_audio);
            cb_args->curr_rx_buf = NULL;
        }
    } else {
        memset(cb_args->mux_output, 0, sizeof(cb_args->mux_output));
    }
    set_dac_output(cb_args, i2s_out);
}

/// i2s_send callback for INT when audio is sending 3 samples per transaction. Outputs processed far end
/// to DAC and processed mics to host.
static void i2s_send_int_3to1(i2s_callback_args_t *cb_args, size_t num_out, int32_t* i2s_out) {
    if(get_next_audio_rx_buf(cb_args)) {
        i2s_out[0] = cb_args->curr_rx_buf->i2s_tx_samps[0].samples[cb_args->i2s_48kHz_sample_number_tx];
        i2s_out[1] = cb_args->curr_rx_buf->i2s_tx_samps[1].samples[cb_args->i2s_48kHz_sample_number_tx];
        if(++(cb_args->i2s_48kHz_sample_number_tx) >= NUM_48K_SAMPS_PER_EXCHANGE){
            cb_args->i2s_48kHz_sample_number_tx = 0;
            fifo_chan_rx_fsm_done(&cb_args->fifo_from_audio);
            cb_args->curr_rx_buf = NULL;
        }
    } else {
        i2s_out[0] = 0;
        i2s_out[1] = 0;
        cb_args->i2s_48kHz_sample_number_tx = 0;
    }
    // if num_out is greater than 2 then there are 2 wires (therefore 4 channels). This design
    // assumes that DAC output is always the second wire.
    if(2 < num_out) {
        // copy dac output to the second I2S wire
        set_dac_output(cb_args, &i2s_out[2]);
    }
}

I2S_CALLBACK_ATTR
static void i2s_send(void *app_data, size_t num_out, int32_t *i2s_sample_buf){
    uint32_t t0 = get_reference_time();

    // Extract all of the exchange data vars and timing check vars from callback args
    i2s_callback_args_t *cb_args = app_data;

    if(appconfUSB_ENABLED){
        if(get_i2s_to_usb_packet_size() == 1)
        {
            i2s_send_ua_1to1(cb_args, num_out, i2s_sample_buf);
        }
        else
        {
            i2s_send_ua_3to1(cb_args, num_out, i2s_sample_buf);
        }
    }
    else
    {
        if(get_i2s_to_usb_packet_size() == 1)
        {
            i2s_send_int_1to1(cb_args, num_out, i2s_sample_buf);
        }
        else
        {
            i2s_send_int_3to1(cb_args, num_out, i2s_sample_buf);
        }
    }
    cb_args->i2s_callback_ticks += get_reference_time() - t0;
}

/// claim a buffer to send to audio. returns true if succesful.
static bool get_next_audio_tx_buf(i2s_callback_args_t* cb_args) {
    if(NULL == cb_args->curr_tx_buf) {
        cb_args->curr_tx_buf = fifo_chan_tx_next_buf(&cb_args->fifo_to_audio);
    }
    if(NULL == cb_args->curr_tx_buf) {
        debug_printf("I2S+\n"); // Shouldn't be possible as audio is always servicing the receive side.
        // However, if it does happen, it means I2S hasn't received enough credits from audio manager which could indicate a
        // timing issue on the audio side or I2S running too fast.
        cb_args->i2s_to_audio_overflow = true;

        return false;
    } else {
        cb_args->i2s_to_audio_overflow = false;
        return true;
    }
}

/// dsp functionality common to INT and UA
static void far_end_dsp_and_send_to_audio_1to1(i2s_callback_args_t* cb_args) {
    far_end_dsp(cb_args->far_end_samples_to_dac, cb_args->far_end_dsp_enable);
    if(get_next_audio_tx_buf(cb_args)) {
        cb_args->curr_tx_buf->far_end_samples_i2s[0].sample = cb_args->far_end_samples_to_audio[0];
        cb_args->curr_tx_buf->far_end_samples_i2s[1].sample = cb_args->far_end_samples_to_audio[1];
        cb_args->curr_tx_buf->was_packed = false;
        fifo_chan_tx_send(&cb_args->fifo_to_audio);
        cb_args->curr_tx_buf = NULL;
    }
}

/// dsp and unpacking functionality common to INT and UA
static void far_end_dsp_unpack_and_send_to_audio_3to1(i2s_callback_args_t* cb_args, size_t num_in) {
    far_end_dsp(cb_args->far_end_samples_to_dac, cb_args->far_end_dsp_enable);
    if(get_next_audio_tx_buf(cb_args)) {
        uint32_t *packed_input_buffer_ready = &cb_args->packed_input_buffer_ready;

        if(cb_args->input_is_packed) {

            uint8_t bitres = 0;

            if(appconfUSB_ENABLED) {
                get_usb_bit_depth(NULL, &bitres); // We only care here about the OUT endpoint bit depth (host-to-device)
            } else {
                bitres = appconfINT_PACKED_BIT_DEPTH;
            }

            assemble_valid_packed_packet(cb_args, num_in, cb_args->far_end_samples_to_audio, bitres);
        } else {
            for(int channel = 0; channel < num_in; channel++){
                cb_args->curr_tx_buf->far_end_samples_i2s[channel].samples[cb_args->i2s_48kHz_sample_number_rx] = cb_args->far_end_samples_to_audio[channel];
            };
        }
        if(++(cb_args->i2s_48kHz_sample_number_rx) >= NUM_48K_SAMPS_PER_EXCHANGE) {
            if (cb_args->input_is_packed)
            {
                if (0 != *packed_input_buffer_ready)
                {
                    for(int channel = 0; channel < num_in; channel++){
                        for (int sample_idx = 0; sample_idx < NUM_48K_SAMPS_PER_EXCHANGE; sample_idx++){
                            cb_args->curr_tx_buf->far_end_samples_i2s[channel].samples[sample_idx] = cb_args->packed_input_buffer[*packed_input_buffer_ready - 1][channel][sample_idx];
                        }
                    }
                    *packed_input_buffer_ready = 0;
                }
                else
                {
                    // We need to give something to the audio manager but there aren't any packed inputs ready - send 0s.
                    for(int channel = 0; channel < num_in; channel++){
                        for (int sample_idx = 0; sample_idx < NUM_48K_SAMPS_PER_EXCHANGE; sample_idx++){
                            cb_args->curr_tx_buf->far_end_samples_i2s[channel].samples[sample_idx] = 0;
                        }
                    }
                }
            }

            cb_args->curr_tx_buf->was_packed = cb_args->input_is_packed;
            fifo_chan_tx_send(&cb_args->fifo_to_audio);
            cb_args->curr_tx_buf = NULL;
            // safety warning: reading from variable which is written by
            // another thread. This is done here as a full sample buffer
            // has been received so we can switch over for the next one.
            cb_args->input_is_packed = cb_args->requested_input_is_packed;
            cb_args->i2s_48kHz_sample_number_rx = 0;
        }
    }
}

/// Exchange with USB, do far end DSP and send to audio.
static void i2s_receive_ua_1to1(i2s_callback_args_t* cb_args, size_t num_in, const int32_t* i2s_in) {
    (void)num_in;
    // exchange with USB
    start_exchange_samples_with_usb(cb_args->c_usb_to_i2s, cb_args->usb_ready);
    sample_collection_t from_usb[appconfUSB_CHANNELS_IN];
    exchange_samples_with_usb(cb_args->c_usb_to_i2s, cb_args->mux_output, from_usb, &cb_args->usb_ready);

    // The source of the far-end reference signal is usually USB.
    // However, if the DAC (not the XVF38xx) does far-end DSP, the reference comes from the signal returned over I2S.
    cb_args->far_end_samples_to_audio[0] = (cb_args->far_end_dac_dsp_enable) ? i2s_in[0] : from_usb[0].sample;
    cb_args->far_end_samples_to_audio[1] = (cb_args->far_end_dac_dsp_enable) ? i2s_in[1] : from_usb[1].sample;

    // Always use USB as far end source for DAC and XVF38xx-based far-end DSP
    cb_args->far_end_samples_to_dac[0] = from_usb[0].sample;
    cb_args->far_end_samples_to_dac[1] = from_usb[1].sample;

    // send far end to audio
    far_end_dsp_and_send_to_audio_1to1(cb_args);
}


/// exchange with USB, do DSP, unpack if necessary and send to audio.
static void i2s_receive_ua_3to1(i2s_callback_args_t* cb_args, size_t num_in, const int32_t* i2s_in) {
    // exchange with USB every third loop.
    if(0 == cb_args->raw_far_end_idx) {
        start_exchange_samples_with_usb(cb_args->c_usb_to_i2s, cb_args->usb_ready);
        exchange_samples_with_usb(cb_args->c_usb_to_i2s, cb_args->mux_output, cb_args->raw_far_end, &cb_args->usb_ready);
    }

    // serialise the samples from USB so they can be dealt with in the same manner as
    // the data in the INT case.
    int idx = cb_args->raw_far_end_idx;

    // The source of the far-end reference signal is usually USB.
    // However, if the DAC (not the XVF38xx) does far-end DSP, the reference comes from the signal returned over I2S.
    cb_args->far_end_samples_to_audio[0] = (cb_args->far_end_dac_dsp_enable) ? i2s_in[0] : cb_args->raw_far_end[0].samples[idx];
    cb_args->far_end_samples_to_audio[1] = (cb_args->far_end_dac_dsp_enable) ? i2s_in[1] : cb_args->raw_far_end[1].samples[idx];

    // Always use USB as far end source for DAC and XVF38xx-based far-end DSP
    cb_args->far_end_samples_to_dac[0] = cb_args->raw_far_end[0].samples[idx];
    cb_args->far_end_samples_to_dac[1] = cb_args->raw_far_end[1].samples[idx];

    if(++idx >= NUM_48K_SAMPS_PER_EXCHANGE) {
        cb_args->raw_far_end_idx = 0;
    } else {
        cb_args->raw_far_end_idx = idx;
    }

    far_end_dsp_unpack_and_send_to_audio_3to1(cb_args, num_in);
}


I2S_CALLBACK_ATTR
static void i2s_receive(void *app_data, size_t num_in, const int32_t *i2s_in){

    uint32_t t0 = get_reference_time();

    // Extract all of the exchange data vars and timing check from callback args
    i2s_callback_args_t *cb_args = app_data;

    if(appconfUSB_ENABLED){
        if(get_i2s_to_usb_packet_size() == 1)
        {
            i2s_receive_ua_1to1(cb_args, num_in, i2s_in);
        }
        else
        {
            i2s_receive_ua_3to1(cb_args, num_in, i2s_in);
        }
    }
    else
    {
        // Store far end samples from I2S
        cb_args->far_end_samples_to_audio[0] = i2s_in[0];
        cb_args->far_end_samples_to_audio[1] = i2s_in[1];
        cb_args->far_end_samples_to_dac[0] = i2s_in[0];
        cb_args->far_end_samples_to_dac[1] = i2s_in[1];

        if(get_src_packing_mode() == SRC_PACK_1_TO_1)
        {
            far_end_dsp_and_send_to_audio_1to1(cb_args);
        }
        else
        {
            far_end_dsp_unpack_and_send_to_audio_3to1(cb_args, num_in);
        }
    }

    (cb_args->i2s_cycle_number)++;

    cb_args->i2s_callback_ticks += get_reference_time() - t0;
    cb_args->i2s_current_idle_time = I2S_CALLBACK_TOTAL_TICKS_LIMIT - cb_args->i2s_callback_ticks;

    // Handle idle time logging and reset control command
    if(cb_args->i2s_reset_min_idle_time){
        cb_args->i2s_min_idle_time = (XS1_TIMER_HZ / appconfLRCLK_NOMINAL_HZ);
        cb_args->i2s_reset_min_idle_time = 0;
    } else{
        cb_args->i2s_min_idle_time = cb_args->i2s_current_idle_time < cb_args->i2s_min_idle_time ? cb_args->i2s_current_idle_time : cb_args->i2s_min_idle_time;
    }
}

static int *p_lock_status = NULL;
/// @brief Save the pointer to the pll lock_status variable
static void set_pll_lock_status_ptr(int* p)
{
    p_lock_status = p;
}

/// @brief Return pll lock_status
int8_t get_i2s_task_pll_lock_status(void)
{
    return (int8_t)*p_lock_status;
}

/// @brief handles main i2s loop and exchanges samples with audio. Also handles Far end DSP
void i2s_task(chanend_t c_audio_to_i2s, chanend_t c_i2s_to_audio, chanend_t c_usb_to_i2s){

    if(get_core_burn_status() != 0){
        SET_FAST_MODE();
    }

#if (appconfNUM_I2S_PINS_OUT == 1)
    port_t p_i2s_dout[appconfNUM_I2S_PINS_OUT] = {appconfPROCESSED_MIC_OUT_PORT}; // far-end out port optional
#else
    port_t p_i2s_dout[appconfNUM_I2S_PINS_OUT] = {appconfPROCESSED_MIC_OUT_PORT, appconfFAR_END_OUT_PORT}; // far-end out port optional
#endif
    port_t p_i2s_din[appconfNUM_I2S_PINS_IN] = {appconfFAR_END_IN_PORT};
    port_t p_bclk = PORT_I2S_BCLK;
    port_t p_lrclk = PORT_I2S_LRCLK;
    port_t p_mclk = PORT_MCLK;
    port_t p_mclk_count = PORT_MCLK_COUNT;  // Used internally by sw_pll
    port_t p_bclk_count = PORT_BCLK_COUNT;  // Used internally by sw_pll
    xclock_t ck_bclk = I2S_CLKBLK;
    i2s_callback_group_t i2s_cb_group;

    port_enable(p_mclk);
    port_enable(p_bclk);
    // NOTE:  p_lrclk does not need to be enabled by the caller

    // Initialise callback function pointers
    i2s_cb_group.init = i2s_init;
    i2s_cb_group.restart_check = i2s_restart_check;
    i2s_cb_group.receive = i2s_receive;
    i2s_cb_group.send = i2s_send;

    sw_pll_state_t sw_pll = {0};

    set_pll_lock_status_ptr(&sw_pll.lock_status);

    if(appconfRECOVER_MCLK_I2S_APP_PLL)
    {
        // Create clock from mclk port and use it to clock the p_mclk_count port which will count MCLKs.
        port_enable(p_mclk_count);
        port_enable(p_bclk_count);

        // Allow p_mclk_count to count mclks
        xclock_t clk_mclk = MCLK_CLKBLK;
        clock_enable(clk_mclk);
        clock_set_source_port(clk_mclk, p_mclk);
        port_set_clock(p_mclk_count, clk_mclk);
        clock_start(clk_mclk);

        // Allow p_bclk_count to count bclks
        port_set_clock(p_bclk_count, ck_bclk);

        sw_pll_lut_init(&sw_pll,
                    SW_PLL_15Q16(0.0),
                    SW_PLL_15Q16(1.0),
                    SW_PLL_15Q16(0.0),
                    PLL_CONTROL_LOOP_COUNT_INT,
                    PLL_RATIO,
                    (appconfBCLK_NOMINAL_HZ / appconfLRCLK_NOMINAL_HZ),
                    frac_values_90,
                    SW_PLL_NUM_LUT_ENTRIES(frac_values_90),
                    APP_PLL_CTL_REG,
                    APP_PLL_DIV_REG,
                    SW_PLL_NUM_LUT_ENTRIES(frac_values_90) / 2,
                    PLL_PPM_RANGE);

        debug_printf("Using SW PLL to track I2S input\n");
    }
    else
    {
        sw_pll.lock_status = SW_PLL_LOCKED; // Important so that I2S status command returns good for fixed MCLK or ext MCLK cases
    }

    // Initialise app_data
    i2s_callback_args_t app_data = {
        .c_usb_to_i2s = c_usb_to_i2s,
        .i2s_callback_ticks = 0,
        .i2s_current_idle_time = (XS1_TIMER_HZ / appconfLRCLK_NOMINAL_HZ),
        .i2s_min_idle_time = (XS1_TIMER_HZ / appconfLRCLK_NOMINAL_HZ),
        .i2s_reset_min_idle_time = 0,
        .curr_rx_buf = NULL,
        .curr_tx_buf = NULL,
        .did_restart = false,
        .i2s_to_audio_overflow = false,
        .i2s_48kHz_sample_number_rx = 0,
        .i2s_48kHz_sample_number_tx = 0,
        .packed_input_buffer_ready = 0,
        .packed_input_buffer = {{{0}}},
        .packed_input_stage = 0,
        .packed_input_valid = 0,
        .packed_input_buffer_number = 0,
        .far_end_dac_dsp_enable = 0,
        .i2s_cycle_number = 0,
        .p_mclk_count = p_mclk_count,
        .p_bclk_count = p_bclk_count,
        .sw_pll = &sw_pll
    };

    i2s_cb_group.app_data = &app_data;

    // Send app_data address over to audio
    s_chan_out_word(c_audio_to_i2s, (uint32_t)&app_data);

    // Initialise the rx_fifo for receiving from audio manager. Sets the sync_data
    // pointer so that the synchronising phase of the fsm still gives us data to
    // work with.
    audio_to_i2s_data_t sync_data;
    memset(&sync_data, 0, sizeof sync_data);
    fifo_chan_rx_fsm_init(&app_data.fifo_from_audio, c_audio_to_i2s, &sync_data);

    i2s_to_audio_data_t i2s_to_audio_data[I2S_TASK_FIFO_DEPTH];   // The fifo buffer from i2s to audio
    fifo_chan_tx_init(&app_data.fifo_to_audio, c_i2s_to_audio, i2s_to_audio_data, sizeof i2s_to_audio_data[0], I2S_TASK_FIFO_DEPTH);

#if appconfI2S_ROLE_MASTER
    i2s_master(
            &i2s_cb_group,
            p_i2s_dout,
            appconfNUM_I2S_PINS_OUT,
            p_i2s_din,
            appconfNUM_I2S_PINS_IN,
            p_bclk,
            p_lrclk,
            p_mclk,
            ck_bclk);
#else
    i2s_slave(
            &i2s_cb_group,
            p_i2s_dout,
            appconfNUM_I2S_PINS_OUT,
            p_i2s_din,
            appconfNUM_I2S_PINS_IN,
            p_bclk,
            p_lrclk,
            ck_bclk);
#endif

}
