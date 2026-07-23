// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT SPECIAL_CMD_HELPERS
#ifndef DEBUG_PRINT_ENABLE_SPECIAL_CMD_HELPERS
    #define DEBUG_PRINT_ENABLE_SPECIAL_CMD_HELPERS 0
#endif
#include "debug_print.h"

#include <stdio.h>
#include <string.h>
#include <platform.h>
#include "platform/platform_conf.h"
#include "servicer.h"
#include "aec_cmds.h"

control_ret_t special_read_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len, int32_t *cmd_handled)
{
#if ON_TILE(1)
    if(res_info->resource == AEC_RESID)
    {
        return aec_special_read_cmd_handler(res_info, cmd, payload, payload_len, cmd_handled);
    }
#endif
#if ON_TILE(0)
    if(res_info->resource == PP_RESID)
    {
        return pp_special_read_cmd_handler(res_info, cmd, payload, payload_len, cmd_handled);
    }
#endif
    *cmd_handled = 0;
    return CONTROL_SUCCESS;  
}

control_ret_t special_write_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, int32_t *cmd_handled)
{
#if ON_TILE(1)
    if(res_info->resource == AEC_RESID)
    {
        return aec_special_write_cmd_handler(res_info, cmd, payload, payload_len, cmd_handled);
    }
#endif
#if ON_TILE(0)
    if(res_info->resource == PP_RESID)
    {
        return pp_special_write_cmd_handler(res_info, cmd, payload, payload_len, cmd_handled);
    }
#endif
    *cmd_handled = 0;
    return CONTROL_SUCCESS;
}

// Helper functions
control_ret_t set_special_cmd_start(control_resource_info_t *res_info)
{
    if(res_info->special_cmd_handler.special_cmd_in_progress)
    {
        return SERVICER_SPECIAL_COMMAND_ALREADY_ONGOING;
    }            
    res_info->special_cmd_handler.special_cmd_in_progress = 1;
    res_info->special_cmd_handler.start_host_coeff_index = 0;
    res_info->special_cmd_handler.start_buf_coeff_index = 0;
    res_info->special_cmd_handler.end_buf_coeff_index = -1; // end_buf_coeff_index less than start_buf_coeff_index indicaing buffer empty

    return CONTROL_SUCCESS;
}

control_ret_t special_cmd_set_coeff_start_offset(control_resource_info_t *res_info, const uint8_t *payload)
{
    // Return an error if at this point there's already a special command packet in the queue.
    if (!res_info->special_cmd_handler.special_cmd_in_progress) // Out of order special command. First send the special cmd sequence start cmd
    {
        return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
    }

    memcpy(&res_info->special_cmd_handler.start_host_coeff_index, &payload[0], sizeof(int32_t));
    if (res_info->special_cmd_handler.start_host_coeff_index >= res_info->special_cmd_handler.special_cmd_payload_size)
    {
        return SERVICER_SPECIAL_COMMAND_BUFFER_OVERFLOW;
    }
    return CONTROL_SUCCESS;
}

/// New and improved chunk-wise implementation

/**
 * @brief Get the number of coefficients we'll be reading or writing
 * 
 * From the payload_len requested by the host, get the number of coefficients we'll be reading from or writing to the local buffer.
 * This function ensure that the num_coeffs returned does not exceed the end of the expected payload buffer size.
 * When that happens, num_coeffs returned are the coefficients that can be read to or written from the device without exceeding the expected payload buffer size.
 * @param sh            Pointer to the special command handler structure
 * @param payload_len   Payload length in bytes that the host wants to read or write
 * @return number of coefficients that will be written or read into the device.
 */
static int32_t get_num_coeffs(special_cmd_handler_t *sh, size_t payload_len)
{
    // From the payload_length sent by the user, get the number of coefficients we'd be actually reading from the buffer or writing to the buffer
    int32_t num_coeffs_written = payload_len / sizeof(float); // Num coefficients that the host wants to write.
    // If writing within the special_cmd_payload_size size, copy to local buffer
    int32_t num_coeffs; // Num coeffs we'll actually write in the buffer
    if(sh->start_host_coeff_index + num_coeffs_written <= sh->special_cmd_payload_size)
    {
        // We can accept everything the host wants to write
        num_coeffs = num_coeffs_written;
    }
    else
    {
        // Note 1: We'll write only part of what the host wants to write and discard the rest.
        // This can happen for the very last chunk, if the host decides to not change the payload_length of filter write command. To handle this
        // we're not returning an error here but writing what we can to the buffer

        // Note 2: It is safe to assume that start_host_coeff_index is in range at this point since there's a separate check for start_host_coeff_index everytime it gets updated by the host
        num_coeffs = sh->special_cmd_payload_size - sh->start_host_coeff_index;
    }
    return num_coeffs;
}

