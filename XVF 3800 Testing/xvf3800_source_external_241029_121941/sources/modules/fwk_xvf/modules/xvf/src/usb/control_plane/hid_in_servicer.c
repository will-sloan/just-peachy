// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define DEBUG_UNIT HID_IN_SERVICER
#ifndef DEBUG_PRINT_ENABLE_HID_IN_SERVICER
    #define DEBUG_PRINT_ENABLE_HID_IN_SERVICER 1
#endif
#include "rtos_printf.h"

#include <stdint.h>
#include "FreeRTOS.h"
#include "device_control.h"
#include "servicer.h"

#include "hid_task_cmds.h"

#include "tusb.h"
#include "usb_descriptors.h"
#include "hid_telephony_device.h"
#include "usb_hid.h"

static inline uint8_t get_button_from_gpi_pin_index(button_press_info_t *button_event, const hid_button_config_t *button_config)
{
    // TODO Dialpad is not handled yet!!
    for(uint32_t i=0; i<TOTAL_HID_BUTTONS; i++)
    {
        if(button_config[i].gpi_source == button_event->gpi_source &&
            (button_config[i].gpi_pin_index == button_event->index))
        {
            return i;
        }
    }
    return TOTAL_HID_BUTTONS;
}

DEVICE_CONTROL_CALLBACK_ATTR
control_ret_t hid_write_cmd(control_resid_t resid, control_cmd_t cmd, const uint8_t *payload, size_t payload_len, void *app_data)
{
    hid_in_servicer_args_t *servicer_args = NULL;
    xassert(app_data != NULL);

    servicer_args = app_data;

    button_press_info_t button_event;
    xassert(payload_len == sizeof(button_press_info_t));
    memcpy(&button_event, payload, payload_len);

    uint8_t button_index = get_button_from_gpi_pin_index(&button_event, servicer_args->hid_button_config);

    xassert(button_index < TOTAL_HID_BUTTONS);

    button_event.index = (int32_t)button_index;

    // Push button press event on the msg queue
    rtos_osal_queue_t *queue_ptr = servicer_args->button_press_queue;
    rtos_osal_status_t ret = rtos_osal_queue_send(queue_ptr, &button_event, RTOS_OSAL_NO_WAIT);
    if(ret != RTOS_OSAL_SUCCESS)
    {
        rtos_printf("WARNING: BUTTON QUEUE FULL. Ignoring the button press event\n");
    }

    return CONTROL_SUCCESS;
}

DEVICE_CONTROL_CALLBACK_ATTR
control_ret_t hid_read_cmd(control_resid_t resid, control_cmd_t cmd, uint8_t *payload, size_t payload_len, void *app_data)
{
  payload[0] = CONTROL_SUCCESS;
  return CONTROL_SUCCESS;
}


void hid_in_servicer(void *args)
{
    hid_in_servicer_args_t *servicer_args = (hid_in_servicer_args_t *) args;
    xassert(servicer_args != NULL);

    device_control_servicer_t hid_servicer_ctx;
    control_resid_t resources[1] = {HID_TASK_RESID};
    control_ret_t dc_ret = device_control_servicer_register(&hid_servicer_ctx,
                                        &servicer_args->device_control_ctx,
                                        1,
                                        resources, 1);
    xassert(dc_ret == CONTROL_SUCCESS);

    while(1)
    {
        device_control_servicer_cmd_recv(&hid_servicer_ctx, hid_read_cmd, hid_write_cmd, servicer_args, RTOS_OSAL_WAIT_FOREVER);
    }
}

