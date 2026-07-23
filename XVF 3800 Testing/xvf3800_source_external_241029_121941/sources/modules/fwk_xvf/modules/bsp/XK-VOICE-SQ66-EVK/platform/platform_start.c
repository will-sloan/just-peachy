// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


/* System headers */
#include <platform.h>

/* FreeRTOS headers */
#include "FreeRTOS.h"

/* Library headers */

/* App headers */
#include "platform_conf.h"
#include "platform/driver_instances.h"
#include "dac3101.h"
#include "app_conf.h"

static void flash_start(void)
{
#if DFU_CONTROL
#if appconfUSB_ENABLED
    rtos_qspi_flash_t * qspi_flash_ctx = get_qspi_flash_ctx();
    rtos_qspi_flash_rpc_config(qspi_flash_ctx, appconfFLASH_RPC_PORT, appconfFLASH_RPC_PRIORITY);
#else
#if ON_TILE(FLASH_TILE_NO)
    rtos_qspi_flash_t * qspi_flash_ctx = get_qspi_flash_ctx();
#endif
#endif


#if ON_TILE(0)
    uint32_t flash_core_map = ~((1 << appconfUSB_INTERRUPT_CORE) | (1 << appconfUSB_SOF_INTERRUPT_CORE));
    rtos_qspi_flash_start(qspi_flash_ctx, appconfQSPI_FLASH_TASK_PRIORITY);
    rtos_qspi_flash_op_core_affinity_set(qspi_flash_ctx, flash_core_map);
#endif
#endif // DFU_CONTROL
}

static void gpio_start(void)
{
    //rtos_gpio_rpc_config(gpio_ctx_t0, appconfGPIO_T0_RPC_PORT, appconfGPIO_RPC_PRIORITY);
    //rtos_gpio_rpc_config(gpio_ctx_t1, appconfGPIO_T1_RPC_PORT, appconfGPIO_RPC_PRIORITY);

#if ON_TILE(0)
    rtos_gpio_t * gpio_ctx_t0 = get_gpio_ctx(0);
    rtos_gpio_start(gpio_ctx_t0);
#endif
#if ON_TILE(1)
    rtos_gpio_t * gpio_ctx_t1 = get_gpio_ctx(1);
    rtos_gpio_start(gpio_ctx_t1);
#endif
}

static void i2c_master_start(void)
{
    rtos_i2c_master_t * i2c_master_ctx = get_i2c_master_ctx();
    rtos_i2c_master_rpc_config(i2c_master_ctx, appconfI2C_MASTER_RPC_PORT, appconfI2C_MASTER_RPC_PRIORITY);
#if ON_TILE(I2C_TILE_NO)
    rtos_i2c_master_start(i2c_master_ctx);
#endif
}

void platform_start(void)
{
    rtos_intertile_t * intertile_ctx = get_intertile_ctx();
    rtos_intertile_start(intertile_ctx);
    flash_start();
    gpio_start();
    i2c_master_start();
    // Note the audio codec start is done under RTOS control in user_config for non I2C slave control builds
}
