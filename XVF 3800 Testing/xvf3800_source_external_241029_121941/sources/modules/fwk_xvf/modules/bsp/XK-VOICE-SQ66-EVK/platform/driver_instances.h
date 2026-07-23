// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


#ifndef DRIVER_INSTANCES_H_
#define DRIVER_INSTANCES_H_

#include "rtos_intertile.h"
#include "rtos_i2c_master.h"
#include "rtos_i2c_slave.h"
#include "rtos_spi_slave.h"
#include "rtos_qspi_flash.h"
#include "rtos_qspi_flash_rpc.h"
#include "rtos_dfu_image.h"
#include "rtos_gpio.h"

/* Driver instances */
rtos_intertile_t * get_intertile_ctx();
rtos_i2c_master_t * get_i2c_master_ctx();
rtos_i2c_slave_t * get_i2c_slave_ctx();
rtos_spi_slave_t * get_spi_slave_ctx();
rtos_gpio_t * get_gpio_ctx(uint32_t tile);
rtos_qspi_flash_t * get_qspi_flash_ctx();
rtos_dfu_image_t * get_dfu_image_ctx();

#endif /* DRIVER_INSTANCES_H_ */
