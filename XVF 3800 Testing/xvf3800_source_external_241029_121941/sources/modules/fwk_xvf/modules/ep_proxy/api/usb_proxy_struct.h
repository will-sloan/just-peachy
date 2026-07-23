// Copyright 2023-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef USB_PROXY_STRUCT_H
#define USB_PROXY_STRUCT_H

#include <xcore/channel.h>

/**
 * The maximum number of USB endpoint numbers supported by the RTOS USB driver.
 */
#define RTOS_USB_ENDPOINT_COUNT_MAX 12

typedef enum {
    e_reset_ep=36,
    e_prepare_setup,
    e_usb_endpoint_transfer_start,
    e_xud_data_get_start,
    e_usb_device_address_set,
    e_reset_ep_by_address,
    e_usb_endpoint_stall_set,
    e_usb_endpoint_stall_clear,
    e_usb_enter_test_mode
} ep0_proxy_cmds_t;

typedef struct rtos_usb_proxy_struct {
    chanend_t c_ep_proxy[RTOS_USB_ENDPOINT_COUNT_MAX];
    chanend_t c_ep_proxy_xfer_complete;
} usb_proxy_t;

#endif
