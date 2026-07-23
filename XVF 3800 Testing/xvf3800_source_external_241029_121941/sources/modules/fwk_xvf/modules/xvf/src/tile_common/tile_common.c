// Copyright 2022-2023 XMOS LIMITED.
// This Software is subject to the terms of the XCORE VocalFusion Licence.


/// Helper functions to aid the setup of the applications that both tiles
/// will use.

#define DEBUG_UNIT TILE_COMMON
#ifndef DEBUG_PRINT_ENABLE_TILE_COMMON
    #define DEBUG_PRINT_ENABLE_TILE_COMMON 0
#endif
#include "debug_print.h"
#include "rtos_printf.h"

#include "tile_common.h"

#include <stdint.h>
#include <stdio.h>
#include <xcore/assert.h>
#include <xcore/chanend.h>
#include <xcore/hwtimer.h>

#include "FreeRTOS.h"
#include "rtos_cores.h"
#include "task.h"
#include "timer.h"
#include "platform/platform_init.h"

#include "shf_bypass/shf_bypass.h"
#include "app_conf.h"
#include "control_init.h"
#include "usb_param_values.h"

#include <print.h>
void report_chanends(unsigned id){
    unsigned free_chanends = 0;
    chanend_t rids[32] = {0};
    chanend_t resid = 0;
    do{
        resid = chanend_alloc();
        if(resid != 0){
            rids[free_chanends] = resid;
            free_chanends++;
        }
    } while(resid != 0);
    for(int i = 0; i < free_chanends; i++){
        chanend_free(rids[i]);
    }
    printstr("Free chanends: ");
    printint(free_chanends);
    printstr(", at id: ");
    printintln(id);
}

void report_locks(unsigned id){
    unsigned free_chanends = 0;
    lock_t rids[32] = {0};
    lock_t resid;
    do{
        resid = lock_alloc();
        if(resid != 0){
            rids[free_chanends] = resid;
            free_chanends++;
        }
    } while(resid != 0);
    for(int i = 0; i < free_chanends; i++){
        lock_free(rids[i]);
    }
    printstr("Free locks: ");
    printint(free_chanends);
    printstr(", at id: ");
    printintln(id);
}


#if ON_TILE(0)
void vApplicationMinimalIdleHook(void)
{
    rtos_printf("idle hook on tile %d core %d\n", THIS_XCORE_TILE, rtos_core_id_get());

    // Do not do an event wait if we wish to burn OS time
    if(get_core_burn_status()){
        return;
    } else {
        asm volatile("waiteu");
    }
}
#endif

#if ON_TILE(1)
void vApplicationMinimalIdleHook(void)
{
    rtos_printf("idle hook on tile %d core %d\n", THIS_XCORE_TILE, rtos_core_id_get());

    // Do not do an event wait if we wish to burn OS time
    if(get_core_burn_status()){
        return;
    } else {
        asm volatile("waiteu");
    }
}
#endif

void vApplicationMallocFailedHook(void)
{
    rtos_printf("Malloc Failed on tile %d!\n", THIS_XCORE_TILE);
    xassert(0);
    for(;;);
}


void tile_common_rtos_burn_thread(void* args){
    for (;;) {
        shf_bypass_wait(XS1_TIMER_HZ * 5);
        rtos_printf( "RTOS task Tile[%d]|RTOSCore[%d] lCoreID[%u]\n", THIS_XCORE_TILE, rtos_core_id_get(), get_logical_core_id());
        if(rtos_core_id_get() == 0){
            rtos_printf("Tile[%d]:\n\tMinimum heap free: %d\n\tCurrent heap free: %d\n", THIS_XCORE_TILE, xPortGetMinimumEverFreeHeapSize(), xPortGetFreeHeapSize());
        }
    }
    //Note for ever loop so task keeps running
}

void tile_common_start_rtos_app(chanend_t c, TaskFunction_t task_function, UBaseType_t task_stack, void* servicer_args)
{
    debug_printf("starting scheduler tile %d\n", THIS_XCORE_TILE);
    platform_init(c);
    control_init();
    chanend_free(c);

    xTaskCreate(
        task_function,
        "rtos start",
        task_stack,
        servicer_args,
        appconfSTARTUP_TASK_PRIORITY,
        NULL);
    vTaskStartScheduler();

}

