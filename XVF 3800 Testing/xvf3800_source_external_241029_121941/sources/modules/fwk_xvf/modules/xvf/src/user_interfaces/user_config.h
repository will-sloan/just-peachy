// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#pragma once
#include "device_control.h"

/**
 * Initialise user hardware. Typically a DAC and LEDs.
 * This is called from io_config_servicer.c at startup before
 * the system for recieving control commands has started.
 *
 * \param device_control_gpio_ctx  pointer to device control for GPIO
 *
 * \returns   0 on success
 *            -1 otherwise
 */
int user_init_hardware(device_control_t *device_control_gpio_ctx);
