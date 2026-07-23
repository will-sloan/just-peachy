// Copyright 2023-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include <xcore/triggerable.h>
#include <xcore/assert.h>
#include "rtos_interrupt.h"
#include "rtos_osal.h"
#include "rtos_usb.h"
#include "usb_descriptors.h"
#include "xud_xfer_data.h"
#include "tusb_config.h"
#include <string.h>
#include <stdbool.h>
#include "platform/platform_conf.h"
#include "tile_common.h"
#include "usb_buffer.h" // For set_device_reset_event()

#include "usb_proxy_struct.h"
#include "usb_proxy.h"

static usb_proxy_t proxy_ctx_t0;

#undef EP_PROXY_BUFFER_SIZE
#define EP_PROXY_BUFFER_SIZE CFG_TUD_ENDPOINT0_SIZE

#define SINGLE_SET_BIT(bit) (1 << bit)
#define SINGLE_UNSET_BIT(bit) (~SINGLE_SET_BIT(bit))

volatile ep_proxy_definition_t ep_proxy_buffers[] = {
    PROXIED(EP_NUM_EP0),
    NOT_PROXIED(EP_NUM_AUDIO),
    PROXIED(EP_NUM_HID)
};

XUD_Result_t XUD_SetBuffer_Finish(chanend c, XUD_ep e);
static unsigned int expect_prepare_setup_from_isr = 0;

static rtos_usb_t usb_ctx_t0;
static channel_t channel_ep_out[RTOS_USB_ENDPOINT_COUNT_MAX];
static channel_t channel_ep_in[RTOS_USB_ENDPOINT_COUNT_MAX];

void ep_proxy_init(
    channel_t chan_ep0_out,
    channel_t chan_ep0_in,
    channel_t chan_ep1_out,
    channel_t chan_ep1_in,
    chanend_t chan_ep0_proxy,
    chanend_t chan_ep_hid_proxy,
    chanend_t c_ep_proxy_xfer_complete)
{
    rtos_usb_t *ctx = &usb_ctx_t0;

    channel_ep_out[0] = chan_ep0_out;
    channel_ep_out[1] = chan_ep1_out;
    channel_ep_in[0] = chan_ep0_in;
    channel_ep_in[1] = chan_ep1_in;

    // In lieu of rtos_usb_init being run, this function now initialises the ctx.
    memset(ctx, 0, sizeof(rtos_usb_t));
    // Note - this proxy_ctx_t0 exists on tile[0]
    memset(&proxy_ctx_t0, 0, sizeof(usb_proxy_t));
    // EP0 out and in channels
    ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP] = chan_ep0_out.end_b;
    ctx->c_ep[EP_NUM_EP0][RTOS_USB_IN_EP] = chan_ep0_in.end_b;
    proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0] = chan_ep0_proxy;
    proxy_ctx_t0.c_ep_proxy[EP_NUM_AUDIO] = chan_ep0_proxy; // This has to exist as there are functions that call this channel expecting it to exist, but we filter commands to it later on.
    proxy_ctx_t0.c_ep_proxy[EP_NUM_HID] = chan_ep_hid_proxy; // We're hardcoding EP_NUMs here since the descriptors haven't been parsed yet.
    proxy_ctx_t0.c_ep_proxy_xfer_complete = c_ep_proxy_xfer_complete;
}

// Because ep_transfer_complete is statically linked in rtos_usb.c, it is replicated here.
static XUD_Result_t t0_ep_transfer_complete(rtos_usb_t *ctx,
                                        const int ep_num,
                                        const int dir,
                                        size_t *len,
                                        int *is_setup)
{
    XUD_Result_t res = XUD_RES_ERR;

    xassert(ep_num < RTOS_USB_ENDPOINT_COUNT_MAX);

    if (dir == RTOS_USB_IN_EP) {
        res = XUD_SetBuffer_Finish(ctx->c_ep[ep_num][dir], ctx->ep[ep_num][dir]);
        *is_setup = 0;
        *len = ctx->ep_xfer_info[ep_num][dir].len;
    } else {
        /* NOTE: XUD_GetBuffer_Finish() is essentially, xud_data_get_check()
         * combined with xud_data_get_finish(). There is no equivalent that
         * handles the finalization of the setup packet. */
        res = xud_data_get_check(ctx->c_ep[ep_num][dir], len, is_setup);

        if (*len > ctx->ep_xfer_info[ep_num][dir].len) {
            rtos_printf("Length of %d bytes transferred on ep %d direction %d. Should have been <= %d\n", *len, ep_num, dir, ctx->ep_xfer_info[ep_num][dir].len);
        }

        xassert(*len <= ctx->ep_xfer_info[ep_num][dir].len);
        ctx->ep_xfer_info[ep_num][dir].len = *len;

        if (res == XUD_RES_OKAY) {
            if (*is_setup) {
                res = xud_setup_data_get_finish(ctx->ep[ep_num][dir]);
                if (res == XUD_RES_ERR) {
                    rtos_printf("USB XFER ERROR from xud_setup_data_get_finish()!\n");
                }
            } else {
                res = xud_data_get_finish(ctx->ep[ep_num][dir]);
                if (res == XUD_RES_ERR) {
                    rtos_printf("USB XFER ERROR from xud_data_get_finish()!\n");
                }
            }
        } else if (res == XUD_RES_ERR) {
            rtos_printf("USB XFER ERROR from xud_data_get_check()!\n");
        }
    }

    return res;
}

