// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT APPLICATION_SERVICER
#ifndef DEBUG_PRINT_ENABLE_APPLICATION_SERVICER
    #define DEBUG_PRINT_ENABLE_APPLICATION_SERVICER 0
#endif
#include "debug_print.h"

#include <xs1.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <platform.h>
#include "platform/platform_conf.h"
#include "servicer.h"
#include "application_cmds.h"
#include "tile_common.h"

// Note info passed in to application_servicer_read_cmd function via global defines from cmake file

#define _STRING(s) #s
#define STRING(s) _STRING(s)
#define REBOOT_DELAY_MS 50

void application_servicer(void *args)
{
    device_control_servicer_t servicer_ctx;

    servicer_t *servicer = (servicer_t*)args;
    xassert(servicer != NULL);

    control_resid_t *resources = (control_resid_t*)pvPortMalloc(servicer->num_resources * sizeof(control_resid_t));
    for(int i=0; i<servicer->num_resources; i++)
    {
        resources[i] = servicer->res_info[i].resource;
    }

    if(APP_CONTROL_TRANSPORT_COUNT > 0)
    {
        control_ret_t dc_ret;
        debug_printf("Calling device_control_servicer_register(), servicer ID %d, on tile %d, core %d.\n", servicer->id, THIS_XCORE_TILE, rtos_core_id_get());

        dc_ret = device_control_servicer_register(&servicer_ctx,
                                            device_control_ctxs,
                                            APP_CONTROL_TRANSPORT_COUNT,
                                            resources, servicer->num_resources);
        debug_printf("Out of device_control_servicer_register(), servicer ID %d, on tile %d. servicer_ctx address = 0x%x\n", servicer->id, THIS_XCORE_TILE, &servicer_ctx);
    }

    vPortFree(resources);

    if(APP_CONTROL_TRANSPORT_COUNT > 0)
    {
        // Wait for control commands
        for(;;){
            device_control_servicer_cmd_recv(&servicer_ctx, read_cmd, write_cmd, servicer, RTOS_OSAL_WAIT_FOREVER);
        }
    }
    else
    {
        for(;;){
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
}


control_ret_t application_servicer_read_cmd(control_resource_info_t * res_info, control_cmd_t cmd, uint8_t * payload, size_t payload_len)
{
    control_ret_t ret = CONTROL_SUCCESS;
    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);

    memset(payload, 0, payload_len);
   
    debug_printf("application_servicer_read_cmd, cmd_id: %d.\n", cmd_id);

    switch(cmd_id)
    {
        case APPLICATION_SERVICER_RESID_VERSION:
            debug_printf("APPLICATION_SERVICER_RESID_VERSION\n");
            static const uint8_t version[3] = {VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH};
            memcpy(payload, &version, sizeof(version));
            break;

        case APPLICATION_SERVICER_RESID_BLD_MSG:
            debug_printf("APPLICATION_SERVICER_RESID_BLD_MSG\n");
            static const char bld_message[] = STRING(BLD_MSG);
            memcpy(payload, bld_message, strlen(bld_message));
            break;

        case APPLICATION_SERVICER_RESID_BLD_HOST:
            debug_printf("APPLICATION_SERVICER_RESID_BLD_HOST\n");
            static const char bld_host[] = STRING(BLD_HOST);
            memcpy(payload, bld_host, strlen(bld_host));
            break;

        case APPLICATION_SERVICER_RESID_BLD_REPO_HASH:
            debug_printf("APPLICATION_SERVICER_RESID_BLD_REPO_HASH\n");
            static const char bld_repo_hash[] = STRING(BLD_REPO_HASH);
            memcpy(payload, bld_repo_hash, strlen(bld_repo_hash));
            break;

        case APPLICATION_SERVICER_RESID_BLD_MODIFIED:
            debug_printf("APPLICATION_SERVICER_RESID_BLD_MODIFIED\n");
            static const char bld_modified[] = STRING(BLD_MODIFIED);
            memcpy(payload, bld_modified, strlen(bld_modified));
            break;

        case APPLICATION_SERVICER_RESID_BOOT_STATUS:
            debug_printf("APPLICATION_SERVICER_RESID_BOOT_STATUS\n");

            static const char boot_ss[] = STRING(SS);  // SPI SLAVE
            static const char boot_jofl[] = STRING(JoF); // JTAG or FLASH
            if(is_spi_slave_boot())
            {
                memcpy(payload, boot_ss, strlen(boot_ss));
            } else {
                memcpy(payload, boot_jofl, strlen(boot_jofl));
            }
            break;

        case APPLICATION_SERVICER_RESID_TEST_CORE_BURN:
            debug_printf("APPLICATION_SERVICER_RESID_TEST_CORE_BURN\n");
            uint8_t core_burn = get_core_burn_status();
            memcpy(payload, &core_burn, sizeof(version));
            break;

        case APPLICATION_SERVICER_RESID_USB_BIT_DEPTH:
            debug_printf("APPLICATION_SERVICER_RESID_USB_BIT_DEPTH\n");
            uint8_t bit_depths[2] = {0};
            get_usb_bit_depth(&bit_depths[0], &bit_depths[1]);
            memcpy(payload, &bit_depths, sizeof(bit_depths));
            break;

        default:
            debug_printf("APPLICATION_SERVICER UNHANDLED COMMAND!!!\n");
            ret = CONTROL_BAD_COMMAND;
            break;
    }

    return ret;
}

// Note there are currently no write commands supported by this RESID
control_ret_t application_servicer_write_cmd(control_resource_info_t * res_info, control_cmd_t cmd, const uint8_t * payload, size_t payload_len)
{
    control_ret_t ret = CONTROL_SUCCESS;
    debug_printf("application_servicer_write_cmd cmd_id %d.\n", CONTROL_CMD_CLEAR_READ(cmd));

    uint8_t cmd_id = CONTROL_CMD_CLEAR_READ(cmd);

    switch(cmd_id)
    {
        case APPLICATION_SERVICER_RESID_REBOOT:
            debug_printf("APPLICATION_SERVICER_RESID_REBOOT\n");
            debug_printf("device is being rebooted\n");
            reboot_xvf3800(REBOOT_DELAY_MS);
            break;

        case APPLICATION_SERVICER_RESID_TEST_CORE_BURN:
            debug_printf("APPLICATION_SERVICER_RESID_TEST_CORE_BURN\n");
            uint8_t core_burn = 0;
#if appconfBURN_MODE_SUPPORTED
            memcpy(&core_burn, payload, sizeof(core_burn));
#endif  
// else burn is always disabled
            set_core_burn_status_and_reboot(core_burn);


            debug_printf("core_burn: %u\n", core_burn);
            break;

        case APPLICATION_SERVICER_RESID_USB_BIT_DEPTH:
            debug_printf("APPLICATION_SERVICER_RESID_USB_BIT_DEPTH\n");
            uint8_t bit_depths[2] = {0};
            memcpy(bit_depths, payload, sizeof(bit_depths));
            set_usb_bit_depth(bit_depths[0], bit_depths[1]);
            break;


        default:
            debug_printf("APPLICATION_SERVICER UNHANDLED COMMAND!!!\n");
            ret = CONTROL_BAD_COMMAND;
            break;
    }

    return ret;
}
