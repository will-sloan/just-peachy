// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2020 Reinhard Panhuber
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 *
 */

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <xcore/hwtimer.h>

#include "FreeRTOS.h"
#include "stream_buffer.h"

#include "usb_descriptors.h"
#include "tusb.h"
#include "rtos_intertile.h"

#include "app_conf.h"
#include "device_control_usb.h"
#include "res_id_defines.h"
#include "usb_buffer_cmds.h"
#include "usb_audio_volume.h"

// Audio controls
// Current states
static bool mute_mic[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1] = {0}; 						// +1 for master channel 0
static int16_t volume_mic[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX + 1] = {0}; 					// +1 for master channel 0
static bool mute_spk[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_RX + 1] = {0}; 						// +1 for master channel 0
static int16_t volume_spk[CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_RX + 1] = {0}; 					// +1 for master channel 0
static uint32_t sampFreq;
static uint8_t clkValid;

// Range states
audio_control_range_4_n_t(1) sampleFreqRng; 						// Sample frequency range state

static volatile bool mic_interface_open = false;
static volatile bool spkr_interface_open = false;


static device_control_t *device_control_ctx;

// API to support commands sent internally from EP0 to the servicers attached on the device_control_usb_ctx servicer
static control_ret_t send_internal_write_cmd(device_control_t *device_control_ctx, control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len)
{
    uint8_t tx_buf[1]; // For status
    size_t tx_len;
    device_control_request(device_control_ctx,
                                resid,
                                cmd,
                                payload_len);

    // Device control does not expect a constant payload, so cast it away.
    device_control_payload_transfer_bidir(device_control_ctx, (uint8_t *)payload, payload_len, tx_buf, &tx_len);
    return tx_buf[0]; // Status is returned in tx_buf[0];
}

//--------------------------------------------------------------------+
// Device callbacks
//--------------------------------------------------------------------+

// Invoked when device is mounted
void tud_mount_cb(void)
{
    ////rtos_printf("USB mounted\n");
}

// Invoked when device is unmounted
void tud_umount_cb(void)
{
    ////rtos_printf("USB unmounted\n");
}

// Invoked when usb bus is suspended
// remote_wakeup_en : if host allow us  to perform remote wakeup
// Within 7ms, device must draw an average of current less than 2.5 mA from bus
void tud_suspend_cb(bool remote_wakeup_en)
{
    (void) remote_wakeup_en;
    xassert(false);
}

// Invoked when usb bus is resumed
void tud_resume_cb(void)
{

}

//--------------------------------------------------------------------+
// Application Callback API Implementations
//--------------------------------------------------------------------+

// Invoked when audio class specific set request received for an EP
bool tud_audio_set_req_ep_cb(uint8_t rhport,
                             tusb_control_request_t const *p_request,
                             uint8_t *pBuff)
{
    (void) rhport;
    (void) pBuff;

    // We do not support any set range requests here, only current value requests
    TU_VERIFY(p_request->bRequest == AUDIO_CS_REQ_CUR);

    // Page 91 in UAC2 specification
    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    uint8_t ep = TU_U16_LOW(p_request->wIndex);

    (void) channelNum;
    (void) ctrlSel;
    (void) ep;

    return false; 	// Yet not implemented
}

// Invoked when audio class specific set request received for an interface
bool tud_audio_set_req_itf_cb(uint8_t rhport,
                              tusb_control_request_t const *p_request,
                              uint8_t *pBuff)
{
    (void) rhport;
    (void) pBuff;

    // We do not support any set range requests here, only current value requests
    TU_VERIFY(p_request->bRequest == AUDIO_CS_REQ_CUR);

    // Page 91 in UAC2 specification
    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    uint8_t itf = TU_U16_LOW(p_request->wIndex);

    (void) channelNum;
    (void) ctrlSel;
    (void) itf;

    return false; 	// Yet not implemented
}

