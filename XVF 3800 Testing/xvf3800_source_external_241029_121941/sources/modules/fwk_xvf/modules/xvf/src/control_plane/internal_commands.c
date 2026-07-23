// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <stdint.h>
#include "internal_commands.h"

// This function sends a write command over the device_control context
control_ret_t send_write_cmd_to_servicer(device_control_t *device_control_ctx, control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, rtos_osal_mutex_t *mutex)
{
    uint8_t tx_buf[1]; // For status
    size_t tx_len;

    if(mutex != NULL)
    {
        rtos_osal_mutex_get(mutex, RTOS_OSAL_WAIT_FOREVER);
    }

    device_control_request(device_control_ctx,
                                resid,
                                cmd,
                                payload_len);

    // Device control does not expect a constant payload, so cast it away.
    device_control_payload_transfer_bidir(device_control_ctx, (uint8_t *)payload, payload_len, tx_buf, &tx_len);

    if(mutex != NULL)
    {
        rtos_osal_mutex_put(mutex);
    }

    return tx_buf[0]; // Status is returned in tx_buf[0];
}

control_ret_t send_read_cmd_to_servicer(device_control_t *device_control_ctx, control_resid_t resid, control_cmd_t cmd, uint8_t *payload, size_t payload_len, rtos_osal_mutex_t *mutex)
{
    size_t rx_size = 0, tx_size;

    if(mutex != NULL)
    {
        rtos_osal_mutex_get(mutex, RTOS_OSAL_WAIT_FOREVER);
    }

    device_control_request(device_control_ctx,
                                resid,
                                cmd,
                                payload_len);


    device_control_payload_transfer_bidir(device_control_ctx, NULL, rx_size, payload, &tx_size);

    if(mutex != NULL)
    {
        rtos_osal_mutex_put(mutex);
    }
    return CONTROL_SUCCESS;
}
