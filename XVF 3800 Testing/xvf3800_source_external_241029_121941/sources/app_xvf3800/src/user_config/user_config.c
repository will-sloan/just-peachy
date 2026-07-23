// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#include "FreeRTOS.h"
#include "app_conf.h"
#include "user_config.h"
#include "io_config_servicer.h"
#include "dac3101.h"

// This file contains the user hardware configuration code. It uses the implementations in dac3101.h (EVK3800)
// and the lower level hardware implementations in dac_port.c

int user_init_hardware(device_control_t *device_control_gpio_ctx)
{
    int errors_encountered = 0;

    rtos_printf("user_init_hardware\n");

#if !defined(MIC_ARRAY_TYPE)
#error
#endif
#if MIC_ARRAY_TYPE == BECLEAR_LINEAR_ARRAY
    write_gpo_pin(device_control_gpio_ctx, GPO_SQ_nLIN_PIN, 0);
#elif MIC_ARRAY_TYPE == BECLEAR_CIRCULAR_ARRAY
    write_gpo_pin(device_control_gpio_ctx, GPO_SQ_nLIN_PIN, 1);
#else
    #error MIC_ARRAY_TYPE invalid
#endif

    // De-assert HOST INTERRUPT line
    write_gpo_pin(device_control_gpio_ctx, GPO_INT_N_PIN, 1); // No interrupt to host asserted when high

#if (appconfUSER_CONFIG_ENABLED == 1)
    // Reset the DAC
    dac3101_codec_reset(device_control_gpio_ctx);

    errors_encountered |= dac3101_init(appconfLRCLK_NOMINAL_HZ);
#endif

    // Test that we can turn on a LED by sending a command from this task to the GPO task
    // Note even though LEDs are active low, we have setup the LED pins in gpo_servicer to drive negaive logic
    for(int i = 0; i < 5; i++){
        write_gpo_pin(device_control_gpio_ctx, GPO_LED_GREEN_PIN, 1); // Turn the green LED on
        vTaskDelay(pdMS_TO_TICKS(100));
        write_gpo_pin(device_control_gpio_ctx, GPO_LED_GREEN_PIN, 0); // Turn the green LED off
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    return errors_encountered;
}