// Invoked when audio class specific set request received for an entity
bool tud_audio_set_req_entity_cb(uint8_t rhport,
                                 tusb_control_request_t const *p_request,
                                 uint8_t *pBuff)
{
    (void) rhport;

    // Page 91 in UAC2 specification
    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    uint8_t itf = TU_U16_LOW(p_request->wIndex);
    uint8_t entityID = TU_U16_HIGH(p_request->wIndex);

    (void) itf;

    // We do not support any set range requests here, only current value requests
    TU_VERIFY(p_request->bRequest == AUDIO_CS_REQ_CUR);

    // If request is for our feature unit
    if (entityID == UAC2_ENTITY_MIC_FEATURE_UNIT) {
        switch (ctrlSel) {
        case AUDIO_FU_CTRL_MUTE:
            // Request uses format layout 1
            TU_VERIFY(p_request->wLength == sizeof(audio_control_cur_1_t));

            mute_mic[channelNum] = ((audio_control_cur_1_t*) pBuff)->bCur;
            usb_buffer_servicer_resid_internal_mic_mute_t mute_vals[USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_MUTE_NUM_VALUES];
            mute_vals[0] = (usb_buffer_servicer_resid_internal_mic_mute_t)channelNum;
            mute_vals[1] = (usb_buffer_servicer_resid_internal_mic_mute_t)mute_mic[channelNum];
            // Send mic mute to usb buffer
            control_ret_t ret = send_internal_write_cmd(device_control_ctx, USB_BUFFER_SERVICER_RESID, USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_MUTE, (const uint8_t*)mute_vals, USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_MUTE_NUM_VALUES*sizeof(usb_buffer_servicer_resid_internal_mic_mute_t));
            xassert(ret == CONTROL_SUCCESS);
            TU_LOG2("    Set Mute: %d of channel: %u\n", mute_mic[channelNum], channelNum);
            return true;

        case AUDIO_FU_CTRL_VOLUME:
            // Request uses format layout 2
            TU_VERIFY(p_request->wLength == sizeof(audio_control_cur_2_t));

            volume_mic[channelNum] = ((audio_control_cur_2_t*) pBuff)->bCur;
            usb_buffer_servicer_resid_internal_mic_vol_t vol_vals[USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_VOL_NUM_VALUES];
            vol_vals[0] = (usb_buffer_servicer_resid_internal_mic_vol_t)channelNum;
            vol_vals[1] = (usb_buffer_servicer_resid_internal_mic_vol_t)volume_mic[channelNum];
            ret = send_internal_write_cmd(device_control_ctx, USB_BUFFER_SERVICER_RESID, USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_VOL, (const uint8_t*)vol_vals, USB_BUFFER_SERVICER_RESID_INTERNAL_MIC_VOL_NUM_VALUES*sizeof(usb_buffer_servicer_resid_internal_mic_vol_t));
            xassert(ret == CONTROL_SUCCESS);

            TU_LOG2("    Set Volume: %d dB of channel: %u\n", volume_mic[channelNum], channelNum);

            return true;

            // Unknown/Unsupported control
        default:
            TU_BREAKPOINT();
            return false;
        }
    }
    if (entityID == UAC2_ENTITY_SPK_FEATURE_UNIT) {
        switch (ctrlSel) {
        case AUDIO_FU_CTRL_MUTE:
            // Request uses format layout 1
            TU_VERIFY(p_request->wLength == sizeof(audio_control_cur_1_t));

            mute_spk[channelNum] = ((audio_control_cur_1_t*) pBuff)->bCur;
            usb_buffer_servicer_resid_internal_spk_mute_t mute_vals[USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_MUTE_NUM_VALUES];
            mute_vals[0] = (usb_buffer_servicer_resid_internal_spk_mute_t)channelNum;
            mute_vals[1] = (usb_buffer_servicer_resid_internal_spk_mute_t)mute_spk[channelNum];
            // Send spk mute to usb buffer
            control_ret_t ret = send_internal_write_cmd(device_control_ctx, USB_BUFFER_SERVICER_RESID, USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_MUTE, (const uint8_t*)mute_vals, USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_MUTE_NUM_VALUES*sizeof(usb_buffer_servicer_resid_internal_spk_mute_t));
            xassert(ret == CONTROL_SUCCESS);

            TU_LOG2("    Set Mute: %d of channel: %u\n", mute_spk[channelNum], channelNum);

            return true;

        case AUDIO_FU_CTRL_VOLUME:
            // Request uses format layout 2
            TU_VERIFY(p_request->wLength == sizeof(audio_control_cur_2_t));

            volume_spk[channelNum] = ((audio_control_cur_2_t*) pBuff)->bCur;
            usb_buffer_servicer_resid_internal_spk_vol_t vol_vals[USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_VOL_NUM_VALUES];
            vol_vals[0] = (usb_buffer_servicer_resid_internal_spk_vol_t)channelNum;
            vol_vals[1] = (usb_buffer_servicer_resid_internal_spk_vol_t)volume_spk[channelNum];

#if (!(DISABLE_FAREXT_GAIN_MATCHING))
            // 0:master, 1:ch0, 2:ch1. If either master or ch0 vol. is updated
            if((channelNum == 0) || (channelNum == 1))
            {
                int32_t gain_i = (int32_t)(int32_t)volume_spk[0] + (int32_t)(int32_t)volume_spk[1]; //Cascade dB gains
                float gain = (float)(gain_i >> 8); // volume is encoded in 8.8 format and since USB_AUDIO_VOLUME_STEP_DB is set to 1dB, volume is always
                // set as an integer value between USB_AUDIO_MIN_VOLUME_DB and USB_AUDIO_MAX_VOLUME_DB so we can safely assume that the lower 8 bits in the 8.8 number will be 0.

                // Send BECLEAR_SUPERHANDSFREE_AEC_FAR_EXTGAIN command to AEC_RESID
                ret = send_internal_write_cmd(device_control_ctx, AEC_RESID, SHF_AEC_FAR_EXTGAIN_CMD, (const uint8_t*)&gain, 1*sizeof(float));
                xassert(ret == CONTROL_SUCCESS);
            }
#endif
            // Send USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_VOL command to USB_BUFFER_SERVICER_RESID
            ret = send_internal_write_cmd(device_control_ctx, USB_BUFFER_SERVICER_RESID, USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_VOL, (const uint8_t*)vol_vals, USB_BUFFER_SERVICER_RESID_INTERNAL_SPK_VOL_NUM_VALUES*sizeof(usb_buffer_servicer_resid_internal_spk_vol_t));
            xassert(ret == CONTROL_SUCCESS);

            TU_LOG2("    Set Volume: %d dB of channel: %u\n", volume_spk[channelNum], channelNum);

            return true;

            // Unknown/Unsupported control
        default:
            TU_BREAKPOINT();
            return false;
        }
    }
    return false;    // Yet not implemented
}

