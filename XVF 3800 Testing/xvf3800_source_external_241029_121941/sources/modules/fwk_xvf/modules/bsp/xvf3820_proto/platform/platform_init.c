// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


/* System headers */
#include <platform.h>
#include <quadflashlib.h>

/* App headers */
#include "platform_conf.h"
#include "platform/driver_instances.h"
#include "platform/platform_init.h"
#include "app_conf.h"


static void flash_rpc_init(void)
{
#if ( 0 < DFU_CONTROL )
#if ON_TILE(FLASH_TILE_NO)
    rtos_intertile_t * intertile_ctx = get_intertile_ctx();
    rtos_qspi_flash_t * qspi_flash_ctx = get_qspi_flash_ctx();
    rtos_dfu_image_t * dfu_image_ctx = get_dfu_image_ctx();

    fl_QuadDeviceSpec qspi_spec = BOARD_QSPI_SPEC;
    fl_QSPIPorts qspi_ports = {
        .qspiCS = PORT_SQI_CS,
        .qspiSCLK = PORT_SQI_SCLK,
        .qspiSIO = PORT_SQI_SIO,
        .qspiClkblk = FLASH_CLKBLK,
    };

    rtos_dfu_image_init(
            dfu_image_ctx,
            &qspi_ports,
            &qspi_spec,
            1);

    rtos_dfu_image_print_debug(dfu_image_ctx);
    // this is needed because the HW timer is used in lib_xcore
    hwtimer_realloc_xc_timer();
    rtos_qspi_flash_init(
            qspi_flash_ctx,
            FLASH_CLKBLK,
            PORT_SQI_CS,
            PORT_SQI_SCLK,
            PORT_SQI_SIO,
            NULL);
    hwtimer_free_xc_timer();
#endif
#endif // DFU_CONTROL
}

static void i2c_master_rpc_init(void)
{
    static rtos_driver_rpc_t i2c_rpc_config;

    rtos_intertile_t * intertile_ctx = get_intertile_ctx();
    rtos_i2c_master_t * i2c_master_ctx = get_i2c_master_ctx();
#if ON_TILE(I2C_TILE_NO) //I2C master
    rtos_intertile_t *client_intertile_ctx[1] = {intertile_ctx};
    rtos_i2c_master_init(
            i2c_master_ctx,
            PORT_I2C_SCL, 0, 0,
            PORT_I2C_SDA, 0, 0,
            0,
            100);

    rtos_i2c_master_rpc_host_init(
            i2c_master_ctx,
            &i2c_rpc_config,
            client_intertile_ctx,
            1);

#else
    rtos_i2c_master_rpc_client_init(
            i2c_master_ctx,
            &i2c_rpc_config,
            intertile_ctx);
#endif

}

static void i2c_slave_init(void)
{
#if ON_TILE(I2C_TILE_NO)
#if appconfI2C_CTRL_ENABLED
    rtos_i2c_slave_t * i2c_slave_ctx = get_i2c_slave_ctx();
    rtos_i2c_slave_init(
                i2c_slave_ctx,
                (1<<appconfI2C_IO_CORE),
                PORT_I2C_SCL,
                PORT_I2C_SDA,
                I2C_SLAVE_ADDR);
#endif
#endif

}

static void spi_slave_init()
{
#if ON_TILE(SPI_TILE_NO)
#if appconfSPI_CTRL_ENABLED
    rtos_spi_slave_t * spi_slave_ctx = get_spi_slave_ctx();
    rtos_spi_slave_init(
        spi_slave_ctx,
        (1<<appconfSPI_IO_CORE),
        SPI_SLAVE_CLKBLK,
        SPI_SLAVE_CPOL,
        SPI_SLAVE_CPHA,
        PORT_SPI_SLAVE_SCLK,
        PORT_SPI_SLAVE_MOSI,
        PORT_SPI_SLAVE_MISO,
        PORT_SPI_SLAVE_CS
    );
#endif
#endif
}

static void gpio_init(void)
{
#if ON_TILE(0)
    rtos_gpio_t * gpio_ctx_t0 = get_gpio_ctx(0);
    rtos_gpio_init(gpio_ctx_t0);
#endif

#if ON_TILE(1)
    rtos_gpio_t * gpio_ctx_t1 = get_gpio_ctx(1);
    rtos_gpio_init(gpio_ctx_t1);
#endif
}



void platform_init(chanend_t other_tile_c)
{
    rtos_intertile_t * intertile_ctx = get_intertile_ctx();
    rtos_intertile_init(intertile_ctx, other_tile_c);
    i2c_slave_init(); // HIL thread won't actually start till rtos_i2c_slave_start() is called so it's safe to initialise I2C Slave here.
    i2c_master_rpc_init();
    spi_slave_init();
    gpio_init();
    flash_rpc_init();
}