#define WDT_PRESCALER_MILLISECONDS   (24000 - 1) // Set prescaler to tick every millisecond, assuming 24MHz XIN. Note max value 65535.

void reboot_xvf3800(unsigned delay)
{
    write_sswitch_reg_no_ack(get_local_tile_id(), XS1_SSWITCH_WATCHDOG_PRESCALER_WRAP_NUM, WDT_PRESCALER_MILLISECONDS);
    write_sswitch_reg_no_ack(get_local_tile_id(), XS1_SSWITCH_WATCHDOG_COUNT_NUM, delay); // Set WDT trigger after this many ticks. Note this is an 11b field so 2047 max
    write_sswitch_reg_no_ack(get_local_tile_id(), XS1_SSWITCH_WATCHDOG_PRESCALER_NUM, 0); // Reset counter
    write_sswitch_reg_no_ack(get_local_tile_id(), XS1_SSWITCH_WATCHDOG_CFG_NUM, (1 << XS1_WATCHDOG_COUNT_ENABLE_SHIFT) | (1 << XS1_WATCHDOG_TRIGGER_ENABLE_SHIFT) );
    debug_printf("Rebooting!\n");
    // Note no while(1); so will return to app. The reboot has been scheduled however.
}


#define CORE_BURN_REBOOT_DELAY_MS       50
/* See https://github0.xmos.com/xmos-int/xflash/blob/master/tools_xflash/Stage2Loader_SharedDefs.h#L110-L117 for safe addresses */
#define CORE_BURN_MAGIC_FLAG_ADDRESS    0xfff80 // Avoid DFU which uses 0xfffcc on Tile[0], even though we are on Tile[1]
#define CORE_BURN_MAGIC_FLAG            0x90C0FFEE //Statistically unlikely arbitrary word
volatile uint32_t *burn_magic_word = (uint32_t*)CORE_BURN_MAGIC_FLAG_ADDRESS;


void set_core_burn_status_and_reboot(uint8_t core_burn)
{
    if(core_burn)
    {
        *burn_magic_word = CORE_BURN_MAGIC_FLAG;
    }else{
        *burn_magic_word = ~CORE_BURN_MAGIC_FLAG;
    }

    reboot_xvf3800(CORE_BURN_REBOOT_DELAY_MS);
}



// Note the core_burn flag is passed across from tile[1] to tile[0] at startup in main across a channel
#if ON_TILE(0)

// This var picks up the burn status persistent RAM flag and is used by the app to control core burn
// to allow worst case timing testing. Used by tile[0] only
static volatile uint8_t use_core_burn = 0;

uint8_t get_core_burn_status(void)
{
    return use_core_burn;
}

void set_core_burn_status(uint8_t core_burn)
{
    use_core_burn = core_burn;
}

#define SPIS_BOOT_STATUS 0x7
#define BOOT_SUCCESS_VALUE 1
#define BOOT_SUCCESS_SHIFT 3

uint8_t is_spi_slave_boot()
{
    uint32_t boot_status = (int32_t)getps(XS1_PS_BOOT_STATUS);

    if(boot_status == (SPIS_BOOT_STATUS | (BOOT_SUCCESS_VALUE << BOOT_SUCCESS_SHIFT)) ) //SPI slave boot mask.
    {
        return 1;
    }
    return 0;
}

#else // ON_TILE(1)

// This version checks the actual magic flag on tile[1]
uint8_t get_core_burn_status(void)
{
    if(*burn_magic_word == CORE_BURN_MAGIC_FLAG)
    {
        return 1;
    }
    return 0;
}

// This var is a Tile[1] copy of the SPI boot status which will be read from tile[0]
static volatile uint8_t is_spi_boot = 0;

uint8_t is_spi_slave_boot(void)
{
    return is_spi_boot;
}