// Invoked when audio class specific get request received for an EP
bool tud_audio_get_req_ep_cb(uint8_t rhport,
                             tusb_control_request_t const *p_request)
{
    (void) rhport;

    // Page 91 in UAC2 specification
    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    uint8_t ep = TU_U16_LOW(p_request->wIndex);

    (void) channelNum;
    (void) ctrlSel;
    (void) ep;

    //	return tud_control_xfer(rhport, p_request, &tmp, 1);

    return false; 	// Yet not implemented
}

// Invoked when audio class specific get request received for an interface
bool tud_audio_get_req_itf_cb(uint8_t rhport,
                              tusb_control_request_t const *p_request)
{
    (void) rhport;

    // Page 91 in UAC2 specification
    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    uint8_t itf = TU_U16_LOW(p_request->wIndex);

    (void) channelNum;
    (void) ctrlSel;
    (void) itf;

    return false; 	// Yet not implemented
}

// Invoked when audio class specific get request received for an entity
bool tud_audio_get_req_entity_cb(uint8_t rhport,
                                 tusb_control_request_t const *p_request)
{
    (void) rhport;

    // Page 91 in UAC2 specification
    uint8_t channelNum = TU_U16_LOW(p_request->wValue);
    uint8_t ctrlSel = TU_U16_HIGH(p_request->wValue);
    // uint8_t itf = TU_U16_LOW(p_request->wIndex); 			// Since we have only one audio function implemented, we do not need the itf value
    uint8_t entityID = TU_U16_HIGH(p_request->wIndex);

    // Input terminal (Microphone input)
    if (entityID == UAC2_ENTITY_MIC_INPUT_TERMINAL) {
        switch (ctrlSel) {
        case AUDIO_TE_CTRL_CONNECTOR:
            ;
            // The terminal connector control only has a get request with only the CUR attribute.

            audio_desc_channel_cluster_t ret;

            // Those are dummy values for now
            ret.bNrChannels = CFG_TUD_AUDIO_FUNC_1_N_CHANNELS_TX;
            ret.bmChannelConfig = 0;
            ret.iChannelNames = 0;

            TU_LOG2("    Get terminal connector\r\n");
            ////rtos_printf("Get terminal connector\r\n");

            return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, (void*) &ret, sizeof(ret));

            // Unknown/Unsupported control selector
        default:
            TU_BREAKPOINT();
            return false;
        }
    }

    // Feature unit
    if (entityID == UAC2_ENTITY_MIC_FEATURE_UNIT) {
        switch (ctrlSel) {
        case AUDIO_FU_CTRL_MUTE:
            // Audio control mute cur parameter block consists of only one byte - we thus can send it right away
            // There does not exist a range parameter block for mute
            TU_LOG2("    Get Mute of channel: %u\r\n", channelNum);
            return tud_control_xfer(rhport, p_request, &mute_mic[channelNum], 1);

        case AUDIO_FU_CTRL_VOLUME:

            switch (p_request->bRequest) {
            case AUDIO_CS_REQ_CUR:
                TU_LOG2("    Get Volume of channel: %u\r\n", channelNum);
                return tud_control_xfer(rhport, p_request, &volume_mic[channelNum], sizeof(volume_mic[channelNum]));
            case AUDIO_CS_REQ_RANGE:
                TU_LOG2("    Get Volume range of channel: %u\r\n", channelNum);

                // Copy values - only for testing - better is version below
                audio_control_range_2_n_t(1) ret;

                ret.wNumSubRanges = 1;
                ret.subrange[0].bMin = USB_AUDIO_MIN_VOLUME_DB;
                ret.subrange[0].bMax = USB_AUDIO_MAX_VOLUME_DB;
                ret.subrange[0].bRes = USB_AUDIO_VOLUME_STEP_DB;

                return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, (void*) &ret, sizeof(ret));

                // Unknown/Unsupported control
            default:
                TU_BREAKPOINT();
                return false;
            }

            // Unknown/Unsupported control
        default:
            TU_BREAKPOINT();
            return false;
        }
    }

    if (entityID == UAC2_ENTITY_SPK_FEATURE_UNIT) {
        switch (ctrlSel) {
        case AUDIO_FU_CTRL_MUTE:
            // Audio control mute cur parameter block consists of only one byte - we thus can send it right away
            // There does not exist a range parameter block for mute
            TU_LOG2("    Get Mute of channel: %u\r\n", channelNum);
            return tud_control_xfer(rhport, p_request, &mute_spk[channelNum], 1);

        case AUDIO_FU_CTRL_VOLUME:

            switch (p_request->bRequest) {
            case AUDIO_CS_REQ_CUR:
                TU_LOG2("    Get Volume of channel: %u\r\n", channelNum);
                return tud_control_xfer(rhport, p_request, &volume_spk[channelNum], sizeof(volume_spk[channelNum]));
            case AUDIO_CS_REQ_RANGE:
                TU_LOG2("    Get Volume range of channel: %u\r\n", channelNum);

                audio_control_range_2_n_t(1) ret;

                ret.wNumSubRanges = 1;
                ret.subrange[0].bMin = USB_AUDIO_MIN_VOLUME_DB;
                ret.subrange[0].bMax = USB_AUDIO_MAX_VOLUME_DB;
                ret.subrange[0].bRes = USB_AUDIO_VOLUME_STEP_DB;

                return tud_audio_buffer_and_schedule_control_xfer(rhport, p_request, (void*) &ret, sizeof(ret));

                // Unknown/Unsupported control
            default:
                TU_BREAKPOINT();
                return false;
            }

            // Unknown/Unsupported control
        default:
            TU_BREAKPOINT();
            return false;
        }
    }

    // Clock Source unit
    if (entityID == UAC2_ENTITY_CLOCK) {
        switch (ctrlSel) {
        case AUDIO_CS_CTRL_SAM_FREQ:

            // channelNum is always zero in this case

            switch (p_request->bRequest) {
            case AUDIO_CS_REQ_CUR:
                TU_LOG2("    Get Sample Freq.\r\n");
                return tud_control_xfer(rhport, p_request, &sampFreq, sizeof(sampFreq));
            case AUDIO_CS_REQ_RANGE:
                TU_LOG2("    Get Sample Freq. range\r\n");
                //((tusb_control_request_t *)p_request)->wLength = 14;
                return tud_control_xfer(rhport, p_request, &sampleFreqRng, sizeof(sampleFreqRng));

                // Unknown/Unsupported control
            default:
                TU_BREAKPOINT();
                return false;
            }

        case AUDIO_CS_CTRL_CLK_VALID:
            // Only cur attribute exists for this request
            TU_LOG2("    Get Sample Freq. valid\r\n");
            return tud_control_xfer(rhport, p_request, &clkValid, sizeof(clkValid));

            // Unknown/Unsupported control
        default:
            TU_BREAKPOINT();
            return false;
        }
    }

    TU_LOG2("  Unsupported entity: %d\r\n", entityID);
    return false; 	// Yet not implemented
}

