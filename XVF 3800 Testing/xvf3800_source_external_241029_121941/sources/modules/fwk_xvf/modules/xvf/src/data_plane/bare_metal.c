// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.

#define DEBUG_UNIT BARE_METAL
#ifndef DEBUG_PRINT_ENABLE_BARE_METAL
    #define DEBUG_PRINT_ENABLE_BARE_METAL 0
#endif
#include "debug_print.h"

#include <platform.h>
#include <xcore/channel.h>
#include <xcore/hwtimer.h>
#include "tile_common.h"
#include "shf_bypass/shf_bypass.h"
#include <print.h>

// Placeholder tasks that will burn MIPS for development purposes

void reserved_core(void){
    debug_printf("reserved_core\n");
    while(1){
        if(get_core_burn_status()){
            shf_bypass_wait(XS1_TIMER_HZ);
        } else {
            shf_bypass_event_wait(XS1_TIMER_HZ);
        }
        debug_printf("reserved_core Tile[%d] logical core ID[%u]\n", THIS_XCORE_TILE, get_logical_core_id());
    }
}
