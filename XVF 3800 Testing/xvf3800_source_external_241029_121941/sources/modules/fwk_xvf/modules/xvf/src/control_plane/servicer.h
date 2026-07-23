// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#pragma once
#include "device_control.h"
#include "packet_queue.h"
#include "cmd_map.h"
#include "resource_ids.h"
#include "shf.h" // For MAX_NL_MODEL_ROWS and MAX_NL_MODEL_COLS defines

/**
 * Maximum number of coefficients that are read or written by the host as part of one packet when using the AEC_RESID_SPECIAL_CMD_AEC_FILTER_COEFFS command. This value
 * should be greater or equal to the 'number_of_values' field of the 'SPECIAL_CMD_AEC_FILTER_COEFFS' command in the aec_cmds.yaml file.
 * This is needed for allocating the size of the special command local buffer in the servicer. The local buffer will need to be
 * CHUNK_SIZE + MAX_COEFFS_PER_PKT - 1 samples long to handle the CHUNK_SIZE not being an exact multiple of the MAX_COEFFS_PER_PKT.
 * For coeff write commands the buffer can overrun by MAX_COEFFS_PER_PKT - 1 samples beyond the CHUNK_SIZE before it gets written to the resource.
 * For coeff read commands there can be a maximum of MAX_COEFFS_PER_PKT - 1 samples already present in the local buffer when a request to read a new chunk into
 * the local buffer is made to the resource.
 */
#define MAX_COEFFS_PER_PKT      (15) // Note that if we ever change the cmd signature to send MORE than 15 coeffs per packet this will need to be updated.

/**
* The chunk size of the SHF read/write coeff buffer because we do not read/write all at the same time. See shf.h SHF_SetAECCoefs_AEC / SHF_GetAECCoefs_AEC
*/
#define AEC_COEFF_CHUNK_SIZE    (256)

/**
* The maximum size of the buffer to store the NL model coefficients
*/
#define NLMODEL_SIZE (MAX_NL_MODEL_ROWS*MAX_NL_MODEL_COLS)

extern device_control_t *device_control_i2c_ctx;
extern device_control_t *device_control_spi_ctx;
extern device_control_t *device_control_usb_ctx;
extern device_control_t *device_control_gpio_ctx; // Device control context for the IO config servicer to send GPO commands to the GPO servicer
extern device_control_t *device_control_ctxs[APP_CONTROL_TRANSPORT_COUNT];

// For handling special commands (Not prototyped so isn't final)
typedef struct {
    uint8_t *special_commands_buffer;
    int32_t special_cmd_in_progress;    /// Flag indicating if a special command is already in progress
    int32_t start_host_coeff_index;     /// stat coefficient index requested by the host
    int32_t special_cmds_buf_size; /// special data chunk size plus extra space for cases when the chunk size is not a multiple of the payload length sent by the host
    int32_t special_cmd_payload_size; /// Expected special command payload size in samples
    int32_t start_buf_coeff_index; /// Absolute filter coefficient index in special_commands_buffer[0]
    int32_t end_buf_coeff_index; /// Absolute index of the last valid filter coefficient index in the special_commands_buffer buffer
    /** No. of coefficients worth of overflow space added to the special cmds buffer to accomodate the special commands buffer size not being a multiple of no. of coefficients
     * sent per control packet. Used for error checking in the special commands handler.*/
    int32_t special_cmds_buf_overflow_size;
}special_cmd_handler_t;

// Structure encapsulating all the information about a resource
typedef struct
{
    control_resid_t resource;
    command_map_t command_map;
    control_pkt_queue_t control_pkt_queue;
    special_cmd_handler_t special_cmd_handler;
}control_resource_info_t;

typedef struct {
    uint32_t start_io; // set to 1 on one servicer per tile to make it responsible for starting the IO tasks on that tile.
    int32_t id; // Unique ID for the servicer. Used for debugging.
    // Num resources
    int32_t num_resources;
    // Resource ID and command map for every resource
    control_resource_info_t *res_info;
}servicer_t;


