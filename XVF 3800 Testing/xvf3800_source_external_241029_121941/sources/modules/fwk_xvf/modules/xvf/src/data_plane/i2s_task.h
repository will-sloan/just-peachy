// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef I2S_TASK_H_
#define I2S_TASK_H_

#include <xcore/parallel.h>
#include <xcore/chanend.h>
#include <xcore/port.h>
#include "stdint.h"
#include "app_conf.h"
#include "fifo_chan/tx.h"
#include "fifo_chan/rx_fsm.h"
#include "sw_pll.h"
#include "audio_task.h"  // For sample_collection_t


/// @brief the i2s task that also handles far end dsp
/// @param c_audio_to_i2s channel to be used in the fifo from audio to i2s
/// @param c_i2s_to_audio channel used in the fifo going the other way.
/// Note please call init_audio_double_buffer from the audio side at startup

void i2s_task(chanend_t c_audio_to_i2s, chanend_t c_i2s_to_audio, chanend_t c_usb_to_i2s);
DECLARE_JOB(i2s_task, (chanend_t, chanend_t, chanend_t));

/// The I2S task and its client (audio_task) both operate on the same clock and
/// therefore will be in sync at least once per sample period. The random change
/// in MIPS in these tasks when other tasks start and stop can cause random variations
/// in processing times on the two tasks. Therefore it is possible for 2 tx or 2 
/// rx events to happen consecutively. The fifo depth must be enough so that the
/// sender does not block and the receiver always has data ready to pull out. see
/// test_rx_fsm and test_rx_fsm greedy for the scenarios where 3 and 5 are required
#define I2S_TASK_FIFO_DEPTH 5

/// Number of received channels sent from I2S to audio
#define I2S_TO_AUDIO_NUM_CHANNELS (appconfNUM_I2S_PINS_IN * 2)
#define AUDIO_TO_I2S_NUM_CHANNELS 2

/// @brief This is type of double buffer between I2S and Audio.
/// Note that these are ALWAYS far end samples so name them as such
typedef struct i2s_to_audio_data_t{
    sample_collection_t far_end_samples_i2s[I2S_TO_AUDIO_NUM_CHANNELS];
    bool was_packed; /// alert client as to how this buffer should be processed
} i2s_to_audio_data_t;

/// @brief This is type of double buffer from Audio to I2S. 
typedef struct audio_to_i2s_data_t{
    sample_collection_t i2s_tx_samps[AUDIO_TO_I2S_NUM_CHANNELS];
} audio_to_i2s_data_t;


/// @brief Struct to describe state struct of I2S that is passed to callback and audio
typedef struct i2s_callback_args_t {
    fifo_chan_tx_t fifo_to_audio;
    i2s_to_audio_data_t* curr_tx_buf;
    fifo_chan_rx_fsm_t fifo_from_audio;
    audio_to_i2s_data_t* curr_rx_buf;     // Pointer to the data coming from audio
    chanend_t c_usb_to_i2s;
    bool usb_ready;

    bool did_restart;
    bool i2s_to_audio_overflow;

    uint32_t i2s_callback_ticks;
    uint32_t i2s_current_idle_time;
    uint32_t i2s_min_idle_time;
    uint32_t i2s_reset_min_idle_time;           // Flag to cause idle time to be reset
    uint32_t i2s_cycle_number;
    uint32_t i2s_48kHz_sample_number_rx;        // Keeps track of 48kHz sample count vs 16kHz
    uint32_t i2s_48kHz_sample_number_tx;
    uint32_t packed_input_stage;                // State for monitoring packing
    int32_t packed_input_buffer[2][2][3];       // Buffer storing the packed input samples
    uint32_t packed_input_buffer_number;        // Index of the packed input samples to use
    uint32_t packed_input_buffer_ready;         // Flag to indicate if buffer with the packed input has new samples
    bool packed_input_valid;                    // Flag to indicate if packed input samples are valid
    bool requested_input_is_packed;             // Written by audio_task thread to set input data type
    bool input_is_packed;                       // Set to `requested_input_is_packed` when safe to do so.
    bool far_end_dsp_enable;                    // Flag to indicate if internal (not DAC) far-end DSP occurs
    bool far_end_dac_dsp_enable;                // Flag to indicate if DAC performs DSP on far-end signal
    int32_t far_end_samples_to_audio[appconfNUM_I2S_PINS_IN * 2]; // may be from host or DAC
    int32_t far_end_samples_to_dac[appconfNUM_I2S_PINS_IN * 2];   // always from host
    sample_collection_t mux_output[AUDIO_TO_I2S_NUM_CHANNELS];     // Left and right channels from the mux in audio
                                                                   // used in UA config only
    sample_collection_t raw_far_end[appconfUSB_CHANNELS_IN];  // store far end for deserialising to DAC, UA only
    int raw_far_end_idx;                   // next loops index into raw_far_en UA only.

    port_t p_mclk_count;                   // Used for keeping track of MCLK output for clock recovery builds
    port_t p_bclk_count;                   // Used for keeping track of BCLK output for clock recovery builds
    sw_pll_state_t *sw_pll;                // Pointer to sw_pll state (if used)

} i2s_callback_args_t;


/// @brief  clear the samples to zero
/// @param  target the samples
void clear_sample_collection(sample_collection_t * target);


/// @param  get the m_clk resource ID
/// @return resource id of mclk used in I2S
port_t get_i2s_mclk_res_id(chanend_t c_audio_i2s);

/// @param  get the callback state struct
/// @return pointer to i2s_callback_args in I2S
i2s_callback_args_t* get_i2s_callback_ptr(chanend_t c_audio_i2s);

#endif