/**
 * @brief Issue a filter read or write command to the resource
 * 
 * This function adds a filter read or write command into the packet queue. The original payload is saved and
 * the payload ptr is updated with the servicer special command buffer address.
 * The payload_len is used for sending the chunk index to the resource.
 * Finally, the packet is added to the queue with the free_when_done flag set to 0 so that it's
 * explicitly freed as part of the special command handling protocol.
 * 
 * @param res_info                      Resource info of the current command 
 * @param cmd                           Command ID of the command
 * @param payload                       Pointer to the payload buffer that needs to be read or written to with filter coeffs by the device 
 * @param chunk_index                   Chunk index for which the resource needs to do a filter read or write 
 * @param local_buf_start_offset        Offset in the special payload buffer that the resource will read or write to.
 * @return control_ret_t                SERVICER_COMMAND_RETRY for all situations. If the command is added successfully to the queue, we'd want 
 *                                      a retry from the host. If the command is not added successfully to the queue, we'd still want a retry from 
 *                                      the host to attempt adding the command again.  
 */
static control_ret_t issue_filter_cmd(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, int32_t chunk_index, int32_t local_buf_start_offset)
{
    debug_printf("issue_filter_cmd(). chunk_index = %d, local_buf_start_offset = %d\n", chunk_index, local_buf_start_offset);
    // Send filter read command to the resource
    control_pkt_t *pkt; // pointer to first free queue packet

    // Get an empty packet.
    control_ret_t ret = queue_get_free_pkt(&pkt, &res_info->control_pkt_queue);
    if (ret != CONTROL_SUCCESS)
    {
        return SERVICER_COMMAND_RETRY; // Ask for a retry if we're not able to find space in the queue
    }
    // Overwrite payload ptr with the special buf ptr
    pkt->save_payload_ptr = pkt->payload;
    pkt->payload = &res_info->special_cmd_handler.special_commands_buffer[local_buf_start_offset*sizeof(float)];
    pkt->payload_len = chunk_index; // Use the payload_len field to send the chunk index
    pkt->res_id = res_info->resource;
    pkt->cmd_id = cmd;
    queue_add_pkt(&res_info->control_pkt_queue, 0); // Set free_when_done to 0 since we want to know when the pkt is done in order to update the special_cmd_handler start and exd index and copy the overrun data to the start of the buffer
    return SERVICER_COMMAND_RETRY; // We ask for a retry for both filter read and write commands.
}

/**
 * @brief Free the special command filter read or write packet once it has been dealt with in the resource.
 * 
 * This function ensures that the payload ptr of the packet is restored with the original value of the payload ptr.
 * 
 * @param cmd_pkt       Pointer to the command packet
 */
static void free_cmd_done_pkt(control_pkt_t *cmd_pkt)
{
    // Free a buffer get/set special command packet after the command is done in the resource
    // Restore the original pkt payload ptr
    xassert(cmd_pkt->save_payload_ptr != NULL); // Should never happen so assert
    cmd_pkt->payload = cmd_pkt->save_payload_ptr; // Restore the payload ptr with its original value.
    cmd_pkt->save_payload_ptr = NULL;   // Set original payload ptr to NULL, indicating that the regular payload ptr is not currently overwritten.
    cmd_pkt->pkt_status = PKT_FREE; // Free the packet since it was added to the queue with free_when_done flag set to False 
}

/**
 * @brief Read data from the local buffer in the servicer.
 * 
 * This function is called when the data requested by the host is already present in the servicer's local buffer and can
 * be read without involving the resource.
 * 
 * @param sh                Pointer to the special command handler structure 
 * @param payload           Payload buffer that needs to be written to with the data read from the local buffer 
 * @param num_coeffs        Number of coefficients that are read from the local buffer and updated in the payload buffer 
 */
