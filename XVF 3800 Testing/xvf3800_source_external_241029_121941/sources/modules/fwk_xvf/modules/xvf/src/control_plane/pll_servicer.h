// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#pragma once
#include <stdint.h>
#include "servicer.h"

/**
 * @brief PLL Buffer servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void pll_servicer_init(servicer_t *servicer);

/**
 * @brief PLL servicer read command handler
 *
 * Handles read commands directed to the PLL servicer
 *
 * @param cmd               Command ID of this command
 * @param payload           payload address that needs to be updated with the read data
 * @param payload_len       Length in bytes of the read command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t pll_servicer_read_cmd(control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/// @brief Task for supplying the PLL status from one tile to the other over the intertile ctx
/// @param args
void supply_pll_status_task(void *args);

/// @brief Get pll lock status value from the USB buffer
/// @param
/// @return PLL lock status value
int8_t get_usb_buffer_pll_lock_status(void);

/// @brief Get PLL lock status value from the I2S thread
/// @param
/// @return
int8_t get_i2s_task_pll_lock_status(void);