static inline void handle_usb_transfer_complete(rtos_usb_t *ctx, ep_proxy_event_t *event)
{
    chan_out_byte(proxy_ctx_t0.c_ep_proxy_xfer_complete, event->xfer_complete.ep_num);
    chan_out_byte(proxy_ctx_t0.c_ep_proxy_xfer_complete, event->xfer_complete.dir);
    chan_out_byte(proxy_ctx_t0.c_ep_proxy_xfer_complete, event->xfer_complete.is_setup);
    chan_out_word(proxy_ctx_t0.c_ep_proxy_xfer_complete, event->xfer_complete.len);
    chan_out_word(proxy_ctx_t0.c_ep_proxy_xfer_complete, event->xfer_complete.result);

    // xud_data_get_check() ensures that if res is XUD_RES_RST, xfer_len and is_setup are both set to 0
    if((event->xfer_complete.dir == RTOS_USB_OUT_EP) && (event->xfer_complete.len > 0))
    {
        // Send H2D data transfer completed on EP0 to the other tile
        chan_out_buf_byte(proxy_ctx_t0.c_ep_proxy_xfer_complete, (uint8_t*)ep_proxy_buffers[EP_NUM_EP0].buffer, event->xfer_complete.len); // Will this cause the interrupt on chan_ep0_proxy to trigger
    }
}

static void handle_ep_command(rtos_usb_t *ctx, chanend_t c_ep_proxy, uint8_t ep0_cmd)
{
    switch(ep0_cmd)
    {
        case e_reset_ep:
        {
            ctx->reset_received = 1;
            uint8_t ep_addr = chan_in_byte(c_ep_proxy);
            XUD_BusSpeed_t xud_speed;
            xud_speed = rtos_usb_endpoint_reset(ctx, ep_addr);
            set_device_reset_event(xud_speed); // Inform USB Buffer of a device reset event
            chan_out_byte(c_ep_proxy, xud_speed);

            triggerable_enable_trigger(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP]);
            triggerable_enable_trigger(ctx->c_ep[EP_NUM_EP0][RTOS_USB_IN_EP]);
#if HID_CONTROL
            triggerable_enable_trigger(ctx->c_ep[EP_NUM_HID][RTOS_USB_IN_EP]);
#endif
        }
        break;
        case e_prepare_setup:
        {
            if(expect_prepare_setup_from_isr)
            {
                expect_prepare_setup_from_isr = 0;
#if HID_CONTROL
                triggerable_enable_trigger(ctx->c_ep[EP_NUM_HID][RTOS_USB_IN_EP]);
#endif
            }
            bool is_setup = true;

            XUD_Result_t res = rtos_usb_endpoint_transfer_start(ctx, 0x00, (uint8_t *) &ep_proxy_buffers[EP_NUM_EP0].buffer[0], CFG_TUD_ENDPOINT0_SIZE, is_setup);
            xassert(res == XUD_RES_OKAY);

            chan_out_byte(c_ep_proxy, 0);
        }
        break;
        case e_usb_endpoint_transfer_start:
        {
            uint8_t ep_addr = chan_in_byte(c_ep_proxy);
            uint8_t len = chan_in_byte(c_ep_proxy);
            XUD_Result_t res = XUD_RES_OKAY;
            bool is_setup = false;
            if((len > 0) && (endpoint_dir(ep_addr) == RTOS_USB_IN_EP))
            {
                if(endpoint_num(ep_addr) != 0)
                {
                    chan_in_buf_byte(c_ep_proxy, (uint8_t*)ep_proxy_buffers[EP_NUM_HID].buffer, len);

                }
                else
                {
                    chan_in_buf_byte(c_ep_proxy, (uint8_t*)ep_proxy_buffers[EP_NUM_EP0].buffer, len);
                }
            }

            // We should only be handling EP0 traffic here.
            // Fake a return if handling a non-EP0
            if (endpoint_num(ep_addr) != 1)
            {
                if(endpoint_num(ep_addr) == EP_NUM_HID)
                {
                    res = rtos_usb_endpoint_transfer_start(ctx, (uint32_t)ep_addr, (uint8_t*)ep_proxy_buffers[EP_NUM_HID].buffer, len, is_setup);
                }
                else
                {
                    res = rtos_usb_endpoint_transfer_start(ctx, (uint32_t)ep_addr, (uint8_t*)ep_proxy_buffers[EP_NUM_EP0].buffer, len, is_setup);
                }
            }
            else
            {
                res = XUD_RES_OKAY;
            }
            chan_out_byte(c_ep_proxy, res);
        }
        break;
        case e_usb_device_address_set:
        {
            uint8_t dev_addr = chan_in_byte(c_ep_proxy);
            XUD_Result_t res = rtos_usb_device_address_set(ctx, dev_addr);
            chan_out_byte(c_ep_proxy, res);
        }
        break;
        case e_reset_ep_by_address:
        {
            uint8_t ep_addr = chan_in_byte(c_ep_proxy);
            rtos_usb_endpoint_state_reset(ctx, ep_addr);
            chan_out_byte(c_ep_proxy, 0);
        }
        break;
        case e_usb_endpoint_stall_set:
        {
            uint8_t ep_addr = chan_in_byte(c_ep_proxy);
            rtos_usb_endpoint_stall_set(ctx, ep_addr);
            chan_out_byte(c_ep_proxy, 0);
        }
        break;
        case e_usb_endpoint_stall_clear:
        {
            uint8_t ep_addr = chan_in_byte(c_ep_proxy);
            rtos_usb_endpoint_stall_clear(ctx, ep_addr);
            chan_out_byte(c_ep_proxy, 0);
        }
        break;
        case e_usb_enter_test_mode:
        {
            unsigned test_mode = chan_in_word(c_ep_proxy);
            rtos_usb_enter_test_mode(ctx, test_mode);
            chan_out_byte(c_ep_proxy, 0);
        }
        break;
    }
}

