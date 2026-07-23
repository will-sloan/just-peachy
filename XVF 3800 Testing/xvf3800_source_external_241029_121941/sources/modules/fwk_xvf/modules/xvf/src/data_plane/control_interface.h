// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#pragma once
#include "device_control_shared.h"

/// control-interface.h
/**
 * Control lookup table entry.
 * 
 * The lookup table is used to avoid using small, repetitive control command getter and setter functions.
 * Instead, the command IDs and the memory in the task that is involved in a command processing is specified
 * in a lookup table.
 */
typedef struct {
    control_cmd_t id; /* Control command ID */
    void* ptr; /* Pointer to the local task memory that needs to be read or written as part of command handling */
} control_lut_t;

/**
 * This type enumerates the possible outcomes when processing a command using the control lookup table.
 */
typedef enum {
    CMD_LOOKUP_SUCCESS = 0, /* Command processed successfully using the lookup table */
    CMD_LOOKUP_FAIL /* Command could not be processed using the lookup table and will need custom handling */
}cmd_lookup_ret_t;

/**
 * @brief Handle control command processing through the control lookup table.
 * 
 * @param lut           Control lookup table
 * @param lut_size      Size of the control lookup table
 * @param cmd           Command from host that needs handling
 * @param payload       Pointer to the payload that needs to be read or written to as part of command processing
 * @param payload_len   Payload length in bytes
 * @return              CMD_LOOKUP_SUCCESS is command processed through the lookup table, CMD_LOOKUP_FAIL otherwise, in 
 *                      which case, the command will need custom handling.
 */
cmd_lookup_ret_t handle_through_lookup(const control_lut_t *lut, size_t lut_size, control_cmd_t cmd, uint8_t *payload, size_t payload_len);