bool tud_audio_set_itf_cb(uint8_t rhport,
                          tusb_control_request_t const *p_request)
{
    (void) rhport;
    uint8_t const itf = tu_u16_low(tu_le16toh(p_request->wIndex));
    uint8_t const alt = tu_u16_low(tu_le16toh(p_request->wValue));
    usb_buffer_servicer_resid_internal_alt_interface_t vals[USB_BUFFER_SERVICER_RESID_INTERNAL_ALT_INTERFACE_NUM_VALUES];
    vals[0] = (usb_buffer_servicer_resid_internal_alt_interface_t)itf;
    vals[1] = (usb_buffer_servicer_resid_internal_alt_interface_t)alt;
    // Send ALT setting to usb_buffer
    control_ret_t ret = send_internal_write_cmd(device_control_ctx, USB_BUFFER_SERVICER_RESID, USB_BUFFER_SERVICER_RESID_INTERNAL_ALT_INTERFACE, (const uint8_t*)vals, USB_BUFFER_SERVICER_RESID_INTERNAL_ALT_INTERFACE_NUM_VALUES*sizeof(usb_buffer_servicer_resid_internal_alt_interface_t));
    xassert(ret == CONTROL_SUCCESS);

#if AUDIO_OUTPUT_ENABLED
    if (itf == ITF_NUM_AUDIO_STREAMING_SPK) {
        /* In case the interface is reset without
         * closing it first */
        spkr_interface_open = false;
    }
#endif
#if AUDIO_INPUT_ENABLED
    if (itf == ITF_NUM_AUDIO_STREAMING_MIC) {
        /* In case the interface is reset without
         * closing it first */
        mic_interface_open = false;
    }
#endif

    ////rtos_printf("Set audio interface %d alt %d\n", itf, alt);

    return true;
}