DEFINE_RTOS_INTERRUPT_CALLBACK(ep_isr, arg)
{
    rtos_usb_ep_xfer_info_t *ep_xfer_info = arg;
    rtos_usb_t *ctx = ep_xfer_info->usb_ctx;
    const int ep_num = ep_xfer_info->ep_num;
    const int dir = ep_xfer_info->dir;
    size_t xfer_len;
    XUD_Result_t res;

    int is_setup;
    res = t0_ep_transfer_complete(ctx, ep_num, dir, &xfer_len, &is_setup);

    // Everything about USB transfer being serial breaks when we get a XUD_RES_RST.
    // This happens at startup and till a reset is processed, xud continues to send resets without waiting
    // for a reset request to be processed. This completely breaks every design assumption.
    // The only way I can deal with this is by fully disabling all interrupts till a reset request is completed.

    // If we expect a request from the tile 1 usb_isr(), we disable ctx->c_ep[EP_NUM_HID] interrupts till this request is received,
    // otherwise, concurrent requests from tile1 usb_isr() to tile0 and tile 0 usb_ep_isr() to tile 1 will cause a deadlock.
    if(res == XUD_RES_RST)
    {
        xassert(ep_num == EP_NUM_EP0); // We think this only comes in over EP0 - let's check that
        // Disable all core 1 interrupts
        triggerable_disable_trigger(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0]);
        triggerable_disable_trigger(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP]);
        triggerable_disable_trigger(ctx->c_ep[EP_NUM_EP0][RTOS_USB_IN_EP]);
#if HID_CONTROL
        triggerable_disable_trigger(ctx->c_ep[EP_NUM_HID][RTOS_USB_IN_EP]);
#endif
    }
    else if((ep_num == EP_NUM_EP0) && (xfer_len == 0)) // For both EP0 IN and OUT, we do the prepare_setup() after the ZLP xfer completes
    {
        expect_prepare_setup_from_isr = 1;
#if HID_CONTROL
        triggerable_disable_trigger(ctx->c_ep[EP_NUM_HID][RTOS_USB_IN_EP]);
#endif
    }

    ep_xfer_info->res = (int32_t) res;

    ep_proxy_event_t event;
    event.xfer_complete.ep_num = ep_num;
    event.xfer_complete.dir = dir;
    event.xfer_complete.result = res;
    event.xfer_complete.is_setup = is_setup;
    event.xfer_complete.len = xfer_len;

    // Seems like it might be okay to send completed xfer to tile 1 from here itself instead of posting an event in the queue
    // and doing it from rtos_ep0_proxy task.
    handle_usb_transfer_complete(ctx, &event);

    if(res == XUD_RES_RST)
    {
        triggerable_enable_trigger(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0]);
        // The ctx->c_ep will be enabled once the reset is fully processed in handle_ep0_command()
    }
}

