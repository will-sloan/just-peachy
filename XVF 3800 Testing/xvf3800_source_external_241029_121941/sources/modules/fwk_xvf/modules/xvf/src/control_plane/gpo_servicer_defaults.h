// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
/// API that must be fulfilled for the data plane to know what values to set.
#ifndef GPO_SERVICER_DEFAULTS_H
#define GPO_SERVICER_DEFAULTS_H

#include <stdint.h>
#include <stddef.h>
#include <user_dsp.h>
#include "rtos_gpio.h"
#include "io_config_cmds.h"

#define GPIO_NUM_OUTPUT_PORTS   1
#define GPO_PORT_BITS           8 // Bit 3, 4, 5, 6, 7 of the 8 bit port are brought out on pckg

/// @brief Struct which will hold the defaults
typedef struct {
    /// Index of the port to configure
    /// It is set via control interface
    gpo_servicer_resid_gpo_port_pin_index_t port_index;

    /// Index of the pin to configure
    /// It is set via control interface
    gpo_servicer_resid_gpo_port_pin_index_t pin_index;

    /// Struct contianing the information used by the RTOS GPIO driver functions
    rtos_gpio_port_id_t led_ports[GPIO_NUM_OUTPUT_PORTS]; // on tile 0.

    /// Matrix holding the output duty cycles for all the pins
    ///
    /// Units: duty cycles
    uint32_t output_port_duty[GPIO_NUM_OUTPUT_PORTS][GPO_PORT_BITS];

    /// Matrix holding the output duty percentage for all the pins
    ///
    /// Units: percentage
    gpo_servicer_resid_gpo_pin_pwm_duty_t output_duty_percent[GPIO_NUM_OUTPUT_PORTS][GPO_PORT_BITS];

    /// Array storing the bitmask with active level values of the pin
    /// One bitmask per port
    gpo_servicer_resid_gpo_pin_active_level_t active_level_bitmap[GPIO_NUM_OUTPUT_PORTS]; //bitmap indicating active high or active low for all pins on a gpo port

    /// Matrix holding the flash masks for all the pins
    gpo_servicer_resid_gpo_pin_flash_mask_t flash_serial_mask[GPIO_NUM_OUTPUT_PORTS][GPO_PORT_BITS];

} gpo_config_t;

// Mapping from all_evk_leds_t to GPO port and pin index
typedef struct
{
    /* data */
    uint32_t port_index;
    uint32_t pin_index;
}gpo_led_mapping_t;


/// @brief function which the gpo servicer will call to get a reference
/// to the defaults
const gpo_config_t* gpo_config_get();

#endif // GPO_SERVICER_DEFAULTS_H
