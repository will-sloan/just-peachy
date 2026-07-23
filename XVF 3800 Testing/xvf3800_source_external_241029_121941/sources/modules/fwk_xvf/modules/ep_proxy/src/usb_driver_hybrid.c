// Copyright 2023-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT USB_HYBRID
#ifndef DEBUG_PRINT_ENABLE_USB_HYBRID
    #define DEBUG_PRINT_ENABLE_USB_HYBRID 0
#endif
#include "debug_print.h"

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
#include "xud_xfer_data.h"
#include "usb_descriptors.h" // For configure_descriptors_for_full_speed()
#include "usb_buffer.h"

#define SETSR(c) asm volatile("setsr %0" : : "n"(c));
#define CLRSR(c) asm volatile("clrsr %0" : : "n"(c));

XUD_Result_t XUD_SetBuffer_Finish(chanend c, XUD_ep e);

static rtos_osal_thread_t usb_buffer_hil_thread;

static void usb_xud_thread(rtos_usb_t *ctx)
{
    /*
     * XUD_Main() appears to require that interrupts be initially disabled.
     */
    rtos_interrupt_mask_all();

    /*
     * XUD_Main() itself uses interrupts, and does re-enable them. However,
     * it assumes that KEDI is not set, therefore it is cleared here.
     */
    CLRSR(XS1_SR_KEDI_MASK);

    (void) s_chan_in_byte(ctx->c_sof_xud);

    rtos_printf("Starting XUD_Main() on core %d with %d endpoints\n", rtos_core_id_get(), ctx->endpoint_count);

    XUD_Main(ctx->c_ep_out_xud,
             ctx->endpoint_count,
             ctx->c_ep_in_xud,
             ctx->endpoint_count,
             ctx->c_sof_xud, // We want the SOFs to go to usb_buffer!
             ctx->endpoint_out_type,
             ctx->endpoint_in_type,
             ctx->speed,
             ctx->power_source);

    SETSR(XS1_SR_KEDI_MASK);
    rtos_interrupt_unmask_all();

    vTaskDelete(NULL);
}

