// Copyright 2022-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// tile 0 main. Starts all top level baremetal and rtos threads.

#define DEBUG_UNIT MAIN_TILE0
#ifndef DEBUG_PRINT_ENABLE_MAIN_TILE0
    #define DEBUG_PRINT_ENABLE_MAIN_TILE0 0
#endif
#include "debug_print.h"

#include "FreeRTOS.h"
#include "rtos_macros.h"
#include "xcore/chanend.h"
#include "xcore/parallel.h"
#include "task.h"


#include <stddef.h>
#include <stdlib.h>
#include <string.h>


// bsp
#include "platform/platform_init.h"
#include "platform/driver_instances.h"
#include "app_conf.h"
#include "platform.h"
#include "tile_common.h"

#include "data_plane.h"
#include "servicer.h"
#include "xud_device.h"
#include "usb_buffer.h"
#include "pll_servicer.h"

#include "usb_proxy.h"

TaskHandle_t io_config_servicer_parent_task = NULL;

#if ( 0 < DFU_CONTROL ) && appconfUSB_ENABLED
/// @brief function to send to tile 1 the information to configure the DFU image context
static void send_dfu_info()
{
    // Send all the necessary information of the DFU Image Context
    rtos_dfu_image_t * dfu_image_ctx = get_dfu_image_ctx();
    rtos_intertile_t * intertile_ctx = get_intertile_ctx();
    uint32_t value = dfu_image_ctx->factory_image_ctx.startAddress;
    rtos_intertile_tx(intertile_ctx, appconfUSB_MANAGER_SYNC_PORT, &value, sizeof(value));
    value = dfu_image_ctx->factory_image_ctx.size;
    rtos_intertile_tx(intertile_ctx, appconfUSB_MANAGER_SYNC_PORT, &value, sizeof(value));
    value = dfu_image_ctx->factory_image_ctx.version;
    rtos_intertile_tx(intertile_ctx, appconfUSB_MANAGER_SYNC_PORT, &value, sizeof(value));
    value = dfu_image_ctx->upgrade_image_ctx.startAddress;
    rtos_intertile_tx(intertile_ctx, appconfUSB_MANAGER_SYNC_PORT, &value, sizeof(value));
    value = dfu_image_ctx->upgrade_image_ctx.size;
    rtos_intertile_tx(intertile_ctx, appconfUSB_MANAGER_SYNC_PORT, &value, sizeof(value));
    value = dfu_image_ctx->upgrade_image_ctx.version;
    rtos_intertile_tx(intertile_ctx, appconfUSB_MANAGER_SYNC_PORT, &value, sizeof(value));
    value = dfu_image_ctx->data_partition_base_addr;
    rtos_intertile_tx(intertile_ctx, appconfUSB_MANAGER_SYNC_PORT, &value, sizeof(value));
}
#endif
/// @brief this tiles rtos entry
static void rtos_app(void* args)
{
    debug_printf("in os on tile[%d]\n", THIS_XCORE_TILE);

    servicer_t** servicers = (servicer_t**)args;

    platform_start();

#if ( 0 < DFU_CONTROL ) && appconfUSB_ENABLED
    send_dfu_info();
#endif

    xTaskCreate(
        gpo_servicer,
        "GPO task",
        RTOS_THREAD_STACK_SIZE(gpo_servicer),
        servicers[GPO_SERVICER_INDEX],
        appconfTEST_TASK_PRIORITY,
        NULL
    );

    xTaskCreate(
        servicer_task,
        "PP servicer",
        RTOS_THREAD_STACK_SIZE(servicer_task),
        servicers[PP_SERVICER_INDEX],
        appconfTEST_TASK_PRIORITY,
        NULL
    );

#if ((DFU_CONTROL > 0) && (!appconfUSB_ENABLED))
    xTaskCreate(
        dfu_servicer,
        "DFU servicer",
        RTOS_THREAD_STACK_SIZE(servicer_task),
        servicers[DFU_SERVICER_INDEX],
        appconfTEST_TASK_PRIORITY,
        NULL
    );
#endif

    xTaskCreate(
        servicer_task,
        "USB Buffer servicer",
        RTOS_THREAD_STACK_SIZE(servicer_task),
        servicers[USB_BUFFER_SERVICER_INDEX],
        appconfTEST_TASK_PRIORITY,
        NULL
    );

    xTaskCreate(
        supply_pll_status_task,
        "supply_pll_status_task",
        RTOS_THREAD_STACK_SIZE(supply_pll_status_task),
        NULL,
        appconfTEST_TASK_PRIORITY,
        NULL
    );

    /* When we spin up the servicers, they block the intertile context. This
     * means that we need to spin up the endpoint proxy afterwards, so that
     * when USB starts we are ready to accept communication straight away */

#if appconfUSB_ENABLED
    ep_proxy_start(configMAX_PRIORITIES-1);
#endif

    // done
    vTaskDelete(NULL);
}

