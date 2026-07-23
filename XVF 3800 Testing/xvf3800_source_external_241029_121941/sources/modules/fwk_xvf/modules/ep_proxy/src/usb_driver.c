// Copyright 2023-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include <xcore/triggerable.h>
#include <xcore/hwtimer.h>
#include "rtos_interrupt.h"
#include "rtos_printf.h"
#include "xud.h"

#include "rtos_usb.h"
#include "usb_descriptors.h" // For configure_descriptors_for_full_speed()

static uint8_t *ep0_out_last_data_xfer_address;
static uint8_t *setup_packet_address;

static usb_proxy_t proxy_ctx_t1;

RTOS_USB_ISR_CALLBACK_ATTR
void pre_dcd_xcore_int_handler(rtos_usb_t *ctx,
                            void *app_data,
                            uint32_t ep_address,
                            size_t xfer_len,
                            rtos_usb_packet_type_t packet_type,
                            XUD_Result_t res)
{
    if (res != XUD_RES_RST)
    {
        if (endpoint_dir(ep_address) == RTOS_USB_OUT_EP)
        {
            if (packet_type == rtos_usb_setup_packet)
            {
                xassert(setup_packet_address != NULL);
                chan_in_buf_byte(proxy_ctx_t1.c_ep_proxy_xfer_complete, setup_packet_address, xfer_len);
            }
            else
            {
                if (xfer_len > 0)
                {
                    // This is the H2D completed data xfer. It needs to be read in the correct buffer
                    // _usbd_ctrl_buf is defined as static uint8_t _usbd_ctrl_buf[CFG_TUD_ENDPOINT0_SIZE];
                    // in usbd_control.c. How do we access it here without changing a tinyusb source file
                    chan_in_buf_byte(proxy_ctx_t1.c_ep_proxy_xfer_complete, ep0_out_last_data_xfer_address, xfer_len);
                }
            }
        }
    }
}

/*  These functions are intended to be linked on tile[1], to "overload" the
    rtos_usb_ functions used in dcd_xcore.c */
XUD_BusSpeed_t rtos_usb_endpoint_reset(rtos_usb_t *ctx,
                                       uint32_t endpoint_addr)
{
    const uint8_t ep_num = endpoint_num(endpoint_addr);

    chan_out_byte(proxy_ctx_t1.c_ep_proxy[ep_num], e_reset_ep);
    chan_out_byte(proxy_ctx_t1.c_ep_proxy[ep_num], endpoint_addr);
    int usb_bus_speed = chan_in_byte(proxy_ctx_t1.c_ep_proxy[ep_num]);
    // If XUD speed is FS, then change _maxEPsize and _interval in ISO audio EP descriptor
    if(usb_bus_speed == XUD_SPEED_FS)
    {
        configure_descriptors_for_full_speed();
    }
    return (XUD_BusSpeed_t)usb_bus_speed;
}

XUD_Result_t rtos_usb_endpoint_transfer_start(rtos_usb_t *ctx,
                                              uint32_t endpoint_addr,
                                              uint8_t *buffer,
                                              size_t len,
                                              bool is_setup)
{
    XUD_Result_t res;
    const int ep_num = endpoint_num(endpoint_addr);
    const int dir = endpoint_dir(endpoint_addr);

    if (!ctx->reset_received) {
        return XUD_RES_ERR;
    }

    if (is_setup)
    {
        (void) endpoint_addr;
        (void) len;
        setup_packet_address = buffer;
        chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], e_prepare_setup);
        res = (XUD_Result_t)chan_in_byte(proxy_ctx_t1.c_ep_proxy[0]);
    }
    else
    {
        ctx->ep_xfer_info[ep_num][dir].len = len;
        chan_out_byte(proxy_ctx_t1.c_ep_proxy[ep_num], e_usb_endpoint_transfer_start);
        chan_out_byte(proxy_ctx_t1.c_ep_proxy[ep_num], (uint8_t)endpoint_addr);
        chan_out_byte(proxy_ctx_t1.c_ep_proxy[ep_num], (uint8_t)len);

        if (len > 0)
        {
            if (dir == RTOS_USB_IN_EP) {
                chan_out_buf_byte(proxy_ctx_t1.c_ep_proxy[ep_num], buffer, len);
            } else {
                if (ep_num == 0) {
                    ep0_out_last_data_xfer_address = buffer;
                }
            }
        }
        res = (XUD_Result_t)chan_in_byte(proxy_ctx_t1.c_ep_proxy[ep_num]);
    }
    return res;
}