DEFINE_RTOS_INTERRUPT_CALLBACK(ep_proxy_isr, arg)
{
    rtos_usb_ep_xfer_info_t *ep_xfer_info = arg;
    rtos_usb_t *ctx = ep_xfer_info->usb_ctx;
    const int ep_num = ep_xfer_info->ep_num; // So we know which c_ep_proxy channel is this request from

    uint8_t cmd = chan_in_byte(proxy_ctx_t0.c_ep_proxy[ep_num]);

    // Seems like it's okay to handle the ep0 command here itself. We can trust tile1 ep0
    // to not issue blocking commands so this should be okay.
    handle_ep_command(ctx, proxy_ctx_t0.c_ep_proxy[ep_num], cmd);
}

static void ep_isr_setup(rtos_usb_t *ctx,
                   int ep_num,
                   int direction)
{
    ctx->ep_xfer_info[ep_num][direction].dir = direction;
    ctx->ep_xfer_info[ep_num][direction].ep_num = ep_num;
    ctx->ep_xfer_info[ep_num][direction].ep_address = (direction << 7) | ep_num;
    ctx->ep_xfer_info[ep_num][direction].usb_ctx = ctx;
    triggerable_setup_interrupt_callback(ctx->c_ep[ep_num][direction], &ctx->ep_xfer_info[ep_num][direction], RTOS_INTERRUPT_CALLBACK(ep_isr));
}

void hid_isr_task(void *args)
{
    rtos_usb_t *ctx = (rtos_usb_t*)&usb_ctx_t0;
    TaskHandle_t *parent_task = (TaskHandle_t*)args;

    uint32_t core_exclude_map;
    rtos_osal_thread_core_exclusion_get(NULL, &core_exclude_map);
    rtos_osal_thread_core_exclusion_set(NULL, SINGLE_UNSET_BIT(EP_PROXY_HID_ISR_CORE));

    triggerable_setup_interrupt_callback(proxy_ctx_t0.c_ep_proxy[EP_NUM_HID],  &ctx->ep_xfer_info[EP_NUM_HID][RTOS_USB_IN_EP], RTOS_INTERRUPT_CALLBACK(ep_proxy_isr));
    triggerable_enable_trigger(proxy_ctx_t0.c_ep_proxy[EP_NUM_HID]);

    rtos_osal_thread_core_exclusion_set(NULL, core_exclude_map);

    xTaskNotify(*parent_task, 1, eSetValueWithOverwrite); // Notify the main task that it's safe to create the remaining Servicers
    vTaskDelete(NULL);
}

