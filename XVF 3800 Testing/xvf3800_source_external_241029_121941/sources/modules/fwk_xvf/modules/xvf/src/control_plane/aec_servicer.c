// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT AEC_SERVICER
#ifndef DEBUG_PRINT_ENABLE_AEC_SERVICER
    #define DEBUG_PRINT_ENABLE_AEC_SERVICER 0
#endif
#include "debug_print.h"

#include <stdio.h>
#include <string.h>
#include <platform.h>
#include "platform/platform_conf.h"
#include "servicer.h"
#include "aec_cmds.h"

#define UINT8_TEST_LEN 60
uint8_t test[UINT8_TEST_LEN] = {0};

control_ret_t aec_special_write_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, int32_t *cmd_handled)
{
    control_ret_t ret = CONTROL_SUCCESS;
    *cmd_handled = 0;
    switch(cmd)
    {
        case AEC_RESID_SPECIAL_CMD_AEC_FAR_MIC_INDEX:
            debug_printf("AEC_RESID_SPECIAL_CMD_AEC_FAR_MIC_INDEX\n");
            *cmd_handled = 1;
            // This command is also an indication to the servicer that a special command sequence is about to start
            ret = set_special_cmd_start(res_info); // Set the special_cmd_handler for a new command start
            if(ret != CONTROL_SUCCESS)
            {
                break;
            }

            control_cmd_info_t *cmd_info = get_cmd_info(AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS, res_info);
            xassert(cmd_info != NULL);
            if(cmd_info->num_vals > MAX_COEFFS_PER_PKT) // Local buffer size is not enough to handle overruns due to chunk_size not being a multiple of payload size. Cannot handle this so assert.
            {
                xassert(0);
            }

            // Forward the command to the resource since it needs to know the far, mic index for which it'll have to get the filter
            ret = servicer_write_to_resource(res_info, cmd, payload, payload_len);
            break;

        case AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFF_START_OFFSET:
            debug_printf("AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFF_START_OFFSET\n");
            *cmd_handled = 1;
            // Return error if a read or write buffer command is already in the queue
            control_pkt_t *cmd_pkt_write_coeffs = queue_check_packet(&res_info->control_pkt_queue, AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS);
            control_pkt_t *cmd_pkt_read_coeffs = queue_check_packet(&res_info->control_pkt_queue, CONTROL_CMD_SET_READ(AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS));
            if((cmd_pkt_write_coeffs != NULL) || (cmd_pkt_read_coeffs != NULL))
            {
                return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
            }

            ret = special_cmd_set_coeff_start_offset(res_info, payload);
            break;

        case AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS:
            debug_printf("AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS\n");
            *cmd_handled = 1;
            ret = special_cmd_write_coeffs_chunk(res_info, cmd, payload, payload_len);
            break;

        case AEC_RESID_AEC_FILTER_CMD_ABORT:
            debug_printf("AEC_RESID_AEC_FILTER_CMD_ABORT\n");
            *cmd_handled = 1;
            // If there's a AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS read or write command in progress, we cannot abort till 
            // this command is completed in the resource.
            ret = special_cmd_abort(res_info, AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS);
            break;
    }
    return ret;
}

control_ret_t aec_special_read_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len, int32_t *cmd_handled)
{
    *cmd_handled = 0;
    control_ret_t ret = CONTROL_SUCCESS;
    switch(CONTROL_CMD_CLEAR_READ(cmd))
    {
        case AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFF_START_OFFSET:
            debug_printf("AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFF_START_OFFSET\n");
            *cmd_handled = 1;
            memcpy(&payload[0], &res_info->special_cmd_handler.start_host_coeff_index, payload_len);
            break;
        case AEC_RESID_SPECIAL_CMD_AEC_FILTER_LENGTH:
            debug_printf("AEC_RESID_SPECIAL_CMD_AEC_FILTER_LENGTH\n");
            *cmd_handled = 1;
            ret = servicer_read_from_resource(res_info, cmd, payload, payload_len);
            if(ret == CONTROL_SUCCESS)
            {
                // Keep a copy of the filter length in the servicer
                memcpy(&res_info->special_cmd_handler.special_cmd_payload_size, payload, sizeof(int32_t));
            }
            break;
        case AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS:
            debug_printf("AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS\n");
            *cmd_handled = 1;

            ret = special_cmd_read_coeffs_chunk(res_info, cmd, payload, payload_len);
            break;
    }
    return ret;
}

control_ret_t aec_servicer_read_cmd(control_resource_info_t * res_info, control_cmd_t cmd, uint8_t * payload, size_t payload_len)
{
    control_ret_t ret = CONTROL_SUCCESS;
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);
    if(cmd_id == AEC_SERVICER_RESID_TEST_CONTROL)
    {
        if(payload_len > UINT8_TEST_LEN)
        {
            return SERVICER_SPECIAL_COMMAND_BUF_SIZE_ERROR;
        }
        memcpy(payload, test, payload_len);
        ret = CONTROL_SUCCESS;
    }
    return ret;
}

control_ret_t aec_servicer_write_cmd(control_resource_info_t * res_info, control_cmd_t cmd, const uint8_t * payload, size_t payload_len)
{
    control_ret_t ret = CONTROL_SUCCESS;
    if(cmd == AEC_SERVICER_RESID_TEST_CONTROL)
    {
        if(payload_len > UINT8_TEST_LEN)
        {
            return SERVICER_SPECIAL_COMMAND_BUF_SIZE_ERROR;
        }
        memcpy(test, payload, payload_len);
        ret = CONTROL_SUCCESS;
    }
    return ret;
}