static void read_from_local_buffer(special_cmd_handler_t *sh, uint8_t *payload, int32_t num_coeffs)
{
    int32_t start_offset = sh->start_host_coeff_index - sh->start_buf_coeff_index;
    debug_printf("read_from_local_buffer(): start_offset %d, num_coeffs = %d\n", start_offset, num_coeffs);
    memcpy(payload, &sh->special_commands_buffer[start_offset * sizeof(float)], num_coeffs*sizeof(float));
}

/**
 * @brief Update the payload array with filter data from the device.
 * 
 * This function handles a read filter data request. The read is completed from the servicer's local buffer if the
 * requested data is present in the local buffer, otherwise a read request for the next chunk is made to the resource
 * in order to fill the local buffer with more data.
 * 
 * This function also handles cases where partial data is present in the local buffer and the rest needs to be fetched from the 
 * resource.
 * 
 * @param res_info              Resource info of the current command 
 * @param cmd                   Command ID of the command
 * @param payload               Payload buffer to update with the read data 
 * @param num_coeffs            Number of coefficients to read and update in the payload buffer
 * @return control_ret_t        CONTROL_SUCCESS if the read request is fully completed from the local buffer,
 *                              SERVICER_SPECIAL_COMMAND_WRONG_ORDER if an out of order start_host_coeff_index is requested by the host,
 *                              SERVICER_COMMAND_RETRY if the read command is added or needs to be added in the queue. 
 */
static control_ret_t read_from_buffer(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, int32_t num_coeffs)
{
    // Read from either the local buffer or forward the read command to the resource
    special_cmd_handler_t *sh = &res_info->special_cmd_handler;
    
    if((sh->start_host_coeff_index >= sh->start_buf_coeff_index) && (sh->start_host_coeff_index + num_coeffs -1 <= sh->end_buf_coeff_index)) // All the data that the host wants to read is present in the local buffer
    {
        debug_printf("data in local buffer\n");
        read_from_local_buffer(sh, payload, num_coeffs);
        if(sh->start_host_coeff_index + num_coeffs >= sh->special_cmd_payload_size)
        {
            // We've returned the expected payload size to the host. Set special_cmd_in_progress to 0
            debug_printf("SPECIAL CMD DONE\n");
            sh->special_cmd_in_progress = 0;
        }
        return CONTROL_SUCCESS;
    }
    else if(sh->start_host_coeff_index >= sh->start_buf_coeff_index) // Part or none of the data that the host wants to read is in the buffer
    {
        debug_printf("data not in local buffer\n");
        // If there's anything in the buffer that the host wants move it to the beginning
        if((sh->end_buf_coeff_index - sh->start_host_coeff_index + 1) >= 0)
        {
            // First move everything that the host wants from the buffer to the beginning of the buffer
            memcpy(sh->special_commands_buffer, &sh->special_commands_buffer[(sh->start_host_coeff_index - sh->start_buf_coeff_index)*sizeof(float)], (sh->end_buf_coeff_index - sh->start_host_coeff_index + 1)*sizeof(float));
            // Update the start index
            sh->start_buf_coeff_index = sh->start_host_coeff_index;
            // Fetch a new chunk from the resource
            int32_t chunk_index = (sh->end_buf_coeff_index + 1) / sh->special_cmds_buf_size;
            int32_t start_offset = (chunk_index*sh->special_cmds_buf_size) - sh->start_buf_coeff_index;// Offset at which to write the next chunk read from the resource into the local buffer
            return issue_filter_cmd(res_info, cmd, payload, chunk_index, start_offset);
        }
        else { // Host wants nothing from the buffer and what it wants doesn't directly follow end_buf_coeff_index.
            // We do not support out of order reads! Host wants to read something not directly following what's currently in the buffer
            return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
        }
    }
    else
    {
        // Error case. Host seems to want data from indexes less than start_buf_coeff_index. We expect host to read in order.
        return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
    }
}

/**
 * @brief Check if the local buffer is full.
 * 
 * The servicer's local buffer holds one chunk of data plus some extra to accomodate the chunk size not being a multiple 
 * of the payload size written by the host. This function checks if the servicers local buffer is full and needs to be sent to 
 * the resource.
 * 
 * @param sh            Pointer to the special command handler structure 
 * @return 1 if the local buffer has at least a chunk size of data or contains the data till the end of the expected payload, 0 otherwise.
 */