void rtos_usb_endpoint_state_reset(rtos_usb_t *ctx,
                                    uint32_t endpoint_addr)
{
    (void) ctx;

    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], e_reset_ep_by_address);
    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], (uint8_t)endpoint_addr);
    chan_in_byte(proxy_ctx_t1.c_ep_proxy[0]);
}

XUD_Result_t rtos_usb_device_address_set(rtos_usb_t *ctx,
                                            uint32_t endpoint_addr)
{
    (void) ctx;

    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], e_usb_device_address_set);
    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], (uint8_t)endpoint_addr);
    int res = chan_in_byte(proxy_ctx_t1.c_ep_proxy[0]);
    return (XUD_Result_t)res;
}

void rtos_usb_endpoint_stall_set(rtos_usb_t *ctx,
                                    uint32_t endpoint_addr)
{
    (void) ctx;

    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], e_usb_endpoint_stall_set);
    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], (uint8_t)endpoint_addr);
    chan_in_byte(proxy_ctx_t1.c_ep_proxy[0]);
}

void rtos_usb_endpoint_stall_clear(rtos_usb_t *ctx,
                                    uint32_t endpoint_addr)
{
    (void) ctx;

    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], e_usb_endpoint_stall_clear);
    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], (uint8_t)endpoint_addr);
    chan_in_byte(proxy_ctx_t1.c_ep_proxy[0]);
}

void rtos_usb_init(
        rtos_usb_t *ctx,
        uint32_t io_core_mask,
        rtos_usb_isr_cb_t isr_cb,
        void *isr_app_data)
{
    memset(ctx, 0, sizeof(rtos_usb_t));

    ctx->isr_cb = isr_cb;
    ctx->isr_app_data = isr_app_data;
}

DEFINE_RTOS_INTERRUPT_CALLBACK(t1_xfer_cplt_isr, arg)
{
    rtos_usb_t *ctx = (rtos_usb_t*)arg;
    uint8_t ep_num = chan_in_byte(proxy_ctx_t1.c_ep_proxy_xfer_complete);
    uint8_t dir = chan_in_byte(proxy_ctx_t1.c_ep_proxy_xfer_complete);
    uint8_t is_setup = chan_in_byte(proxy_ctx_t1.c_ep_proxy_xfer_complete);
    uint32_t xfer_len = chan_in_word(proxy_ctx_t1.c_ep_proxy_xfer_complete);
    XUD_Result_t res = (XUD_Result_t)chan_in_word(proxy_ctx_t1.c_ep_proxy_xfer_complete);

    if (res == XUD_RES_RST) {
        ctx->reset_received = 1;
    }

    if (ctx->isr_cb != NULL) {
        // This gets around the fact that dcd_xcore_int_handler is static in dcd_xcore.c, so can't be modified nor called directly, but ISRs must also have a stack size known at link time.
        pre_dcd_xcore_int_handler(ctx, ctx->isr_app_data, ctx->ep_xfer_info[ep_num][dir].ep_address, xfer_len, is_setup ? rtos_usb_setup_packet : rtos_usb_data_packet, res);
        ctx->isr_cb(ctx, ctx->isr_app_data, ctx->ep_xfer_info[ep_num][dir].ep_address, xfer_len, is_setup ? rtos_usb_setup_packet : rtos_usb_data_packet, res);
    }
}

