// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#define DEBUG_UNIT CONTROL_INIT
#ifndef DEBUG_PRINT_ENABLE_CONTROL_INIT
    #define DEBUG_PRINT_ENABLE_CONTROL_INIT 0
#endif
#include "debug_print.h"

#include <stdio.h>
#include <platform.h>
#include "platform/platform_conf.h"
#include "platform/driver_instances.h"
#include "device_control_i2c.h"
#include "device_control_spi.h"
#include "control_init.h"
#include "servicer.h"

#if appconfI2C_CTRL_ENABLED
#if ON_TILE(I2C_TILE_NO)
static device_control_t device_control_i2c_ctx_s;
#else
static device_control_client_t device_control_i2c_ctx_s;
#endif
device_control_t *device_control_i2c_ctx = (device_control_t *) &device_control_i2c_ctx_s;
#endif

#if appconfSPI_CTRL_ENABLED
#if ON_TILE(SPI_TILE_NO)
static device_control_t device_control_spi_ctx_s;
#else
static device_control_client_t device_control_spi_ctx_s;
#endif
device_control_t *device_control_spi_ctx = (device_control_t *) &device_control_spi_ctx_s;
#endif

#if appconfUSB_CTRL_ENABLED
#if ON_TILE(USB_EP0_TILE_NO)
static device_control_t device_control_usb_ctx_s;
#else
static device_control_client_t device_control_usb_ctx_s;
#endif
device_control_t *device_control_usb_ctx = (device_control_t *) &device_control_usb_ctx_s;
#endif

device_control_t *device_control_ctxs[APP_CONTROL_TRANSPORT_COUNT] = {
#if appconfI2C_CTRL_ENABLED
        (device_control_t *) &device_control_i2c_ctx_s,
#endif
#if appconfSPI_CTRL_ENABLED
        (device_control_t *) &device_control_spi_ctx_s,
#endif
#if appconfUSB_CTRL_ENABLED
        (device_control_t *) &device_control_usb_ctx_s,
#endif
};

// Device control context for the GPI task to communicate with the GPO and HID task
#if ON_TILE(GPI_PORT_TILE_NO)
static device_control_t device_control_gpio_ctx_s;
#else
static device_control_client_t device_control_gpio_ctx_s;
#endif
device_control_t *device_control_gpio_ctx = (device_control_t *) &device_control_gpio_ctx_s;

#if (appconfUSB_CTRL_ENABLED && HID_CONTROL)
    #define NUM_SERVICERS_DEVICE_CONTROL_GPIO_CTX (2) // 2 servicers registering on the device_control_gpio_ctx. GPO and HID servicer
#else
    #define NUM_SERVICERS_DEVICE_CONTROL_GPIO_CTX (1) // Only the GPO servicer registering on the device_control_gpio_ctx
#endif

