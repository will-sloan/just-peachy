// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

// This file contains the i2s task and the associated callbacks which handle building
// buffers for SHF, taking samples fom mic_array, sample rate conversion and muxing
#include <stddef.h>
#define DEBUG_UNIT PLL_SERVICER
#ifndef DEBUG_PRINT_ENABLE_PLL_SERVICER
    #define DEBUG_PRINT_ENABLE_PLL_SERVICER 0
#endif
#include "debug_print.h"

#include <print.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <platform.h>
#include <string.h>

#include "packet_queue.h"
#include "device_control_shared.h"
#include "platform/driver_instances.h" // For the intertile ctx
#include "pll_cmds.h"
#include "pll_servicer.h"

/** Helper functions for implementing the PLL_LOCK_STATUS command.
 * The PLL is part of the I2S task (tile1) for the INT device and the usb_buffer (tile0) task for the UA device variant.
 * The PLL servicer is on tile1. When servicing the PLL_LOCK_STATUS command, for the UA device, it fetches the lock_status
 * from tile0 using the intertile ctx. For the INT device, it reads the lock_status that is stored in global memory on tile 0.
 */

/// @brief  Task for supplying the lock status from tile0 to tile 1
void supply_pll_status_task(void *args) {
    uint8_t *c_ptr;
    rtos_intertile_t * intertile_ctx = get_intertile_ctx();
    for(;;)
    {
        uint32_t msg_length = rtos_intertile_rx(intertile_ctx,
                                    appconfUSB_COMMUNICATE_PLL_STATUS_PORT,
                                    (void **) &c_ptr,
                                    RTOS_OSAL_WAIT_FOREVER);
        (void) msg_length;
        rtos_osal_free(c_ptr);
        int8_t lock_status = get_usb_buffer_pll_lock_status();
        rtos_intertile_tx(intertile_ctx, appconfUSB_COMMUNICATE_PLL_STATUS_PORT, &lock_status, 1);
    }
}

/// @brief Handler function for read commands directed to the audio servicer
control_ret_t pll_servicer_read_cmd(control_cmd_t cmd, uint8_t *payload, size_t payload_len)
{
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);
    control_ret_t ret = CONTROL_SUCCESS;
    switch(cmd_id)
    {
        case PLL_SERVICER_RESID_PLL_LOCK_STATUS:
        {
            // Handle differently for UA and INT variants
#if appconfUSB_ENABLED
            uint8_t temp = 0;
            rtos_intertile_t * intertile_ctx = get_intertile_ctx();
            rtos_intertile_tx(intertile_ctx, appconfUSB_COMMUNICATE_PLL_STATUS_PORT, &temp, 1);
            int8_t *c_ptr;
            uint32_t msg_length = rtos_intertile_rx(intertile_ctx,
                                        appconfUSB_COMMUNICATE_PLL_STATUS_PORT,
                                        (void **) &c_ptr,
                                        RTOS_OSAL_WAIT_FOREVER);
            (void) msg_length;
            pll_servicer_resid_pll_lock_status_t val = (pll_servicer_resid_pll_lock_status_t)*c_ptr;
            memcpy(payload, &val, payload_len);
            rtos_osal_free(c_ptr);
            break;
#else
            pll_servicer_resid_pll_lock_status_t val = (pll_servicer_resid_pll_lock_status_t)get_i2s_task_pll_lock_status();
            memcpy(payload, &val, payload_len);
#endif
        }
        break;
    }
    return ret;

}