static inline void ep_xfer_info_init(rtos_usb_t *ctx,
                                    int ep_num,
                                    int direction)
{
    ctx->ep_xfer_info[ep_num][direction].dir = direction;
    ctx->ep_xfer_info[ep_num][direction].ep_num = ep_num;
    ctx->ep_xfer_info[ep_num][direction].ep_address = (direction << 7) | ep_num;
    ctx->ep_xfer_info[ep_num][direction].usb_ctx = ctx;
}

void rtos_usb_start(
        rtos_usb_t *ctx,
        size_t endpoint_count,
        XUD_EpType endpoint_out_type[],
        XUD_EpType endpoint_in_type[],
        XUD_BusSpeed_t speed,
        XUD_PwrConfig power_source,
        unsigned interrupt_core_id,
        int sof_interrupt_core_id)
{

    for (int i = 0; i < endpoint_count; i++)
    {
        ctx->endpoint_out_type[i] = endpoint_out_type[i];
        ctx->endpoint_in_type[i] = endpoint_in_type[i];

        if (endpoint_out_type[i] != XUD_EPTYPE_DIS) {
            ep_xfer_info_init(ctx, i, RTOS_USB_OUT_EP);
        }
        if (endpoint_in_type[i] != XUD_EPTYPE_DIS) {
            ep_xfer_info_init(ctx, i, RTOS_USB_IN_EP);
        }
    }

#if configNUM_CORES > 1
    uint32_t core_exclude_map;
    rtos_osal_thread_core_exclusion_get(NULL, &core_exclude_map);
    rtos_osal_thread_core_exclusion_set(NULL, ~(1 << interrupt_core_id));
#endif
    triggerable_setup_interrupt_callback(proxy_ctx_t1.c_ep_proxy_xfer_complete, ctx, RTOS_INTERRUPT_CALLBACK(t1_xfer_cplt_isr));

    chan_out_word(proxy_ctx_t1.c_ep_proxy[0], endpoint_count);
    chan_out_buf_byte(proxy_ctx_t1.c_ep_proxy[0], (uint8_t*)&endpoint_out_type[0], endpoint_count*sizeof(XUD_EpType));
    chan_out_word(proxy_ctx_t1.c_ep_proxy[0], endpoint_count);
    chan_out_buf_byte(proxy_ctx_t1.c_ep_proxy[0], (uint8_t*)&endpoint_in_type[0], endpoint_count*sizeof(XUD_EpType));
    chan_out_word(proxy_ctx_t1.c_ep_proxy[0], power_source);
    chan_out_word(proxy_ctx_t1.c_ep_proxy[0], speed);

    triggerable_enable_trigger(proxy_ctx_t1.c_ep_proxy_xfer_complete);
#if configNUM_CORES > 1
    rtos_osal_thread_core_exclusion_set(NULL, core_exclude_map);
#endif
}

void usb_driver_init(chanend_t c_ep0_proxy, chanend_t c_ep_hid_proxy, chanend_t c_ep_proxy_xfer_complete)
{
    // Note: This proxy_ctx_t1 exists on tile[1]
    memset(&proxy_ctx_t1, 0, sizeof(usb_proxy_t));

    proxy_ctx_t1.c_ep_proxy[0] = c_ep0_proxy;
    proxy_ctx_t1.c_ep_proxy[1] = c_ep0_proxy; // This has to exist as there are functions that call this channel expecting it to exist, but we filter commands to it later on.
    proxy_ctx_t1.c_ep_proxy[2] = c_ep_hid_proxy; // TODO Hardcoded, assuming endpoint 2 is HID
    proxy_ctx_t1.c_ep_proxy_xfer_complete = c_ep_proxy_xfer_complete;
}

void rtos_usb_enter_test_mode(rtos_usb_t *ctx,
                            unsigned test_mode)
{
    (void) ctx;

    chan_out_byte(proxy_ctx_t1.c_ep_proxy[0], e_usb_enter_test_mode);
    chan_out_word(proxy_ctx_t1.c_ep_proxy[0], test_mode);
    chan_in_byte(proxy_ctx_t1.c_ep_proxy[0]);
}