// Servicer tasks
/**
 * @brief Generic servicer task.
 * The servicers that only receive and process requests from the host are implemented as the generic servicer.
 *
 * \param servicer      Pointer to the Servicer's state data structure
 */
void servicer_task(void *servicer);

/**
 * @brief IO config servicer task.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void io_config_servicer(void *args);

/**
 * @brief GPO servicer task.
 *
 * This task handles GPO commands and drives the pins on the GPO port.
 *
 * \param servicer      Pointer to the Servicer's state data structure
 */
void gpo_servicer(void *args);

/**
 * @brief Application servicer task.
 *
 * This task handles Application level commands such as firmware information.
 *
 * \param servicer      Pointer to the Servicer's state data structure
 */
void application_servicer(void *args);

/**
 * @brief DFU servicer task.
 *
 * This task handles DFU commands from the device control interface and relays
 * them to the internal DFU INT state machine.
 *
 * \param args      Pointer to the Servicer's state data structure
 */
void dfu_servicer(void *args);

// Servicer initialization functions
/**
 * @brief AEC servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void aec_servicer_init(servicer_t *servicer);

/**
 * @brief Audio servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void audio_servicer_init(servicer_t *servicer);

/**
 * @brief Application servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void application_servicer_init(servicer_t *servicer);

/**
 * @brief IO Config servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void io_config_servicer_init(servicer_t *servicer);

/**
 * @brief PP servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void pp_servicer_init(servicer_t *servicer);

/**
 * @brief DFU servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void dfu_servicer_init(servicer_t *servicer);

/**
 * @brief GPO servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void gpo_servicer_init(servicer_t *servicer);

/**
 * @brief USB Buffer servicer initialisation function.
 * \param servicer      Pointer to the Servicer's state data structure
 */
void usb_buffer_servicer_init(servicer_t *servicer);

// Servicer device_control callback functions
/**
 * @brief Device control callback function to handle a read command.
 *
 * @param resid         Resource ID of the command
 * @param cmd           Command ID of the command
 * @param payload       Pointer to the payload buffer that needs to be updated with the read command response.
 * @param payload_len   Length of the payload buffer
 * @param app_data      Application specific data.
 * @return              CONTROL_SUCCESS is command is handled successfully,
 *                      otherwise control_ret_t error status indicating the error.
 */
extern DEVICE_CONTROL_CALLBACK_ATTR
control_ret_t read_cmd(control_resid_t resid, control_cmd_t cmd, uint8_t *payload, size_t payload_len, void *app_data);

/**
 * @brief Device control callback function to handle a write command
 *
 * @param resid         Resource ID of the command
 * @param cmd           Command ID of the command
 * @param payload       Pointer to the payload buffer containing the payload the host wants to write to the device.
 * @param payload_len   Length of the payload buffer
 * @param app_data      Application specific data
 * @return              CONTROL_SUCCESS is command is handled successfully,
 *                      otherwise control_ret_t error status indicating the error.
 */
extern DEVICE_CONTROL_CALLBACK_ATTR
control_ret_t write_cmd(control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, void *app_data);

// Servicer helper functions
/**
 * @brief Check if a command exists in the command map for a given resource and return the pointer to the cmd info object for the given command
 *
 * @param cmd_id        Command ID for which the control_cmd_info_t object is required.
 * @param res_info      Pointer to the resource info which contains all the command info objects for a given resource.
 * @return              Pointer to a control_cmd_info_t object when one is found for the given Command ID, NULL otherwise.
 */
control_cmd_info_t* get_cmd_info(uint8_t cmd_id, const control_resource_info_t *res_info);

/**
 * @brief Check if a resource ID is one of the resources supported by a servicer and return a pointer to the resource info object.
 *
 * @param resource      Resource ID that needs to be checked.
 * @param servicer      Pointer to the servicer state structure that holds all the resource info objects for the servicer.
 * @return              Pointer to the resource_info_t object when one is found for a given resource ID, NULL otherwise.
 */
