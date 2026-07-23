// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include "platform/driver_instances.h"

static rtos_intertile_t intertile_ctx_s;
static rtos_i2c_master_t i2c_master_ctx_s;
static rtos_i2c_slave_t i2c_slave_ctx_s;
static rtos_spi_slave_t spi_slave_ctx_s;
static rtos_gpio_t gpio_ctx_t0_s;
static rtos_gpio_t gpio_ctx_t1_s;
static rtos_qspi_flash_t qspi_flash_ctx_s;
static rtos_dfu_image_t dfu_image_ctx_s;

rtos_intertile_t * get_intertile_ctx()
{
    return &intertile_ctx_s;
}

rtos_i2c_master_t * get_i2c_master_ctx()
{
    return &i2c_master_ctx_s;
}

rtos_i2c_slave_t * get_i2c_slave_ctx()
{
    return &i2c_slave_ctx_s;
}

rtos_spi_slave_t * get_spi_slave_ctx()
{
    return &spi_slave_ctx_s;
}

rtos_gpio_t * get_gpio_ctx(uint32_t tile)
{
    switch (tile)
    {
        case 0:
        {
            return &gpio_ctx_t0_s;
            break;
        }
        case 1:
        {
            return &gpio_ctx_t1_s;
            break;
        }
        default:
        {
            return NULL;
            break;
        }
    }
}

rtos_qspi_flash_t * get_qspi_flash_ctx()
{
    return &qspi_flash_ctx_s;
}

rtos_dfu_image_t * get_dfu_image_ctx()
{
    return &dfu_image_ctx_s;
}
