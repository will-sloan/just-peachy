// Copyright 2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.
#ifndef IO_CONFIG_SERVICER_DEFAULTS_H
#define IO_CONFIG_SERVICER_DEFAULTS_H

#include <stdint.h>
#include <stddef.h>
#include <user_dsp.h>
#include "io_config_cmds.h"

// Define the number of ports in use.
#define GPIO_NUM_INPUT_PORTS 2
// There may be more input pins than ports e.g. two pins on the same port. May not exceed 32.
#define GPIO_NUM_INPUT_PINS 2

typedef struct {
    // Index of the pin to configure; set by control command
    io_config_servicer_resid_gpi_index_t pindex;

    // Array indicating the value of the pin indexed by pindex at the time the value last changed. Should be the same as the current value.
    io_config_servicer_resid_gpi_value_t value[GPIO_NUM_INPUT_PINS];

    // Array indicating whether the pin indexed by pindex has been triggered. Cleared when read.
    io_config_servicer_resid_gpi_event_pending_t event_pending[GPIO_NUM_INPUT_PINS];

    // Array of active level settings indexed by pindex.
    io_config_servicer_resid_gpi_active_level_t active_level[GPIO_NUM_INPUT_PINS];

    // Array of interrupt directions indexed by pindex.
    io_config_servicer_resid_gpi_event_config_t event_config[GPIO_NUM_INPUT_PINS]; 
} gpi_config_t;

/// @brief function which the gpo servicer will call to get a reference
/// to the defaults
const gpi_config_t* gpi_config_get();

#endif // IO_CONFIG_SERVICER_DEFAULTS_H