int32_t get_buffer_full(special_cmd_handler_t *sh)
{
    // Check if the buffer is full, i.e, we've written in the special_cmds_buf_size samples in the buffer and optionally overrun into the extra space

    // We've written the expected payload size or the local buffer is full
    return ((sh->end_buf_coeff_index >= sh->start_buf_coeff_index + sh->special_cmds_buf_size - 1) || (sh->end_buf_coeff_index >= (sh->special_cmd_payload_size -1)));
}

/**
 * @brief Write data to the local buffer in the servicer
 * 
 * @param res_info              Resource info of the current command 
 * @param cmd                   Command ID of the command
 * @param payload               Payload buffer containing the data the host wants to write into the device
 * @param num_coeffs            Number of coefficients to write into the local buffer 
 */
control_ret_t write_to_local_buffer(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t num_coeffs)
{
    // Write payload to the local buffer. Update end_buf_coeff_index

    special_cmd_handler_t *sh = &res_info->special_cmd_handler;
    int32_t next_free_offset = sh->end_buf_coeff_index - sh->start_buf_coeff_index + 1; // Get the offset in the local buffer to start writing to

    // Make sure we're not going past the overflow area
    size_t remaining_size = sh->special_cmds_buf_size + sh->special_cmds_buf_overflow_size - next_free_offset;
    if(num_coeffs > remaining_size)
    {
        return SERVICER_SPECIAL_COMMAND_BUFFER_OVERFLOW;
    }
    memcpy(&sh->special_commands_buffer[next_free_offset * sizeof(float)], payload, num_coeffs*sizeof(float));

    // Increment end_buf_coeff_index to be the absolute index of the last valid coefficient in the buffer
    sh->end_buf_coeff_index += num_coeffs;
    return CONTROL_SUCCESS;
}

/**
 * @brief Write the coefficients in the payload buffer into the device
 * 
 * This function handles a write filter data request. If there is space in the servicer's local buffer the write request is
 * completed by writing into it, otherwise, if the servicer's local buffer is full, a request is made to copy the local buffer data into the resource
 * and the host is requested to retry the write till there is space in the local buffer.
 * 
 * @param res_info              Resource info of the current command
 * @param cmd                   Command ID of the command 
 * @param payload               Payload buffer containing the data the host wants to write into the device 
 * @param num_coeffs            Number of coefficients to write into the device 
 * @param flag_write_locally    Flag indicating whether a local buffer write needs to be attempted. This is set to 1 when a request is received for the first time and 0 in case of a retry. 
 * @return control_ret_t        CONTROL_SUCCESS if the data is written into the local buffer, SERVICER_COMMAND_RETRY if a request is made
 *                              to move data from the local buffer into the resource.        
 */
control_ret_t write_to_buffer(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t num_coeffs, int32_t flag_write_locally)
{
    special_cmd_handler_t *sh = &res_info->special_cmd_handler;
    // Optionally write to local buffer and optionally forward the chunk buffer to the resource
    control_ret_t ret = CONTROL_SUCCESS;
    // Write to local buffer 
    // flag_write_locally is 0 if we only want to issue the filter write command to resource but not write the payload locally since it's already been written
    if (flag_write_locally)
    {
        // Write to the local buffer
        ret = write_to_local_buffer(res_info, cmd, payload, num_coeffs);
        if(ret != CONTROL_SUCCESS)
        {
            return ret;
        }
    }
    // If a full chunk has been written to the local buffer, issue a filter write command to the resource
    if(get_buffer_full(sh))
    {
        debug_printf("BUFFER FULL\n");
        // Calculate the chunk index
        int32_t chunk_index = sh->start_buf_coeff_index / sh->special_cmds_buf_size;
    
        // Issue write filter command
        ret = issue_filter_cmd(res_info, cmd, payload, chunk_index, 0);
    }

    return ret;
}