void control_init() {
    control_ret_t ret = CONTROL_SUCCESS;
    rtos_intertile_t * intertile_ctx = get_intertile_ctx();
#if appconfI2C_CTRL_ENABLED
    ret = device_control_init(device_control_i2c_ctx,
                                THIS_XCORE_TILE == I2C_TILE_NO ? DEVICE_CONTROL_HOST_MODE : DEVICE_CONTROL_CLIENT_MODE,
                                (NUM_TILE_0_SERVICERS + NUM_TILE_1_SERVICERS - 1), // GPO servicer does not register with I2C or SPI device control context
                                &intertile_ctx, 1);
    xassert(ret == CONTROL_SUCCESS);

    ret = device_control_start(device_control_i2c_ctx,
                                appconfDEVICE_CONTROL_I2C_PORT,
                                appconfDEVICE_CONTROL_I2C_CLIENT_PRIORITY);
    xassert(ret == CONTROL_SUCCESS);
#endif

#if appconfSPI_CTRL_ENABLED
    ret = device_control_init(device_control_spi_ctx,
                        THIS_XCORE_TILE == SPI_TILE_NO ? DEVICE_CONTROL_HOST_MODE : DEVICE_CONTROL_CLIENT_MODE,
                        (NUM_TILE_0_SERVICERS + NUM_TILE_1_SERVICERS - 1), // GPO servicer does not register with I2C or SPI device control context
                        &intertile_ctx, 1);
    xassert(ret == CONTROL_SUCCESS);

    ret = device_control_start(device_control_spi_ctx,
                            appconfDEVICE_CONTROL_SPI_PORT,
                            appconfDEVICE_CONTROL_I2C_CLIENT_PRIORITY);

    xassert(ret == CONTROL_SUCCESS);
#endif

#if appconfUSB_CTRL_ENABLED
    ret = device_control_init(device_control_usb_ctx,
                        THIS_XCORE_TILE == USB_EP0_TILE_NO ? DEVICE_CONTROL_HOST_MODE : DEVICE_CONTROL_CLIENT_MODE,
                        (NUM_TILE_0_SERVICERS + NUM_TILE_1_SERVICERS - 1), // GPO servicer does not register with USB device control context
                        &intertile_ctx, 1);
    xassert(ret == CONTROL_SUCCESS);

    ret = device_control_start(device_control_usb_ctx,
                            appconfDEVICE_CONTROL_USB_PORT,
                            appconfDEVICE_CONTROL_USB_CLIENT_PRIORITY);

    xassert(ret == CONTROL_SUCCESS);
#endif

    ret = device_control_init(device_control_gpio_ctx,
                                THIS_XCORE_TILE == GPI_PORT_TILE_NO ? DEVICE_CONTROL_HOST_MODE : DEVICE_CONTROL_CLIENT_MODE,
                                (NUM_SERVICERS_DEVICE_CONTROL_GPIO_CTX),
                                &intertile_ctx, 1);
    xassert(ret == CONTROL_SUCCESS);

    ret = device_control_start(device_control_gpio_ctx,
                                appconfDEVICE_CONTROL_GPIO_PORT,
                                appconfDEVICE_CONTROL_GPIO_CLIENT_PRIORITY);
    xassert(ret == CONTROL_SUCCESS);
}

void control_start_io_tasks()
{
#if ON_TILE(I2C_TILE_NO)
#if appconfI2C_CTRL_ENABLED
    rtos_i2c_slave_t * i2c_slave_ctx = get_i2c_slave_ctx();
    debug_printf("control_start tile %d. Call rtos_i2c_slave_start(), core %d\n", THIS_XCORE_TILE, rtos_core_id_get());
    // the type casting below is needed as the data types and the function signature are defined in the xcore_sdk
    rtos_i2c_slave_start(i2c_slave_ctx,
                            device_control_i2c_ctx,
                            (void (*)(rtos_i2c_slave_t *, void *)) device_control_i2c_start_cb,
                            (void (*)(rtos_i2c_slave_t *, void *, uint8_t *, size_t)) device_control_i2c_rx_cb,
                            (size_t (*)(rtos_i2c_slave_t *, void *, uint8_t **)) device_control_i2c_tx_start_cb,
                            NULL,
                            NULL,
                            NULL,
                            appconfI2C_ISR_CORE,
                            configMAX_PRIORITIES - 1);
    debug_printf("control_start tile %d. Out of rtos_i2c_slave_start()\n", THIS_XCORE_TILE);
#endif
#endif

#if ON_TILE(SPI_TILE_NO)
#if appconfSPI_CTRL_ENABLED
    rtos_spi_slave_t * spi_slave_ctx = get_spi_slave_ctx();
    debug_printf("control_start tile %d. Call rtos_spi_slave_start(), core %d\n", THIS_XCORE_TILE, rtos_core_id_get());
    // the type casting below is needed as the data types and the function signature are defined in the xcore_sdk
    rtos_spi_slave_start(spi_slave_ctx,
                            device_control_spi_ctx,
                            (void (*)(rtos_spi_slave_t *, void *)) device_control_spi_start_cb,
                            (void (*)(rtos_spi_slave_t *, void *)) device_control_spi_xfer_done_cb,
                            appconfSPI_ISR_CORE,
                            configMAX_PRIORITIES - 1);
    debug_printf("control_start tile %d. Out of rtos_spi_slave_start()\n", THIS_XCORE_TILE);
#endif
#endif
}