bool tud_audio_set_itf_close_EP_cb(uint8_t rhport,
                                   tusb_control_request_t const *p_request)
{
    (void) rhport;
    uint8_t const itf = tu_u16_low(tu_le16toh(p_request->wIndex));
    uint8_t const alt = tu_u16_low(tu_le16toh(p_request->wValue));
    usb_buffer_servicer_resid_internal_alt_interface_t vals[USB_BUFFER_SERVICER_RESID_INTERNAL_ALT_INTERFACE_NUM_VALUES];
    vals[0] = (usb_buffer_servicer_resid_internal_alt_interface_t)itf;
    vals[1] = (usb_buffer_servicer_resid_internal_alt_interface_t)alt;
    // Send ALT setting to usb_buffer
    control_ret_t ret = send_internal_write_cmd(device_control_ctx, USB_BUFFER_SERVICER_RESID, USB_BUFFER_SERVICER_RESID_INTERNAL_ALT_INTERFACE, (const uint8_t*)vals, USB_BUFFER_SERVICER_RESID_INTERNAL_ALT_INTERFACE_NUM_VALUES*sizeof(usb_buffer_servicer_resid_internal_alt_interface_t));
    xassert(ret == CONTROL_SUCCESS);

#if AUDIO_OUTPUT_ENABLED
    if (itf == ITF_NUM_AUDIO_STREAMING_SPK) {
        spkr_interface_open = false;
    }
#endif
#if AUDIO_INPUT_ENABLED
    if (itf == ITF_NUM_AUDIO_STREAMING_MIC) {
        mic_interface_open = false;
    }
#endif

    ////rtos_printf("Close audio interface %d alt %d\n", itf, alt);

    return true;
}

void usb_audio_init(rtos_intertile_t *intertile_ctx,
                    unsigned priority)
{
    // Init values
    sampFreq = appconfUSB_AUDIO_SAMPLE_RATE;
    clkValid = 1;

    sampleFreqRng.wNumSubRanges = 1;
    sampleFreqRng.subrange[0].bMin = appconfUSB_AUDIO_SAMPLE_RATE;
    sampleFreqRng.subrange[0].bMax = appconfUSB_AUDIO_SAMPLE_RATE;
    sampleFreqRng.subrange[0].bRes = 0;

    device_control_ctx = device_control_usb_get_ctrl_ctx_cb();
}