control_resource_info_t* get_res_info(control_resid_t resource, const servicer_t *servicer);

/**
 * @brief Validate the command received in the servicer and return a pointer to the command info if the command is valid.
 *
 * All checks related to the command such as command ID being valid, correctness of the payload length,
 * validation of the actual payload for write commands are done in this function.
 *
 * @param cmd_info      Pointer in which the address of the command info is returned if this is a valid command/
 * @param res_info      Resource info of the resource the command is meant for.
 * @param cmd           Command ID of the command that needs validating
 * @param payload       Payload buffer of the command that needs validating.
 * @param payload_len   Payload length of the payload.
 * @return              CONTROL_SUCCESS if the command is found to be valid for the given resource. control_ret_t error otherwise
 *                      indicating the error code of the specific validation check that failed.
 */
control_ret_t validate_cmd(control_cmd_info_t **cmd_info,
                            control_resource_info_t *res_info,
                            control_cmd_t cmd,
                            const uint8_t *payload,
                            size_t payload_len);

/**
 * @brief Function for handling write commands directed to the servicer resource itself.
 *
 * @param resid         Command Resource ID
 * @param cmd           Command Command ID
 * @param payload       Command write payload buffer
 * @param payload_len   Length of the payload buffer
 * @return              CONTROL_SUCCESS if write command processed successfully. contro_ret_t error status otherwise.
 */
control_ret_t servicer_write_cmd(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len);

/**
 * @brief               Function for handling read commands directed to the servicer resource itself.
 *
 * @param resid         Command Resource ID
 * @param cmd           Command Command ID
 * @param payload       Payload buffer to populate with the read response
 * @param payload_len   Length of the payload buffer
 * @return              CONTROL_SUCCESS if read command processed successfully. contro_ret_t error status otherwise.
 */