void ep_proxy_task(void *app_data)
{
    rtos_usb_t *ctx = (rtos_usb_t*)&usb_ctx_t0;

    uint32_t num_out_endpoints;
    uint32_t num_in_endpoints;
    XUD_EpType epTypeTableOut[RTOS_USB_ENDPOINT_COUNT_MAX];
    XUD_EpType epTypeTableIn[RTOS_USB_ENDPOINT_COUNT_MAX];
    XUD_PwrConfig pwrConfig;
    XUD_BusSpeed_t desiredSpeed;

    // Handshake with tile[1] - gets the numbers of OUT and IN endpoints from the parsed descriptors, and sets up the epTypeTables
    num_out_endpoints = chan_in_word(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0]);
    chan_in_buf_byte(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0], (uint8_t*)&epTypeTableOut[0], num_out_endpoints*sizeof(XUD_EpType));
    num_in_endpoints = chan_in_word(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0]);
    chan_in_buf_byte(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0], (uint8_t*)&epTypeTableIn[0], num_in_endpoints*sizeof(XUD_EpType));
    pwrConfig = chan_in_word(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0]);
    desiredSpeed = chan_in_word(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0]);

    /* Allocate channels for endpoints EP2 and above.
     * EP0 channels are allocated in main since we use c_ep0_out for signalling to _XUD_Main for starting XUD
     * EP1 channels are also allocated there since EP1 is handled in bare metal
     * ep_proxy_init then populates these */
    for (int i = EP_NUM_HID; i < num_out_endpoints; i++)
    {
        if(epTypeTableOut[i] != XUD_EPTYPE_DIS)
        {
            channel_ep_out[i] = chan_alloc();
            ctx->c_ep[i][RTOS_USB_OUT_EP] = channel_ep_out[i].end_b;
        }
    }
    for (int i = EP_NUM_HID; i < num_in_endpoints; i++)
    {
        if(epTypeTableIn[i] != XUD_EPTYPE_DIS)
        {
            channel_ep_in[i] = chan_alloc();
            ctx->c_ep[i][RTOS_USB_IN_EP] = channel_ep_in[i].end_b;
        }
    }

    /* Ensure that all USB interrupts are enabled on the requested core */
    uint32_t core_exclude_map;
    rtos_osal_thread_core_exclusion_get(NULL, &core_exclude_map);
    rtos_osal_thread_core_exclusion_set(NULL,  SINGLE_UNSET_BIT(EP_PROXY_ISR_CORE));

    // Attach ep_isr_setup ISR to HID endpoints as well
    for(int i=0; i<num_out_endpoints; i++)
    {
        if((i==0) || (epTypeTableOut[i] == XUD_EPTYPE_INT))
        {
            ep_isr_setup(ctx, i, RTOS_USB_OUT_EP);
        }
    }

    for(int i=0; i<num_in_endpoints; i++)
    {
        if((i==0) || (epTypeTableIn[i] == XUD_EPTYPE_INT))
        {
            ep_isr_setup(ctx, i, RTOS_USB_IN_EP);
        }
    }

    // One interrupt per endpoint needs to be setup for the proxy <-> endpoint communication
    // Any direction would do, since there's one interrupt per endpoint. TODO Would this work if there are both HID output and input endpoints??
    triggerable_setup_interrupt_callback(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0],  &ctx->ep_xfer_info[EP_NUM_EP0][RTOS_USB_IN_EP], RTOS_INTERRUPT_CALLBACK(ep_proxy_isr));

    /* Restore the core exclusion map for the calling thread */
    rtos_osal_thread_core_exclusion_set(NULL, core_exclude_map);

    TaskHandle_t parent_task = xTaskGetCurrentTaskHandle();
    xTaskCreate(
        hid_isr_task,
        "HID ISR task",
        RTOS_THREAD_STACK_SIZE(hid_isr_task),
        &parent_task,
        appconfTEST_TASK_PRIORITY,
        NULL
    );

    uint32_t val;
    xTaskNotifyWait(0, ~0, &val, portMAX_DELAY);

    triggerable_enable_trigger(proxy_ctx_t0.c_ep_proxy[EP_NUM_EP0]);

    // Signal to wrap_XUD_Main to start USB, and sends required info
    chan_out_word(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], num_out_endpoints);
    chan_out_word(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], num_in_endpoints);
    chan_out_buf_byte(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], (uint8_t *)&epTypeTableOut[0], num_out_endpoints*sizeof(XUD_EpType));
    chan_out_buf_byte(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], (uint8_t *)&epTypeTableIn[0], num_in_endpoints*sizeof(XUD_EpType));
    chan_out_buf_byte(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], (uint8_t *)&channel_ep_out[0], num_out_endpoints*sizeof(channel_t));
    chan_out_buf_byte(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], (uint8_t *)&channel_ep_in[0], num_in_endpoints*sizeof(channel_t));
    chan_out_word(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], pwrConfig);
    chan_out_word(ctx->c_ep[EP_NUM_EP0][RTOS_USB_OUT_EP], desiredSpeed);


    for(int i=0; i<num_out_endpoints; i++)
    {
        if((i==0) || (epTypeTableOut[i] == XUD_EPTYPE_INT))
        {
            ctx->ep[i][RTOS_USB_OUT_EP] = XUD_InitEp(ctx->c_ep[i][RTOS_USB_OUT_EP]); // Blocking! Call after signalling XUD_Main to start
            triggerable_enable_trigger(ctx->c_ep[i][RTOS_USB_OUT_EP]);
        }
    }

    for(int i=0; i<num_in_endpoints; i++)
    {
        if((i==0) || (epTypeTableIn[i] == XUD_EPTYPE_INT))
        {
            ctx->ep[i][RTOS_USB_IN_EP] = XUD_InitEp(ctx->c_ep[i][RTOS_USB_IN_EP]);
            triggerable_enable_trigger(ctx->c_ep[i][RTOS_USB_IN_EP]);
        }
    }

    vTaskDelete(NULL);

    return;
}

void ep_proxy_start(unsigned priority)
{
    xTaskCreate((TaskFunction_t) ep_proxy_task,
        "ep_proxy_task",
        RTOS_THREAD_STACK_SIZE(ep_proxy_task),
        NULL,
        priority,
        NULL);
}