static XUD_Result_t ep_transfer_complete(rtos_usb_t *ctx,
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

DEFINE_RTOS_INTERRUPT_CALLBACK(usb_isr, arg)
{
    rtos_usb_ep_xfer_info_t *ep_xfer_info = arg;
    rtos_usb_t *ctx = ep_xfer_info->usb_ctx;
    const int ep_num = ep_xfer_info->ep_num;
    const int dir = ep_xfer_info->dir;
    size_t xfer_len;
    XUD_Result_t res;

    if (ctx->ep[ep_num][dir] != 0) {
        int is_setup;
        res = ep_transfer_complete(ctx, ep_num, dir, &xfer_len, &is_setup);
        ep_xfer_info->res = (int32_t) res;

        if (res == XUD_RES_RST) {
            ctx->reset_received = 1;
        }

        if (ctx->isr_cb != NULL) {
            ctx->isr_cb(ctx, ctx->isr_app_data, ep_xfer_info->ep_address, xfer_len, is_setup ? rtos_usb_setup_packet : rtos_usb_data_packet, res);
        }
    } else {
        ctx->ep[ep_num][dir] = XUD_InitEp(ctx->c_ep[ep_num][dir]);
        rtos_printf("EP %d %d initialized\n", ep_num, dir);
    }
}

DEFINE_RTOS_INTERRUPT_CALLBACK(usb_sof_isr, arg)
{
    rtos_usb_t *ctx = arg;

    (void) s_chan_in_word(ctx->c_sof);

    if (ctx->isr_cb != NULL) {
        ctx->isr_cb(ctx, ctx->isr_app_data, 0, 0, rtos_usb_sof_packet, XUD_RES_OKAY);
    }
}

static inline int endpoint_num(uint32_t endpoint_addr)
{
    return endpoint_addr & 0xF;
}

static inline int endpoint_dir(uint32_t endpoint_addr)
{
    return (endpoint_addr >> 7) & 1;
}

XUD_Result_t rtos_usb_endpoint_ready(rtos_usb_t *ctx,
                                     uint32_t endpoint_addr,
                                     unsigned timeout)
{
    const int ep_num = endpoint_num(endpoint_addr);
    const int dir = endpoint_dir(endpoint_addr);
    rtos_osal_tick_t start_time;

    start_time = rtos_osal_tick_get();
    while (ctx->ep[ep_num][dir] == 0 && rtos_osal_tick_get() - start_time < timeout) {
        rtos_osal_delay(1);
    }

    if (ctx->ep[ep_num][dir] != 0) {
        return XUD_RES_OKAY;
    } else {
        return XUD_RES_ERR;
    }
}

XUD_Result_t rtos_usb_all_endpoints_ready(rtos_usb_t *ctx,
                                          unsigned timeout)
{
    rtos_osal_tick_t start_time;

    start_time = rtos_osal_tick_get();
    while (!ctx->reset_received && rtos_osal_tick_get() - start_time < timeout) {
        rtos_osal_delay(1);
    }

    if (ctx->reset_received) {
        return XUD_RES_OKAY;
    } else {
        return XUD_RES_ERR;
    }
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

    xassert(ep_num < RTOS_USB_ENDPOINT_COUNT_MAX);

    if (!ctx->reset_received) {
        return XUD_RES_ERR;
    }
    if(ep_num == 1) // Audio EP is handled in bare-metal
    {
        return XUD_RES_OKAY;
    }

    ctx->ep_xfer_info[ep_num][dir].len = len;

    if (dir == RTOS_USB_IN_EP) {
        res = XUD_SetReady_InPtr(ctx->ep[ep_num][dir], (unsigned int)buffer, len);
    } else {
        if (is_setup) {
            // NOTE: A candidate name for this function in lib_xud would be: XUD_SetReady_SetupPtr
            res = xud_setup_data_get_start(ctx->ep[ep_num][dir], buffer);
        } else {
            res = XUD_SetReady_OutPtr(ctx->ep[ep_num][dir], (unsigned int)buffer);
        }
    }

    return res;
}

XUD_BusSpeed_t rtos_usb_endpoint_reset(rtos_usb_t *ctx,
                                       uint32_t endpoint_addr)
{
    uint8_t ep_num = endpoint_num(endpoint_addr);
    uint8_t dir = endpoint_dir(endpoint_addr);

    XUD_ep one = ctx->ep[ep_num][dir];
    XUD_ep *two = NULL;

    xassert(ctx->reset_received);

    dir = dir ? 0 : 1;

    if (ctx->ep[ep_num][dir] != 0) {
        two = &ctx->ep[ep_num][dir];
    }

    if (one == 0) {
        xassert(two != NULL);
        one = *two;
        two = NULL;
    }

    return XUD_ResetEndpoint(one, two);
}

static void ep_cfg(rtos_usb_t *ctx,
                   int ep_num,
                   int direction,
                   bool setup_interrupt /* To allow the hybrid thing*/)
{
    channel_t tmp_chan = chan_alloc();

    xassert(tmp_chan.end_a != 0);
    if (direction == RTOS_USB_OUT_EP) {
        ctx->c_ep_out_xud[ep_num] = tmp_chan.end_a;
    } else {
        ctx->c_ep_in_xud[ep_num] = tmp_chan.end_a;
    }
    ctx->c_ep[ep_num][direction] = tmp_chan.end_b;

    ctx->ep_xfer_info[ep_num][direction].dir = direction;
    ctx->ep_xfer_info[ep_num][direction].ep_num = ep_num;
    ctx->ep_xfer_info[ep_num][direction].ep_address = (direction << 7) | ep_num;
    ctx->ep_xfer_info[ep_num][direction].usb_ctx = ctx;
    if(setup_interrupt == true)
    {
        triggerable_setup_interrupt_callback(ctx->c_ep[ep_num][direction], &ctx->ep_xfer_info[ep_num][direction], RTOS_INTERRUPT_CALLBACK(usb_isr));
        triggerable_enable_trigger(ctx->c_ep[ep_num][direction]);
    }
}

void rtos_usb_enter_test_mode(rtos_usb_t *ctx,
                            unsigned test_mode)
{
    XUD_SetTestMode(ctx->ep[0][RTOS_USB_OUT_EP], test_mode);
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
    int i;
    uint32_t core_exclude_map;

    rtos_printf("In rtos_usb_start()\n");

    ctx->power_source = power_source;
    ctx->speed = speed;

    xassert(endpoint_count > 0 && endpoint_count <= RTOS_USB_ENDPOINT_COUNT_MAX);
    ctx->endpoint_count = endpoint_count;

    rtos_printf("endpoint_count = %d\n", endpoint_count);

    /* Ensure that all USB interrupts are enabled on the requested core */
    rtos_osal_thread_core_exclusion_get(NULL, &core_exclude_map);

    if (sof_interrupt_core_id >= 0) {
        ctx->sof_interrupt_enabled = 1;
        rtos_osal_thread_core_exclusion_set(NULL, ~(1 << sof_interrupt_core_id));
        triggerable_setup_interrupt_callback(ctx->c_sof, ctx, RTOS_INTERRUPT_CALLBACK(usb_sof_isr));
        triggerable_enable_trigger(ctx->c_sof);
    }

    rtos_osal_thread_core_exclusion_set(NULL, ~(1 << interrupt_core_id));

    for (i = 0; i < endpoint_count; i++) {

        ctx->endpoint_out_type[i] = endpoint_out_type[i];
        ctx->endpoint_in_type[i] = endpoint_in_type[i];
        rtos_printf("ep %d: ep_out_type = 0x%x, ep_in_type = 0x%x\n", i, ctx->endpoint_out_type[i], ctx->endpoint_in_type[i]);

        if (endpoint_out_type[i] != XUD_EPTYPE_DIS) {
            if(endpoint_out_type[i] != XUD_EPTYPE_ISO)
            {
                ep_cfg(ctx, i, RTOS_USB_OUT_EP, true);
            }
            else // Isochronous endpoints are handled in bare-metal
            {
                ep_cfg(ctx, i, RTOS_USB_OUT_EP, false);
            }
        }
        if (endpoint_in_type[i] != XUD_EPTYPE_DIS) {
            if(endpoint_in_type[i] != XUD_EPTYPE_ISO)
            {
                ep_cfg(ctx, i, RTOS_USB_IN_EP, true);
            }
            else // Isochronous endpoints are handled in bare-metal
            {
                ep_cfg(ctx, i, RTOS_USB_IN_EP, false);
            }
        }
    }

    /* Tells the I/O thread to enter XUD_Main() */
    s_chan_out_byte(ctx->c_sof, 0);

    // Signal usb_buffer_wrapper. We do this after signalling usb_xud_thread since usb_buffer also selects on the c_sof
    xTaskNotify(usb_buffer_hil_thread.thread, 1, eSetValueWithOverwrite); // Notify the main task that it's safe to create the remaining Servicers

    /* Restore the core exclusion map for the calling thread */
    rtos_osal_thread_core_exclusion_set(NULL, core_exclude_map);
}

static rtos_usb_t *rtos_usb_ctx_save = NULL;
void rtos_usb_init(
        rtos_usb_t *ctx,
        uint32_t io_core_mask,
        rtos_usb_isr_cb_t isr_cb,
        void *isr_app_data)
{
    // HACK. Save the ctx address so usb_buffer_wrapper thread can access it to get the channels it shares with XUD
    rtos_usb_ctx_save = ctx;

    channel_t tmp_chan;

    memset(ctx, 0, sizeof(rtos_usb_t));

    ctx->isr_cb = isr_cb;
    ctx->isr_app_data = isr_app_data;

    tmp_chan = chan_alloc();
    xassert(tmp_chan.end_a != 0);
    ctx->c_sof_xud = tmp_chan.end_a;
    ctx->c_sof = tmp_chan.end_b;

    rtos_osal_thread_create(
            &ctx->hil_thread,
            "usb_hil_thread",
            (rtos_osal_entry_function_t) usb_xud_thread,
            ctx,
            RTOS_THREAD_STACK_SIZE(usb_xud_thread),
            RTOS_OSAL_HIGHEST_PRIORITY);

    /* Ensure the USB thread is never preempted */
    rtos_osal_thread_preemption_disable(&ctx->hil_thread);
    /* And ensure it only runs on one of the specified cores */
    rtos_osal_thread_core_exclusion_set(&ctx->hil_thread, ~io_core_mask);
}

void usb_buffer_wrapper_thread(void *args)
{
    chanend_t chan_usb_to_i2s = (chanend_t)args;
    // Wait to be notified before it's safe to start usb_buffer()
    uint32_t val;
    xTaskNotifyWait(0, ~0, &val, portMAX_DELAY);

    // Can't seem to send more than 4 args so send ref to struct http://bugzilla/show_bug.cgi?id=18745
    usb_buffer_args_t usb_task_args = {
        .chan_ep_audio_out = rtos_usb_ctx_save->c_ep[1][RTOS_USB_OUT_EP],
        .chan_ep_audio_in = rtos_usb_ctx_save->c_ep[1][RTOS_USB_IN_EP],
        .chan_usb_to_i2s = chan_usb_to_i2s,
        .chan_sof = rtos_usb_ctx_save->c_sof
    };
    usb_buffer(&usb_task_args);
    vTaskDelete(NULL);
}

void usb_buffer_init(chanend_t chan_usb_to_i2s)
{
    rtos_osal_thread_create(
            &usb_buffer_hil_thread,
            "usb_buffer_hil_thread",
            (rtos_osal_entry_function_t)usb_buffer_wrapper_thread,
            (void*)chan_usb_to_i2s,
            RTOS_THREAD_STACK_SIZE(usb_buffer_wrapper_thread),
            RTOS_OSAL_HIGHEST_PRIORITY);

    /* Ensure the USB thread is never preempted */
    rtos_osal_thread_preemption_disable(&usb_buffer_hil_thread);
    /* And ensure it only runs on one of the specified cores */
    rtos_osal_thread_core_exclusion_set(&usb_buffer_hil_thread, ~(1 << appconfUSB_BUFFER_CORE));
}



static inline unsigned ep_event_flag(const int ep_num,
                                     const int dir)
{
    return 1 << (ep_num + (dir ? RTOS_USB_ENDPOINT_COUNT_MAX : 0));
}

RTOS_USB_ISR_CALLBACK_ATTR
static void usb_simple_isr_cb(rtos_usb_t *ctx,
                              void *app_data,
                              uint32_t ep_address,
                              size_t xfer_len,
                              rtos_usb_packet_type_t packet_type,
                              XUD_Result_t res)

{
    rtos_osal_event_group_t *event_group = app_data;
    (void) xfer_len;
    (void) res;

    if (packet_type == rtos_usb_data_packet || packet_type == rtos_usb_setup_packet) {
        rtos_osal_event_group_set_bits(event_group,
                                       ep_event_flag(endpoint_num(ep_address),
                                                     endpoint_dir(ep_address)));
    }
}

static int endpoint_wait(rtos_usb_t *ctx,
                         const uint32_t ep_flags,
                         unsigned timeout)
{
    rtos_osal_status_t status;
    uint32_t flags;
    rtos_osal_event_group_t *event_group = ctx->isr_app_data;

    status = rtos_osal_event_group_get_bits(
            event_group,
            ep_flags,
            RTOS_OSAL_AND_CLEAR,
            &flags,
            timeout);

    if (status == RTOS_OSAL_SUCCESS) {
        return 0;
    } else {
        return -1;
    }
}

XUD_Result_t rtos_usb_simple_transfer_complete(rtos_usb_t *ctx,
                                               uint32_t endpoint_addr,
                                               size_t *len,
                                               unsigned timeout)
{
    const int ep_num = endpoint_num(endpoint_addr);
    const int dir = endpoint_dir(endpoint_addr);

    if (endpoint_wait(ctx, ep_event_flag(ep_num, dir), timeout) == 0) {
        if (len != NULL) {
            *len = ctx->ep_xfer_info[ep_num][dir].len;
        }
        return ctx->ep_xfer_info[ep_num][dir].res;
    } else {
        return XUD_RES_ERR;
    }
}


void rtos_usb_simple_init(
        rtos_usb_t *ctx,
        uint32_t io_core_mask)
{
    static rtos_osal_event_group_t event_group;

    rtos_osal_event_group_create(&event_group, "usb_ev_grp");

    rtos_usb_init(
            ctx,
            io_core_mask,
            usb_simple_isr_cb,
            &event_group);
}
