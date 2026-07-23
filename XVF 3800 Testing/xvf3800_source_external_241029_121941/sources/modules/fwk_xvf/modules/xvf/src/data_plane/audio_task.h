// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef AUDIO_TASK_H_
#define AUDIO_TASK_H_

#include <xcore/parallel.h>
#include <xcore/chanend.h>
#include "packet_queue.h"
#include "user_dsp.h"
#include "sample_delay.h"

/// samples in the collection array
#define SAMPLE_COLLECTION_SIZE 3

/// @brief This is type of double buffer type between Audio and I2S/USB (if present).
typedef union sample_collection_t
{
    int32_t sample;
    int32_t samples[SAMPLE_COLLECTION_SIZE];
} sample_collection_t;

/// @brief This is type of buffer between USB and Audio.
/// Note that these are far end or packed samples
typedef struct usb_to_audio_data_t{
    sample_collection_t far_end_samples_usb[appconfUSB_CHANNELS_OUT];
    bool was_packed; /// alert client as to how this buffer should be processed
} usb_to_audio_data_t;

/// @brief This is type of buffer from Audio to USB. 
typedef struct audio_to_usb_data_t{
    sample_collection_t usb_tx_samps[appconfUSB_CHANNELS_IN];
} audio_to_usb_data_t;


/// @brief  Audio task config params that can be configured using the control interface
typedef struct
{
    float mic_gain;
    float ref_gain;
    uint32_t min_idle_time;
    uint32_t current_idle_time;
    uint32_t max_control_time;
    float current_azimuths[USER_DSP_NUM_OUTPUT_CHANNELS];
    bool audio_to_i2s_overflow;
    uint8_t current_selected_channels[USER_DSP_NUM_OUTPUT_CHANNELS];
    sample_delay_t sys_delay;
    sample_delay_t mic_delay;
}audio_task_params_t;


/// @brief handles audio plumbing
/// @param c_mic_to_audio the channel connecting to mic_array
/// @param c_shf_aec the channel connecting to shf aec
/// @param c_audio_i2s channel connecting to the audio task logical core
/// @param chan_usb_to_audio channel connecting to the usb core
/// @param control_pkt_queue_t pkt_queue Pointer to the control packet queue
void audio_manager_task(chanend_t c_mic_to_audio,
                        chanend_t c_shf_aec,
                        chanend_t c_audio_to_i2s,
                        chanend_t c_i2s_to_audio, 
                        control_pkt_queue_t *control_pkt_queue);
DECLARE_JOB(audio_manager_task, (chanend_t, chanend_t, chanend_t, chanend_t, control_pkt_queue_t*));


#endif