void set_spi_slave_boot_status(uint8_t spi_boot_status)
{
    is_spi_boot = spi_boot_status;
}
#endif // ON_TILE(1)


// Note the bit_depth info is passed across from tile[1] to tile[0] at startup in main across a channel
/* See https://github0.xmos.com/xmos-int/xflash/blob/master/tools_xflash/Stage2Loader_SharedDefs.h#L110-L117 for safe addresses */
#define IN_BIT_DEPTH_MAGIC_FLAG_ADDRESS  0xffff4    // Avoid CORE_BURN_MAGIC_FLAG_ADDRESS and DFU which uses 0xfffcc on Tile[0], even though we are on Tile[1]
#define OUT_BIT_DEPTH_MAGIC_FLAG_ADDRESS 0xffff8    // Avoid CORE_BURN_MAGIC_FLAG_ADDRESS and DFU which uses 0xfffcc on Tile[0], even though we are on Tile[1]
#define BIT_DEPTH_KEY                    0xb17de9fc // Statistically unlikely arbitrary word with bottom two bits masked off
#define BIT_DEPTH_KEY_MASK               0xfffffffc // Mask for above
#define USB_BIT_DEPTH_REBOOT_DELAY_MS    50


#if ON_TILE(0)

static volatile uint8_t g_bit_depth_in = 0;
static volatile uint8_t g_bit_depth_out = 0;

void get_usb_bit_depth(uint8_t *bit_depth_in, uint8_t *bit_depth_out)
{
    if (bit_depth_in != NULL)
        {*bit_depth_in = g_bit_depth_in;}
    if (bit_depth_out != NULL)
        {*bit_depth_out = g_bit_depth_out;}
}

void set_usb_bit_depth(uint8_t bit_depth_in, uint8_t bit_depth_out)
{
    g_bit_depth_in = bit_depth_in;
    g_bit_depth_out = bit_depth_out;
}

#else // ON_TILE(1)

volatile uint32_t *in_bit_depth_register = (uint32_t*)IN_BIT_DEPTH_MAGIC_FLAG_ADDRESS;
volatile uint32_t *out_bit_depth_register = (uint32_t*)OUT_BIT_DEPTH_MAGIC_FLAG_ADDRESS;

// Note that bit depth is encoded as follows in bottom 2 bits - 00 -> invalid, 01 -> 16bit, 10 -> 24bit, 11 -> 32bit
void set_usb_bit_depth(uint8_t bit_depth_in, uint8_t bit_depth_out)
{
#if appconfUSB_ENABLED // Makes sense only for the UA device
    *in_bit_depth_register = BIT_DEPTH_KEY | (bit_depth_in / 8 - 1);
    *out_bit_depth_register = BIT_DEPTH_KEY | (bit_depth_out / 8 - 1);

    reboot_xvf3800(USB_BIT_DEPTH_REBOOT_DELAY_MS);
#endif
}

void get_usb_bit_depth(uint8_t *bit_depth_in, uint8_t *bit_depth_out)
{
#if appconfUSB_ENABLED
    if (bit_depth_in != NULL)
    {
        if((*in_bit_depth_register & BIT_DEPTH_KEY_MASK) == BIT_DEPTH_KEY)
        {
            *bit_depth_in = ((*in_bit_depth_register & ~BIT_DEPTH_KEY_MASK) + 1) * 8;
        } else {
            *bit_depth_in = DEFAULT_BIT_DEPTH_IN;
        }
    }

    if (bit_depth_out != NULL)
    {
        if((*out_bit_depth_register & BIT_DEPTH_KEY_MASK) == BIT_DEPTH_KEY)
        {
            *bit_depth_out = ((*out_bit_depth_register & ~BIT_DEPTH_KEY_MASK) + 1) * 8;
        } else {
            *bit_depth_out = DEFAULT_BIT_DEPTH_OUT;
        }
    }
#else
    if (bit_depth_in != NULL)
        {*bit_depth_in = 0;}
    if (bit_depth_out != NULL)
        {*bit_depth_out = 0;}
#endif
}

#endif // ON_TILE(1)
