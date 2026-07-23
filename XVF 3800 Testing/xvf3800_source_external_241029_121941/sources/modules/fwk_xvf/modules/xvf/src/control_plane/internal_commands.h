// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#pragma once
#include "device_control.h"

/**
 * @brief Send a write command over a device_control context
 *
 * @param device_control_ctx    Pointer to the device_control context on which to send the command
 * @param resid                 ResourceID for the resource the command is directed to
 * @param cmd                   CmdID of the command
 * @param payload               Buffer containing the write command payload
 * @param payload_len           payload length in bytes
 * @param mutex                 Mutex handle for when the device_control function calls need to be guarded by a mutex. NULL otherwise.
 * @return control_ret_t        CONTROL_SUCCESS if command processed successfully, control_ret_t error enum error status otherwise
 */
control_ret_t send_write_cmd_to_servicer(device_control_t *device_control_ctx, control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, rtos_osal_mutex_t *mutex);

/**
 * @brief Send a read command over a device_control context
 *
 * @param device_control_ctx    Pointer to the device_control context on which to send the command
 * @param resid                 ResourceID for the resource the command is directed to
 * @param cmd                   CmdID of the command
 * @param payload               Buffer in which to copy the read command payload
 * @param payload_len           payload length in bytes
 * @param mutex                 Mutex handle for when the device_control function calls need to be guarded by a mutex. NULL otherwise.
 * @return control_ret_t        CONTROL_SUCCESS if command processed successfully, control_ret_t error enum error status otherwise
 */
control_ret_t send_read_cmd_to_servicer(device_control_t *device_control_ctx, control_resid_t resid, control_cmd_t cmd, uint8_t *payload, size_t payload_len, rtos_osal_mutex_t *mutex);
