// Copyright 2021-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#include <platform.h>

/* Library headers */
#include "rtos_printf.h"
#include "device_control_usb.h"

/* App headers */
#include "servicer.h"
#include "app_conf.h"

// USB device control application callback function definitions
#if appconfUSB_CTRL_ENABLED

/* This function requires modifying from the stock function given in rtos/modules/sw_services/device_control/transport/usb/device_control_usb.c
 * The stock function registers servicers at the point the USB interface is opened, which breaches timing - it takes far too long and the host times out.
 * This application moves that initialisation to elsewhere in the application code, so we present here a modified version removing that initialisation. */

static uint16_t device_control_usb_open_no_register(uint8_t rhport, tusb_desc_interface_t const *itf_desc, uint16_t max_len)
{
    TU_VERIFY(TUSB_CLASS_VENDOR_SPECIFIC == itf_desc->bInterfaceClass);

    TU_VERIFY(itf_desc->bNumEndpoints == 0);

    uint16_t const drv_len = sizeof(tusb_desc_interface_t);
    TU_VERIFY(max_len >= drv_len);

    rtos_printf("Device control USB interface #%d opened\n", itf_desc->bInterfaceNumber);

    return drv_len;
}

device_control_t *device_control_usb_get_ctrl_ctx_cb(void)
{
    return device_control_usb_ctx;
}

static usbd_class_driver_t device_control_usb_app_driver_no_register;

usbd_class_driver_t const* usbd_app_driver_get_cb(uint8_t *driver_count)
{
    *driver_count = 1;

    device_control_usb_app_driver_no_register.init = device_control_usb_app_driver.init;
    device_control_usb_app_driver_no_register.reset = device_control_usb_app_driver.reset;
    device_control_usb_app_driver_no_register.open = device_control_usb_open_no_register;
    device_control_usb_app_driver_no_register.control_xfer_cb = NULL;
    device_control_usb_app_driver_no_register.xfer_cb = NULL;
    device_control_usb_app_driver_no_register.sof = NULL;

    return &device_control_usb_app_driver_no_register;
}
#endif
