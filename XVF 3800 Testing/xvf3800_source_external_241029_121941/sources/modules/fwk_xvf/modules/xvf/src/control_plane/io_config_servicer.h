// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#pragma once
#include "device_control.h"
#include "servicer.h"

/**
 * @brief Send a command to the GPO task to write to a GPO pin
 *
 * This function sends a command to write to a GPO pin over the device_control_gpio_ctx.
 *
 * @param device_control_ctx    Pointer to the device_control context that the command will be sent over.
 * @param pin_index             GPO pin index to write to
 * @param state                 state that the GPO pin needs to be configured to. Note some pins (eg. LED) have negative logic.
 *                              See init_gpo(void) in gpo_servicer.c for details
 */
control_ret_t write_gpo_pin(device_control_t *device_control_ctx, uint32_t pin_index, uint32_t pin_value);