control_ret_t special_cmd_read_coeffs_chunk(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len)
{
    // Process read filter command from the host
    control_ret_t ret = CONTROL_SUCCESS;
    special_cmd_handler_t *sh = &res_info->special_cmd_handler;
    debug_printf("special_cmd_read_coeffs_chunk() START: start_buf_coeff_index = %d, end_buf_coeff_index = %d, start_host_coeff_index = %d\n", sh->start_buf_coeff_index, sh->end_buf_coeff_index, sh->start_host_coeff_index);

    if(!sh->special_cmd_in_progress) // Out of order special command. First send the special cmd start cmd
    {
        return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
    }

    int32_t num_coeffs = get_num_coeffs(sh, payload_len);
    control_pkt_t *cmd_pkt = queue_check_packet(&res_info->control_pkt_queue, cmd);
    if (cmd_pkt != NULL) // Packet is already in queue
    {
        debug_printf("pkt in queue\n");
        if (cmd_pkt->pkt_status == PKT_DONE) // Read cmd is completed by the resource
        {
            // Free the packet
            free_cmd_done_pkt(cmd_pkt);

            // New chunk has been read. Increment the end index
            sh->end_buf_coeff_index = sh->end_buf_coeff_index + sh->special_cmds_buf_size;
            // Fall-through to read_from_buffer() to do the actual read
        }
        else if (cmd_pkt->pkt_status == PKT_WAIT) // Read cmd is in the queue but not yet completed by the resource. We continue signalling a RETRY
        {
            return SERVICER_COMMAND_RETRY;
        }
    }
    ret = read_from_buffer(res_info, cmd, payload, num_coeffs);
    debug_printf("special_cmd_read_coeffs_chunk() END: start_buf_coeff_index = %d, end_buf_coeff_index = %d, start_host_coeff_index = %d, ret = %d\n", sh->start_buf_coeff_index, sh->end_buf_coeff_index, sh->start_host_coeff_index, ret);
    return ret;
}

 
control_ret_t special_cmd_write_coeffs_chunk(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len)
{
    // Process write filter command from the host
    control_ret_t ret = CONTROL_SUCCESS;
    special_cmd_handler_t *sh = &res_info->special_cmd_handler;

    if(!sh->special_cmd_in_progress) // Out of order special command. First send the special cmd start cmd
    {
        return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
    }

    int32_t num_coeffs = get_num_coeffs(sh, payload_len);

    debug_printf("special_cmd_write_coeffs_chunk() START: start_buf_coeff_index = %d, end_buf_coeff_index = %d, start_host_coeff_index = %d, num_coeffs = %d\n", sh->start_buf_coeff_index, sh->end_buf_coeff_index, sh->start_host_coeff_index, num_coeffs);

    // Check if the local buffer is full and ready to be written out to the resource
    if(get_buffer_full(&res_info->special_cmd_handler))
    {
        // Buffer is full. We need to write to the resource.
        // Check if the write command has previously been issued.
        control_pkt_t *cmd_pkt = queue_check_packet(&res_info->control_pkt_queue, cmd); // Is this command already in the queue
        if(cmd_pkt == NULL)
        {
            debug_printf("Write pkt not in queue\n");
            //  Write command is not in queue.
            // Add write command to queue but don't attempt to write to local buffer
            ret = write_to_buffer(res_info, cmd, payload, num_coeffs, 0);
            return ret;
        }
        else
        {
            // Write command in queue. Check command status
            if(cmd_pkt->pkt_status == PKT_WAIT)
            {
                debug_printf("Write pkt PKT_WAIT\n");
                // Packet still pending. return RETRY to the host
                return SERVICER_COMMAND_RETRY;
            }
            else if(cmd_pkt->pkt_status == PKT_DONE)
            {
                debug_printf("Write pkt PKT_DONE\n");
                // Free the packet
                free_cmd_done_pkt(cmd_pkt);
                
                //Set special_cmd_in_progress to 0 if we've reached the end of expected payload
                if(sh->end_buf_coeff_index >= (sh->special_cmd_payload_size -1))
                {
                    debug_printf("SPECIAL CMD DONE\n");
                    sh->special_cmd_in_progress = 0;
                }
                else
                {
                    // Update start_buf_coeff_index
                    sh->start_buf_coeff_index = sh->start_buf_coeff_index + sh->special_cmds_buf_size;
                    // Copy the extra data that didn't fit in the previous chunk to the beginning of the buffer
                    debug_printf("Copying %d coeffs to buffer start\n", sh->end_buf_coeff_index - sh->start_buf_coeff_index + 1);
                    memcpy(sh->special_commands_buffer, sh->special_commands_buffer + (sh->special_cmds_buf_size*sizeof(float)), (sh->end_buf_coeff_index - sh->start_buf_coeff_index + 1)*sizeof(float));
                }
                // We do not need to fall-through to write_to_buffer() here. This is expected to be a retry from the host for data that was previously accepted in the local buffer and has now partially
                // or fully written to the resource.

                // Signal to the host that the write it has been retrying for is now complete
                return CONTROL_SUCCESS;
            }
        }
    }
    // Do some checks before writing to buffer.
    // Make sure the special_cmd_handler_t->start_host_coeff_index is what we're expecting, which is special_cmd_handler_t->end_buf_coeff_index + 1
    if(sh->start_host_coeff_index != sh->end_buf_coeff_index + 1)
    {
        return SERVICER_SPECIAL_COMMAND_WRONG_ORDER;
    }
    ret = write_to_buffer(res_info, cmd, payload, num_coeffs, 1);
    debug_printf("special_cmd_write_coeffs_chunk() END: start_buf_coeff_index = %d, end_buf_coeff_index = %d, start_host_coeff_index = %d, ret = %d\n", sh->start_buf_coeff_index, sh->end_buf_coeff_index, sh->start_host_coeff_index, ret);
    
    return ret;
}