control_ret_t servicer_read_cmd(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief               Function for getting a read command processed by the servicer's underlying resource
 *
 * @param res_info      Command Resource ID
 * @param cmd           Command command IO
 * @param payload       Payload buffer to populate with the read response
 * @param payload_len   Length of the payload buffer
 * @return              CONTROL_SUCCESS if read command processed successfully. contro_ret_t error status otherwise.
 */
control_ret_t servicer_read_from_resource(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief               Function for getting a write command processed by the servicer's underlying resource
 *
 * @param res_info      Command Resource ID
 * @param cmd           Command command IO
 * @param payload       Command write payload buffer
 * @param payload_len   Length of the payload buffer
 * @return              CONTROL_SUCCESS if write command processed successfully. contro_ret_t error status otherwise.
 */
control_ret_t servicer_write_to_resource(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len);

// Special command handler functions
/**
 * @brief Special read command handler function.
 *
 * This is a wrapper function that is called from the DEVICE_CONTROL_CALLBACK_ATTR read_cmd() function to
 * handle special read commands. Based on the resource ID of the command, this function forwards the command to
 * the resource specific special read command handler function.
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the read data
 * @param payload_len       Length in bytes of the read command payload
 * @param cmd_handled       Pointer to the flag indicating if this command was handled in the special command handler
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t special_read_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len, int32_t *cmd_handled);

/**
 * @brief Special write command handler function.
 *
 * This is a wrapper function that is called from the DEVICE_CONTROL_CALLBACK_ATTR write_cmd() function to
 * handle special write commands. Based on the resource ID of the command, this function forwards the command to
 * the resource specific special write command handler function.
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the read data
 * @param payload_len       Length in bytes of the read command payload
 * @param cmd_handled       Pointer to the flag indicating if this command was handled in the special command handler
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t special_write_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, int32_t *cmd_handled);

/**
 * @brief AEC special read command handler
 *
 * Handles read commands that are part of the special command handling protocol in AEC. The only special command
 * supported in the AEC is the AEC filter read command.
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the read data
 * @param payload_len       Length in bytes of the read command payload
 * @param cmd_handled       Pointer to the flag indicating if this command was handled in the special command handler
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t aec_special_read_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len, int32_t *cmd_handled);

/**
 * @brief AEC special write commands handler
 *
 * Handles write commands that are part of the special command handling protocol in AEC. The only special command
 * supported in the AEC is the AEC filter read command.
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @param cmd_handled       Pointer to the flag indicating if this command was handled in the special command handler
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t aec_special_write_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, int32_t *cmd_handled);

/**
 * @brief AEC servicer read command handler
 *
 * Handles read commands dedicated to AEC servicer
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t aec_servicer_read_cmd(control_resource_info_t * res_info, control_cmd_t cmd, uint8_t * payload, size_t payload_len);

/**
 * @brief AEC servicer write command handler
 *
 * Handles write commands dedicated to AEC servicer
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t aec_servicer_write_cmd(control_resource_info_t * res_info, control_cmd_t cmd, const uint8_t * payload, size_t payload_len);

/**
 * @brief PP special read command handler
 *
 * Handles read commands that are part of the special command handling protocol in the PP module. The only special commands
 * supported in the PP are the PP NLModel buffer read and write commands.
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the read data
 * @param payload_len       Length in bytes of the read command payload
 * @param cmd_handled       Pointer to the flag indicating if this command was handled in the special command handler
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t pp_special_read_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len, int32_t *cmd_handled);

/**
 * @brief PP special write commands handler
 *
 * Handles write commands that are part of the special command handling protocol in the PP module. The only special commands
 * supported in the PP are the PP NLModel buffer read and write commands.
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @param cmd_handled       Pointer to the flag indicating if this command was handled in the special command handler
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t pp_special_write_cmd_handler(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, int32_t *cmd_handled);

// Special command handler helper functions
/**
 * @brief special command protocol sequence start command handler
 *
 * This function is called when a command indicating special command sequence start is received. It sets the special_cmd_handler state
 * in the servicer data structure ready to receive a special command protocol sequence. The host is required to send
 * this command before sending the commands to set coeff start index and reading/writing the special buffer. If either
 * of these commands are sent before sending the start command, SERVICER_SPECIAL_COMMAND_WRONG_ORDER error is returned.
 *
 * @param res_info          Resource info of the current command
 * @return control_ret_t    CONTROL_SUCCESS if command handled correctly, SERVICER_SPECIAL_COMMAND_ALREADY_ONGOING if the
 *                          start command is sent in the middle of an ongoing special command sequence.
 */
control_ret_t set_special_cmd_start(control_resource_info_t *res_info);

/**
 * @brief Set start coefficient index command handler
 *
 * This function is called when a command that sets the start coefficient offset is received. The start coefficient offset
 * is set by the device indicating the absolute offset in the buffer where the next read or write to the buffer will
 * be done.
 *
 * @param res_info              Resource info of the current command
 * @param payload               Pointer to the command payload that contains the coeff start offset set by the host
 * @return control_ret_t        CONTROL_SUCCESS if command handled correctly, SERVICER_SPECIAL_COMMAND_WRONG_ORDER if
 *                              this command is sent before sending a start command, SERVICER_SPECIAL_COMMAND_BUFFER_OVERFLOW
 *                              if the start coeff index is greater than the buffer size.
 */
control_ret_t special_cmd_set_coeff_start_offset(control_resource_info_t *res_info, const uint8_t *payload);

/**
 * @brief Handler function for special buffer read requests.
 *
 * @param res_info              Resource info of the current command
 * @param cmd                   Command ID of the command
 * @param payload               Payload buffer to update with the read data
 * @param payload_len           Reuqested payload len in bytes
 * @return control_ret_t        CONTROL_SUCCESS if payload buffer successfully updated with read data,
 *                              SERVICER_COMMAND_RETRY if host needs to retry the read request
 *                              SERVICER_SPECIAL_COMMAND_WRONG_ORDER for any error related to the order in which commands are issued.
 */
control_ret_t special_cmd_read_coeffs_chunk(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief Handler function for special buffer write requests.
 *
 * @param res_info              Resource info of the current command
 * @param cmd                   Command ID of the command
 * @param payload               Payload buffer containing coefficients that need to be written into the device
 * @param payload_len           payload len in bytes
 * @return control_ret_t        CONTROL_SUCCESS if payload buffer is successfully written in the device,
 *                              SERVICER_COMMAND_RETRY if host needs to retry the write request
 *                              SERVICER_SPECIAL_COMMAND_WRONG_ORDER for any error related to the order in which commands are issued.
 */
control_ret_t special_cmd_write_coeffs_chunk(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len);


/**
 * @brief GPO servicer read command handler
 *
 * Handles read commands dedicated to the GPO servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t gpo_servicer_read_cmd(control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief GPO servicer write command handler
 *
 * Handles write commands dedicated to the GPO servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t gpo_servicer_write_cmd(control_cmd_t cmd, const uint8_t *payload, size_t payload_len);

/**
 * @brief Application servicer read command handler
 *
 * Handles read commands dedicated to the Application servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t application_servicer_read_cmd(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief Application servicer write command handler
 *
 * Handles write commands dedicated to the Application servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t application_servicer_write_cmd(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len);

/**
 * @brief GPI servicer read command handler
 *
 * Handles read commands dedicated to the GPI servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t gpi_servicer_read_cmd(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief GPI servicer write command handler
 *
 * Handles write commands dedicated to the GPI servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t gpi_servicer_write_cmd(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len);

/**
 * @brief Handler function for special cmd abort command
 *
 * @param res_info                  Resource info of the current command
 * @param buffer_write_command      Buffer write command ID that is searched for in the packet queue. Special command
 *                                  sequence is not aborted if there's a buffer write or read command queued up.
 * @return control_ret_t            CONTROL_SUCCESS if the command handled successfully, SERVICER_COMMAND_RETRY if the host
 *                                  needs to retry the abort command. A RETRY is returned when there's a buffer write or read command
 *                                  queued up. The host is expected to keep retrying the abort till the buffer write or read command is completed.
 */
control_ret_t special_cmd_abort(control_resource_info_t *res_info, control_cmd_t buffer_write_command);

/**
 * @brief USB Buffer servicer write command handler
 *
 * Handles write commands directed to the USB Buffer servicer
 *
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t usb_buffer_servicer_write_cmd(control_cmd_t cmd, const uint8_t *payload, size_t payload_len);

/**
 * @brief USB Buffer servicer read command handler
 *
 * Handles read commands directed to the USB Buffer servicer
 *
 * @param cmd               Command ID of this command
 * @param payload           payload address that needs to be updated with the read data
 * @param payload_len       Length in bytes of the read command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t usb_buffer_servicer_read_cmd(control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief DFU servicer read command handler
 *
 * Handles read commands dedicated to the DFU servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t dfu_servicer_read_cmd(control_resource_info_t *res_info, control_cmd_t cmd, uint8_t *payload, size_t payload_len);

/**
 * @brief DFU servicer write command handler
 *
 * Handles write commands dedicated to the DFU servicer resource
 *
 * @param res_info          Resource info of the current command
 * @param cmd               Command ID of this command
 * @param payload           Pointer to the payload that contains the write data
 * @param payload_len       Length in bytes of the write command payload
 * @return control_ret_t    CONTROL_SUCCESS if command handled successfully,
 *                          otherwise control_ret_t error status indicating the error.
 */
control_ret_t dfu_servicer_write_cmd(control_resource_info_t *res_info, control_cmd_t cmd, const uint8_t *payload, size_t payload_len);


void hid_in_servicer(void *args);
