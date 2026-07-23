// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#include <string.h>
#include "control_interface.h"

cmd_lookup_ret_t handle_through_lookup(const control_lut_t *lut, size_t lut_size, control_cmd_t cmd, uint8_t *payload, size_t payload_len)
{
    uint8_t is_read = IS_CONTROL_CMD_READ(cmd);
    control_cmd_t cmd_id = CONTROL_CMD_SET_WRITE(cmd); // Clear the read bit in order to compare against the command IDs stored in the resource

    for(int i=0; i<lut_size; i++)
    {
        if(cmd_id == lut[i].id)
        {
            if(is_read)
            {
                memcpy(payload, lut[i].ptr, payload_len);
            }
            else
            {
                memcpy(lut[i].ptr, payload, payload_len);
            }
            return CMD_LOOKUP_SUCCESS;
        }
    }
    return CMD_LOOKUP_FAIL;
}
