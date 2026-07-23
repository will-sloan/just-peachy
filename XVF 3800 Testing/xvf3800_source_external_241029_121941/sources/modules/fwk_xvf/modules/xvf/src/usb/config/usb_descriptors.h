// Copyright 2021-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef USB_DESCRIPTORS_H_
#define USB_DESCRIPTORS_H_

#include <stddef.h> // For size_t
#include "tusb_config.h"
#include "usb_param_values.h"

// BCD device format is  0xJJMN where JJ is the major version number,
// M is the minor version number and N is the patch version number
// By default we use the same version of the firmware
#define BCD_DEVICE  ( ( VERSION_MAJOR << 8 ) \
                    + ( VERSION_MINOR << 4 ) \
                    + VERSION_PATCH )

#if CFG_TUD_AUDIO_ENABLE_EP_IN && CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX > 0
#define AUDIO_INPUT_ENABLED 1
#else
#define AUDIO_INPUT_ENABLED 0
#endif
#if CFG_TUD_AUDIO_ENABLE_EP_OUT && CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_RX > 0
#define AUDIO_OUTPUT_ENABLED 1
#else
#define AUDIO_OUTPUT_ENABLED 0
#endif

enum {
    ITF_NUM_AUDIO_CONTROL = 0,
#if AUDIO_OUTPUT_ENABLED
    ITF_NUM_AUDIO_STREAMING_SPK,
#endif
#if AUDIO_INPUT_ENABLED
    ITF_NUM_AUDIO_STREAMING_MIC,
#endif
    ITF_XMOS_DEV_CTRL,
#if ( 0 < DFU_CONTROL )
    ITF_NUM_DFU_MODE,
#endif
#if HID_CONTROL
    ITF_NUM_HID,
#endif
    ITF_NUM_TOTAL
};

#define EP_NUM_EP0   0
#define EP_NUM_AUDIO 1
#define EP_NUM_HID   2
#define ALL_EPS {EP_NUM_EP0, EP_NUM_AUDIO, EP_NUM_HID}


#define REPORT_ID_TEAMS_BUTTON      (0x9B)
#define REPORT_ID_MISC_BUTTONS      (1)
#define REPORT_ID_VOLUME_BUTTONS    (2)

#define REPORT_ID_TEAMS_ASP         (0x9A)

// Unit numbers are arbitrary selected
#define UAC2_ENTITY_CLOCK               0x01
// Speaker path
#define UAC2_ENTITY_SPK_INPUT_TERMINAL  0x11
#define UAC2_ENTITY_SPK_FEATURE_UNIT    0x12
#define UAC2_ENTITY_SPK_OUTPUT_TERMINAL 0x13

// Microphone path
#define UAC2_ENTITY_MIC_INPUT_TERMINAL  0x21
#define UAC2_ENTITY_MIC_FEATURE_UNIT    0x22
#define UAC2_ENTITY_MIC_OUTPUT_TERMINAL 0x23

extern const size_t uac2_bytes_per_sample_rx_offset;
extern const size_t uac2_bytes_per_sample_tx_offset;
extern const size_t uac2_ep_out_sz_offset;
extern const size_t uac2_ep_in_sz_offset;

/// @brief Modify the relevant descriptor fields to enumerate as a FullSpeed device
void configure_descriptors_for_full_speed();

#endif /* USB_DESCRIPTORS_H_ */