/**
 * @brief Handle a queued up filter read or write packet during a special command abort process.
 * 
 * If a filter read or write packet is already queued up, it cannot be freed till the resource
 * is done processing the packet. Once the packet is in PKT_DONE state, it needs to be freed and the payload_ptr
 * needs to be restored to the original payload_ptr.
 * 
 * @param cmd_pkt           Pointer to the queued up packet.
 * @return control_ret_t    CONTROL_SUCCESS if the queued up packet is freed successfully, SERVICER_COMMAND_RETRY otherwise if
 *                          the queued up packet is still not processed in the resource.
 */
static control_ret_t special_cmd_abort_handle_queued_up_packet(control_pkt_t *cmd_pkt)
{
    // Check if the packet is done 
    if (cmd_pkt->pkt_status == PKT_DONE) // cmd is completed by the resource
    {
        // Free the packet
        free_cmd_done_pkt(cmd_pkt);            
        return CONTROL_SUCCESS;
        
    }
    else // cmd_pkt->pkt_status is PKT_WAIT)
    {
        return SERVICER_COMMAND_RETRY;
    }
}

/**
 * @brief Reset the special command handler state
 * 
 * @param res_info Resource info of the special command handler resource.
 */
static void reset_special_command_sequence(control_resource_info_t *res_info)
{
    // end the special command sequence safely
    res_info->special_cmd_handler.special_cmd_in_progress = 0;
    res_info->special_cmd_handler.start_host_coeff_index = 0;
    res_info->special_cmd_handler.start_buf_coeff_index = 0;
    res_info->special_cmd_handler.end_buf_coeff_index = -1; // end_buf_coeff_index less than start_buf_coeff_index indicaing buffer empty
}

control_ret_t special_cmd_abort(control_resource_info_t *res_info, control_cmd_t buffer_write_command)
{
    control_ret_t ret = CONTROL_SUCCESS;
    // Check if a filter write packet is queued up
    control_pkt_t *cmd_pkt = queue_check_packet(&res_info->control_pkt_queue, buffer_write_command);
    if(cmd_pkt != NULL)
    {
        // Filter write queued up
        ret = special_cmd_abort_handle_queued_up_packet(cmd_pkt); // Check if safe to reset protocol
        if(ret == CONTROL_SUCCESS)
        {
            // Safe to reset the protocol
            reset_special_command_sequence(res_info);
        }
    }
    else
    {
        // Check if a filter read command is in progress. There can be only one in progress at a time
        cmd_pkt = queue_check_packet(&res_info->control_pkt_queue, CONTROL_CMD_SET_READ(buffer_write_command));
        if (cmd_pkt != NULL)
        {
            // Filter read queued up
            ret = special_cmd_abort_handle_queued_up_packet(cmd_pkt);
            if(ret == CONTROL_SUCCESS) // Safe to reset the protocol
            {
                reset_special_command_sequence(res_info);
            }
        }
        else
        {
            // Neither read or write filter packet queued up. Safe to exit special command loop
            reset_special_command_sequence(res_info);
        }
    }
    return ret;
}


