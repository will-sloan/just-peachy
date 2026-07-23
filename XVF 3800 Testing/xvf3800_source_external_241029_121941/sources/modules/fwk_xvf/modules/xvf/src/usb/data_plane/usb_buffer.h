// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef _USB_BUFFER_H_
#define _USB_BUFFER_H_

#include <xcore/parallel.h>
#include <xcore/interrupt_wrappers.h>
#include <xcore/interrupt.h>
#include <xcore/triggerable.h>

#include "audio_task.h"    // For SAMPLE_COLLECTION_SIZE

/// @brief  Structure to declar an array of channels ends passed to usb_buffer
typedef struct usb_buffer_args_t{
    chanend_t chan_ep_audio_out;
    chanend_t chan_ep_audio_in;
    chanend_t chan_usb_to_i2s;
    chanend_t chan_sof;
} usb_buffer_args_t;

DECLARE_JOB(usb_buffer, (usb_buffer_args_t *));
/// @brief handles buffering between audio and usb as well as packing and rate control
/// @param args the array of channel ends passed to connect to XUD/Audio
/// @param ep0_proxy_ctx the strcuture containing the state of ep0 proxy
void usb_buffer(usb_buffer_args_t * args);

/// @brief  Inititalise the USB mic and speaker volume multipliers.
void init_vol_muls(void);


/// @brief Called from usb_proxy to inform the usb_buffer of a device reset event
/// @param xud_speed Bus speed at which the host expects the device to operate
void set_device_reset_event(XUD_BusSpeed_t xud_speed);

#endif
