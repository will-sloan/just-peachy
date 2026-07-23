// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#pragma once

/// @brief  IO Expander task arguments structure
typedef struct {
    device_control_t *device_control_ctx;   /// Device control ctx over which to send button press notifications as internal commands to the HID servicer
    rtos_osal_mutex_t *mutex;               /// Mutex to guard sending internal commands over the device_control_gpio_ctx
}io_expander_task_args_t;

/// @brief IO Expander task. This task reads buttons and configures LEDs on the PCAL6416A board via the I2C Master interface
/// @param args Pointer to io_expander_task_args_t arguments structure
void io_expander_task(void *args);
