// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT PP_SERVICER
#ifndef DEBUG_PRINT_ENABLE_PP_SERVICER
    #define DEBUG_PRINT_ENABLE_PP_SERVICER 0
#endif
#include "debug_print.h"

#include <stdio.h>
#include <string.h>
#include <platform.h>
#include "platform/platform_conf.h"
#include "servicer.h"
#include "pp_cmds.h"

control_ret_t pp_special_write_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, int32_t *cmd_handled)
{
    control_ret_t ret = CONTROL_SUCCESS;
    control_pkt_t *cmd_pkt_write_coeffs = NULL;
    control_pkt_t *cmd_pkt_read_coeffs = NULL;
    *cmd_handled = 0;
    switch(cmd)
    {
        case PP_RESID_SPECIAL_CMD_NLMODEL_START:
            *cmd_handled = 1;

            // This command is also an indication to the servicer that a special command sequence is about to start
            ret = set_special_cmd_start(res_info); // Set the special_cmd_handler for a new command start
            break;

        case PP_RESID_SPECIAL_CMD_NLMODEL_COEFF_START_OFFSET:
            *cmd_handled = 1;
            // Return error if a read or write buffer command is already in the queue
            cmd_pkt_write_coeffs = queue_check_packet(&res_info->control_pkt_queue, PP_RESID_SPECIAL_CMD_PP_NLMODEL);
            cmd_pkt_read_coeffs = queue_check_packet(&res_info->control_pkt_queue, CONTROL_CMD_SET_READ(PP_RESID_SPECIAL_CMD_PP_NLMODEL));
            if((cmd_pkt_write_coeffs != NULL) || (cmd_pkt_read_coeffs != NULL))
            {
                return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
            }
            ret = special_cmd_set_coeff_start_offset(res_info, payload);
            break;

        case PP_RESID_SPECIAL_CMD_PP_NLMODEL:
            *cmd_handled = 1;
            ret = special_cmd_write_coeffs_chunk(res_info, cmd, payload, payload_len);
            break;

        case PP_RESID_PP_NL_MODEL_CMD_ABORT:
            *cmd_handled = 1;
            ret = special_cmd_abort(res_info, PP_RESID_SPECIAL_CMD_PP_NLMODEL);
            break;
        case PP_RESID_SPECIAL_CMD_EQUALIZATION_START:
            *cmd_handled = 1;

            // This command is also an indication to the servicer that a special command sequence is about to start
            ret = set_special_cmd_start(res_info); // Set the special_cmd_handler for a new command start
            break;

        case PP_RESID_SPECIAL_CMD_EQUALIZATION_COEFF_START_OFFSET:
            *cmd_handled = 1;
            // Return error if a read or write buffer command is already in the queue
            cmd_pkt_write_coeffs = queue_check_packet(&res_info->control_pkt_queue, PP_RESID_SPECIAL_CMD_PP_EQUALIZATION);
            cmd_pkt_read_coeffs = queue_check_packet(&res_info->control_pkt_queue, CONTROL_CMD_SET_READ(PP_RESID_SPECIAL_CMD_PP_EQUALIZATION));
            if((cmd_pkt_write_coeffs != NULL) || (cmd_pkt_read_coeffs != NULL))
            {
                return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
            }
            ret = special_cmd_set_coeff_start_offset(res_info, payload);
            break;

        case PP_RESID_SPECIAL_CMD_PP_EQUALIZATION:
            *cmd_handled = 1;
            ret = special_cmd_write_coeffs_chunk(res_info, cmd, payload, payload_len);
            break;

        case PP_RESID_PP_EQUALIZATION_CMD_ABORT:
            *cmd_handled = 1;
            ret = special_cmd_abort(res_info, PP_RESID_SPECIAL_CMD_PP_EQUALIZATION);
            break;
    }
    return ret;
}

control_ret_t pp_special_read_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len, int32_t *cmd_handled)
{
    *cmd_handled = 0;
    control_ret_t ret = CONTROL_SUCCESS;
    switch(CONTROL_CMD_CLEAR_READ(cmd))
    {
        case PP_RESID_SPECIAL_CMD_NLMODEL_COEFF_START_OFFSET:
            *cmd_handled = 1;
            memcpy(&payload[0], &res_info->special_cmd_handler.start_host_coeff_index, payload_len);
            break;
        case PP_RESID_SPECIAL_CMD_PP_NLMODEL_NROW_NCOL:
            *cmd_handled = 1;
            ret = servicer_read_from_resource(res_info, cmd, payload, payload_len);
            if(ret == CONTROL_SUCCESS)
            {
                int32_t nrow_cols[2];
                memcpy(nrow_cols, payload, 2*sizeof(int32_t));
                // Keep a copy of the NLModel length in the servicer
                res_info->special_cmd_handler.special_cmd_payload_size = nrow_cols[0] * nrow_cols[1]; // Size of the 2D NLModel buffer
                res_info->special_cmd_handler.special_cmds_buf_size = NLMODEL_SIZE; // Set the buffer size, as it differs from the one for the equalization filter
                if(res_info->special_cmd_handler.special_cmds_buf_size < res_info->special_cmd_handler.special_cmd_payload_size)
                {
                    // If the servicer's special command buffer is not big enough for the expected payload
                    return SERVICER_SPECIAL_COMMAND_BUF_SIZE_ERROR;
                }
            }
            break;
        case PP_RESID_SPECIAL_CMD_PP_NLMODEL:
            *cmd_handled = 1;
            ret = special_cmd_read_coeffs_chunk(res_info, cmd, payload, payload_len);
            break;
        case PP_RESID_SPECIAL_CMD_PP_EQUALIZATION_NUM_BANDS:
            *cmd_handled = 1;

            ret = servicer_read_from_resource(res_info, cmd, payload, payload_len);
            if(ret == CONTROL_SUCCESS)
            {
                int32_t num_values = 0;
                memcpy(&num_values, payload, sizeof(int32_t));

                // Keep a copy of the equalization length in the servicer
                res_info->special_cmd_handler.special_cmd_payload_size = num_values; // Size of the equalization filter
                res_info->special_cmd_handler.special_cmds_buf_size = num_values; // Set the buffer size, as it differs from the one for the NL model
            }
            break;
        case PP_RESID_SPECIAL_CMD_PP_EQUALIZATION:
            *cmd_handled = 1;
            ret = special_cmd_read_coeffs_chunk(res_info, cmd, payload, payload_len);
            break;
    }
    return ret;
}