DECLARE_JOB(wrap_XUD_Main, (chanend_t, chanend_t));
void wrap_XUD_Main(chanend_t c_ep0_out_a, chanend_t c_sof)
{
    XUD_EpType epTypeTableOut[RTOS_USB_ENDPOINT_COUNT_MAX];
    XUD_EpType epTypeTableIn[RTOS_USB_ENDPOINT_COUNT_MAX];
    channel_t channel_ep_out[RTOS_USB_ENDPOINT_COUNT_MAX];
    channel_t channel_ep_in[RTOS_USB_ENDPOINT_COUNT_MAX];

    if(get_core_burn_status() != 0){
        SET_FAST_MODE();
    }
    // The order in which things happen
    // 1. offtile ep0 starts and finishes registering servicers on the device_control ctx it hosts.
    // 2. It indicates to ep0 proxy over chan_ep0_proxy that ep0 init is done.
    // 3. ep0 proxy indicates to XUD_Main over chan_ep0_out that XUD_Main can be started.
    int num_out_endpoints = chan_in_word(c_ep0_out_a);
    int num_in_endpoints = chan_in_word(c_ep0_out_a);
    chan_in_buf_byte(c_ep0_out_a, (uint8_t *)&epTypeTableOut[0], num_out_endpoints*sizeof(XUD_EpType));
    chan_in_buf_byte(c_ep0_out_a, (uint8_t *)&epTypeTableIn[0], num_in_endpoints*sizeof(XUD_EpType));
    chan_in_buf_byte(c_ep0_out_a, (uint8_t *)&channel_ep_out[0], num_out_endpoints*sizeof(channel_t));
    chan_in_buf_byte(c_ep0_out_a, (uint8_t *)&channel_ep_in[0], num_in_endpoints*sizeof(channel_t));
    XUD_PwrConfig pwrConfig = chan_in_word(c_ep0_out_a);
    XUD_BusSpeed_t desiredSpeed = chan_in_word(c_ep0_out_a);

    chanend_t c_ep_out[RTOS_USB_ENDPOINT_COUNT_MAX];
    chanend_t c_ep_in[RTOS_USB_ENDPOINT_COUNT_MAX];

    // Package chanends into the format XUD expects them
    for (int i = 0; i < num_out_endpoints; i++)
    {
        if(epTypeTableOut[i] != XUD_EPTYPE_DIS)
        {
            c_ep_out[i] = channel_ep_out[i].end_a;
        }
    }
    for (int i = 0; i < num_in_endpoints; i++)
    {
        if(epTypeTableIn[i] != XUD_EPTYPE_DIS)
        {
            c_ep_in[i] = channel_ep_in[i].end_a;
        }
    }

    hwtimer_realloc_xc_timer();

    XUD_Main(c_ep_out,
            num_out_endpoints,
            c_ep_in,
            num_in_endpoints,
            c_sof,
            (XUD_EpType *) epTypeTableOut,
            (XUD_EpType *) epTypeTableIn,
            desiredSpeed,
            pwrConfig);

    hwtimer_free_xc_timer();
}

