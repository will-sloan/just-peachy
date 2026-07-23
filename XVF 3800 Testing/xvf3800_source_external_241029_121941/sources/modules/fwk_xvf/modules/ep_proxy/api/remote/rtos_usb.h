// Copyright 2023-2024 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#ifndef RTOS_USB_H_
#define RTOS_USB_H_

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <xcore/channel.h>
#include "xud.h"
#include "XUD_HAL.h"
#include "xud_device.h"

#include "rtos_osal.h"
#include "rtos_driver_rpc.h"

#include "usb_proxy_struct.h"

/* This section is copied from rtos_usb.h.
 * If changes are made upstream, they will need copying to here.
 */

/**
 * @{
 * This is used to index into the second dimension of many of the
 * RTOS USB driver's endpoint arrays.
 */
#define RTOS_USB_OUT_EP 0
#define RTOS_USB_IN_EP  1
/**@}*/

/**
 * This attribute must be specified on the RTOS USB interrupt callback function
 * provided by the application.
 */
#define RTOS_USB_ISR_CALLBACK_ATTR __attribute__((fptrgroup("rtos_usb_isr_cb_fptr_grp")))

typedef enum {
    rtos_usb_data_packet,
    rtos_usb_setup_packet,
    rtos_usb_sof_packet
} rtos_usb_packet_type_t;

/**
 * Typedef to the RTOS USB driver instance struct.
 */
typedef struct rtos_usb_struct rtos_usb_t;

/**
 * Function pointer type for application provided RTOS USB interrupt callback function.
 *
 * This callback function is called when there is a USB transfer interrupt.
 *
 * \param ctx           A pointer to the associated USB driver instance.
 * \param app_data      A pointer to application specific data provided
 *                      by the application. Used to share data between
 *                      this callback function and the application.
 * \param ep_address    The address of the USB endpoint that the transfer
 *                      has completed on.
 * \param xfer_len      The length of the data transferred.
 * \param packet_type   The type of packet transferred. See rtos_usb_packet_type_t.
 * \param res           The result of the transfer. See XUD_Result_t.
 */
typedef void (*rtos_usb_isr_cb_t)(rtos_usb_t *ctx, void *app_data, uint32_t ep_address, size_t xfer_len, rtos_usb_packet_type_t packet_type, XUD_Result_t res);

/**
 * Struct to hold USB transfer state data per endpoint, used
 * as the argument to the ISR.
 *
 * The members in this struct should not be accessed directly.
 */
typedef struct {
    /** A pointer to the associated RTOS USB driver instance. */
    rtos_usb_t *usb_ctx;
    /** The requested transfer length - either the maximum length for
    OUT transfers, or the actual length for IN transfers */
    size_t len;
    /** The endpoint address for the transfer */
    uint8_t ep_address;
    /** The direction of the transfer. Either RTOS_USB_OUT_EP or RTOS_USB_IN_EP */
    uint8_t dir;
    /** The endpoint number (lower 4 bits of the endpoint address) */
    uint8_t ep_num;
    /** The result of the transfer */
    int8_t res;
} rtos_usb_ep_xfer_info_t;

/**
 * Struct representing an RTOS USB driver instance.
 *
 * The members in this struct should not be accessed directly.
 */
struct rtos_usb_struct {
    size_t endpoint_count;
    chanend_t c_ep_out_xud[RTOS_USB_ENDPOINT_COUNT_MAX];
    chanend_t c_ep_in_xud[RTOS_USB_ENDPOINT_COUNT_MAX];
    chanend_t c_sof_xud;
    chanend_t c_sof;
    int sof_interrupt_enabled;

    XUD_EpType endpoint_out_type[RTOS_USB_ENDPOINT_COUNT_MAX];
    XUD_EpType endpoint_in_type[RTOS_USB_ENDPOINT_COUNT_MAX];
    XUD_PwrConfig power_source;
    XUD_BusSpeed_t speed;

    chanend_t c_ep[RTOS_USB_ENDPOINT_COUNT_MAX][2];
    XUD_ep ep[RTOS_USB_ENDPOINT_COUNT_MAX][2];
    int reset_received;
    rtos_osal_thread_t hil_thread;
    RTOS_USB_ISR_CALLBACK_ATTR rtos_usb_isr_cb_t isr_cb;
    void *isr_app_data;
    rtos_usb_ep_xfer_info_t ep_xfer_info[RTOS_USB_ENDPOINT_COUNT_MAX][2];
};

static inline int endpoint_num(uint32_t endpoint_addr)
{
    return endpoint_addr & 0xF;
}

static inline int endpoint_dir(uint32_t endpoint_addr)
{
    return (endpoint_addr >> 7) & 1;
}

void usb_driver_init(chanend_t c_ep0_proxy, chanend_t c_ep_hid_proxy, chanend_t c_ep_proxy_xfer_complete);


/*  These functions are intended to be linked on tile[1], to "overload" the
    rtos_usb_ functions used in dcd_xcore.c */

void rtos_usb_init(
        rtos_usb_t *ctx,
        uint32_t io_core_mask,
        rtos_usb_isr_cb_t isr_cb,
        void *isr_app_data);

void rtos_usb_start(
        rtos_usb_t *ctx,
        size_t endpoint_count,
        XUD_EpType endpoint_out_type[],
        XUD_EpType endpoint_in_type[],
        XUD_BusSpeed_t speed,
        XUD_PwrConfig power_source,
        unsigned interrupt_core_id,
        int sof_interrupt_core_id);

void rtos_usb_endpoint_state_reset(rtos_usb_t *ctx, uint32_t endpoint_addr);
XUD_Result_t rtos_usb_device_address_set(rtos_usb_t *ctx, uint32_t endpoint_addr);
void rtos_usb_endpoint_stall_set(rtos_usb_t *ctx, uint32_t endpoint_addr);
void rtos_usb_endpoint_stall_clear(rtos_usb_t *ctx, uint32_t endpoint_addr);
XUD_BusSpeed_t rtos_usb_endpoint_reset(rtos_usb_t *ctx, uint32_t endpoint_addr);
XUD_Result_t rtos_usb_endpoint_transfer_start(rtos_usb_t *ctx,
                                              uint32_t endpoint_addr,
                                              uint8_t *buffer,
                                              size_t len,
                                              bool is_setup);
void rtos_usb_enter_test_mode(rtos_usb_t *ctx,
                            unsigned test_mode);

#endif