/// @brief this tiles entry point
void main_tile0(chanend_t c0, chanend_t c1, chanend_t c2, chanend_t c3)
{
    (void)c3;
    servicer_t* tile_0_servicers[NUM_TILE_0_SERVICERS]; // Array of pointers
    // Initialise control related things
    servicer_t servicer_pp;
    servicer_t servicer_gpo;
    servicer_t servicer_usb_buffer;
    tile_0_servicers[PP_SERVICER_INDEX] = &servicer_pp;
    tile_0_servicers[GPO_SERVICER_INDEX] = &servicer_gpo;
    tile_0_servicers[USB_BUFFER_SERVICER_INDEX] = &servicer_usb_buffer;

    pp_servicer_init(tile_0_servicers[PP_SERVICER_INDEX]);
    gpo_servicer_init(tile_0_servicers[GPO_SERVICER_INDEX]);
    usb_buffer_servicer_init(tile_0_servicers[USB_BUFFER_SERVICER_INDEX]);

#if (DFU_CONTROL > 0) && (!appconfUSB_ENABLED)
    servicer_t servicer_dfu;
    tile_0_servicers[DFU_SERVICER_INDEX] = &servicer_dfu;
    dfu_servicer_init(tile_0_servicers[DFU_SERVICER_INDEX]);
#endif

    // Open new cross tile paths tile0 c0 <-> tile 1 c1 using existing channel c1 <-> c0
    c0 = chanend_alloc();
    chanend_set_dest(c0, chan_in_word(c1));
    chan_out_word(c1, c0);

    // Now share info with other tile
    chan_out_byte(c0, is_spi_slave_boot()); // Send tile[0] boot info over to tile[1]
    chanend_t c_mic_to_audio = c0;
    set_core_burn_status(chan_in_byte(c0)); // Receive core burn status from tile[1] and set for later use
    set_usb_bit_depth(chan_in_byte(c0), chan_in_byte(c0)); // Receive USB bit depths from tile[1] for local use

    // Open new cross tile paths tile0 c2 <-> tile 1 c2 using existing channel c1 <-> c0
    c2 = chanend_alloc();
    chanend_set_dest(c2, chan_in_word(c1));
    chan_out_word(c1, c2);
    chanend_t c_aec_to_pp = c2;

    // Open new cross tile paths tile0 chan_usb_to_i2s <-> tile 1 chan_usb_to_i2s using existing channel c0 <-> c1
    chanend_t chan_usb_to_i2s = chanend_alloc();
    chanend_set_dest(chan_usb_to_i2s, chan_in_word(c1));
    chan_out_word(c1, chan_usb_to_i2s);

    // Open new cross tile paths tile0 c_ep0_proxy <-> tile 1 c_ep0_proxy using existing channel c0 <-> c1
    chanend_t c_ep0_proxy;
    c_ep0_proxy = chanend_alloc();
    chanend_set_dest(c_ep0_proxy, chan_in_word(c1));
    chan_out_word(c1, c_ep0_proxy);

    chanend_t c_ep_hid_proxy;
    c_ep_hid_proxy = chanend_alloc();
    chanend_set_dest(c_ep_hid_proxy, chan_in_word(c1));
    chan_out_word(c1, c_ep_hid_proxy);

    chanend_t c_ep_proxy_xfer_complete;
    c_ep_proxy_xfer_complete = chanend_alloc();
    chanend_set_dest(c_ep_proxy_xfer_complete, chan_in_word(c1));
    chan_out_word(c1, c_ep_proxy_xfer_complete);

#if appconfUSB_ENABLED
    // Allocate some channels for USB. The rest are allocated in usb_proxy.c

    channel_t channel_ep0_out = chan_alloc();
    channel_t channel_ep1_out = chan_alloc();
    channel_t channel_ep0_in = chan_alloc();
    channel_t channel_ep1_in = chan_alloc();

    channel_t channel_sof = chan_alloc();

    // Can't seem to send more than 4 args so send ref to struct http://bugzilla/show_bug.cgi?id=18745
    usb_buffer_args_t usb_task_args = {
        .chan_ep_audio_out = channel_ep1_out.end_b,
        .chan_ep_audio_in = channel_ep1_in.end_b,
        .chan_usb_to_i2s = chan_usb_to_i2s,
        .chan_sof = channel_sof.end_b
    };

     ep_proxy_init(channel_ep0_out,
                    channel_ep0_in,
                    channel_ep1_out,
                    channel_ep1_in,
                    c_ep0_proxy,
                    c_ep_hid_proxy,
                    c_ep_proxy_xfer_complete);

     init_vol_muls(); // Initialise the USB volume multipliers. This needs to be done before XUD is started
#endif

    PAR_JOBS(
        PJOB(INTERRUPT_PERMITTED(pp_task), (&c_aec_to_pp, &servicer_pp.res_info[PP_RESID - PP_SERVICER_RESID].control_pkt_queue)),               // Spawns three high priority logical cores
        PJOB(mic_array_task, (c_mic_to_audio)),
#if (appconfUSB_ENABLED != 0)
        PJOB(usb_buffer, (&usb_task_args)),
        PJOB(wrap_XUD_Main, (channel_ep0_out.end_a, channel_sof.end_a)),
#endif
        PJOB(tile_common_start_rtos_app, (c1, rtos_app, RTOS_THREAD_STACK_SIZE(rtos_app), &tile_0_servicers))
    );
}
